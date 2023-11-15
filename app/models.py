from peewee import (
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    PostgresqlDatabase,
)

db = PostgresqlDatabase(
    "postgres", user="postgres", password="postgres", host="postgres", port=5432
)


# Définissez vos modèles de table
class Tickets(Model):
    id = IntegerField(primary_key=True)
    barcode = CharField()
    type = CharField()
    url = CharField()
    status = CharField()
    image_id = CharField()
    flavour = CharField()
    created_at = DateTimeField()

    class Meta:
        database = db


class ModeratorActions(Model):
    id = IntegerField(primary_key=True)
    action_type = CharField()
    moderator_id = IntegerField()
    user_id = IntegerField()
    ticket_id = ForeignKeyField(Tickets, backref="moderator_actions")
    created_at = DateTimeField()

    class Meta:
        database = db


class Flags(Model):
    id = IntegerField(primary_key=True)
    ticket_id = ForeignKeyField(Tickets, backref="flags")
    barcode = CharField()
    type = CharField()
    url = CharField()
    user_id = CharField()
    device_id = CharField()
    source = CharField()
    confidence = FloatField()
    image_id = CharField()
    flavour = CharField()
    reason = CharField()
    comment = CharField(max_length=500)
    created_at = DateTimeField()

    class Meta:
        database = db
