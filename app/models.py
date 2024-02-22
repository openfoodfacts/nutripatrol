from peewee import (
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    Model,
    PostgresqlDatabase,
    TextField,
)
from peewee_migrate import Router

from .config import settings

db = PostgresqlDatabase(
    settings.postgres_db,
    user=settings.postgres_user,
    password=settings.postgres_password,
    host=settings.postgres_host,
    port=settings.postgres_port,
)


class TicketModel(Model):
    # barcode of the product, if any
    barcode = TextField(null=True)
    type = CharField(max_length=50)
    url = TextField()
    status = CharField(max_length=50)
    image_id = CharField(null=True)
    flavor = CharField(max_length=20)
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "tickets"


class ModeratorActionModel(Model):
    action_type = CharField(max_length=20)
    user_id = TextField()
    ticket = ForeignKeyField(TicketModel, backref="moderator_actions")
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "moderator_actions"


class FlagModel(Model):
    ticket = ForeignKeyField(TicketModel, backref="flags")
    barcode = TextField(null=True)
    type = CharField(max_length=50)
    url = TextField()
    user_id = TextField()
    device_id = TextField()
    source = CharField()
    confidence = FloatField(null=True)
    image_id = CharField(null=True)
    flavor = CharField(max_length=20)
    reason = TextField(null=True)
    comment = TextField(null=True)
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "flags"


def run_migration():
    """Run all unapplied migrations."""
    # embedding schema does not exist at DB initialization
    router = Router(db, migrate_dir=settings.migration_dir)
    # Run all unapplied migrations
    router.run()


def add_revision(name: str):
    """Create a migration revision."""
    router = Router(db, migrate_dir=settings.migration_dir)
    router.create(name, auto=True)
