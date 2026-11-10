"""Tests for the labels moderators put on tickets.

Labels are shared between tickets, never deleted, and internal to moderation:
the users who flagged a ticket see neither its labels nor the label changes in
its history. Every label put on or taken off a ticket is a moderator action.
"""

import asyncio
from datetime import datetime

import httpx
import pytest
from peewee import SqliteDatabase

from app import api as api_module
from app.api import app
from app.middleware import auth as auth_module
from app.models import (
    FlagModel,
    LabelModel,
    ModeratorActionModel,
    TicketCommentModel,
    TicketLabelModel,
    TicketModel,
)

BARCODE = "3017620422003"
MODELS = [
    TicketModel,
    FlagModel,
    LabelModel,
    ModeratorActionModel,
    TicketCommentModel,
    TicketLabelModel,
]


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


def create_label(name, color=None):
    response = request("POST", "/api/v1/labels", {"name": name, "color": color})
    assert response.status_code == 200, response.text
    return response.json()


def add_label(ticket_id, label_id):
    return request("POST", f"/api/v1/tickets/{ticket_id}/labels/{label_id}")


def test_a_moderator_creates_a_label(database, act_as):
    label = create_label("  Vandal  ", "error")

    assert label["name"] == "Vandal"
    assert label["color"] == "error"
    assert label["created_by"] == "a-moderator"


def test_creating_an_existing_name_in_another_case_returns_that_label(database, act_as):
    first = create_label("Vandal")
    second = create_label("vANDAL")

    assert second["id"] == first["id"]
    assert second["name"] == "Vandal"
    assert LabelModel.select().count() == 1


def test_labels_are_listed_by_name_with_their_ticket_count(database, act_as):
    ticket = make_ticket()
    vandal = create_label("vandal")
    create_label("Bug")
    add_label(ticket.id, vandal["id"])

    response = request("GET", "/api/v1/labels")

    assert response.status_code == 200, response.text
    assert [
        (label["name"], label["ticket_count"]) for label in response.json()["labels"]
    ] == [
        ("Bug", 0),
        ("vandal", 1),
    ]


def test_a_label_is_renamed_and_recolored(database, act_as):
    label = create_label("vandal")

    response = request(
        "PATCH",
        f"/api/v1/labels/{label['id']}",
        {"name": "Vandalism", "color": "warning"},
    )

    assert response.status_code == 200, response.text
    assert (response.json()["name"], response.json()["color"]) == (
        "Vandalism",
        "warning",
    )


def test_renaming_a_label_to_a_taken_name_is_a_409(database, act_as):
    create_label("Bug")
    label = create_label("vandal")

    response = request("PATCH", f"/api/v1/labels/{label['id']}", {"name": "BUG"})

    assert response.status_code == 409
    assert LabelModel.get_by_id(label["id"]).name == "vandal"


def test_a_label_can_be_recased(database, act_as):
    label = create_label("vandal")

    response = request("PATCH", f"/api/v1/labels/{label['id']}", {"name": "Vandal"})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Vandal"


def test_an_unknown_color_is_refused(database, act_as):
    response = request("POST", "/api/v1/labels", {"name": "Bug", "color": "#ff0000"})

    assert response.status_code == 422


def test_labels_cannot_be_deleted(database, act_as):
    label = create_label("vandal")

    response = request("DELETE", f"/api/v1/labels/{label['id']}")

    assert response.status_code == 405
    assert LabelModel.select().count() == 1


def test_adding_a_label_twice_records_it_once(database, act_as):
    ticket = make_ticket()
    label = create_label("vandal")

    first = add_label(ticket.id, label["id"])
    second = add_label(ticket.id, label["id"])

    assert first.status_code == second.status_code == 200
    assert [lab["name"] for lab in second.json()["labels"]] == ["vandal"]
    assert TicketLabelModel.select().count() == 1
    [action] = ModeratorActionModel.select()
    assert (action.action_type, action.label_id, action.user_id) == (
        "label_added",
        label["id"],
        "a-moderator",
    )


