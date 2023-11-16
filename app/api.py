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
from app.models import Flags, db
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


class FlagResponse(BaseModel):
    id: int
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
    created_at: datetime


class FlagsUpdate(BaseModel):
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


# Update a flag
@app.patch("/flags/{flag_id}")
async def update_flag(flag_id: int, updated_data: FlagsUpdate):
    with db:
        try:
            flag = Flags.get_by_id(flag_id)
            Flags.update(**updated_data.dict())
            flag.save()
            return {"message": f"Flag with id {flag_id} updated successfully"}
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
