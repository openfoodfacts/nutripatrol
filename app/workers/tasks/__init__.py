from app.types import ProductIdentifier
from app.models import TicketModel, db
from app.utils.logger import get_logger

logger = get_logger(__name__)


@db
def delete_ticket_job(product_id: ProductIdentifier):
    """This job is triggered by a `deleted` event on Redis Stream,
    when the given image has been removed from the database.

    In this case, we must delete all the associated tickets
    that have not been annotated.
    """
    logger.info("%s deleted, deleting associated tickets...", product_id)
    deleted_tickets = (
        TicketModel.delete()
        .where(
            TicketModel.barcode == product_id.barcode,
            TicketModel.flavor == product_id.flavor,
        )
        .execute()
    )

    logger.info(
        "%s tickets deleted",
        deleted_tickets,
    )
