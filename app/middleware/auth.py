import asyncio
import hashlib
import os
from enum import StrEnum, auto
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import HTTPException, Request
from fastapi_cache.decorator import cache


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
            # It seems that Starlette ignores the scheme provided
            # by the request headers if the reverse proxy IP address is not in
            # the trusted proxies list.
            # So we force it to be https, as we never want to use http here.
            "https",
            new_netloc,
            "",  # path
            "",  # params
            "",  # query
            "",  # fragment
        )
    )

    return base_url


# Usage example:
# auth_url = get_auth_base_url(request)
# auth_url would be something like 'https://world.openfoodfacts.net/'


def get_auth_dependency(user_status: UserStatus):
    async def wrapper(request: Request):
        return await auth_dependency(request, user_status)

    return wrapper


async def auth_dependency(request: Request, user_status: UserStatus):
    session_cookie = request.cookies.get("session")
    auth_base_url = get_auth_server(request) + "/cgi/auth.pl"

    if not session_cookie:
        raise HTTPException(status_code=401, detail="Missing session token")

    if user_status not in UserStatus:
        raise HTTPException(
            status_code=400, detail=f"Invalid user status : {user_status}"
        )

    user_data = await get_user_data(session_cookie, auth_base_url)

    if user_status == UserStatus.isModerator:
        if user_data.get("moderator") != 1:
            raise HTTPException(status_code=403, detail="User is not a moderator")

    elif user_status == UserStatus.isLoggedIn:
        if user_data.get("moderator") is None:
            raise HTTPException(status_code=403, detail="User is not logged in")


async def get_user_data(session_cookie: str, auth_base_url: str) -> dict:
    if not session_cookie:
        return await _fetch_user_data(session_cookie, auth_base_url)
    return await _get_user_data_cached(session_cookie, auth_base_url)


@cache(key_builder=generate_cache_key, namespace="user-data", expire=60 * 60)
async def _get_user_data_cached(session_cookie: str, auth_base_url: str) -> dict:
    return await _fetch_user_data(session_cookie, auth_base_url)


async def _fetch_user_data(session_cookie: str, auth_base_url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            auth_base_url, cookies={"session": session_cookie}, params={"body": "1"}
        )

    if response.status_code != 200:
        await asyncio.sleep(2)
        raise HTTPException(status_code=401, detail="Invalid session token")

    return response.json().get("user", {})
