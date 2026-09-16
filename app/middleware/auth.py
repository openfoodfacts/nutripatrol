import asyncio
import hashlib
import os
from enum import StrEnum, auto
from typing import NamedTuple
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import HTTPException, Request
from fastapi_cache.decorator import cache
from openfoodfacts.utils import get_logger

logger = get_logger(__name__)


class UserStatus(StrEnum):
    isModerator = auto()
    isLoggedIn = auto()


def generate_cache_key(*args, **kwargs) -> str:
    # Expecting session_cookie at position 0, auth_base_url at position 1
    try:
        session_cookie = args[0]
        auth_base_url = args[1]
    except IndexError:
        raise ValueError("Missing required parameters for cache key (positional args)")

    key_raw = f"{auth_base_url}:{session_cookie}"
    return "user-data:" + hashlib.md5(key_raw.encode()).hexdigest()


def get_auth_server(request: Request):
    """
    Get auth server URL from request
    """
    # For dev purposes, we can use a static auth server with AUTH_SERVER_STATIC
    auth_server_static = os.getenv("AUTH_SERVER_STATIC")
    if auth_server_static:
        return auth_server_static
    url = str(request.base_url)  # e.g. 'https://nutripatrol.openfoodfacts.net/'
    parsed_url = urlparse(url)

    # Replace the subdomain 'nutripatrol' with 'world' in the netloc
    new_netloc = parsed_url.netloc.replace("nutripatrol", "world")

    # Rebuild the URL with the new netloc and original scheme
    base_url = urlunparse(
        (
            "https",  # Use 'https' scheme, as auth server is always secure
            new_netloc,
            "",
            "",
            "",
            "",
        )
    )

    return base_url


# Usage example:
# auth_url = get_auth_base_url(request)
# auth_url would be something like 'https://world.openfoodfacts.net/'


class AuthenticatedUser(NamedTuple):
    """The user a request acts as, and whether they moderate."""

    user_id: str
    is_moderator: bool


def get_auth_dependency(user_status: UserStatus):
    async def wrapper(request: Request) -> str:
        return await auth_dependency(request, user_status)

    return wrapper


async def authenticated_user(request: Request) -> AuthenticatedUser:
    """Authenticate any logged-in user, and report whether they moderate.

    Used by the endpoints that serve both kinds of user rather than turning
    one of them away: a moderator sees every flag and ticket, while a plain
    user only sees the flags they raised themselves, and the tickets those
    flags are attached to.
    """
    return await _authenticate(request, UserStatus.isLoggedIn)


async def auth_dependency(request: Request, user_status: UserStatus) -> str:
    """Authenticate the request and return the acting user's id."""
    return (await _authenticate(request, user_status)).user_id


async def _authenticate(request: Request, user_status: UserStatus) -> AuthenticatedUser:
    """Authenticate the request against `user_status`, or raise.

    Returns who the request acts as, so that a caller which accepts several
    kinds of user can tell them apart afterwards.
    """
    # Check for bearer token in Authorization header
    # Currently, this is only for robotoff
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # Check if hashed token matches the env variable
        token = auth_header.split(" ")[1]
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        hashed_env_token = hashlib.sha256(
            os.getenv("AUTH_BEARER_TOKEN_ROBOTOFF").encode()
        ).hexdigest()
        if hashed_token != hashed_env_token:
            raise HTTPException(status_code=403, detail="Invalid bearer token")
        # The bearer token skips the `user_status` check entirely, so it has
        # always satisfied `isModerator` as well: it is reported as a
        # moderator so that the endpoints which filter on that keep serving
        # Robotoff everything, as they did before they could tell.
        return AuthenticatedUser("robotoff", is_moderator=True)

    # If no bearer token is provided, we check for session cookie
    # Check for session cookie
    session_cookie = request.cookies.get("session")
    auth_base_url = get_auth_server(request) + "/cgi/auth.pl"

    if not session_cookie:
        raise HTTPException(status_code=401, detail="Missing session token")

    if user_status not in UserStatus:
        raise HTTPException(
            status_code=400, detail=f"Invalid user status : {user_status}"
        )

    auth_response = await _get_user_data_cached(session_cookie, auth_base_url)
    user_data = auth_response.get("user", {})
    is_moderator = user_data.get("moderator") == 1

    if user_status == UserStatus.isModerator:
        if not is_moderator:
            raise HTTPException(status_code=403, detail="User is not a moderator")

    elif user_status == UserStatus.isLoggedIn:
        if user_data.get("moderator") is None:
            raise HTTPException(status_code=403, detail="User is not logged in")

    user_id = auth_response.get("user_id", "")
    if not user_id:
        logger.warning("auth.pl returned no user_id for an authenticated session")
    return AuthenticatedUser(user_id, is_moderator)


class ModeratorSession(NamedTuple):
    """A moderator, and the session we act on their behalf with."""

    user_id: str
    session_cookie: str


async def moderator_session(request: Request) -> ModeratorSession:
    """Authenticate a moderator and return their Open Food Facts session.

    Used by the endpoints that write to Open Food Facts on the moderator's
    behalf: they need the session cookie itself, not just the user id, so that
    Open Food Facts applies its own permission checks and attributes the edit
    to the moderator. This rules out the Robotoff bearer token, which
    authenticates a machine with no Open Food Facts session behind it.
    """
    user_id = await auth_dependency(request, UserStatus.isModerator)
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        raise HTTPException(
            status_code=401,
            detail="This action is performed on Open Food Facts on your behalf, "
            "and requires an Open Food Facts session cookie",
        )
    return ModeratorSession(user_id, session_cookie)


@cache(key_builder=generate_cache_key, namespace="user-data", expire=60 * 60)
async def _get_user_data_cached(session_cookie: str, auth_base_url: str) -> dict:
    return await _fetch_user_data(session_cookie, auth_base_url)


async def _fetch_user_data(session_cookie: str, auth_base_url: str) -> dict:
    """Fetch the full auth.pl response body.

    Kept as the full body (not just the nested "user" object) because the
    acting user's id is only available at the top level, as "user_id".
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            auth_base_url, cookies={"session": session_cookie}, params={"body": "1"}
        )

    if response.status_code != 200:
        await asyncio.sleep(2)
        raise HTTPException(status_code=401, detail="Invalid session token")

    return response.json()
