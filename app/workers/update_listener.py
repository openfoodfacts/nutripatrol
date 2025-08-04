from app.workers.tasks import delete_ticket_job
from redis import Redis
from openfoodfacts.redis import RedisUpdate
from openfoodfacts.redis import UpdateListener as BaseUpdateListener
from app.utils.logger import get_logger
from app.settings import REDIS_HOST, REDIS_UPDATE_HOST, REDIS_UPDATE_PORT, REDIS_STREAM_NAME, REDIS_LATEST_ID_KEY
from app.types import ProductIdentifier, ServerType
from app.workers.queues import (
    enqueue_job,
    get_high_queue,
    get_low_queue,
)


logger = get_logger(__name__)
redis_conn = Redis(host=REDIS_HOST)


def get_redis_client():
    """Get the Redis client where Product Opener publishes its product updates."""
    return Redis(
        host=REDIS_UPDATE_HOST,
        port=REDIS_UPDATE_PORT,
        decode_responses=True,
    )


class UpdateListener(BaseUpdateListener):
    def process_redis_update(self, redis_update: RedisUpdate):
        logger.debug("New update: %s", redis_update)

        if redis_update.product_type is None:
            logger.warning("Product type is null, skipping")
            return

        action = redis_update.action
        server_type = ServerType.from_product_type(redis_update.product_type)
        product_id = ProductIdentifier(redis_update.code, server_type)

        # Check if the update was triggered by scanbot or specific mass update accounts
        is_scanbot_or_mass_update = redis_update.user_id in [
            "scanbot",
            "update_all_products",
        ]
        # Select queue based on triggering actor
        selected_queue = (
            get_low_queue() if is_scanbot_or_mass_update else get_high_queue(product_id)
        )

        if redis_update.user_id == "nutripatrol-app" or "[nutripatrol]" in redis_update.comment:
            # If the update was triggered by Nutripatrol (automatically of through a user
            # annotation), we skip it as the DB is already up to date with respect to
            # Product Opener changes. Besides, it prevents unnecessary processing and
            # race conditions during insight update/deletion.
            logger.info(
                "Skipping update for product %s triggered by Nutripatrol",
                redis_update.code,
            )
            return

        if action == "deleted":
            logger.info("Product %s has been deleted", redis_update.code)
            enqueue_job(
                func=delete_ticket_job,
                queue=selected_queue,
                job_kwargs={"result_ttl": 0},
                product_id=product_id,
            )


def run_update_listener():
    """Run the update import daemon.

    This daemon listens to the Redis stream containing information about
    product updates and triggers appropriate actions.
    """
    logger.info("Starting Redis update listener...")
    while True:
        try:
            redis_client = get_redis_client()
            update_listener = UpdateListener(
                redis_client=redis_client,
                redis_stream_name=REDIS_STREAM_NAME,
                redis_latest_id_key=REDIS_LATEST_ID_KEY,
            )
            update_listener.run()
        except Exception as e:
            logger.critical(
                "Unexpected error in update listener: %s", str(e), exc_info=True
            )
            raise
