"""Tests for moving a ticket's product to another project.

It is two writes in two places -- the product type on Open Food Facts, the
ticket status here -- so what matters is their order: the ticket is only
closed once Open Food Facts has accepted the move.
"""

import asyncio
from datetime import datetime

import httpx
import pytest
from peewee import SqliteDatabase

from app import api as api_module
from app.api import app
from app.middleware.auth import ModeratorSession, moderator_session
from app.models import FlagModel, ModeratorActionModel, TicketModel
from app.off_api import OFFAPIError

BARCODE = "3017620422003"
MODELS = [TicketModel, FlagModel, ModeratorActionModel]
SESSION = ModeratorSession(user_id="a-moderator", session_cookie="a-session-cookie")


@pytest.fixture
def database(tmp_path, monkeypatch):
    """Run the endpoint against a throwaway SQLite database."""
    test_db = SqliteDatabase(str(tmp_path / "nutripatrol.db"))
    test_db.bind(MODELS)
    test_db.create_tables(MODELS)
    test_db.close()
    monkeypatch.setattr(api_module, "db", test_db)
    yield test_db
    test_db.close()


@pytest.fixture
def moderator():
    app.dependency_overrides[moderator_session] = lambda: SESSION
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def off_update(monkeypatch):
    """Record the Open Food Facts write instead of sending it."""
    calls = []

    def stub(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "success", "product": args[1]}

    monkeypatch.setattr(api_module, "update_product", stub)
    return calls


def make_ticket(**overrides):
    fields = {
        "barcode": BARCODE,
        "type": "product",
        "url": f"https://world.openfoodfacts.org/product/{BARCODE}",
        "status": "open",
        "flavor": "off",
        "created_at": datetime.utcnow(),
        **overrides,
    }
    return TicketModel.create(**fields)


def move(ticket_id, json):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post(
                f"/api/v1/tickets/{ticket_id}/move_product", json=json
            )

    return asyncio.run(send())


def test_the_product_is_moved_and_the_ticket_closed_as_fixed(
    database, moderator, off_update
):
    ticket = make_ticket()

    response = move(ticket.id, {"flavor": "obf", "comment": "a shampoo"})

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "closed-fixed"
    args, kwargs = off_update[0]
    # Sent to the server the product is on now, which moves it on save.
    assert args[:4] == (BARCODE, {"product_type": "beauty"}, "off", "a-session-cookie")
    assert kwargs["comment"] == "a shampoo"
    action = ModeratorActionModel.get(ModeratorActionModel.ticket == ticket.id)
    assert (action.user_id, action.action_type) == ("a-moderator", "closed-fixed")


def test_a_failed_move_leaves_the_ticket_open(database, moderator, monkeypatch):
    ticket = make_ticket()

    def refuse(*args, **kwargs):
        raise OFFAPIError("no_permission", status_code=403)

    monkeypatch.setattr(api_module, "update_product", refuse)

    response = move(ticket.id, {"flavor": "opff"})

    assert response.status_code == 403
    assert TicketModel.get_by_id(ticket.id).status == "open"
    assert ModeratorActionModel.select().count() == 0


@pytest.mark.parametrize(
    "ticket_fields,flavor",
    [
        ({"flavor": "obf"}, "obf"),
        ({"flavor": "off-pro"}, "obf"),
        ({"barcode": None, "type": "search"}, "obf"),
    ],
    ids=["same-project", "pro-platform", "search-ticket"],
)
def test_a_move_that_makes_no_sense_is_refused(
    database, moderator, off_update, ticket_fields, flavor
):
    ticket = make_ticket(**ticket_fields)

    response = move(ticket.id, {"flavor": flavor})

    assert response.status_code == 400
    assert off_update == []
    assert TicketModel.get_by_id(ticket.id).status == "open"


@pytest.mark.parametrize("flavor", ["off-pro", "off_pro", "op", "openbeautyfacts"])
def test_only_a_project_can_be_a_destination(database, moderator, off_update, flavor):
    ticket = make_ticket(flavor="obf")

    response = move(ticket.id, {"flavor": flavor})

    assert response.status_code == 422
    assert off_update == []


def test_an_unknown_ticket_is_not_found(database, moderator, off_update):
    response = move(12345, {"flavor": "obf"})

    assert response.status_code == 404
    assert off_update == []
