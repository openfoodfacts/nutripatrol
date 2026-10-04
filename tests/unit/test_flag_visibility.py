"""Tests for who gets to read a flag, and the ticket it is attached to.

A ticket gathers the flags of everyone who reported the same product, so the
two questions are not the same one: a flagger follows the ticket their report
opened, and the moderation it received, without ever seeing the reports the
other users filed on it.
"""

import asyncio
from datetime import datetime

import httpx
import pytest
from peewee import SqliteDatabase

from app import api as api_module
from app.api import app
from app.middleware import auth as auth_module
from app.models import FlagModel, ModeratorActionModel, TicketModel
from app.off_api import ProductSnapshot

BARCODE = "3017620422003"
OTHER_BARCODE = "3229820129488"
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
def act_as(monkeypatch):
    """Answer the auth server as whoever the test is currently acting as.

    Returned as a setter rather than a fixture per user, because these tests
    are about one user reaching for what another one left behind.
    """
    current = {"user_id": "alice", "moderator": 0}

    async def user_data(session_cookie, auth_base_url):
        return {
            "user_id": current["user_id"],
            "user": {"moderator": current["moderator"]},
        }

    monkeypatch.setattr(auth_module, "_get_user_data_cached", user_data)

    def switch(user_id, moderator=0):
        current.update(user_id=user_id, moderator=moderator)

    return switch


@pytest.fixture(autouse=True)
def no_off_call(monkeypatch):
    """Keep flag creation from reaching out to Open Food Facts."""
    monkeypatch.setattr(
        api_module, "fetch_product_snapshot", lambda *args, **kwargs: ProductSnapshot()
    )
    monkeypatch.setattr(
        api_module, "fetch_image_upload_metadata", lambda *args, **kwargs: (None, None)
    )


