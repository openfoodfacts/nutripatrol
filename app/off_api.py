"""Client for the Open Food Facts API.

The read part captures what Open Food Facts only exposes for the current
revision of a product: the uploader and upload date of an image, which
disappear from the product JSON as soon as the image is deleted and are only
recoverable by walking the product revisions one by one, and the revision
number a flag was raised on, which pins the product version the flagger saw.

The write part performs the moderation actions a moderator triggers from
NutriPatrol -- deleting and moving images, deleting a product, editing its
fields. They all run *on behalf of* the moderator: their Open Food Facts
session cookie is forwarded, so Open Food Facts applies its own permission
checks and attributes the edit to them rather than to NutriPatrol.
"""

import logging
from datetime import datetime, timezone
from typing import Any, NamedTuple

import requests
from openfoodfacts import Flavor
from openfoodfacts.utils import URLBuilder

from app.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = "NutriPatrol (https://github.com/openfoodfacts/nutripatrol)"

# The fetch happens while a moderator is waiting for their action to be saved,
# so keep the timeouts short: not capturing the uploader must never prevent a
# ticket from being closed.
TIMEOUT = (2, 5)

# Writes are the moderator's actual action rather than a best-effort extra, and
# Open Food Facts saves a full product revision before answering, so give them
# room -- but still bounded, a moderator is waiting in front of the UI.
WRITE_TIMEOUT = (5, 30)


class OFFAPIError(Exception):
    """An Open Food Facts write request failed.

    `status_code` is the HTTP status NutriPatrol answers with. It defaults to
    502 -- Open Food Facts is upstream, and its refusals are not the API
    caller's fault -- and is set to the status Open Food Facts returned when
    that status is meaningful to the caller (403 when the moderator lacks the
    right, 404 when the product does not exist).
    """

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _get_uploaded_images(images: dict) -> dict:
    """Return the {imgid: image} mapping of a product `images` object.

    Handles both product schemas: images are under an `uploaded` key since
    schema 1002, and were at the root of the `images` object before.
    """
    uploaded = images.get("uploaded")
    if isinstance(uploaded, dict):
        return uploaded
    return {key: value for key, value in images.items() if key.isdigit()}


def _resolve_imgid(images: dict, image_id: str) -> str | None:
    """Resolve a ticket `image_id` to the id of the image that was uploaded.

    `image_id` is either the id of an uploaded image ("1"), or the id of a
    selected image ("front_fr"), which is cropped from an uploaded one.
    """
    if image_id.isdigit():
        return image_id

    selected = images.get("selected")
    if isinstance(selected, dict):
        # schema >= 1002: images.selected.{image_type}.{image_lc}
        image_ref = next(
            (
                ref
                for image_type, images_by_lc in selected.items()
                for image_lc, ref in images_by_lc.items()
                if f"{image_type}_{image_lc}" == image_id
            ),
            None,
        )
    else:
        # older schema: images.{image_type}_{image_lc}
        image_ref = images.get(image_id)

    if not isinstance(image_ref, dict) or image_ref.get("imgid") is None:
        return None
    return str(image_ref["imgid"])


def extract_image_upload_metadata(
    images: dict | None, image_id: str
) -> tuple[str | None, datetime | None]:
    """Return the (uploader, upload date) of `image_id` in a product `images`
    object, or (None, None) if the image is not there anymore."""
    if not isinstance(images, dict):
        return None, None

    imgid = _resolve_imgid(images, image_id)
    if imgid is None:
        return None, None

    image = _get_uploaded_images(images).get(imgid)
    if not isinstance(image, dict):
        return None, None

    uploaded_at = None
    uploaded_t = image.get("uploaded_t")
    if uploaded_t is not None:
        try:
            # `uploaded_t` is a UNIX timestamp, stored as an integer, or as a
            # string for the oldest products. Like every other datetime of the
            # database, it is stored as a naive UTC datetime.
            uploaded_at = datetime.fromtimestamp(
                int(uploaded_t), tz=timezone.utc
            ).replace(tzinfo=None)
        except (TypeError, ValueError):
            logger.warning("invalid uploaded_t for image %s: %r", imgid, uploaded_t)

    return image.get("uploader") or None, uploaded_at


