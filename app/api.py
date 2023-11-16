from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from openfoodfacts.utils import get_logger
from peewee import DoesNotExist
from playhouse.shortcuts import model_to_dict
from pydantic import BaseModel, Field

from app.config import settings
from app.models import Flags, Tickets, db
from app.utils import init_sentry

logger = get_logger(level=settings.log_level.to_int())


app = FastAPI(
    title="nutripatrol",
    contact={
        "name": "The Open Food Facts team",
        "url": "https://world.openfoodfacts.org",
        "email": "contact@openfoodfacts.org",
    },
    license_info={
        "name": " AGPL-3.0",
        "url": "https://www.gnu.org/licenses/agpl-3.0.en.html",
    },
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
init_sentry(settings.sentry_dns)


@app.get("/", response_class=HTMLResponse)
def main_page(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return """User-agent: *\nDisallow: /"""


# CRUD Flags


class FlagCreate(BaseModel):
    barcode: str
    type: str
    url: str
    user_id: str
    device_id: str
    source: str
    confidence: float
    image_id: str
    flavour: str
    reason: str
    comment: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Create a flag
@app.post("/flags")
def create_flag(flag: FlagCreate):
    with db:
        try:
            new_flag = Flags.create(**flag.dict())
            return model_to_dict(new_flag)
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Get all flags
@app.get("/flags")
def get_flags():
    with db:
        try:
            flags = Flags.select()
            return [model_to_dict(flag) for flag in flags]
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Get flag by ID
@app.get("/flags/{flag_id}")
def get_flag(flag_id: int):
    with db:
        try:
            flag = Flags.get_by_id(flag_id)
            return model_to_dict(flag)
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Flag not found")
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Delete a flag
@app.delete("/flags/{flag_id}")
async def delete_flag(flag_id: int):
    with db:
        try:
            flag = Flags.get_by_id(flag_id)
            flag.delete_instance()
            return {"message": f"Flag with ID {flag_id} has been deleted"}
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Flag not found")
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# CRUD Tickets


class TicketCreate(BaseModel):
    barcode: str
    type: str
    url: str
    status: str
    image_id: str
    flavour: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Create a ticket
@app.post("/tickets")
def create_ticket(ticket: TicketCreate):
    with db:
        try:
            new_ticket = Tickets.create(**ticket.dict())
            return model_to_dict(new_ticket)
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Get all tickets
@app.get("/tickets")
def get_tickets():
    with db:
        try:
            tickets = Tickets.select()
            return [model_to_dict(ticket) for ticket in tickets]
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Get ticket by id
@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    with db:
        try:
            ticket = Tickets.get_by_id(ticket_id)
            return model_to_dict(ticket)
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Flag not found")
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Delete ticket by id
@app.delete("/tickets/{ticket_id}")
def delete_ticket(ticket_id: int):
    with db:
        try:
            flag = Tickets.get_by_id(ticket_id)
            flag.delete_instance()
            return {"message": f"Flag with ID {ticket_id} has been deleted"}
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Flag not found")
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")
