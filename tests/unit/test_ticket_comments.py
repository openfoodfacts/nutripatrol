"""Tests for the comments moderators write on tickets.

A comment is always its own moderator action, of type `comment`, so that it
sits in the ticket history next to the status changes. Closing with a comment
records two actions, the comment first, the close one millisecond later.
"""

import asyncio
from datetime import datetime, timedelta

import httpx
import pytest
from peewee import SqliteDatabase

from app import api as api_module
from app.api import app
from app.middleware import auth as auth_module
from app.models import FlagModel, ModeratorActionModel, TicketCommentModel, TicketModel

BARCODE = "3017620422003"
MODELS = [TicketModel, FlagModel, ModeratorActionModel, TicketCommentModel]


@pytest.fixture
def database(tmp_path, monkeypatch):
    """Run the endpoints against a throwaway SQLite database."""
    test_db = SqliteDatabase(str(tmp_path / "nutripatrol.db"))
    test_db.bind(MODELS)
    test_db.create_tables(MODELS)
    test_db.close()
    monkeypatch.setattr(api_module, "db", test_db)
    # Closing a ticket captures the image upload metadata from Open Food Facts.
    monkeypatch.setattr(
        api_module, "fetch_image_upload_metadata", lambda *args, **kwargs: (None, None)
    )
    yield test_db
    test_db.close()


@pytest.fixture
def act_as(monkeypatch):
    """Answer the auth server as whoever the test is currently acting as."""
    current = {"user_id": "a-moderator", "moderator": 1}

    async def user_data(session_cookie, auth_base_url):
        return {
            "user_id": current["user_id"],
            "user": {"moderator": current["moderator"]},
        }

    monkeypatch.setattr(auth_module, "_get_user_data_cached", user_data)

    def switch(user_id, moderator=0):
        current.update(user_id=user_id, moderator=moderator)

    return switch


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


def make_ticket(flagged_by="alice"):
    ticket = TicketModel.create(
        barcode=BARCODE,
        type="product",
        url=f"https://world.openfoodfacts.org/product/{BARCODE}",
        status="open",
        flavor="off",
        created_at=datetime.utcnow(),
    )
    FlagModel.create(
        ticket=ticket,
        barcode=BARCODE,
        type="product",
        url=ticket.url,
        user_id=flagged_by,
        device_id="a-device",
        source="web",
        flavor="off",
        reason="nutrition_data",
        created_at=datetime.utcnow(),
    )
    return ticket


def test_a_comment_is_recorded_as_a_comment_action(database, act_as):
    ticket = make_ticket()

    response = request(
        "POST", f"/api/v1/tickets/{ticket.id}/comments", {"text": "  Asked OFF  "}
    )

    assert response.status_code == 200, response.text
    comment = response.json()
    assert comment["text"] == "Asked OFF"
    assert comment["user_id"] == "a-moderator"
    assert comment["ticket_id"] == ticket.id
    action = ModeratorActionModel.get_by_id(comment["moderator_action_id"])
    assert (action.action_type, action.user_id) == ("comment", "a-moderator")
    # A comment does not change the status.
    assert TicketModel.get_by_id(ticket.id).status == "open"


def test_comments_are_listed_oldest_first(database, act_as):
    ticket = make_ticket()
    for text in ["first", "second"]:
        request("POST", f"/api/v1/tickets/{ticket.id}/comments", {"text": text})

    response = request("GET", f"/api/v1/tickets/{ticket.id}/comments")

    assert response.status_code == 200, response.text
    assert [c["text"] for c in response.json()["comments"]] == ["first", "second"]
    assert response.json()["total"] == 2


def test_the_flagger_reads_the_comments_but_no_one_else(database, act_as):
    ticket = make_ticket(flagged_by="alice")
    request("POST", f"/api/v1/tickets/{ticket.id}/comments", {"text": "On it"})

    act_as("alice")
    response = request("GET", f"/api/v1/tickets/{ticket.id}/comments")
    assert response.status_code == 200, response.text
    assert [c["text"] for c in response.json()["comments"]] == ["On it"]

    act_as("bob")
    response = request("GET", f"/api/v1/tickets/{ticket.id}/comments")
    assert response.status_code == 404