def _resolve_flavor(flavor: Flavor | str) -> Flavor | None:
    """Return the Flavor a ticket or a flag refers to, or None if unknown.

    Accepts a Flavor, its name ("off_pro") or its value ("off-pro"): a flag
    carries the enum, while a ticket read back from the database carries the
    value it was stored as.
    """
    if isinstance(flavor, Flavor):
        return flavor
    try:
        return Flavor[flavor]
    except KeyError:
        pass
    try:
        return Flavor(flavor)
    except ValueError:
        return None


def _fetch_product(barcode: str, flavor: Flavor | str, fields: str) -> dict | None:
    """Fetch `fields` of a product from Open Food Facts.

    Returns None if the product could not be read -- unknown flavor, unknown
    product, or Open Food Facts out of reach. Every caller reads this while a
    user is waiting for their own request to be saved, so a failure here is
    logged and reported as "nothing to capture", never raised.
    """
    flavor_enum = _resolve_flavor(flavor)
    if flavor_enum is None:
        logger.warning("unknown flavor %r for barcode %s", flavor, barcode)
        return None

    base_url = URLBuilder.world(flavor_enum, settings.off_tld)
    url = f"{base_url}/api/v2/product/{barcode}.json"
    try:
        response = requests.get(
            url,
            params={"fields": fields},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        product = response.json().get("product")
    except (requests.RequestException, ValueError):
        logger.warning("could not fetch %s from %s", fields, url, exc_info=True)
        return None

    return product if isinstance(product, dict) else None


def fetch_image_upload_metadata(
    barcode: str, image_id: str, flavor: Flavor | str
) -> tuple[str | None, datetime | None]:
    """Fetch the (uploader, upload date) of an image from Open Food Facts.

    Returns (None, None) if the image was already deleted, or if Open Food
    Facts could not be reached: capturing this metadata is best effort.
    """
    # v2 returns the images object in the pre-1002 schema, which
    # extract_image_upload_metadata() also handles.
    product = _fetch_product(barcode, flavor, "images")
    if product is None:
        return None, None

    return extract_image_upload_metadata(product.get("images"), image_id)


def extract_revision(product: dict, barcode: str = "") -> int | None:
    """Return the revision number of a product, or None if it has none."""
    rev = product.get("rev")
    try:
        # `rev` is an integer, but the oldest products store it as a string.
        return int(rev)
    except (TypeError, ValueError):
        logger.warning("invalid rev for barcode %s: %r", barcode, rev)
        return None


class ProductSnapshot(NamedTuple):
    """What a flag records about the product it was raised on.

    Open Food Facts increments `rev` on every product change, so the revision
    pins the exact product version the flagger saw, which a moderator
    reviewing the flag later cannot otherwise recover. The image uploader is
    there for the same reason: both describe the product at flag time, and
    neither can be read back once the product moves on.

    Every field defaults to None: the capture is best effort, and a snapshot
    that could not be read must never prevent a flag from being saved.
    """

    revision: int | None = None
    image_uploader: str | None = None
    image_uploaded_at: datetime | None = None


def fetch_product_snapshot(
    barcode: str, flavor: Flavor | str, image_id: str | None = None
) -> ProductSnapshot:
    """Read everything a new flag captures about its product, in one request.

    Pass `image_id` when the flag is about an image *and* its uploader is not
    known yet; the image metadata is then read from the same product JSON as
    the revision, rather than by a second round trip.
    """
    # v2 returns the images object in the pre-1002 schema, which
    # extract_image_upload_metadata() also handles.
    fields = "rev" if image_id is None else "images,rev"
    product = _fetch_product(barcode, flavor, fields)
    if product is None:
        return ProductSnapshot()

    revision = extract_revision(product, barcode)
    if image_id is None:
        return ProductSnapshot(revision=revision)

    uploader, uploaded_at = extract_image_upload_metadata(
        product.get("images"), image_id
    )
    return ProductSnapshot(revision, uploader, uploaded_at)


def _base_url(flavor: Flavor | str) -> str:
    """Return the world base URL of a flavor.

    For instance https://world.openfoodfacts.org for the `off` flavor.
    """
    flavor_enum = _resolve_flavor(flavor)
    if flavor_enum is None:
        raise OFFAPIError(f"unknown flavor {flavor!r}", status_code=400)
    return URLBuilder.world(flavor_enum, settings.off_tld)


def _request(
    method: str,
    url: str,
    session_cookie: str,
    *,
    data: dict | None = None,
    json: dict | None = None,
) -> requests.Response:
    """Send a request as the moderator owning `session_cookie`.

    Redirects are deliberately not followed. Open Food Facts answers all the
    endpoints we call directly, so a redirect means something else happened --
    the session was not accepted and we are being sent to the login page, or
    the product lives on another flavor's server. Following it would forward
    the moderator's session cookie to whatever the redirect points at.
    """
    try:
        return requests.request(
            method,
            url,
            data=data,
            json=json,
            cookies={"session": session_cookie},
            headers={"User-Agent": USER_AGENT},
            timeout=WRITE_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        logger.warning("%s %s failed", method, url, exc_info=True)
        raise OFFAPIError(f"could not reach Open Food Facts: {exc}") from exc


def _check_not_redirected(response: requests.Response) -> None:
    """Raise if Open Food Facts answered with a redirect.

    Checked on the status alone rather than on `response.is_redirect`, which is
    also false for a redirect that carries no Location header.
    """
    if 300 <= response.status_code < 400:
        # See _request(): most often an unauthenticated session being sent to
        # the login page.
        raise OFFAPIError(
            "Open Food Facts redirected the request, which usually means the "
            "moderator session was not accepted, or that the product is not on "
            "this flavor",
            status_code=502,
        )


def _check_response(response: requests.Response) -> None:
    """Raise on the HTTP-level failures that are common to every write."""
    _check_not_redirected(response)
    if response.status_code == 403:
        raise OFFAPIError(
            "Open Food Facts refused the action for this user", status_code=403
        )
    if response.status_code >= 400:
        raise OFFAPIError(
            f"Open Food Facts returned HTTP {response.status_code}",
            status_code=502,
        )


def _json_body(response: requests.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise OFFAPIError(
            "Open Food Facts returned a non-JSON response", status_code=502
        ) from exc
    if not isinstance(payload, dict):
        raise OFFAPIError(
            "Open Food Facts returned an unexpected response", status_code=502
        )
    return payload


def move_images(
    barcode: str,
    imgids: list[int],
    move_to: str,
    flavor: Flavor | str,
    session_cookie: str,
    copy_data: bool = False,
) -> dict:
    """Move uploaded images of a product to another product, or to the trash.

    `imgids` are the ids of *uploaded* images (1, 2...). Open Food Facts
    silently skips anything else here, so the id of a selected image
    ("front_fr") has to be resolved to the uploaded image it was cropped from
    first -- see `_resolve_imgid()`.

    `move_to` is the destination barcode, or "trash" to delete the images. A
    destination barcode that has no product yet is created by Open Food Facts;
    `copy_data` then also copies the source product's fields onto it.

    Returns the parsed Open Food Facts response, whose `images` key lists the
    images the source product is left with.
    """
    url = f"{_base_url(flavor)}/cgi/product_image_move.pl"
    response = _request(
        "POST",
        url,
        session_cookie,
        data={
            "code": barcode,
            "imgids": ",".join(str(imgid) for imgid in imgids),
            "move_to_override": move_to,
            "copy_data_override": "true" if copy_data else "false",
        },
    )
    _check_response(response)

    # product_image_move.pl answers 200 with {"status": "status not ok"} on
    # every business error (unknown product, invalid barcode, image already
    # moved), so the HTTP status alone says nothing.
    payload = _json_body(response)
    if payload.get("status") != "ok":
        raise OFFAPIError(
            payload.get("error") or "Open Food Facts could not move the images"
        )
    return payload


def delete_images(
    barcode: str,
    imgids: list[int],
    flavor: Flavor | str,
    session_cookie: str,
) -> dict:
    """Delete uploaded images of a product, by moving them to the trash."""
    return move_images(barcode, imgids, "trash", flavor, session_cookie)


def delete_product(
    barcode: str,
    comment: str,
    flavor: Flavor | str,
    session_cookie: str,
) -> None:
    """Delete a product page.

    Open Food Facts does not erase the product: it flags the current revision
    as deleted, which a moderator can undo from the product edit form.
    """
    url = f"{_base_url(flavor)}/cgi/product.pl"
    response = _request(
        "POST",
        url,
        session_cookie,
        data={
            "type": "delete",
            "action": "process",
            "code": barcode,
            "comment": comment,
        },
    )
    # product.pl is the HTML edit form, not an API: it answers 403 when the
    # user is not a moderator, and 200 with the "product saved" page
    # otherwise. There is no body to inspect.
    _check_response(response)


def change_barcode(
    barcode: str,
    new_barcode: str,
    flavor: Flavor | str,
    session_cookie: str,
) -> dict:
    """Change the barcode of a product.

    Open Food Facts keeps the old barcode in the product's `old_code`, and
    refuses the change if a product already exists under `new_barcode`.
    """
    url = f"{_base_url(flavor)}/cgi/product_jqm2.pl"
    response = _request(
        "POST",
        url,
        session_cookie,
        data={"code": barcode, "new_code": new_barcode},
    )
    _check_response(response)

    # Like product_image_move.pl, the write API v2 reports business errors --
    # including "no permission" and "the new barcode already exists" -- as
    # {"status": 0} inside a 200 response.
    payload = _json_body(response)
    if payload.get("status") != 1:
        raise OFFAPIError(
            payload.get("status_verbose")
            or "Open Food Facts refused the barcode change"
        )
    return payload


def _format_v3_errors(payload: dict) -> str:
    """Turn the `errors` of a write API v3 response into one readable line."""
    messages = []
    for error in payload.get("errors") or []:
        if not isinstance(error, dict):
            continue
        message = error.get("message") or {}
        field = error.get("field") or {}
        text = message.get("lc_name") or message.get("id")
        if not text:
            continue
        field_id = field.get("id")
        messages.append(f"{text} ({field_id})" if field_id else text)
    return "; ".join(messages) or "unknown error"


def update_product(
    barcode: str,
    fields: dict[str, Any],
    flavor: Flavor | str,
    session_cookie: str,
    comment: str | None = None,
    lc: str = "en",
) -> dict:
    """Update product fields through the write API v3.

    `fields` is passed as-is as the `product` object, so it takes the field
    names of the v3 schema -- `obsolete` ("on" to mark a product obsolete, ""
    to un-mark it), `product_name_fr`, `categories`... Open Food Facts warns
    about the fields it does not recognise instead of failing, so those are
    logged rather than raised.

    Returns the parsed response, whose `product` key holds the updated fields.
    """
    url = f"{_base_url(flavor)}/api/v3/product/{barcode}"
    body: dict[str, Any] = {"lc": lc, "fields": "updated", "product": fields}
    if comment:
        body["comment"] = comment
    response = _request("PATCH", url, session_cookie, json=body)

    _check_not_redirected(response)
    # Unlike the CGI endpoints, API v3 does set a meaningful HTTP status, and
    # puts the reason in the body -- so read the body before giving up on the
    # status code.
    payload = _json_body(response)
    if payload.get("status") != "success":
        raise OFFAPIError(
            _format_v3_errors(payload),
            status_code=403 if response.status_code == 403 else 502,
        )

    for warning in payload.get("warnings") or []:
        logger.info("Open Food Facts warning on %s: %r", barcode, warning)
    return payload
