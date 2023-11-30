from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from openfoodfacts import Flavor
from openfoodfacts.utils import get_logger
from peewee import DoesNotExist
from playhouse.shortcuts import model_to_dict
from pydantic import BaseModel, Field

from app.config import settings
from app.models import FlagModel, TicketModel, db
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


class TicketCreate(BaseModel):
    barcode: str = Field(..., description="Barcode of the product")
    type: str = Field(..., description="Type of the issue")
    url: str = Field(..., description="URL of the product")
    status: str = Field(..., description="Status of the ticket")
    image_id: str = Field(..., description="Image ID of the product")
    flavour: Flavor = Field(..., description="Flavour of the product")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Ticket(TicketCreate):
    id: int = Field(..., description="ID of the ticket")


class FlagCreate(BaseModel):
    barcode: str = Field(..., description="Barcode of the product")
    type: str = Field(..., description="Type of the issue")
    url: str = Field(..., description="URL of the product")
    user_id: str = Field(..., description="User ID of the flagger")
    device_id: str = Field(..., description="Device ID of the flagger")
    source: str = Field(..., description="Source of the flag")
    confidence: float = Field(..., description="Confidence of the flag")
    image_id: str = Field(..., description="Image ID of the product")
    flavour: Flavor = Field(..., description="Flavour of the product")
    reason: str = Field(..., description="Reason of the flag")
    comment: str = Field(..., description="Comment of the flag")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Flag(FlagCreate):
    id: int = Field(..., description="ID of the flag")
    ticket_id: int = Field(..., description="ID of the ticket associated with the flag")


# Create a flag (one to one relationship)
@app.post("/flags")
def create_flag(flag: FlagCreate) -> Flag:
    with db:
        try:
            # Search for existing ticket
            # With the same barcode, url, type and flavour
            ticket = TicketModel.get_or_none(
                TicketModel.barcode == flag.barcode,
                TicketModel.url == flag.url,
                TicketModel.type == flag.type,
                TicketModel.flavour == flag.flavour,
            )
            # If no ticket found, create a new one
            if ticket is None:
                newTicket = TicketCreate(
                    barcode=flag.barcode,
                    url=flag.url,
                    type=flag.type,
                    flavour=flag.flavour,
                    status="open",
                    image_id=flag.image_id,
                )
                ticket = _create_ticket(newTicket)
            new_flag = FlagModel.create(**flag.model_dump())
            # Associate the flag with the ticket
            new_flag.ticket_id = ticket.id
            new_flag.save()
            return new_flag
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Get all flags (one to many relationship)
@app.get("/flags")
def get_flags():
    with db:
        try:
            flags = FlagModel.select()
            return [model_to_dict(flag) for flag in flags]
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Get flag by ID (one to one relationship)
@app.get("/flags/{flag_id}")
def get_flag(flag_id: int):
    with db:
        try:
            flag = FlagModel.get_by_id(flag_id)
            return flag
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Flag not found")
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


def _create_ticket(ticket: TicketCreate):
    return TicketModel.create(**ticket.model_dump())


# Create a ticket (one to one relationship)
@app.post("/tickets")
def create_ticket(ticket: TicketCreate) -> Ticket:
    with db:
        return _create_ticket(ticket)


# Get all tickets (one to many relationship)
@app.get("/tickets")
def get_tickets():
    with db:
        try:
            tickets = TicketModel.select()
            return [model_to_dict(ticket) for ticket in tickets]
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Get ticket by id (one to one relationship)
@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    with db:
        try:
            ticket = TicketModel.get_by_id(ticket_id)
            return ticket
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Flag not found")
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Get all flags for a ticket by id (one to many relationship)
@app.get("/tickets/{ticket_id}/flags")
def get_flags_by_ticket(ticket_id: int):
    with db:
        try:
            flags = FlagModel.select().where(FlagModel.ticket_id == ticket_id)
            return [model_to_dict(flag) for flag in flags]
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")


# Update ticket status by id with enum : open, closed (soft delete)
@app.put("/tickets/{ticket_id}/status")
def update_ticket_status(ticket_id: int, status: str):
    if status not in ["open", "closed"]:
        raise HTTPException(
            status_code=400,
            detail="Status must be one of the following : open, closed",
        )
    with db:
        try:
            ticket = TicketModel.get_by_id(ticket_id)
            ticket.status = status
            ticket.save()
            return {"message": f"Ticket with ID {ticket_id} has been updated"}
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Ticket not found")
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"{error}")
