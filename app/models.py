from peewee import (
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    Model,
    PostgresqlDatabase,
)

from .config import settings

db = PostgresqlDatabase(
    settings.postgres_db,
    user=settings.postgres_user,
    password=settings.postgres_password,
    host=settings.postgres_host,
    port=settings.postgres_port,
)


class TicketModel(Model):
    barcode = CharField(null=True)
    type = CharField()
    url = CharField()
    status = CharField()
    image_id = CharField(null=True)
    flavor = CharField()
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "tickets"


class ModeratorActionModel(Model):
    action_type = CharField()
    moderator_id = CharField()
    user_id = CharField()
    ticket = ForeignKeyField(TicketModel, backref="moderator_actions")
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "moderator_actions"


class FlagModel(Model):
    ticket = ForeignKeyField(TicketModel, backref="flags")
    barcode = CharField(null=True)
    type = CharField()
    url = CharField()
    user_id = CharField()
    device_id = CharField()
    source = CharField()
    confidence = FloatField(null=True)
    image_id = CharField(null=True)
    flavor = CharField()
    reason = CharField(null=True)
    comment = CharField(max_length=500, null=True)
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "flags"