def request(method, url, json=None):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            cookies={"session": "a-session-cookie"},
        ) as client:
            return await client.request(method, url, json=json)

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
    response = request("POST", "/api/v1/flags", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def flag_of(act_as, user_id, **overrides):
    """Have `user_id` raise a flag, acting as them while it is created."""
    act_as(user_id)
    return post_flag(user_id, **overrides)


# --- Reading one's own flags -------------------------------------------------


def test_a_user_reads_the_flag_they_created(database, act_as):
    flag = flag_of(act_as, "alice")

    response = request("GET", f"/api/v1/flags/{flag['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["id"] == flag["id"]


def test_a_user_cannot_read_a_flag_created_by_someone_else(database, act_as):
    alice_flag = flag_of(act_as, "alice")
    # Bob flags the same product, so the two flags share a ticket.
    bob_flag = flag_of(act_as, "bob", reason="inappropriate")
    assert bob_flag["ticket_id"] == alice_flag["ticket_id"]

    response = request("GET", f"/api/v1/flags/{alice_flag['id']}")

    # 404 rather than 403: bob does not get to find out that the flag exists.
    assert response.status_code == 404, response.text


def test_a_user_lists_their_own_flags_only(database, act_as):
    alice_flag = flag_of(act_as, "alice")
    flag_of(act_as, "bob", reason="inappropriate")

    act_as("alice")
    response = request("GET", "/api/v1/flags")

    assert response.status_code == 200, response.text
    flags = response.json()["flags"]
    assert [flag["id"] for flag in flags] == [alice_flag["id"]]
    # The listing publishes a flag the way reading one does: a peewee row
    # calls the foreign key "ticket", and used to be handed over as such,
    # which the response model rejected.
    assert flags[0]["ticket_id"] == alice_flag["ticket_id"]


def test_a_moderator_lists_every_flag(database, act_as):
    alice_flag = flag_of(act_as, "alice")
    bob_flag = flag_of(act_as, "bob", reason="inappropriate")

    act_as("mod", moderator=1)
    response = request("GET", "/api/v1/flags")

    assert response.status_code == 200, response.text
    assert sorted(flag["id"] for flag in response.json()["flags"]) == sorted(
        [alice_flag["id"], bob_flag["id"]]
    )


def test_a_moderator_reads_a_flag_they_did_not_create(database, act_as):
    alice_flag = flag_of(act_as, "alice")

    act_as("mod", moderator=1)
    response = request("GET", f"/api/v1/flags/{alice_flag['id']}")

    assert response.status_code == 200, response.text


def test_the_batch_endpoint_hands_a_user_their_own_flags_only(database, act_as):
    alice_flag = flag_of(act_as, "alice")
    flag_of(act_as, "bob", reason="inappropriate")
    ticket_id = alice_flag["ticket_id"]

    act_as("alice")
    response = request("POST", "/api/v1/flags/batch", json={"ticket_ids": [ticket_id]})

    assert response.status_code == 200, response.text
    flags = response.json()["ticket_id_to_flags"][str(ticket_id)]
    assert [flag["id"] for flag in flags] == [alice_flag["id"]]


def test_the_batch_endpoint_leaves_out_a_ticket_a_user_did_not_flag(database, act_as):
    bob_flag = flag_of(act_as, "bob")

    act_as("alice")
    response = request(
        "POST", "/api/v1/flags/batch", json={"ticket_ids": [bob_flag["ticket_id"]]}
    )

    assert response.status_code == 200, response.text
    assert response.json()["ticket_id_to_flags"] == {}


# --- Reading the ticket a flag opened ----------------------------------------


def test_a_user_reads_the_ticket_their_flag_is_attached_to(database, act_as):
    flag = flag_of(act_as, "alice")

    response = request("GET", f"/api/v1/tickets/{flag['ticket_id']}")

    assert response.status_code == 200, response.text
    assert response.json()["id"] == flag["ticket_id"]


def test_a_user_cannot_read_a_ticket_they_did_not_flag(database, act_as):
    bob_flag = flag_of(act_as, "bob", barcode=OTHER_BARCODE)

    act_as("alice")
    response = request("GET", f"/api/v1/tickets/{bob_flag['ticket_id']}")

    assert response.status_code == 404, response.text


def test_a_user_lists_the_tickets_they_flagged_only(database, act_as):
    alice_flag = flag_of(act_as, "alice")
    flag_of(act_as, "bob", barcode=OTHER_BARCODE)

    act_as("alice")
    response = request("GET", "/api/v1/tickets")

    assert response.status_code == 200, response.text
    body = response.json()
    assert [ticket["id"] for ticket in body["tickets"]] == [alice_flag["ticket_id"]]
    # The count follows the listing, so the paging a client computes from it
    # does not betray how many other tickets there are.
    assert body["total"] == 1


def test_a_user_cannot_match_a_ticket_on_the_reason_someone_else_gave(database, act_as):
    """The `reason` filter runs over the user's own flags, not every flag."""
    alice_flag = flag_of(act_as, "alice", reason="other")
    bob_flag = flag_of(act_as, "bob", reason="inappropriate")
    assert bob_flag["ticket_id"] == alice_flag["ticket_id"]

    act_as("alice")
    response = request("GET", "/api/v1/tickets?reason=inappropriate")

    assert response.status_code == 200, response.text
    assert response.json()["tickets"] == []


def test_a_moderator_lists_every_ticket(database, act_as):
    alice_flag = flag_of(act_as, "alice")
    bob_flag = flag_of(act_as, "bob", barcode=OTHER_BARCODE)

    act_as("mod", moderator=1)
    response = request("GET", "/api/v1/tickets")

    assert response.status_code == 200, response.text
    assert sorted(ticket["id"] for ticket in response.json()["tickets"]) == sorted(
        [alice_flag["ticket_id"], bob_flag["ticket_id"]]
    )


# --- Reading what was done about it ------------------------------------------


def close(ticket_id, act_as):
    act_as("mod", moderator=1)
    response = request("PUT", f"/api/v1/tickets/{ticket_id}/status?status=closed-fixed")
    assert response.status_code == 200, response.text


def test_a_user_reads_the_actions_taken_on_the_ticket_they_flagged(database, act_as):
    flag = flag_of(act_as, "alice")
    close(flag["ticket_id"], act_as)

    act_as("alice")
    response = request("GET", f"/api/v1/tickets/{flag['ticket_id']}/actions")

    assert response.status_code == 200, response.text
    actions = response.json()["actions"]
    assert [action["action_type"] for action in actions] == ["closed-fixed"]
    assert actions[0]["user_id"] == "mod"


def test_a_user_cannot_read_the_actions_of_a_ticket_they_did_not_flag(database, act_as):
    bob_flag = flag_of(act_as, "bob", barcode=OTHER_BARCODE)
    close(bob_flag["ticket_id"], act_as)

    act_as("alice")
    response = request("GET", f"/api/v1/tickets/{bob_flag['ticket_id']}/actions")

    assert response.status_code == 404, response.text


# --- What stays with the moderators ------------------------------------------


def test_a_user_cannot_moderate_the_ticket_they_flagged(database, act_as):
    flag = flag_of(act_as, "alice")

    response = request(
        "PUT", f"/api/v1/tickets/{flag['ticket_id']}/status?status=closed-fixed"
    )

    assert response.status_code == 403, response.text
    assert TicketModel.get_by_id(flag["ticket_id"]).status == "open"


def test_a_user_cannot_read_the_statistics(database, act_as):
    act_as("alice")

    response = request("GET", "/api/v1/stats")

    assert response.status_code == 403, response.text


def test_an_anonymous_visitor_reads_nothing(database, act_as):
    flag = flag_of(act_as, "alice")

    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(f"/api/v1/flags/{flag['id']}")

    assert asyncio.run(send()).status_code == 401


def test_a_logged_out_session_reads_nothing(database, act_as, monkeypatch):
    """auth.pl answers without a `moderator` key when nobody is logged in."""
    flag = flag_of(act_as, "alice")

    async def logged_out(session_cookie, auth_base_url):
        return {"user": {}}

    monkeypatch.setattr(auth_module, "_get_user_data_cached", logged_out)
    response = request("GET", f"/api/v1/flags/{flag['id']}")

    assert response.status_code == 403, response.text


def test_a_flag_is_not_readable_once_it_is_gone(database, act_as):
    """An unknown id answers the same 404 as someone else's flag."""
    act_as("alice")

    response = request("GET", "/api/v1/flags/404")

    assert response.status_code == 404, response.text


def test_the_creation_date_is_still_recorded(database, act_as):
    """Guards the fixtures here against the server-stamped fields."""
    flag = flag_of(act_as, "alice")

    assert FlagModel.get_by_id(flag["id"]).created_at <= datetime.utcnow()


# --- Users a session does not name -------------------------------------------
#
# A flag carries whatever user id its client sent, and auth.pl does not always
# name the user behind a session, so both sides of the "is this your flag?"
# comparison can be empty. An empty id is not an identity: it must never match,
# or every user auth.pl leaves unnamed reads every unattributed flag, and every
# ticket behind it, as if they had raised them.


def unnamed_session(monkeypatch):
    """Act as a logged-in user auth.pl answers about without a `user_id`."""

    async def user_data(session_cookie, auth_base_url):
        return {"user": {"moderator": 0}}

    monkeypatch.setattr(auth_module, "_get_user_data_cached", user_data)


def test_an_unnamed_user_lists_no_ticket(database, act_as, monkeypatch):
    flag_of(act_as, "")
    flag_of(act_as, "alice", barcode=OTHER_BARCODE)

    unnamed_session(monkeypatch)
    response = request("GET", "/api/v1/tickets")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tickets"] == []
    assert body["total"] == 0


def test_an_unnamed_user_lists_no_flag(database, act_as, monkeypatch):
    flag_of(act_as, "")

    unnamed_session(monkeypatch)
    response = request("GET", "/api/v1/flags")

    assert response.status_code == 200, response.text
    assert response.json()["flags"] == []


def test_an_unnamed_user_cannot_read_an_unattributed_flag(
    database, act_as, monkeypatch
):
    flag = flag_of(act_as, "")

    unnamed_session(monkeypatch)
    response = request("GET", f"/api/v1/flags/{flag['id']}")

    assert response.status_code == 404, response.text


def test_an_unnamed_user_cannot_read_an_unattributed_ticket(
    database, act_as, monkeypatch
):
    flag = flag_of(act_as, "")

    unnamed_session(monkeypatch)
    response = request("GET", f"/api/v1/tickets/{flag['ticket_id']}")

    assert response.status_code == 404, response.text


def test_an_unnamed_user_cannot_read_the_actions_of_an_unattributed_ticket(
    database, act_as, monkeypatch
):
    flag = flag_of(act_as, "")
    close(flag["ticket_id"], act_as)

    unnamed_session(monkeypatch)
    response = request("GET", f"/api/v1/tickets/{flag['ticket_id']}/actions")

    assert response.status_code == 404, response.text


def test_the_batch_endpoint_hands_an_unnamed_user_nothing(
    database, act_as, monkeypatch
):
    flag = flag_of(act_as, "")

    unnamed_session(monkeypatch)
    response = request(
        "POST", "/api/v1/flags/batch", json={"ticket_ids": [flag["ticket_id"]]}
    )

    assert response.status_code == 200, response.text
    assert response.json()["ticket_id_to_flags"] == {}


def test_an_unnamed_user_cannot_match_an_unattributed_ticket_on_its_reason(
    database, act_as, monkeypatch
):
    """The `reason` filter is no way around it either."""
    flag_of(act_as, "", reason="inappropriate")

    unnamed_session(monkeypatch)
    response = request("GET", "/api/v1/tickets?reason=inappropriate")

    assert response.status_code == 200, response.text
    assert response.json()["tickets"] == []


def test_a_session_that_names_the_empty_user_reads_nothing_either(database, act_as):
    """auth.pl naming the user "" is the same non-identity as naming none."""
    flag = flag_of(act_as, "")

    act_as("")
    assert request("GET", "/api/v1/flags").json()["flags"] == []
    assert request("GET", "/api/v1/tickets").json()["tickets"] == []
    assert request("GET", f"/api/v1/flags/{flag['id']}").status_code == 404
    assert request("GET", f"/api/v1/tickets/{flag['ticket_id']}").status_code == 404


def test_a_named_user_does_not_read_an_unattributed_flag(database, act_as):
    unattributed = flag_of(act_as, "", barcode=OTHER_BARCODE)

    act_as("alice")
    response = request("GET", f"/api/v1/flags/{unattributed['id']}")

    assert response.status_code == 404, response.text


def test_a_moderator_still_reads_an_unattributed_flag(database, act_as):
    """Unattributed flags belong to nobody, which leaves them to moderation."""
    flag = flag_of(act_as, "")

    act_as("mod", moderator=1)
    assert request("GET", f"/api/v1/flags/{flag['id']}").status_code == 200
    assert [f["id"] for f in request("GET", "/api/v1/flags").json()["flags"]] == [
        flag["id"]
    ]
    assert request("GET", f"/api/v1/tickets/{flag['ticket_id']}").status_code == 200
    assert [t["id"] for t in request("GET", "/api/v1/tickets").json()["tickets"]] == [
        flag["ticket_id"]
    ]


def test_an_unnamed_user_can_still_raise_a_flag(database, act_as, monkeypatch):
    """Reading nothing is not being turned away: flagging still works."""
    unnamed_session(monkeypatch)

    response = request(
        "POST",
        "/api/v1/flags",
        json={
            "barcode": BARCODE,
            "type": "product",
            "flavor": "off",
            "user_id": "alice",
            "source": "web",
            "reason": "other",
        },
    )

    assert response.status_code == 200, response.text


def test_a_named_user_still_reads_their_own_flag_through_the_empty_id_guard(
    database, act_as
):
    """The guard against the empty id must not cost a real user their flags."""
    flag_of(act_as, "")
    alice_flag = flag_of(act_as, "alice")

    act_as("alice")
    response = request("GET", "/api/v1/flags")

    assert response.status_code == 200, response.text
    assert [f["id"] for f in response.json()["flags"]] == [alice_flag["id"]]
