from openfoodfacts.redis import get_redis_client, UpdateListener, RedisUpdate

from app.api import TicketStatus
from app.models import TicketModel


class MyUpdateListener(UpdateListener):
    def process_redis_update(self, redis_update: RedisUpdate):
        print(f"Received update for product {redis_update.code}")
        print(f"Action: {redis_update.action}, User: {redis_update.user_id}")
        if redis_update.is_image_deletion():
            deleted_images = redis_update.diffs["uploaded_image"]["delete"]
            for image_id in deleted_images:
                print(f"Deleted image ID: {image_id}")

                ticket = TicketModel.get_or_none(TicketModel.image_id == image_id)
                if ticket:
                    print(f"Marking ticket {ticket.id} as resolved.")
                    ticket.status = TicketStatus.closed
                    ticket.save()


def main():
    redis = get_redis_client(host="localhost", port=6379, db=0)
    listener = MyUpdateListener(
        redis_client=redis,
        redis_stream_name="product_updates",
        redis_latest_id_key="last_processed_id",
    )
    listener.run()


if __name__ == "__main__":
    main()
