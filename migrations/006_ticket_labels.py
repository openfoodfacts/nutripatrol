"""Peewee migrations -- 006_ticket_labels.py."""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""

    @migrator.create_model
    class LabelModel(pw.Model):
        id = pw.AutoField()
        name = pw.CharField(max_length=64)
        name_key = pw.CharField(max_length=64, unique=True)
        color = pw.CharField(max_length=16, null=True)
        created_by = pw.TextField()
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "labels"

    @migrator.create_model
    class TicketLabelModel(pw.Model):
        id = pw.AutoField()
        ticket = pw.ForeignKeyField(
            column_name="ticket_id", field="id", model=migrator.orm["tickets"]
        )
        label = pw.ForeignKeyField(
            column_name="label_id",
            field="id",
            model=migrator.orm["labels"],
            index=True,
        )
        user_id = pw.TextField()
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "ticket_labels"
            indexes = ((("ticket", "label"), True),)

    migrator.add_fields(
        "moderator_actions",
        label=pw.ForeignKeyField(
            column_name="label_id",
            field="id",
            model=migrator.orm["labels"],
            null=True,
        ),
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""

    # Postgres drops the index with the column, but drop it explicitly so that
    # the rollback also works on databases that do not (e.g. SQLite).
    migrator.drop_index("moderator_actions", "label")
    migrator.remove_fields("moderator_actions", "label")
    migrator.remove_model("ticket_labels")
    migrator.remove_model("labels")
