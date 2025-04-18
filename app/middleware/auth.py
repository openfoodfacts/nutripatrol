from fastapi import Depends, Request, HTTPException
import httpx
import os
from enum import StrEnum, auto


class UserStatus(StrEnum):
    isModerator = auto()
    isLoggedIn = auto()


PO_AUTH_ROUTE = os.getenv("PO_AUTH_ROUTE")
if PO_AUTH_ROUTE is None:
    raise RuntimeError("PO_AUTH_ROUTE environment variable is not set.")


def get_auth_dependency(user_status: UserStatus):
    async def wrapper(request: Request):
        return await auth_dependency(request, user_status)
    return Depends(wrapper)


async def auth_dependency(request: Request, user_status: UserStatus):
    session_cookie = request.cookies.get("session")

    if not session_cookie:
        raise HTTPException(status_code=401, detail="Missing session token")

    if user_status not in UserStatus:
        raise HTTPException(status_code=400, detail=f"Invalid user status : {user_status}")

    user_data = await get_user_data(session_cookie)

    if user_status == UserStatus.isModerator:
        if user_data.get("moderator") != 1:
            raise HTTPException(status_code=403, detail="User is not a moderator")

    elif user_status == UserStatus.isLoggedIn:
        if user_data.get("moderator") is None:
            raise HTTPException(status_code=403, detail="User is not logged in")


async def get_user_data(session_cookie: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            PO_AUTH_ROUTE,
            cookies={"session": session_cookie},
            params={"body": "1"}
        )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session token")

    return response.json().get("user", {})
