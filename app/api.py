import hashlib
from datetime import datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from openfoodfacts import Flavor
from openfoodfacts.images import generate_image_url
from openfoodfacts.utils import URLBuilder, get_logger
from peewee import DoesNotExist
from playhouse.shortcuts import model_to_dict
from pydantic import BaseModel, Field, model_validator

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
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api_v1_router = APIRouter(prefix="/api/v1")
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


def _get_device_id(request: Request):
    """Get the device ID from the request, or generate one if not provided."""
    device_id = request.query_params.get("device_id")
    if device_id is None:
        device_id = hashlib.sha1(str(request.client.host).encode()).hexdigest()
    return device_id


class TicketStatus(StrEnum):
    open = auto()
    closed = auto()


class IssueType(StrEnum):
    """Type of the flag/ticket."""

    # Issue about any of the product fields (image excluded), or about the
    # product as a whole
    product = auto()
    # Issue about a product image
    image = auto()
    # Issue about search results
    search = auto()


class TicketCreate(BaseModel):
    barcode: str | None = Field(
        None,
        description="Barcode of the product, if the ticket is about a product or a product image. "
        "In case of a search issue, this field is null.",
    )
    type: IssueType = Field(..., description="Type of the issue")
    url: str = Field(..., description="URL of the product or of the flagged image")
    status: TicketStatus = Field(
        default=TicketStatus.open, description="Status of the ticket"
    )
    image_id: str | None = Field(
        None,
        description="ID of the flagged image, if the ticket type is `image`",
        examples=["1", "front_fr"],
    )
    flavor: Flavor = Field(
        ..., description="Flavor (project) associated with the ticket"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation datetime of the ticket"
    )


class Ticket(TicketCreate):
    id: int = Field(..., description="ID of the ticket")


class SourceType(StrEnum):
    mobile = auto()
    web = auto()
    robotoff = auto()