def test_removing_a_label_records_a_label_removed_action(database, act_as):
    ticket = make_ticket()
    label = create_label("vandal")
    add_label(ticket.id, label["id"])

    response = request("DELETE", f"/api/v1/tickets/{ticket.id}/labels/{label['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["labels"] == []
    assert [a.action_type for a in ModeratorActionModel.select()] == [
        "label_added",
        "label_removed",
    ]


def test_removing_a_label_the_ticket_does_not_have_records_nothing(database, act_as):
    ticket = make_ticket()
    label = create_label("vandal")

    response = request("DELETE", f"/api/v1/tickets/{ticket.id}/labels/{label['id']}")

    assert response.status_code == 200, response.text
    assert ModeratorActionModel.select().count() == 0


@pytest.mark.parametrize("missing", ["ticket", "label"])
def test_labelling_with_an_unknown_ticket_or_label_is_a_404(database, act_as, missing):
    ticket = make_ticket()
    label = create_label("vandal")
    ticket_id = 999 if missing == "ticket" else ticket.id
    label_id = 999 if missing == "label" else label["id"]

    response = add_label(ticket_id, label_id)

    assert response.status_code == 404


def test_the_history_carries_the_label(database, act_as):
    ticket = make_ticket()
    label = create_label("vandal", "error")
    add_label(ticket.id, label["id"])

    response = request("GET", f"/api/v1/tickets/{ticket.id}/actions")

    [action] = response.json()["actions"]
    assert action["action_type"] == "label_added"
    assert action["label"]["name"] == "vandal"
    assert action["comment"] is None


def test_the_label_filter_keeps_tickets_with_any_of_the_labels(database, act_as):
    vandal_ticket, bug_ticket, both_ticket, plain_ticket = [
        make_ticket() for _ in range(4)
    ]
    vandal = create_label("vandal")
    bug = create_label("bug")
    add_label(vandal_ticket.id, vandal["id"])
    add_label(bug_ticket.id, bug["id"])
    add_label(both_ticket.id, vandal["id"])
    add_label(both_ticket.id, bug["id"])

    one = request("GET", f"/api/v1/tickets?label={vandal['id']}")
    several = request("GET", f"/api/v1/tickets?label={vandal['id']}&label={bug['id']}")

    assert {t["id"] for t in one.json()["tickets"]} == {
        vandal_ticket.id,
        both_ticket.id,
    }
    assert {t["id"] for t in several.json()["tickets"]} == {
        vandal_ticket.id,
        bug_ticket.id,
        both_ticket.id,
    }
    assert plain_ticket.id not in {t["id"] for t in several.json()["tickets"]}


def test_tickets_carry_their_labels_for_moderators(database, act_as):
    ticket = make_ticket()
    label = create_label("vandal")
    add_label(ticket.id, label["id"])

    listed = request("GET", "/api/v1/tickets").json()["tickets"][0]
    shown = request("GET", f"/api/v1/tickets/{ticket.id}").json()

    assert [lab["name"] for lab in listed["labels"]] == ["vandal"]
    assert [lab["name"] for lab in shown["labels"]] == ["vandal"]


def test_a_flagger_sees_neither_labels_nor_label_changes(database, act_as):
    ticket = make_ticket(flagged_by="alice")
    label = create_label("vandal")
    add_label(ticket.id, label["id"])
    request("POST", f"/api/v1/tickets/{ticket.id}/comments", {"text": "On it"})

    act_as("alice")
    listed = request("GET", "/api/v1/tickets")
    shown = request("GET", f"/api/v1/tickets/{ticket.id}")
    history = request("GET", f"/api/v1/tickets/{ticket.id}/actions")
    # The label filter is a moderator one: ignored, not an empty answer that
    # would tell which tickets have the label.
    filtered = request("GET", "/api/v1/tickets?label=999")

    assert listed.json()["tickets"][0]["labels"] == []
    assert shown.json()["labels"] == []
    assert [a["action_type"] for a in history.json()["actions"]] == ["comment"]
    assert history.json()["total"] == 1
    assert [t["id"] for t in filtered.json()["tickets"]] == [ticket.id]


@pytest.mark.parametrize(
    "method,url,body",
    [
        ("GET", "/api/v1/labels", None),
        ("POST", "/api/v1/labels", {"name": "mine"}),
        ("PATCH", "/api/v1/labels/{label}", {"name": "mine"}),
        ("POST", "/api/v1/tickets/{ticket}/labels/{label}", None),
        ("DELETE", "/api/v1/tickets/{ticket}/labels/{label}", None),
    ],
)
def test_label_routes_are_for_moderators(database, act_as, method, url, body):
    ticket = make_ticket(flagged_by="alice")
    label = create_label("vandal")
    act_as("alice")

    response = request(method, url.format(ticket=ticket.id, label=label["id"]), body)

    assert response.status_code == 403
    assert LabelModel.select().count() == 1
    assert TicketLabelModel.select().count() == 0
