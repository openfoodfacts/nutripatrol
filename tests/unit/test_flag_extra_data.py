"""Tests for the structured details a flag can carry beyond its comment.

The point of `extra_data` is that a fact survives from the person who knew it
to the moderator who can act on it. So these tests care less about the shape
of the payload than about the journey: that a value written through the API
comes back out of the database unchanged, through every route that reads a
flag, and that the clients which send nothing of the sort keep working.
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
OTHER_BARCODE = "4335619032118"
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


@pytest.fixture(autouse=True)
def no_off_call(monkeypatch):
    """Keep the product snapshot from reaching Open Food Facts."""
    monkeypatch.setattr(
        api_module, "fetch_product_snapshot", lambda *a, **k: ProductSnapshot()
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


def test_extra_data_survives_the_round_trip_to_the_database(database, logged_in):
    """The value the reporter gave is the value the moderator reads.

    Worth its own assertion against the model rather than against the
    response: a JSON column that stored a repr, or a cast SQLite quietly
    turned into `0`, would still answer this request correctly from the
    object it just built in memory.
    """
    response = post_flag(
        reason="wrong_barcode",
        extra_data={
            "correct_barcode": OTHER_BARCODE,
            "suggested_action": "delete_product",
        },
    )

    assert response.status_code == 200, response.text
    stored = FlagModel.get_by_id(response.json()["id"]).extra_data
    assert stored == {
        "correct_barcode": OTHER_BARCODE,
        "suggested_action": "delete_product",
    }


def test_extra_data_comes_back_from_every_route_that_reads_a_flag(database, logged_in):
    """Including the batch route, which is the one the moderation UI calls.

    It answers with raw rows and no response model, so it reads the column
    through peewee alone -- a path the single-flag routes do not exercise.
    """
    created = post_flag(
        reason="copyright", extra_data={"offending_uploader": "prepperapp"}
    ).json()

    single = request("GET", f"/api/v1/flags/{created['id']}")
    assert single.status_code == 200, single.text
    assert single.json()["extra_data"] == {"offending_uploader": "prepperapp"}

    listed = request("GET", "/api/v1/flags")
    assert listed.json()["flags"][0]["extra_data"] == {
        "offending_uploader": "prepperapp"
    }

    batch = request(
        "POST", "/api/v1/flags/batch", json={"ticket_ids": [created["ticket_id"]]}
    )
    assert batch.status_code == 200, batch.text
    flags = batch.json()["ticket_id_to_flags"][str(created["ticket_id"])]
    assert flags[0]["extra_data"] == {"offending_uploader": "prepperapp"}


def test_a_flag_without_extra_data_is_still_a_flag(database, logged_in):
    """Robotoff and the mobile app send a reason and a comment, no more.

    Neither is deployed from this repository, so this is the guarantee that
    adding the field did not quietly make it required.
    """
    response = post_flag(reason="other", comment="plain old flag")

    assert response.status_code == 200, response.text
    assert response.json()["extra_data"] is None
    assert FlagModel.get_by_id(response.json()["id"]).extra_data is None


def test_a_key_the_reason_does_not_accept_is_refused(database, logged_in):
    """Named, rather than dropped: a client that collected a fact and spelled
    the key wrong should hear about it instead of losing the fact."""
    response = post_flag(
        reason="wrong_barcode", extra_data={"correct_barcodes": OTHER_BARCODE}
    )

    assert response.status_code == 422
    assert "correct_barcodes" in response.text


def test_extra_data_is_refused_for_a_reason_that_takes_none(database, logged_in):
    response = post_flag(reason="human", extra_data={"correct_barcode": OTHER_BARCODE})

    assert response.status_code == 422
    assert "human" in response.text


def test_extra_data_is_refused_for_a_reason_outside_the_taxonomy(database, logged_in):
    """The reason itself is still accepted -- see the unknown-reason test
    below -- but there is no schema to read the payload against."""
    response = post_flag(
        reason="something-new", extra_data={"correct_barcode": OTHER_BARCODE}
    )

    assert response.status_code == 422


def test_a_barcode_field_refuses_something_that_is_not_one(database, logged_in):
    """These values are interpolated into the Open Food Facts URLs the
    moderation endpoints call, so the constraint is the same as there."""
    response = post_flag(reason="wrong_barcode", extra_data={"correct_barcode": "abc"})

    assert response.status_code == 422


def test_a_selected_image_id_is_not_an_uploaded_one(database, logged_in):
    """`front_fr` names a crop rather than a file, and Open Food Facts
    ignores it when asked to delete or move one."""
    response = post_flag(
        type="image",
        image_id="1",
        reason="duplicate",
        extra_data={"duplicate_of_image_id": "front_fr"},
    )

    assert response.status_code == 422


def test_unanswered_questions_are_not_stored_at_all(database, logged_in):
    """So that "not asked" and "answered nothing" do not have to be told
    apart later, by a UI deciding whether to render a field."""
    response = post_flag(
        reason="wrong_barcode",
        extra_data={"correct_barcode": OTHER_BARCODE, "suggested_action": None},
    )

    assert response.status_code == 200, response.text
    assert response.json()["extra_data"] == {"correct_barcode": OTHER_BARCODE}


def test_an_unknown_reason_is_recorded_rather_than_refused(database, logged_in, caplog):
    """The mobile app files flags with the reason `"string"`, and it is not
    deployed from here. Refusing those would break reporting for everyone
    using it, so they are counted until the logs are quiet."""
    response = post_flag(reason="string")

    assert response.status_code == 200, response.text
    assert response.json()["reason"] == "string"
    assert "string" in caplog.text


def test_a_flag_stored_before_the_taxonomy_is_still_readable(database, logged_in):
    """Rows written by a client we do not control, or before any of this
    existed, must not turn a stricter form into a 500 on `GET /flags`."""
    created = post_flag(reason="other").json()
    FlagModel.update(reason="test reason").where(
        FlagModel.id == created["id"]
    ).execute()

    response = request("GET", f"/api/v1/flags/{created['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["reason"] == "test reason"


def test_a_ticket_can_be_filtered_by_a_reason_the_form_submits(database, logged_in):
    """`wrong_barcode` answered 422 before the taxonomy was reconciled: the
    form submitted it and the filter did not know it."""
    post_flag(reason="wrong_barcode", extra_data={"correct_barcode": OTHER_BARCODE})

    response = request("GET", "/api/v1/tickets?reason=wrong_barcode")

    assert response.status_code == 200, response.text
    assert [t["barcode"] for t in response.json()["tickets"]] == [BARCODE]


def test_the_reason_list_describes_what_each_one_accepts(database, logged_in):
    response = request("GET", "/api/v1/reasons")

    assert response.status_code == 200, response.text
    by_value = {r["value"]: r for r in response.json()["reasons"]}

    wrong_barcode = by_value["wrong_barcode"]
    assert wrong_barcode["types"] == ["product"]
    assert wrong_barcode["bot_only"] is False
    assert "correct_barcode" in wrong_barcode["extra_data_schema"]["properties"]

    assert by_value["human"]["bot_only"] is True
    assert by_value["human"]["extra_data_schema"] is None
    # Offered on both a product and an image: someone can regret creating the
    # page as easily as uploading the photo.
    assert by_value["delete_request"]["types"] == ["product", "image"]


def test_two_reports_of_the_same_reason_stay_one_report(database, logged_in):
    """Deliberately keyed on the reason and not on `extra_data`: keying on it
    would let one person file the same complaint five times by changing a
    character."""
    first = post_flag(
        reason="wrong_barcode", extra_data={"correct_barcode": OTHER_BARCODE}
    )
    second = post_flag(
        reason="wrong_barcode", extra_data={"correct_barcode": "9999999999999"}
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 409


def test_an_uploader_handle_is_constrained(database, logged_in):
    """It is rendered as a link to an Open Food Facts contributor page."""
    assert (
        post_flag(
            type="image",
            image_id="1",
            reason="copyright",
            extra_data={"offending_uploader": "not a handle"},
        ).status_code
        == 422
    )


def test_a_source_url_must_look_like_one(database, logged_in):
    assert (
        post_flag(
            type="image",
            image_id="1",
            reason="copyright",
            extra_data={"original_source_url": "javascript:alert(1)"},
        ).status_code
        == 422
    )