def test_only_moderators_comment(database, act_as):
    ticket = make_ticket(flagged_by="alice")
    act_as("alice")

    response = request(
        "POST", f"/api/v1/tickets/{ticket.id}/comments", {"text": "Me too"}
    )

    assert response.status_code == 403
    assert TicketCommentModel.select().count() == 0


@pytest.mark.parametrize("text", ["", "   ", "x" * 2001])
def test_an_empty_or_too_long_comment_is_refused(database, act_as, text):
    ticket = make_ticket()

    response = request("POST", f"/api/v1/tickets/{ticket.id}/comments", {"text": text})

    assert response.status_code == 422
    assert ModeratorActionModel.select().count() == 0


def test_commenting_on_an_unknown_ticket_is_a_404(database, act_as):
    response = request("POST", "/api/v1/tickets/999/comments", {"text": "Hello"})

    assert response.status_code == 404


def test_close_with_comment_records_the_comment_then_the_close(database, act_as):
    ticket = make_ticket()

    response = request(
        "POST",
        f"/api/v1/tickets/{ticket.id}/close_with_comment",
        {"status": "closed-fixed", "comment": "Added the nutrition table"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "closed-fixed"
    assert response.json()["comment_count"] == 1
    comment_action, close_action = ModeratorActionModel.select().order_by(
        ModeratorActionModel.created_at
    )
    assert comment_action.action_type == "comment"
    assert close_action.action_type == "closed-fixed"
    assert close_action.created_at - comment_action.created_at == timedelta(
        milliseconds=1
    )
    assert TicketCommentModel.get().moderator_action_id == comment_action.id


def test_the_history_lists_the_close_above_its_comment(database, act_as):
    ticket = make_ticket()
    request(
        "POST",
        f"/api/v1/tickets/{ticket.id}/close_with_comment",
        {"status": "closed-no-issue", "comment": "The values are right"},
    )

    response = request("GET", f"/api/v1/tickets/{ticket.id}/actions")

    assert response.status_code == 200, response.text
    actions = response.json()["actions"]
    assert [a["action_type"] for a in actions] == ["closed-no-issue", "comment"]
    assert actions[0]["comment"] is None
    assert actions[1]["comment"]["text"] == "The values are right"


def test_my_actions_include_my_comments(database, act_as):
    ticket = make_ticket()
    request("POST", f"/api/v1/tickets/{ticket.id}/comments", {"text": "Noted"})

    response = request("GET", "/api/v1/moderator_actions/me")

    assert response.status_code == 200, response.text
    [action] = response.json()["actions"]
    assert action["action_type"] == "comment"
    assert action["comment"]["text"] == "Noted"


def test_close_with_comment_on_a_ticket_already_closed_so_keeps_the_comment(
    database, act_as
):
    ticket = make_ticket()
    request("PUT", f"/api/v1/tickets/{ticket.id}/status?status=closed-fixed")

    response = request(
        "POST",
        f"/api/v1/tickets/{ticket.id}/close_with_comment",
        {"status": "closed-fixed", "comment": "Also fixed the brand"},
    )

    assert response.status_code == 200, response.text
    assert [a.action_type for a in ModeratorActionModel.select()] == [
        "closed-fixed",
        "comment",
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"status": "open", "comment": "Reopening"},
        {"status": "closed-fixed", "comment": ""},
        {"status": "closed-fixed"},
    ],
    ids=["reopen", "empty-comment", "no-comment"],
)
def test_close_with_comment_refuses_a_bad_request(database, act_as, body):
    ticket = make_ticket()

    response = request("POST", f"/api/v1/tickets/{ticket.id}/close_with_comment", body)

    assert response.status_code == 422
    assert TicketModel.get_by_id(ticket.id).status == "open"
    assert ModeratorActionModel.select().count() == 0


def test_tickets_carry_their_comment_count(database, act_as):
    commented = make_ticket()
    make_ticket()
    for text in ["one", "two"]:
        request("POST", f"/api/v1/tickets/{commented.id}/comments", {"text": text})

    response = request("GET", "/api/v1/tickets")

    assert response.status_code == 200, response.text
    counts = {t["id"]: t["comment_count"] for t in response.json()["tickets"]}
    assert counts == {commented.id: 2, commented.id + 1: 0}
    response = request("GET", f"/api/v1/tickets/{commented.id}")
    assert response.json()["comment_count"] == 2
