"""Tests for app/moderation_api.py, the endpoints that act on Open Food Facts.

They cover what NutriPatrol is responsible for -- authenticating the
moderator, validating the request, and reporting an Open Food Facts failure
as such. What is sent to Open Food Facts is covered by test_off_write.py.
"""

import asyncio

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import moderation_api as moderation_module
from app.api import app
from app.middleware.auth import ModeratorSession, moderator_session
from app.off_api import OFFAPIError

BARCODE = "3017620422003"
SESSION = ModeratorSession(user_id="a-moderator", session_cookie="a-session-cookie")


class Client:
    """Calls the app in-process.

    Not starlette's TestClient: it builds an httpx.Client(app=...), which httpx
    dropped in 0.28 -- the version this project pins.
    """

    def request(self, method, url, json=None):
        async def send():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.request(method, url, json=json)

        return asyncio.run(send())

    def post(self, url, json=None):
        return self.request("POST", url, json=json)

    def patch(self, url, json=None):
        return self.request("PATCH", url, json=json)


@pytest.fixture
def client():
    # The moderator and their Open Food Facts session are what the auth
    # middleware provides; these tests are about what the endpoints do with it.
    app.dependency_overrides[moderator_session] = lambda: SESSION
    yield Client()
    app.dependency_overrides.clear()


@pytest.fixture
def off_call(monkeypatch):
    """Replace every Open Food Facts write with a recording stub."""
    calls = {}

    def record(name, result):
        def stub(*args, **kwargs):
            calls[name] = (args, kwargs)
            if isinstance(result, Exception):
                raise result
            return result

        return stub

    def install(name, result):
        monkeypatch.setattr(moderation_module, name, record(name, result))
        return calls

    return install


def test_delete_images(client, off_call):
    calls = off_call("delete_images", {"status": "ok", "images": [{"imgid": 3}]})

    response = client.post(
        f"/api/v1/products/{BARCODE}/images/delete",
        json={"imgids": [1, 2], "flavor": "off"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "barcode": BARCODE,
        "imgids": [1, 2],
        # What the product is left with, so the caller can refresh without
        # re-fetching the product.
        "remaining_imgids": [3],
    }
    args, kwargs = calls["delete_images"]
    assert args[0] == BARCODE
    assert args[1] == [1, 2]
    assert args[3] == SESSION.session_cookie


def test_move_images_to_the_same_product_is_rejected(client, off_call):
    calls = off_call("move_images", {"status": "ok"})

    response = client.post(
        f"/api/v1/products/{BARCODE}/images/move",
        json={"imgids": [1], "flavor": "off", "move_to": BARCODE},
    )

    assert response.status_code == 400
    assert calls == {}


@pytest.mark.parametrize("barcode", ["abc", "3017620422003.json", "3017620422003/x"])
def test_a_non_numeric_barcode_is_rejected(client, off_call, barcode):
    """Barcodes end up in the Open Food Facts URL we call while carrying the
    moderator's session cookie, so they never reach Open Food Facts as free
    text -- anything but digits could point the request elsewhere."""
    calls = off_call("delete_images", {"status": "ok"})

    response = client.post(
        f"/api/v1/products/{barcode}/images/delete",
        json={"imgids": [1], "flavor": "off"},
    )

    # 422 when the route matches and the pattern rejects it, 404 when the
    # barcode does not even look like one path segment. Either way, nothing
    # was sent to Open Food Facts.
    assert response.status_code in (404, 422)
    assert calls == {}


def test_deleting_no_image_is_rejected(client, off_call):
    calls = off_call("delete_images", {"status": "ok"})

    response = client.post(
        f"/api/v1/products/{BARCODE}/images/delete",
        json={"imgids": [], "flavor": "off"},
    )

    assert response.status_code == 422
    assert calls == {}


def test_an_open_food_facts_failure_is_reported_to_the_caller(client, off_call):
    off_call("delete_images", OFFAPIError("product does not exist", status_code=502))

    response = client.post(
        f"/api/v1/products/{BARCODE}/images/delete",
        json={"imgids": [1], "flavor": "off"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "product does not exist"}


def test_a_refusal_keeps_its_status(client, off_call):
    off_call("delete_product", OFFAPIError("not allowed", status_code=403))

    response = client.post(
        f"/api/v1/products/{BARCODE}/delete",
        json={"flavor": "off", "comment": "spam"},
    )

    assert response.status_code == 403


def test_deleting_a_product_requires_a_reason(client, off_call):
    calls = off_call("delete_product", None)

    response = client.post(
        f"/api/v1/products/{BARCODE}/delete", json={"flavor": "off", "comment": ""}
    )

    assert response.status_code == 422
    assert calls == {}


def test_change_barcode(client, off_call):
    calls = off_call("change_barcode", {"status": 1})

    response = client.post(
        f"/api/v1/products/{BARCODE}/change_barcode",
        json={"flavor": "off", "new_barcode": "3017620425003"},
    )

    assert response.status_code == 200
    assert response.json() == {"barcode": "3017620425003", "old_barcode": BARCODE}
    assert calls["change_barcode"][0][1] == "3017620425003"


def test_update_product(client, off_call):
    calls = off_call(
        "update_product",
        {"status": "success", "product": {"categories": "en:biscuits"}},
    )

    response = client.patch(
        f"/api/v1/products/{BARCODE}",
        json={
            "flavor": "off",
            "fields": {"categories": "en:biscuits"},
            "comment": "flagged as miscategorised",
        },
    )

    assert response.status_code == 200
    assert response.json()["updated_fields"] == {"categories": "en:biscuits"}
    _, kwargs = calls["update_product"]
    assert kwargs["comment"] == "flagged as miscategorised"


@pytest.mark.parametrize(
    "obsolete,expected", [(True, "on"), (False, "")], ids=["obsolete", "not-obsolete"]
)
def test_obsolete_is_sent_as_the_checkbox_value(client, off_call, obsolete, expected):
    """Open Food Facts stores `obsolete` as "on"/"", not as a boolean."""
    calls = off_call("update_product", {"status": "success", "product": {}})

    response = client.post(
        f"/api/v1/products/{BARCODE}/obsolete",
        json={"flavor": "off", "obsolete": obsolete},
    )

    assert response.status_code == 200
    assert calls["update_product"][0][1] == {"obsolete": expected}


def make_request(headers=None, cookies=None):
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        raw_headers.append(
            (b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode())
        )
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "query_string": b"",
            "headers": raw_headers,
        }
    )


def test_a_bearer_token_cannot_act_on_open_food_facts(monkeypatch):
    """Robotoff authenticates with a bearer token, which has no Open Food Facts
    session behind it to attribute an edit to."""
    monkeypatch.setenv("AUTH_BEARER_TOKEN_ROBOTOFF", "a-token")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            moderator_session(make_request(headers={"Authorization": "Bearer a-token"}))
        )

    assert excinfo.value.status_code == 401
    assert "session cookie" in excinfo.value.detail
