from datetime import datetime, timedelta

import pytest
from peewee import SqliteDatabase

import app.api as api
from app.api import IssueType, TicketStatus, get_tickets
from app.models import FlagModel, ModeratorActionModel, TicketModel

MODELS = [TicketModel, FlagModel, ModeratorActionModel]


@pytest.fixture()
def test_db(monkeypatch):
    database = SqliteDatabase(":memory:")
    monkeypatch.setattr(api, "db", database)
    with database.bind_ctx(MODELS):
        database.create_tables(MODELS)
        yield database
        database.drop_tables(MODELS)


def _create_ticket(
    barcode: str,
    status: TicketStatus,
    created_at: datetime,
):
    return TicketModel.create(
        barcode=barcode,
        type=IssueType.product,
        url=f"https://world.openfoodfacts.org/product/{barcode}",
        status=status,
        image_id=None,
        flavor="off",
        created_at=created_at,
    )


def test_get_tickets_without_filters_returns_all_ticket_statuses(test_db):
    now = datetime(2026, 1, 1, 12, 0, 0)
    _create_ticket("111", TicketStatus.open, now)
    _create_ticket("222", TicketStatus.closed, now + timedelta(minutes=1))

    response = get_tickets(_=None)

    assert response.max_page == 1
    assert [ticket.barcode for ticket in response.tickets] == ["222", "111"]
    assert [ticket.status for ticket in response.tickets] == [
        TicketStatus.closed,
        TicketStatus.open,
    ]


def test_get_tickets_with_status_filter_still_filters_results(test_db):
    now = datetime(2026, 1, 1, 12, 0, 0)
    _create_ticket("111", TicketStatus.open, now)
    _create_ticket("222", TicketStatus.closed, now + timedelta(minutes=1))

    response = get_tickets(status=TicketStatus.open, _=None)

    assert response.max_page == 1
    assert [ticket.barcode for ticket in response.tickets] == ["111"]
    assert [ticket.status for ticket in response.tickets] == [TicketStatus.open]


def test_get_tickets_without_filters_returns_empty_page_when_no_tickets(test_db):
    response = get_tickets(_=None)

    assert response.max_page == 0
    assert response.tickets == []
