from fastapi import Request, HTTPException
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

PO_AUTH_ROUTE = os.getenv("PO_AUTH_ROUTE")
if PO_AUTH_ROUTE is None:
    raise RuntimeError("PO_AUTH_ROUTE environment variable is not set.")


async def auth_dependency(request: Request):
    token = request.headers.get("Authorization")

    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token_value = token.split("Bearer ")[1]

    async with httpx.AsyncClient() as client:
        response = await client.get(PO_AUTH_ROUTE, params={"token": token_value})

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
