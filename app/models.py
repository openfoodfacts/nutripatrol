import json

from peewee import (
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
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


class JSONBField(TextField):
    """A JSONB column that also survives the SQLite the tests run on.

    `playhouse.postgres_ext.BinaryJSONField` would be the obvious choice, but
    it needs a `PostgresqlExtDatabase` and emits a cast to `jsonb` that SQLite
    quietly evaluates to `0`, which would make every test store nothing.
    Declaring the column type by hand keeps the production schema identical
    and leaves the value readable on both.

    Postgres coerces the text parameter into the column's type on assignment
    and hands the value back already decoded; SQLite hands back the text that
    was stored. Hence the isinstance check rather than a blind `json.loads`.
    """

    field_type = "JSONB"

    def db_value(self, value):
        return None if value is None else json.dumps(value)

    def python_value(self, value):
        if value is None or not isinstance(value, (str, bytes)):
            return value
        return json.loads(value)


class TicketModel(Model):
    # barcode of the product, if any
    barcode = TextField(null=True)
    type = CharField(max_length=50)
    url = TextField()
    status = CharField(max_length=50)
    image_id = CharField(null=True)
    flavor = CharField(max_length=20)
    created_at = DateTimeField()
    # Open Food Facts drops the uploader and the upload date of an image
    # as soon as the image is deleted, so we capture them while the image
    # still exists, when a moderator closes the ticket.
    image_uploader = TextField(null=True, index=True)
    image_uploaded_at = DateTimeField(null=True)

    class Meta:
        database = db
        table_name = "tickets"


class LabelModel(Model):
    """A label moderators put on tickets, to sort and filter them.

    Labels are shared by every ticket, so that one is renamed once for all of
    them, and are never deleted.
    """

    name = CharField(max_length=64)
    # The name, lowercased: unique, so that "Vandal" and "vandal" are one
    # label.
    name_key = CharField(max_length=64, unique=True)
    # One of the MUI palette colors, see `LabelColor` in app/api.py.
    color = CharField(max_length=16, null=True)
    created_by = TextField()
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "labels"


class ModeratorActionModel(Model):
    action_type = CharField(max_length=20)
    user_id = TextField()
    ticket = ForeignKeyField(TicketModel, backref="moderator_actions")
    created_at = DateTimeField()
    # The label added or removed, on `label_added` and `label_removed`
    # actions.
    label = ForeignKeyField(LabelModel, null=True, backref="moderator_actions")

    class Meta:
        database = db
        table_name = "moderator_actions"


class TicketCommentModel(Model):
    """A comment a moderator wrote on a ticket.

    Every comment is recorded with a moderator action of its own, of type
    `comment`, so that it takes its place in the ticket history and in the
    moderator's own list of actions. `ticket`, `user_id` and `created_at`
    repeat the action's, so that listing the comments of a ticket stays a
    single-table query.
    """

    ticket = ForeignKeyField(TicketModel, backref="comments", index=True)
    moderator_action = ForeignKeyField(
        ModeratorActionModel, backref="comment", unique=True
    )
    user_id = TextField()
    text = TextField()
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "ticket_comments"


class TicketLabelModel(Model):
    """A label currently on a ticket."""

    ticket = ForeignKeyField(TicketModel, backref="ticket_labels")
    label = ForeignKeyField(LabelModel, backref="ticket_labels", index=True)
    # The moderator who put it there, and when.
    user_id = TextField()
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "ticket_labels"
        indexes = ((("ticket", "label"), True),)


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
    # Structured details about the report, whose shape depends on `reason`:
    # the correct barcode behind a `wrong_barcode`, the offending uploader
    # behind a `copyright`. Validated at the API boundary
    # (app/flag_extra_data.py), never here.
    extra_data = JSONBField(null=True)
    # Revision of the Open Food Facts product at the time the flag was raised,
    # captured on creation so that a moderator knows which product version the
    # flagger was looking at. Null when the flag is not about a product, or
    # when Open Food Facts could not be reached.
    product_revision = IntegerField(null=True)
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
