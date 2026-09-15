"""Tests for flag creation, and for what it captures from Open Food Facts.

Open Food Facts only serves the current revision of a product, so anything
that belongs to the moment the flag was raised -- the revision the flagger was
looking at, the uploader of the image they flagged -- has to be recorded then.
Afterwards there is no way to get it back.
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
def logged_in(monkeypatch):
    """Answer the auth server as it does for a logged-in, plain user."""

    async def user_data(session_cookie, auth_base_url):
        return {"user_id": "alice", "user": {"moderator": 0}}

    monkeypatch.setattr(auth_module, "_get_user_data_cached", user_data)


@pytest.fixture
def snapshot(monkeypatch):
    """Set what the single product fetch of a new flag returns.

    Returns the list of (barcode, flavor, image_id) it was called with, which
    is what says how many requests Open Food Facts actually receives.
    """

    def install(revision=None, image_uploader=None, image_uploaded_at=None):
        calls = []

        def stub(barcode, flavor, image_id=None):
            calls.append((barcode, flavor, image_id))
            return ProductSnapshot(revision, image_uploader, image_uploaded_at)

        monkeypatch.setattr(api_module, "fetch_product_snapshot", stub)
        return calls

    return install


@pytest.fixture
def moderator(monkeypatch):
    """Answer the auth server as it does for a moderator."""

    async def user_data(session_cookie, auth_base_url):
        return {"user_id": "mod", "user": {"moderator": 1}}

    monkeypatch.setattr(auth_module, "_get_user_data_cached", user_data)


@pytest.fixture
def uploader(monkeypatch):
    """Set what the close-time retry reads, on the ticket closing path."""

    def install(result):
        calls = []

        def stub(barcode, image_id, flavor):
            calls.append((barcode, image_id, flavor))
            return result

        monkeypatch.setattr(api_module, "fetch_image_upload_metadata", stub)
        return calls

    return install


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


def post_flag(**overrides):
    body = {
        "barcode": BARCODE,
        "type": "product",
        "flavor": "off",
        "user_id": "alice",
        "source": "web",
        "reason": "other",
        **overrides,
    }
    return request("POST", "/api/v1/flags", json=body)


UPLOADED_AT = datetime(2024, 5, 31, 16, 8, 37)


def test_the_product_revision_is_captured(database, logged_in, snapshot):
    calls = snapshot(revision=42)
    response = post_flag()

    assert response.status_code == 200, response.text
    assert response.json()["product_revision"] == 42
    assert calls == [(BARCODE, "off", None)]
    # And it is persisted, not just echoed back.
    assert FlagModel.get_by_id(response.json()["id"]).product_revision == 42


def test_a_search_flag_has_no_product_to_look_up(database, logged_in, snapshot):
    calls = snapshot(revision=42)
    # A search flag carries its own URL: there is no product to build one from.
    response = post_flag(
        barcode=None, type="search", url="https://world.openfoodfacts.org/?q=nutella"
    )

    assert response.status_code == 200, response.text
    assert response.json()["product_revision"] is None
    assert calls == []


def test_an_unknown_revision_does_not_prevent_the_flag(database, logged_in, snapshot):
    """Capturing the revision is best effort: the flag matters more."""
    snapshot()
    response = post_flag()

    assert response.status_code == 200, response.text
    assert response.json()["product_revision"] is None
    assert FlagModel.select().count() == 1


def test_an_image_flag_costs_one_request(database, logged_in, snapshot):
    """The revision and the image metadata are read together, not twice."""
    calls = snapshot(revision=42, image_uploader="bob", image_uploaded_at=UPLOADED_AT)
    response = post_flag(type="image", image_id="1")

    assert response.status_code == 200, response.text
    # One fetch, asked for the image too -- not one fetch per thing captured.
    assert calls == [(BARCODE, "off", "1")]
    assert response.json()["product_revision"] == 42
    ticket = TicketModel.get_by_id(response.json()["ticket_id"])
    assert ticket.image_uploader == "bob"
    assert ticket.image_uploaded_at == UPLOADED_AT


def test_a_product_flag_does_not_ask_for_the_image(database, logged_in, snapshot):
    calls = snapshot(revision=42)
    response = post_flag()

    assert response.status_code == 200, response.text
    assert calls == [(BARCODE, "off", None)]
    assert TicketModel.get_by_id(response.json()["ticket_id"]).image_uploader is None


def test_an_already_deleted_image_does_not_prevent_the_ticket(
    database, logged_in, snapshot
):
    """Capturing the uploader is best effort: the flag matters more."""
    snapshot(revision=42)
    response = post_flag(type="image", image_id="1")

    assert response.status_code == 200, response.text
    assert TicketModel.get_by_id(response.json()["ticket_id"]).image_uploader is None


def test_a_flag_joining_a_ticket_does_not_ask_for_the_image_again(
    database, logged_in, snapshot
):
    """The ticket already holds it, so the second fetch leaves it out."""
    calls = snapshot(revision=42, image_uploader="bob", image_uploaded_at=UPLOADED_AT)
    first = post_flag(type="image", image_id="1")
    second = post_flag(type="image", image_id="1", reason="inappropriate")

    assert second.status_code == 200, second.text
    assert second.json()["ticket_id"] == first.json()["ticket_id"]
    # Still one request per flag, but the second one only carries the revision.
    assert calls == [(BARCODE, "off", "1"), (BARCODE, "off", None)]


def test_the_uploader_is_looked_up_again_when_the_ticket_is_closed(
    database, moderator, snapshot, uploader
):
    """A ticket created while Open Food Facts was down has another chance."""
    snapshot(revision=42)
    ticket_id = post_flag(type="image", image_id="1").json()["ticket_id"]
    assert TicketModel.get_by_id(ticket_id).image_uploader is None

    # By the time the ticket is closed, the image is readable again.
    calls = uploader(("bob", UPLOADED_AT))
    response = request("PUT", f"/api/v1/tickets/{ticket_id}/status?status=closed")

    assert response.status_code == 200, response.text
    assert calls == [(BARCODE, "1", "off")]
    assert TicketModel.get_by_id(ticket_id).image_uploader == "bob"


def test_a_ticket_that_already_has_an_uploader_is_not_looked_up_again(
    database, moderator, snapshot, uploader
):
    snapshot(revision=42, image_uploader="bob", image_uploaded_at=UPLOADED_AT)
    ticket_id = post_flag(type="image", image_id="1").json()["ticket_id"]

    calls = uploader(("someone else", None))
    response = request("PUT", f"/api/v1/tickets/{ticket_id}/status?status=closed")

    assert response.status_code == 200, response.text
    assert calls == []
    assert TicketModel.get_by_id(ticket_id).image_uploader == "bob"


def test_the_creation_date_is_stamped_by_the_server(database, logged_in, snapshot):
    snapshot(revision=42)
    before = datetime.utcnow()
    response = post_flag()
    after = datetime.utcnow()

    assert response.status_code == 200, response.text
    created_at = FlagModel.get_by_id(response.json()["id"]).created_at
    assert before <= created_at <= after


def test_a_client_cannot_set_the_creation_date(database, logged_in, snapshot):
    """Refused outright, rather than silently dropped."""
    snapshot(revision=42)
    response = post_flag(created_at="2020-01-01T00:00:00")

    assert response.status_code == 422
    assert FlagModel.select().count() == 0


def test_a_client_cannot_set_the_product_revision(database, logged_in, snapshot):
    snapshot(revision=42)
    response = post_flag(product_revision=1)

    assert response.status_code == 422


def test_a_misspelled_field_is_reported(database, logged_in, snapshot):
    """`comments` used to be accepted and the comment quietly lost."""
    snapshot(revision=42)
    response = post_flag(comments="please look at this")

    assert response.status_code == 422
    assert "comments" in response.text
