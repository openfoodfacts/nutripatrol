"""The flag taxonomy: what a report can be about, and why.

This is the authority for both halves of the system. The API validates
incoming flags against it and exposes it through `GET /reasons`; the frontend
mirrors it in `src/const/flagsConst.ts`. Before this module there were three
disagreeing lists -- the filter enum here, the form's options, and the
moderator's filter choices -- and filtering by a reason the form actually
submits answered 422.

It lives apart from `app.api` so that `app.flag_extra_data`, which hangs a
schema off each reason, can import it without a cycle.
"""

from enum import StrEnum, auto


class IssueType(StrEnum):
    """Type of the flag/ticket."""

    # Issue about any of the product fields (image excluded), or about the
    # product as a whole
    product = auto()
    # Issue about a product image
    image = auto()
    # Issue about search results
    search = auto()


class ReasonType(StrEnum):
    """Why a product, an image or a search result was reported.

    The counts are the flags that carried each value when the taxonomy was
    drawn up, over the 17 405 flags of closed tickets. They are there to say
    which reasons matter, and which ones were invented to catch reports that
    had nowhere to go: those used to pile up under `other`, which is why it is
    the second most frequent value in the table.
    """

    # --- shared ---------------------------------------------------------
    other = auto()  # 4 771, and Robotoff's fallback

    # --- product --------------------------------------------------------
    wrong_data = auto()  # 337
    missing_data = auto()  # 42
    wrong_barcode = auto()  # 101
    # Reports that the page is not a product of this project at all: a
    # cosmetic on Open Food Facts, a pet food, a roll of toilet paper.
    not_a_product = auto()
    duplicate_product = auto()
    discontinued = auto()
    spam_or_vandalism = auto()
    # Trademark and copyright takedowns aimed at the product page itself,
    # which arrive as letters from a rights holder rather than as edits.
    legal_takedown = auto()
    # Out of scope on purpose: complaints aimed at the manufacturer (mold,
    # weight, a refund). Nothing can be fixed on Open Food Facts, but the
    # reports arrive anyway, and a reason of their own is what lets them be
    # closed in one gesture instead of read one by one.
    product_complaint = auto()

    # --- image ----------------------------------------------------------
    inappropriate = auto()  # 333, form and Robotoff
    # Zero flags carried this before, and 193 described it in prose under
    # `other` or `inappropriate`.
    copyright = auto()
    # The misspelling is deliberate: it is the value already stored on rows
    # and sent by clients we do not control.
    includes_personal_infos = auto()  # 3
    # An image uploaded on the wrong barcode -- it belongs to another
    # product, rather than being wrong about this one.
    wrong_product = auto()
    duplicate = auto()  # 5
    outdated = auto()  # 11

    # --- product or image -----------------------------------------------
    # "I created this by mistake", "please remove the photo I uploaded".
    delete_request = auto()

    # --- search ---------------------------------------------------------
    no_results = auto()
    wrong_results = auto()

    # --- bot-only -------------------------------------------------------
    # Robotoff's own vocabulary. Valid on the API and filterable in the
    # admin, but never offered by the flag form.
    human = auto()  # 10 844
    beauty = auto()  # 953, stored but no longer emitted


#: Reasons only the automated sources use. A person picking one of these
#: would mean a client bug, not a report.
BOT_ONLY_REASONS = frozenset({ReasonType.human, ReasonType.beauty})


#: Which reasons the flag form offers for each type of issue.
#:
#: This is *not* enforced on the API: Robotoff hardcodes `type: "image"` and
#: the mobile app files product reasons freely. It describes the form, and
#: drives the moderator's grouping.
REASONS_BY_TYPE: dict[IssueType, tuple[ReasonType, ...]] = {
    IssueType.product: (
        ReasonType.wrong_data,
        ReasonType.missing_data,
        ReasonType.wrong_barcode,
        ReasonType.not_a_product,
        ReasonType.duplicate_product,
        ReasonType.discontinued,
        ReasonType.spam_or_vandalism,
        ReasonType.legal_takedown,
        ReasonType.delete_request,
        ReasonType.product_complaint,
        ReasonType.other,
    ),
    IssueType.image: (
        ReasonType.inappropriate,
        ReasonType.copyright,
        ReasonType.includes_personal_infos,
        ReasonType.wrong_product,
        ReasonType.duplicate,
        ReasonType.outdated,
        ReasonType.delete_request,
        ReasonType.other,
    ),
    IssueType.search: (
        ReasonType.no_results,
        ReasonType.wrong_results,
        ReasonType.other,
    ),
}


#: Every value `flags.reason` is offered as. Rows written before the taxonomy
#: hold other things, which is why `reason` is read back as a plain string:
#: this is what the form offers and what the filters accept.
VALID_REASONS = frozenset(reason.value for reason in ReasonType)
