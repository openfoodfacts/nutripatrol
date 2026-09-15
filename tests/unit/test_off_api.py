import json
from datetime import datetime

import requests
from openfoodfacts import Flavor

from app import off_api
from app.off_api import extract_image_upload_metadata, fetch_product_snapshot

UPLOADED_T = 1717171717
UPLOADED_AT = datetime(2024, 5, 31, 16, 8, 37)

# Product images as returned since schema 1002
IMAGES = {
    "uploaded": {
        "1": {"uploader": "alice", "uploaded_t": UPLOADED_T, "sizes": {}},
        "2": {"uploader": "bob", "uploaded_t": UPLOADED_T + 60, "sizes": {}},
    },
    "selected": {
        "front": {"fr": {"imgid": "1", "rev": 12, "sizes": {}}},
        "ingredients": {"fr": {"imgid": "2", "rev": 14, "sizes": {}}},
    },
}

# Same product images, in the flat schema that /api/v2 still returns
LEGACY_IMAGES = {
    "1": {"uploader": "alice", "uploaded_t": UPLOADED_T, "sizes": {}},
    "2": {"uploader": "bob", "uploaded_t": UPLOADED_T + 60, "sizes": {}},
    "front_fr": {"imgid": "1", "rev": 12, "sizes": {}},
    "ingredients_fr": {"imgid": "2", "rev": 14, "sizes": {}},
}


def test_uploaded_image_id():
    assert extract_image_upload_metadata(IMAGES, "1") == ("alice", UPLOADED_AT)


def test_selected_image_id():
    """A selected image is cropped from an uploaded one, which we credit."""
    assert extract_image_upload_metadata(IMAGES, "front_fr") == ("alice", UPLOADED_AT)
    assert extract_image_upload_metadata(IMAGES, "ingredients_fr")[0] == "bob"


def test_legacy_schema():
    assert extract_image_upload_metadata(LEGACY_IMAGES, "1") == ("alice", UPLOADED_AT)
    assert extract_image_upload_metadata(LEGACY_IMAGES, "front_fr") == (
        "alice",
        UPLOADED_AT,
    )


def test_deleted_image():
    """Deleting an image removes it from the product, and unselects it."""
    assert extract_image_upload_metadata({"uploaded": {"2": {}}}, "1") == (None, None)
    assert extract_image_upload_metadata(IMAGES, "front_it") == (None, None)
    assert extract_image_upload_metadata({}, "1") == (None, None)
    assert extract_image_upload_metadata(None, "1") == (None, None)


def test_selected_image_whose_uploaded_image_was_deleted():
    images = {"uploaded": {}, "selected": {"front": {"fr": {"imgid": "1"}}}}
    assert extract_image_upload_metadata(images, "front_fr") == (None, None)


def test_missing_or_invalid_upload_date():
    """Images uploaded before 2015-08-04 have no uploader nor upload date."""
    assert extract_image_upload_metadata({"uploaded": {"1": {}}}, "1") == (None, None)
    images = {"uploaded": {"1": {"uploader": "alice", "uploaded_t": "not a date"}}}
    assert extract_image_upload_metadata(images, "1") == ("alice", None)


def test_upload_date_stored_as_a_string():
    images = {"uploaded": {"1": {"uploader": "alice", "uploaded_t": str(UPLOADED_T)}}}
    assert extract_image_upload_metadata(images, "1") == ("alice", UPLOADED_AT)


class FakeGet:
    """Stands in for the Open Food Facts read API."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def fake_off(monkeypatch, status_code=200, json_body=None, exc=None):
    response = requests.Response()
    response.status_code = status_code
    response._content = b"" if json_body is None else json.dumps(json_body).encode()
    fake = FakeGet(exc or response)
    monkeypatch.setattr(off_api.requests, "get", fake)
    return fake


def test_fetch_the_revision_alone(monkeypatch):
    fake = fake_off(monkeypatch, json_body={"product": {"rev": 42}})
    assert fetch_product_snapshot("3017620422003", "off").revision == 42
    # Only `rev` is asked for: the product JSON is otherwise huge.
    assert fake.calls[0]["params"] == {"fields": "rev"}
    assert fake.calls[0]["url"].endswith("/api/v2/product/3017620422003.json")


def test_the_revision_and_the_image_come_from_one_request(monkeypatch):
    """The two things a new flag captures are in the same product JSON."""
    fake = fake_off(
        monkeypatch, json_body={"product": {"rev": 42, "images": LEGACY_IMAGES}}
    )
    snapshot = fetch_product_snapshot("3017620422003", "off", "front_fr")

    assert len(fake.calls) == 1
    assert fake.calls[0]["params"] == {"fields": "images,rev"}
    assert snapshot == (42, "alice", UPLOADED_AT)


def test_an_image_deleted_before_the_flag_still_yields_the_revision(monkeypatch):
    fake_off(monkeypatch, json_body={"product": {"rev": 42, "images": {}}})
    assert fetch_product_snapshot("3017620422003", "off", "1") == (42, None, None)


def test_a_flavor_enum_or_string_is_accepted():
    """A flag carries the enum, a ticket read from the database its value."""
    for flavor in (Flavor.off_pro, "off_pro", "off-pro"):
        assert off_api._resolve_flavor(flavor) is Flavor.off_pro
    assert off_api._resolve_flavor("not a flavor") is None


def test_an_unknown_flavor_is_not_requested(monkeypatch):
    fake = fake_off(monkeypatch, json_body={"product": {"rev": 42}})
    assert fetch_product_snapshot("3017620422003", "not a flavor") == (None, None, None)
    assert fake.calls == []


def test_revision_stored_as_a_string(monkeypatch):
    fake_off(monkeypatch, json_body={"product": {"rev": "42"}})
    assert fetch_product_snapshot("3017620422003", "off").revision == 42


def test_missing_or_invalid_revision(monkeypatch):
    fake_off(monkeypatch, json_body={"product": {"rev": "not a revision"}})
    assert fetch_product_snapshot("3017620422003", "off").revision is None
    fake_off(monkeypatch, json_body={"product": {}})
    assert fetch_product_snapshot("3017620422003", "off").revision is None


def test_unknown_product_has_no_revision(monkeypatch):
    """/api/v2 answers 404 with {"status": 0} for an unknown product."""
    fake_off(monkeypatch, status_code=404, json_body={"status": 0})
    assert fetch_product_snapshot("3017620422003", "off").revision is None


def test_an_unreachable_open_food_facts_does_not_raise(monkeypatch):
    """Capturing the revision must never prevent a flag from being saved."""
    fake_off(monkeypatch, exc=requests.ConnectionError("boom"))
    assert fetch_product_snapshot("3017620422003", "off").revision is None
    fake_off(monkeypatch, json_body=None)  # 200 with a non-JSON body
    assert fetch_product_snapshot("3017620422003", "off").revision is None
