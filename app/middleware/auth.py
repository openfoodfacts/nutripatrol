from fastapi import Request, HTTPException
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

PO_AUTH_ROUTE = os.getenv("PO_AUTH_ROUTE")
if PO_AUTH_ROUTE is None:
    raise RuntimeError("PO_AUTH_ROUTE environment variable is not set.")


async def auth_dependency(request: Request):
    session_cookie = request.cookies.get("session")
    print(f"Request : {request.cookies}")

    if not session_cookie:
        raise HTTPException(status_code=401, detail="Missing session token")

    async with httpx.AsyncClient() as client:
        response = await client.get(PO_AUTH_ROUTE, cookies={"session": session_cookie}, params={"body": "1"})

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")

        moderator = response.json().get("user", {}).get("moderator")

        if moderator == 0:
            raise HTTPException(status_code=403, detail="User is not authorized to access this resource")
