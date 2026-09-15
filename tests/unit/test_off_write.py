"""Tests for the Open Food Facts write helpers.

The interesting part is not the happy path but how failures are detected: the
CGI endpoints Open Food Facts still exposes for these actions answer HTTP 200
with the error in the JSON body, so anything that only looks at the HTTP status
reports a refused edit as a success.
"""

import json

import pytest
import requests
from openfoodfacts import Flavor
from openfoodfacts.utils import URLBuilder

from app import off_api
from app.config import settings
from app.off_api import (
    OFFAPIError,
    change_barcode,
    delete_images,
    delete_product,
    move_images,
    update_product,
)

SESSION = "a-session-cookie"


def make_response(status_code=200, json_body=None, headers=None):
    response = requests.Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    response._content = b"" if json_body is None else json.dumps(json_body).encode()
    return response


class FakeOFF:
    """Stands in for Open Food Facts: records requests, replies in order."""

    def __init__(self):
        self.calls = []
        self.replies = []

    def will_reply(self, **kwargs):
        """Queue the next response, as make_response() builds it."""
        self.replies.append(make_response(**kwargs))

    def will_fail(self, exc):
        """Queue a transport failure instead of a response."""
        self.replies.append(exc)

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    @property
    def call(self):
        """The single request that was sent."""
        assert len(self.calls) == 1, f"expected 1 request, got {len(self.calls)}"
        return self.calls[0]


@pytest.fixture
def off(monkeypatch):
    fake = FakeOFF()
    monkeypatch.setattr(off_api.requests, "request", fake)
    return fake


def base_url(flavor=Flavor.off):
    return URLBuilder.world(flavor, settings.off_tld)


def test_delete_images_sends_the_move_to_trash_form(off):
    off.will_reply(json_body={"status": "ok", "images": [{"imgid": 3}]})

    result = delete_images("3017620422003", [1, 2], Flavor.off, SESSION)

    call = off.call
    assert call["method"] == "POST"
    assert call["url"] == f"{base_url()}/cgi/product_image_move.pl"
    assert call["data"] == {
        "code": "3017620422003",
        "imgids": "1,2",
        "move_to_override": "trash",
        "copy_data_override": "false",
    }
    # The edit is made on the moderator's behalf, not NutriPatrol's.
    assert call["cookies"] == {"session": SESSION}
    # See _request(): a redirect must never carry the session cookie onwards.
    assert call["allow_redirects"] is False
    assert result["images"] == [{"imgid": 3}]


def test_move_images_targets_the_destination_barcode(off):
    off.will_reply(json_body={"status": "ok"})

    move_images(
        "3017620422003", [1], "3017620425003", Flavor.off, SESSION, copy_data=True
    )

    assert off.call["data"]["move_to_override"] == "3017620425003"
    assert off.call["data"]["copy_data_override"] == "true"


def test_move_images_reports_an_error_returned_with_a_200(off):
    """product_image_move.pl answers 200 even when it refuses the move."""
    off.will_reply(
        json_body={
            "status": "status not ok",
            "error": "error - product does not exist: 3017620422003",
        }
    )

    with pytest.raises(OFFAPIError) as excinfo:
        delete_images("3017620422003", [1], Flavor.off, SESSION)

    assert "product does not exist" in excinfo.value.message
    assert excinfo.value.status_code == 502


def test_the_flavor_picks_the_server(off):
    off.will_reply(json_body={"status": "ok"})

    delete_images("3017620422003", [1], Flavor.obf, SESSION)

    assert off.call["url"].startswith(base_url(Flavor.obf))
    assert base_url(Flavor.obf) != base_url(Flavor.off)


def test_unknown_flavor_is_a_client_error(off):
    with pytest.raises(OFFAPIError) as excinfo:
        delete_images("3017620422003", [1], "not-a-flavor", SESSION)

    assert excinfo.value.status_code == 400
    assert off.calls == []


def test_delete_product_posts_the_edit_form(off):
    off.will_reply(json_body=None)

    delete_product("3017620422003", "spam", Flavor.off, SESSION)

    call = off.call
    assert call["url"] == f"{base_url()}/cgi/product.pl"
    assert call["data"] == {
        "type": "delete",
        "action": "process",
        "code": "3017620422003",
        "comment": "spam",
    }


def test_a_refusal_is_reported_as_such(off):
    """product.pl answers 403 when the user is not a moderator."""
    off.will_reply(status_code=403)

    with pytest.raises(OFFAPIError) as excinfo:
        delete_product("3017620422003", "spam", Flavor.off, SESSION)

    assert excinfo.value.status_code == 403


def test_a_redirect_is_not_followed(off):
    """A redirect means the session was refused, not that it went through."""
    off.will_reply(status_code=302, headers={"Location": "/cgi/login.pl"})

    with pytest.raises(OFFAPIError) as excinfo:
        delete_product("3017620422003", "spam", Flavor.off, SESSION)

    assert "redirected" in excinfo.value.message


def test_a_redirect_without_a_location_is_not_followed_either(off):
    off.will_reply(status_code=302)

    with pytest.raises(OFFAPIError):
        delete_product("3017620422003", "spam", Flavor.off, SESSION)


def test_change_barcode_sends_the_new_code(off):
    off.will_reply(json_body={"status": 1})

    change_barcode("3017620422003", "3017620425003", Flavor.off, SESSION)

    call = off.call
    assert call["url"] == f"{base_url()}/cgi/product_jqm2.pl"
    assert call["data"] == {"code": "3017620422003", "new_code": "3017620425003"}


def test_change_barcode_reports_a_status_0(off):
    """The write API v2 reports "no permission" as {"status": 0} in a 200."""
    off.will_reply(
        json_body={"status": 0, "status_verbose": "error_new_code_already_exists"}
    )

    with pytest.raises(OFFAPIError) as excinfo:
        change_barcode("3017620422003", "3017620425003", Flavor.off, SESSION)

    assert excinfo.value.message == "error_new_code_already_exists"


def test_update_product_patches_the_v3_endpoint(off):
    off.will_reply(json_body={"status": "success", "product": {"obsolete": "on"}})

    result = update_product(
        "3017620422003",
        {"obsolete": "on"},
        Flavor.off,
        SESSION,
        comment="no longer sold",
        lc="fr",
    )

    call = off.call
    assert call["method"] == "PATCH"
    assert call["url"] == f"{base_url()}/api/v3/product/3017620422003"
    assert call["json"] == {
        "lc": "fr",
        "fields": "updated",
        "product": {"obsolete": "on"},
        "comment": "no longer sold",
    }
    assert result["product"] == {"obsolete": "on"}


def test_update_product_formats_the_v3_errors(off):
    off.will_reply(
        status_code=403,
        json_body={
            "status": "failure",
            "errors": [
                {
                    "message": {"id": "no_permission"},
                    "field": {"id": "obsolete"},
                    "impact": {"id": "failure"},
                }
            ],
        },
    )

    with pytest.raises(OFFAPIError) as excinfo:
        update_product("3017620422003", {"obsolete": "on"}, Flavor.off, SESSION)

    assert excinfo.value.message == "no_permission (obsolete)"
    assert excinfo.value.status_code == 403


def test_a_network_failure_is_not_a_silent_success(off):
    off.will_fail(requests.ConnectTimeout("timed out"))

    with pytest.raises(OFFAPIError) as excinfo:
        delete_images("3017620422003", [1], Flavor.off, SESSION)

    assert "could not reach Open Food Facts" in excinfo.value.message
