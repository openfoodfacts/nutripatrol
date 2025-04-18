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
    print("Hello from auth.py")

    if not session_cookie:
        raise HTTPException(status_code=401, detail="Missing session token")

    if user_status not in UserStatus:
        raise HTTPException(status_code=400, detail="Invalid user status")

    if user_status == UserStatus.isModerator:
        if not await auth_request(session_cookie, UserStatus.isModerator):
            raise HTTPException(status_code=403, detail="User is not a moderator")

    elif user_status == UserStatus.isLoggedIn:
        if not await auth_request(session_cookie, UserStatus.isLoggedIn):
            raise HTTPException(status_code=403, detail="User is not logged in")


async def auth_request(sessionCookie, user_status: UserStatus):
    async with httpx.AsyncClient() as client:
        response = await client.get(PO_AUTH_ROUTE, cookies={"session": sessionCookie}, params={"body": "1"})

        if response.status_code != 200:
            return False

        user_data = response.json().get("user", {})
        if user_status == UserStatus.isModerator and user_data.get("moderator") == 1:
            return True
        elif user_status == UserStatus.isLoggedIn and user_data.get("moderator") is not None:
            return True
        else:
            return False
