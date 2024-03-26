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

description = """
The nutripatrol API is used to report and manage issues with products and images on [Open Food Facts](https://world.openfoodfacts.org/), Open Prices, Open Pet Food Facts, Open Beauty Facts.
We call a report a "**flag**" and a report will be associated with a "**ticket**" if it does not exist for this product or image. Otherwise it will be associated with the existing ticket.

## Flags

A flag containes the following main fields:
- `barcode`: Barcode of the product, if the flag is about a product or a product image. In case of a search issue, this field is null.

- `type`: Type of the issue. It can be `product`, `image` or `search`.
- `url`: URL of the product or of the flagged image.
- `user_id`: Open Food Facts User ID of the flagger.
- `source`: Source of the flag. It can be a user from the mobile app, the web or a flag generated automatically by robotoff.
- `confidence`: Confidence score of the model that generated the flag, this field should only be provided by Robotoff.
- `image_id`: ID of the flagged image, if the ticket type is `image`.
- `flavor`: Flavor (project) associated with the ticket.
- `reason`: Reason for flagging provided by the user. For images, it can be `image_to_delete_wrong_product`,

`image_to_delete_spam` or `image_to_delete_face`. For products it can be `product_to_delete`. The field is optional.
- `comment`: Comment provided by the user during flagging. This is a free text field.

## Tickets
Automatically created when a flag is created and no ticket exists for the product or image.

A ticket containes the following main fields:
- `barcode`: Barcode of the product, if the ticket is about a product or a product image. In case of a search issue, this field is null.

- `type`: Type of the issue. It can be `product`, `image` or `search`.
- `url`: URL of the product or of the flagged image.
- `status`: Status of the ticket. It can be `open` or `closed`.
- `image_id`: ID of the flagged image, if the ticket type is `image`.
- `flavor`: Flavor (project) associated with the ticket.


"""

app = FastAPI(
    title="nutripatrol",
    description=description,
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


@api_v1_router.post("/flags")
def create_flag(flag: FlagCreate, request: Request):
    """Create a flag for a product.

    This function is used to create a flag for a product or an image.
    A flag is a request for a product or an image to be reviewed.
    A flag is associated with a ticket.
    A ticket is created if it does not exist for this product or image.
    A ticket can be associated with multiple flags.
    """
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


@api_v1_router.get("/flags")
def get_flags():
    """Get all flags.

    This function is used to get all flags.
    """
    with db:
        return {"flags": list(FlagModel.select().dicts().iterator())}


@api_v1_router.get("/flags/{flag_id}")
def get_flag(flag_id: int):
    """Get a flag by ID.

    This function is used to get a flag by its ID.
    """
    with db:
        try:
            return FlagModel.get_by_id(flag_id)
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Not found")


def _create_ticket(ticket: TicketCreate):
    """Create a ticket."""
    return TicketModel.create(**ticket.model_dump())


@api_v1_router.post("/tickets")
def create_ticket(ticket: TicketCreate) -> Ticket:
    """Create a ticket.

    This function is used to create a ticket for a product or an image.
    A ticket is a request for a product or an image to be reviewed.
    """
    with db:
        return _create_ticket(ticket)


def _get_ticket(status: TicketStatus | None, type_: IssueType | None):
    """Get tickets with optional filters."""
    query = TicketModel.select()

    if status is not None:
        query = query.where(TicketModel.status == status)

    if type_ is not None:
        query = query.where(TicketModel.type == type_)

    with db:
        return {"tickets": list(query.dicts())}


@api_v1_router.get("/tickets")
def get_tickets(status: TicketStatus | None = None, type_: IssueType | None = None):
    """Get all tickets.

    This function is used to get all tickets with status open
    """
    with db:
        return _get_ticket(status, type_)


@api_v1_router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    """Get a ticket by ID.

    This function is used to get a ticket by its ID.
    """
    with db:
        try:
            return model_to_dict(TicketModel.get_by_id(ticket_id))
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Not found")


@api_v1_router.get("/tickets/{ticket_id}/flags")
def get_flags_by_ticket(ticket_id: int):
    """Get all flags for a ticket by ID.

    This function is used to get all flags for a ticket by its ID.
    """
    with db:
        return {
            "flags": list(
                FlagModel.select()
                .where(FlagModel.ticket_id == ticket_id)
                .dicts()
                .iterator()
            )
        }


@api_v1_router.put("/tickets/{ticket_id}/status")
def update_ticket_status(ticket_id: int, status: TicketStatus):
    """Update the status of a ticket by ID.

    This function is used to update the status of a ticket by its ID.
    """
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
