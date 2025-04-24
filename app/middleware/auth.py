import asyncio
from enum import StrEnum, auto

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi_cache import FastAPICache

import os


class UserStatus(StrEnum):
    isModerator = auto()
    isLoggedIn = auto()


def get_auth_server(request: Request):
    """
    Get auth server URL from request

    We deduce it by changing part of the request base URL
    according to FOLKSONOMY_PREFIX and AUTH_PREFIX settings
    """
    # For dev purposes, we can use a static auth server with AUTH_SERVER_STATIC
    # which can be specified in local_settings.py
    auth_server_static = os.getenv("AUTH_SERVER_STATIC")
    if auth_server_static and auth_server_static != "":
        return auth_server_static
    base_url = f"{request.base_url.scheme}://{request.base_url.netloc}"
    # remove folksonomy prefix and add AUTH prefix
    base_url = base_url.replace("nutripatrol" or "", "world" or "")
    return base_url


def get_auth_dependency(user_status: UserStatus):
    async def wrapper(request: Request):
        return await auth_dependency(request, user_status)

    return Depends(wrapper)


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
    cache = FastAPICache.get_backend()
    cache_key = f"user-data:{session_cookie}"

    cached_data = await cache.get(cache_key)
    if cached_data:
        return cached_data

    async with httpx.AsyncClient() as client:
        response = await client.get(
            auth_base_url, cookies={"session": session_cookie}, params={"body": "1"}
        )

    if response.status_code != 200:
        # Protect against brute-force
        await asyncio.sleep(2)
        raise HTTPException(status_code=401, detail="Invalid session token")

    user = response.json().get("user", {})

    if user:
        await cache.set(cache_key, user, expire=3600)  # Cache for 1 hour

    return user
