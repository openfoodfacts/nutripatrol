"""Endpoints that act on Open Food Facts on a moderator's behalf.

NutriPatrol itself only records what a moderator decided; carrying it out means
editing Open Food Facts. These endpoints do that server-side, forwarding the
moderator's Open Food Facts session cookie, rather than having the browser talk
to Open Food Facts directly: the flavor and the endpoint shapes stay in one
place, and every caller (web UI, mobile app) gets the same behaviour.

The router is mounted under /api/v1 by `app.api`, which also registers
`off_api_error_handler` on the application.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from openfoodfacts import Flavor
from pydantic import BaseModel, Field, StringConstraints

from app.middleware.auth import ModeratorSession, moderator_session
from app.off_api import (
    OFFAPIError,
    change_barcode,
    delete_images,
    delete_product,
    move_images,
    update_product,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def off_api_error_handler(request: Request, exc: OFFAPIError) -> JSONResponse:
    """Report an Open Food Facts failure the way an HTTPException would."""
    logger.warning("Open Food Facts action failed: %s", exc.message)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


# Barcodes are interpolated into the Open Food Facts URLs we call while
# carrying the moderator's session cookie, so they are never taken as free
# text: Open Food Facts barcodes are numeric, and anything else could point the
# request somewhere else entirely.
Barcode = Annotated[str, StringConstraints(pattern=r"^\d{1,30}$")]


class ImageActionRequest(BaseModel):
    """Common body of the image actions: which images, on which flavor."""

    imgids: list[int] = Field(
        ...,
        min_length=1,
        description="Ids of the *uploaded* images to act on. The id of a "
        "selected image (`front_fr`) is not accepted here: it designates a "
        "crop of an uploaded image, and Open Food Facts ignores it.",
        examples=[[1, 2]],
    )
    flavor: Flavor = Field(..., description="Flavor (project) the product belongs to")


class ImageMoveRequest(ImageActionRequest):
    move_to: Barcode = Field(
        ...,
        description="Barcode of the product to move the images to. Open Food "
        "Facts creates that product if it does not exist yet.",
    )
    copy_data: bool = Field(
        False,
        description="When the destination product is created, also copy the "
        "source product's fields (name, brands, categories...) onto it.",
    )


class ImageActionResponse(BaseModel):
    barcode: str = Field(..., description="Barcode the images were taken from")
    imgids: list[int] = Field(..., description="Ids of the images acted on")
    remaining_imgids: list[int] = Field(
        ...,
        description="Ids of the images the source product is left with, as "
        "reported by Open Food Facts once the action was applied",
    )


def _remaining_imgids(payload: dict) -> list[int]:
    """Read the images left on the product, out of a move response."""
    imgids = []
    for image in payload.get("images") or []:
        if isinstance(image, dict) and isinstance(image.get("imgid"), int):
            imgids.append(image["imgid"])
    return imgids


@router.post("/products/{barcode}/images/delete")
def delete_product_images(
    barcode: Barcode,
    body: ImageActionRequest,
    session: ModeratorSession = Depends(moderator_session),
) -> ImageActionResponse:
    """Delete images of a product on Open Food Facts.

    Open Food Facts moves them to the trash rather than erasing them, so the
    action can be reviewed afterwards.
    """
    payload = delete_images(barcode, body.imgids, body.flavor, session.session_cookie)
    logger.info("%s deleted images %s of %s", session.user_id, body.imgids, barcode)
    return ImageActionResponse(
        barcode=barcode,
        imgids=body.imgids,
        remaining_imgids=_remaining_imgids(payload),
    )


@router.post("/products/{barcode}/images/move")
def move_product_images(
    barcode: Barcode,
    body: ImageMoveRequest,
    session: ModeratorSession = Depends(moderator_session),
) -> ImageActionResponse:
    """Move images of a product to another product on Open Food Facts.

    Used when an image was uploaded on the wrong barcode: it belongs to a real
    product, so it is moved rather than deleted.
    """
    if body.move_to == barcode:
        raise HTTPException(
            status_code=400, detail="Cannot move images to the same product"
        )
    payload = move_images(
        barcode,
        body.imgids,
        body.move_to,
        body.flavor,
        session.session_cookie,
        copy_data=body.copy_data,
    )
    logger.info(
        "%s moved images %s from %s to %s",
        session.user_id,
        body.imgids,
        barcode,
        body.move_to,
    )
    return ImageActionResponse(
        barcode=barcode,
        imgids=body.imgids,
        remaining_imgids=_remaining_imgids(payload),
    )


class ProductDeleteRequest(BaseModel):
    flavor: Flavor = Field(..., description="Flavor (project) the product belongs to")
    comment: str = Field(
        ...,
        min_length=1,
        description="Reason for the deletion. Open Food Facts records it in "
        "the product history, so it should say why the product was removed.",
    )


class ProductActionResponse(BaseModel):
    barcode: str = Field(..., description="Barcode of the product acted on")


@router.post("/products/{barcode}/delete")
def delete_off_product(
    barcode: Barcode,
    body: ProductDeleteRequest,
    session: ModeratorSession = Depends(moderator_session),
) -> ProductActionResponse:
    """Delete a product on Open Food Facts.

    Open Food Facts flags the product as deleted rather than erasing it: a
    moderator can undo it from the product edit form.
    """
    delete_product(barcode, body.comment, body.flavor, session.session_cookie)
    logger.info("%s deleted product %s", session.user_id, barcode)
    return ProductActionResponse(barcode=barcode)


class ChangeBarcodeRequest(BaseModel):
    flavor: Flavor = Field(..., description="Flavor (project) the product belongs to")
    new_barcode: Barcode = Field(
        ..., description="Barcode to give the product instead of the current one"
    )


class ChangeBarcodeResponse(BaseModel):
    barcode: str = Field(..., description="New barcode of the product")
    old_barcode: str = Field(..., description="Barcode the product had before")


@router.post("/products/{barcode}/change_barcode")
def change_product_barcode(
    barcode: Barcode,
    body: ChangeBarcodeRequest,
    session: ModeratorSession = Depends(moderator_session),
) -> ChangeBarcodeResponse:
    """Change the barcode of a product on Open Food Facts.

    Open Food Facts refuses the change if a product already exists under the
    new barcode.
    """
    if body.new_barcode == barcode:
        raise HTTPException(
            status_code=400, detail="The new barcode is the current one"
        )
    change_barcode(barcode, body.new_barcode, body.flavor, session.session_cookie)
    logger.info(
        "%s changed barcode %s to %s", session.user_id, barcode, body.new_barcode
    )
    return ChangeBarcodeResponse(barcode=body.new_barcode, old_barcode=barcode)


class ProductUpdateRequest(BaseModel):
    flavor: Flavor = Field(..., description="Flavor (project) the product belongs to")
    fields: dict[str, Any] = Field(
        ...,
        min_length=1,
        description="Product fields to write, using the names of the Open Food "
        "Facts write API v3. Open Food Facts warns about the fields it does "
        "not recognise instead of failing, so a typo silently does nothing.",
        examples=[{"categories": "en:biscuits", "product_name_fr": "Petit beurre"}],
    )
    comment: str | None = Field(
        None, description="Reason for the edit, recorded in the product history"
    )
    lc: str = Field(
        "en",
        min_length=2,
        max_length=5,
        description="Language the values of the localized fields are written in",
    )


class ProductUpdateResponse(BaseModel):
    barcode: str = Field(..., description="Barcode of the product acted on")
    updated_fields: dict[str, Any] = Field(
        ..., description="The fields as Open Food Facts saved them"
    )


@router.patch("/products/{barcode}")
def update_off_product(
    barcode: Barcode,
    body: ProductUpdateRequest,
    session: ModeratorSession = Depends(moderator_session),
) -> ProductUpdateResponse:
    """Edit product fields on Open Food Facts."""
    payload = update_product(
        barcode,
        body.fields,
        body.flavor,
        session.session_cookie,
        comment=body.comment,
        lc=body.lc,
    )
    logger.info("%s updated %s on %s", session.user_id, sorted(body.fields), barcode)
    return ProductUpdateResponse(
        barcode=barcode, updated_fields=payload.get("product") or {}
    )


class ObsoleteRequest(BaseModel):
    flavor: Flavor = Field(..., description="Flavor (project) the product belongs to")
    obsolete: bool = Field(
        ...,
        description="Whether the product is no longer sold. Obsolete products "
        "are kept, but left out of search results.",
    )
    comment: str | None = Field(
        None, description="Reason for the edit, recorded in the product history"
    )


@router.post("/products/{barcode}/obsolete")
def set_product_obsolete(
    barcode: Barcode,
    body: ObsoleteRequest,
    session: ModeratorSession = Depends(moderator_session),
) -> ProductUpdateResponse:
    """Mark a product as no longer sold on Open Food Facts, or un-mark it."""
    payload = update_product(
        barcode,
        # Open Food Facts stores this checkbox field as "on" or the empty
        # string, not as a boolean.
        {"obsolete": "on" if body.obsolete else ""},
        body.flavor,
        session.session_cookie,
        comment=body.comment,
    )
    logger.info("%s set obsolete=%s on %s", session.user_id, body.obsolete, barcode)
    return ProductUpdateResponse(
        barcode=barcode, updated_fields=payload.get("product") or {}
    )
