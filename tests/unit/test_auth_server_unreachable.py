"""How the API reports an Open Food Facts auth server that fails it.

Only a 401/403 from auth.pl is a verdict on the session. Anything else -
unreachable, a 5xx, a body that is not JSON - must come back as an explicit
502 naming the auth server and what went wrong, not as a bare 500 and not as
"Invalid session token", which would log everybody out over an outage.
"""

import asyncio

import httpx
import pytest
from fastapi import HTTPException

from app.middleware import auth as auth_module

AUTH_URL = "https://world.openfoodfacts.org/cgi/auth.pl"


@pytest.fixture
def auth_server(monkeypatch):
    """Answer the API's auth.pl calls with `handler` instead of the network."""
    real_client = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(
            auth_module.httpx,
            "AsyncClient",
            lambda: real_client(transport=httpx.MockTransport(handler)),
        )

    monkeypatch.setattr(auth_module.asyncio, "sleep", _no_sleep)
    return install


async def _no_sleep(seconds):
    pass


def fetch():
    with pytest.raises(HTTPException) as raised:
        asyncio.run(auth_module._fetch_user_data("a-session", AUTH_URL))
    return raised.value


def test_an_unreachable_auth_server_is_a_502_saying_why(auth_server):
    def refuse(request):
        raise httpx.ConnectError("All connection attempts failed", request=request)

    auth_server(refuse)
    error = fetch()

    assert error.status_code == 502
    assert AUTH_URL in error.detail
    assert "ConnectError: All connection attempts failed" in error.detail


def test_a_timeout_without_a_message_still_names_the_error(auth_server):
    def hang(request):
        raise httpx.ConnectTimeout("", request=request)

    auth_server(hang)
    error = fetch()

    assert error.status_code == 502
    assert "ConnectTimeout" in error.detail


def test_an_auth_server_error_is_not_reported_as_a_bad_session(auth_server):
    auth_server(lambda request: httpx.Response(503, text="down for maintenance"))
    error = fetch()

    assert error.status_code == 502
    assert "HTTP 503" in error.detail


def test_a_non_json_answer_is_a_502(auth_server):
    auth_server(
        lambda request: httpx.Response(
            200, text="<html>challenge</html>", headers={"content-type": "text/html"}
        )
    )
    error = fetch()

    assert error.status_code == 502
    assert "text/html" in error.detail


@pytest.mark.parametrize("status", [401, 403])
def test_a_rejected_session_is_still_a_401(auth_server, status):
    auth_server(
        lambda request: httpx.Response(
            status, json={"status": 0, "status_verbose": "user not signed-in"}
        )
    )
    error = fetch()

    assert error.status_code == 401
    assert error.detail == "Invalid session token"
