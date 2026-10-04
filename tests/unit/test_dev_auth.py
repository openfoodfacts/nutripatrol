"""Tests for the local-dev escape hatch that names the acting user by header.

`AUTH_DEV_USERS` exists so that a front end on localhost - which can never
hold an Open Food Facts session cookie - can still be a logged-out visitor, a
plain contributor or a moderator in turn. What matters is that it produces
*the same* three answers the real authentication does, permission checks
included, rather than waving every request through.
"""

import asyncio

import httpx
import pytest
from peewee import SqliteDatabase

from app import api as api_module
from app.api import app
from app.middleware import auth as auth_module
from app.models import FlagModel, ModeratorActionModel, TicketModel
from app.off_api import ProductSnapshot

BARCODE = "3017620422003"
MODELS = [TicketModel, FlagModel, ModeratorActionModel]


@pytest.fixture
def database(tmp_path, monkeypatch):
    """Run the endpoints against a throwaway SQLite database."""
    test_db = SqliteDatabase(str(tmp_path / "nutripatrol.db"))
    test_db.bind(MODELS)
    test_db.create_tables(MODELS)
    test_db.close()
    monkeypatch.setattr(api_module, "db", test_db)
    yield test_db
    test_db.close()


@pytest.fixture
def dev_users(monkeypatch):
    """Turn the escape hatch on, as setting AUTH_DEV_USERS=1 would."""
    monkeypatch.setattr(auth_module.settings, "auth_dev_users", True)


@pytest.fixture(autouse=True)
def no_off_call(monkeypatch):
    """Keep flag creation from reaching out to Open Food Facts."""
    monkeypatch.setattr(
        api_module, "fetch_product_snapshot", lambda *args, **kwargs: ProductSnapshot()
    )
    monkeypatch.setattr(
        api_module, "fetch_image_upload_metadata", lambda *args, **kwargs: (None, None)
    )


@pytest.fixture(autouse=True)
def no_auth_server(monkeypatch):
    """Fail loudly if a test reaches the real authentication path.

    These tests carry no session cookie, so nothing should ever get as far as
    asking an auth server about one.
    """

    async def unexpected(*args, **kwargs):
        raise AssertionError("the auth server should not be called")

    monkeypatch.setattr(auth_module, "_get_user_data_cached", unexpected)


def as_user(user_id=None, moderator=False):
    """The headers a dev-mode request identifies itself with, if any."""
    headers = {}
    if user_id is not None:
        headers[auth_module.DEV_USER_ID_HEADER] = user_id
    if moderator:
        headers[auth_module.DEV_MODERATOR_HEADER] = "1"
    return headers


def request(method, url, headers=None, json=None):
    async def send():
        transport = httpx.ASGITransport(app=app)
        # No cookies: the whole point is a client that has no session to send.
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, url, headers=headers, json=json)

    return asyncio.run(send())


def post_flag(user_id, **overrides):
    body = {
        "barcode": BARCODE,
        "type": "product",
        "flavor": "off",
        "user_id": user_id,
        "source": "web",
        "reason": "other",
        **overrides,
    }
    response = request("POST", "/api/v1/flags", headers=as_user(user_id), json=body)
    assert response.status_code == 200, response.text
    return response.json()


# --- The hatch stays shut unless it is opened --------------------------------


def test_the_headers_are_ignored_when_the_setting_is_off(database, monkeypatch):
    # Pinned rather than assumed: the setting is read from the environment,
    # which a developer running the suite may well have turned on.
    monkeypatch.setattr(auth_module.settings, "auth_dev_users", False)

    response = request("GET", "/api/v1/flags", headers=as_user("alice", moderator=True))

    # Falls through to the session cookie the request does not have, which is
    # what any deployment without AUTH_DEV_USERS must do with these headers.
    assert response.status_code == 401, response.text


def test_no_headers_is_a_logged_out_visitor(database, dev_users):
    response = request("GET", "/api/v1/flags")

    assert response.status_code == 401, response.text


def test_the_robotoff_bearer_token_still_works(database, dev_users, monkeypatch):
    monkeypatch.setenv("AUTH_BEARER_TOKEN_ROBOTOFF", "a-token")

    response = request(
        "GET", "/api/v1/flags", headers={"Authorization": "Bearer a-token"}
    )

    assert response.status_code == 200, response.text


# --- ...and then tells the three users apart ---------------------------------


def test_a_dev_user_lists_their_own_flags_only(database, dev_users):
    alice_flag = post_flag("alice")
    post_flag("bob", reason="inappropriate")

    response = request("GET", "/api/v1/flags", headers=as_user("alice"))

    assert response.status_code == 200, response.text
    assert [flag["id"] for flag in response.json()["flags"]] == [alice_flag["id"]]


def test_a_dev_moderator_lists_every_flag(database, dev_users):
    alice_flag = post_flag("alice")
    bob_flag = post_flag("bob", reason="inappropriate")

    response = request("GET", "/api/v1/flags", headers=as_user("mod", moderator=True))

    assert response.status_code == 200, response.text
    assert sorted(flag["id"] for flag in response.json()["flags"]) == sorted(
        [alice_flag["id"], bob_flag["id"]]
    )


def test_a_dev_user_is_turned_away_from_a_moderator_endpoint(database, dev_users):
    flag = post_flag("alice")

    response = request(
        "PUT",
        f"/api/v1/tickets/{flag['ticket_id']}/status?status=closed",
        headers=as_user("alice"),
    )

    assert response.status_code == 403, response.text


def test_a_dev_moderator_is_let_into_a_moderator_endpoint(database, dev_users):
    flag = post_flag("alice")

    response = request(
        "PUT",
        f"/api/v1/tickets/{flag['ticket_id']}/status?status=closed",
        headers=as_user("mod", moderator=True),
    )

    assert response.status_code == 200, response.text


def test_a_dev_moderator_sees_the_actions_they_recorded(database, dev_users):
    flag = post_flag("alice")
    moderator = as_user("mod", moderator=True)
    request(
        "PUT",
        f"/api/v1/tickets/{flag['ticket_id']}/status?status=closed",
        headers=moderator,
    )

    response = request("GET", "/api/v1/moderator_actions/me", headers=moderator)

    assert response.status_code == 200, response.text
    actions = response.json()["actions"]
    # The action is attributed to the header's user id, which is what makes
    # "my actions" mean anything in a dev stack.
    assert [action["user_id"] for action in actions] == ["mod"]
