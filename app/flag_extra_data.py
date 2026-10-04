"""What each reason lets a reporter tell us, beyond a paragraph of prose.

Every field is optional. A reporter who only wants to say "this is wrong" is
still filing a valid flag, and the form must not get slower to fill for the
ones who stop there.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.flag_reasons import ReasonType

# Barcodes here end up interpolated into the Open Food Facts URLs that
# `app.moderation_api` calls, so they are constrained the same way they are
# there: digits only, nothing that could point a request elsewhere.
Barcode = Annotated[str, StringConstraints(pattern=r"^\d{4,30}$")]
# Only *uploaded* image ids. The id of a selected image ("front_fr")
# designates a crop rather than a file, and Open Food Facts ignores it when
# asked to delete or move one -- see moderation_api.ImageActionRequest.
ImgId = Annotated[int, Field(gt=0)]
OffUserId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._-]{2,40}$")]
Url = Annotated[
    str, StringConstraints(pattern=r"^https?://", min_length=1, max_length=500)
]


class ExtraData(BaseModel):
    """What every reason's payload has in common, which is its strictness.

    No field is shared. Which image a report is about is the flag's own
    `image_id`, and an image id inside `extra_data` means a *second* image
    the reason needs named -- the one `duplicate` says this is a copy of.

    Unknown keys are refused rather than dropped: a client sending
    `correct_barcodes` deserves to hear about it, instead of having the one
    fact it collected silently disappear.
    """

    model_config = ConfigDict(extra="forbid")


class WrongBarcodeExtra(ExtraData):
    correct_barcode: Barcode | None = Field(
        None, description="The barcode printed on the pack."
    )
    suggested_action: (
        Literal["change_barcode", "delete_product", "move_images"] | None
    ) = Field(
        None,
        description="What the reporter thinks should happen. Roughly half of "
        "these reports ask for a deletion because they have already recreated "
        "the product under the right barcode.",
    )


class CopyrightExtra(ExtraData):
    # 193 reports in prose, and none under this reason, because the reason was
    # added after they were filed. Naming the uploader is the point: the same
    # handful of accounts appear again and again, so the useful action is to
    # look at the account, not only at the one picture.
    offending_uploader: OffUserId | None = Field(
        None, description="Open Food Facts account that uploaded the image."
    )
    original_source_url: Url | None = Field(
        None, description="Where the image was taken from."
    )
    rights_holder: Literal["me", "company_i_represent", "third_party"] | None = None


class WrongProductExtra(ExtraData):
    correct_barcode: Barcode | None = Field(
        None, description="The product the image actually shows."
    )


class DuplicateImageExtra(ExtraData):
    duplicate_of_image_id: ImgId | None = Field(
        None, description="The image this one duplicates."
    )


class PersonalInfoExtra(ExtraData):
    # Deliberately a closed list rather than free text: the point is to say
    # *where* the personal information is, not to copy it into a second field
    # that is stored just as long.
    kind: Literal["face", "name", "address", "document", "screen"] | None = None
    is_me: bool | None = Field(
        None,
        description="Whether the reporter is the person shown. These carry a "
        "legal clock and should be handled first.",
    )


#: The schema each reason accepts. A reason absent from the table accepts no
#: `extra_data` at all, which is most of them: a reason earns an entry once
#: there is an action a moderator could take with the answer.
#:
#: Pydantic cannot discriminate a union on a field that lives outside it, so
#: the reason is looked up here rather than being repeated inside the payload
#: -- which also keeps the error message about the key the caller got wrong,
#: instead of about a union with fifteen branches.
EXTRA_DATA_MODELS: dict[ReasonType, type[ExtraData]] = {
    # product
    ReasonType.wrong_barcode: WrongBarcodeExtra,
    # image
    ReasonType.copyright: CopyrightExtra,
    ReasonType.wrong_product: WrongProductExtra,
    ReasonType.duplicate: DuplicateImageExtra,
    ReasonType.includes_personal_infos: PersonalInfoExtra,
}