class FlagCreate(BaseModel):
    barcode: str | None = Field(
        None,
        description="Barcode of the product, if the flag is about a product or a product image. "
        "In case of a search issue, this field is null.",
    )
    type: IssueType = Field(..., description="Type of the issue")
    url: str = Field(..., description="URL of the product or of the flagged image")
    user_id: str = Field(..., description="Open Food Facts User ID of the flagger")
    source: SourceType = Field(
        ...,
        description="Source of the flag. It can be a user from the mobile app, "
        "the web or a flag generated automatically by robotoff.",
    )
    confidence: float | None = Field(
        None,
        ge=0,
        le=1,
        description="Confidence score of the model that generated the flag, "
        "this field should only be provided by Robotoff.",
    )
    image_id: str | None = Field(
        None,
        min_length=1,
        description="ID of the flagged image",
        examples=["1", "front_fr"],
    )
    flavor: Flavor = Field(
        ..., description="Flavor (project) associated with the ticket"
    )
    reason: str | None = Field(
        None,
        min_length=1,
        description="Reason for flagging provided by the user. The field is optional.",
    )
    comment: str | None = Field(
        None,
        description="Comment provided by the user during flagging. This is a free text field.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation datetime of the flag"
    )

    @model_validator(mode="after")
    def image_id_is_provided_when_type_is_image(self) -> "FlagCreate":
        """Validate that `image_id` is provided when flag type is `image`."""
        if self.type is IssueType.image and self.image_id is None:
            raise ValueError("`image_id` must be provided when flag type is `image`")
        return self

    @model_validator(mode="after")
    def barcode_should_not_be_provided_for_search_type(self) -> "FlagCreate":
        """Validate that `barcode` is not provided when flag type is
        `search`."""
        if self.type is IssueType.search and self.barcode is not None:
            raise ValueError(
                "`barcode` must not be provided when flag type is `search`"
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def generate_url(cls, data: Any) -> Any:
        """Generate a URL for the flag based on the flag type and flavor."""
        if not isinstance(data, dict):
            # Let Pydantic handle the validation
            return data
        flag_type = data.get("type")
        flavor = data.get("flavor")
        barcode = data.get("barcode")
        image_id = data.get("image_id")

        if not flag_type or flavor not in [f.value for f in Flavor]:
            # Let Pydantic handle the validation
            return data

        flavor_enum = Flavor[flavor]
        environment = settings.off_tld
        # Set-up a default URL in case validation fails

        if flag_type == "product":
            base_url = URLBuilder.world(flavor_enum, environment)
            data["url"] = f"{base_url}/product/{barcode}"
        elif flag_type == "image":
            if image_id:
                data["url"] = generate_image_url(
                    barcode, image_id, flavor_enum, environment
                )
            else:
                # Set-up a dummy URL in case image_id is not provided
                # Pydantic otherwise raises an error
                data["url"] = "http://localhost"

        return data


class Flag(FlagCreate):
    id: int = Field(..., description="ID of the flag")
    ticket_id: int = Field(..., description="ID of the ticket associated with the flag")
    device_id: str = Field(..., description="Device ID of the flagger")


# Create a flag (one to one relationship)
@api_v1_router.post("/flags")
def create_flag(flag: FlagCreate, request: Request):
    with db:
        # Check if the flag already exists
        if (
            FlagModel.get_or_none(
                FlagModel.barcode == flag.barcode,
                FlagModel.url == flag.url,
                FlagModel.type == flag.type,
                FlagModel.flavor == flag.flavor,
                FlagModel.user_id == flag.user_id,
            )
            is not None
        ):
            raise HTTPException(
                status_code=409,
                detail="Flag already exists",
            )

        # Search for existing ticket
        # With the same barcode, url, type and flavor
        ticket = TicketModel.get_or_none(
            TicketModel.barcode == flag.barcode,
            TicketModel.url == flag.url,
            TicketModel.type == flag.type,
            TicketModel.flavor == flag.flavor,
        )
        # If no ticket found, create a new one
        if ticket is None:
            ticket = _create_ticket(
                TicketCreate(
                    barcode=flag.barcode,
                    url=flag.url,
                    type=flag.type,
                    flavor=flag.flavor,
                    image_id=flag.image_id,
                )
            )
        elif ticket.status == TicketStatus.closed:
            # Reopen the ticket if it was closed
            ticket.status = TicketStatus.open
            ticket.save()

        device_id = _get_device_id(request)
        return model_to_dict(
            FlagModel.create(ticket=ticket, device_id=device_id, **flag.model_dump())
        )


# Get all flags (one to many relationship)
@api_v1_router.get("/flags")
def get_flags():
    with db:
        return {"flags": list(FlagModel.select().dicts().iterator())}


# Get flag by ID (one to one relationship)
@api_v1_router.get("/flags/{flag_id}")
def get_flag(flag_id: int):
    with db:
        try:
            return FlagModel.get_by_id(flag_id)
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Not found")


def _create_ticket(ticket: TicketCreate):
    return TicketModel.create(**ticket.model_dump())


# Create a ticket (one to one relationship)
@api_v1_router.post("/tickets")
def create_ticket(ticket: TicketCreate) -> Ticket:
    with db:
        return _create_ticket(ticket)


# Get all tickets (one to many relationship)
@api_v1_router.get("/tickets")
def get_tickets():
    with db:
        return {"tickets": list(TicketModel.select().dicts().iterator())}


# Get ticket by id (one to one relationship)
@api_v1_router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    with db:
        try:
            return model_to_dict(TicketModel.get_by_id(ticket_id))
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Not found")


# Get all flags for a ticket by id (one to many relationship)
@api_v1_router.get("/tickets/{ticket_id}/flags")
def get_flags_by_ticket(ticket_id: int):
    with db:
        return {
            "flags": list(
                FlagModel.select()
                .where(FlagModel.ticket_id == ticket_id)
                .dicts()
                .iterator()
            )
        }


# Update ticket status by id with enum : open, closed (soft delete)
@api_v1_router.put("/tickets/{ticket_id}/status")
def update_ticket_status(ticket_id: int, status: TicketStatus):
    with db:
        try:
            ticket = TicketModel.get_by_id(ticket_id)
            ticket.status = status
            ticket.save()
            return model_to_dict(ticket)
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Not found")


@api_v1_router.get("/status")
def status():
    """Health check endpoint."""
    return {"status": "ok"}


app.include_router(api_v1_router)
