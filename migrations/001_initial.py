"""Peewee migrations -- 001_initial.py."""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""

    @migrator.create_model
    class TicketModel(pw.Model):
        id = pw.AutoField()
        barcode = pw.TextField(null=True)
        type = pw.CharField(max_length=50)
        url = pw.TextField()
        status = pw.CharField(max_length=50)
        image_id = pw.CharField(max_length=255, null=True)
        flavor = pw.CharField(max_length=20)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "tickets"

    @migrator.create_model
    class FlagModel(pw.Model):
        id = pw.AutoField()
        ticket = pw.ForeignKeyField(
            column_name="ticket_id", field="id", model=migrator.orm["tickets"]
        )
        barcode = pw.TextField(null=True)
        type = pw.CharField(max_length=50)
        url = pw.TextField()
        user_id = pw.TextField()
        device_id = pw.TextField()
        source = pw.CharField(max_length=255)
        confidence = pw.FloatField(null=True)
        image_id = pw.CharField(max_length=255, null=True)
        flavor = pw.CharField(max_length=20)
        reason = pw.TextField(null=True)
        comment = pw.TextField(null=True)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "flags"

    @migrator.create_model
    class ModeratorActionModel(pw.Model):
        id = pw.AutoField()
        action_type = pw.CharField(max_length=20)
        user_id = pw.TextField()
        ticket = pw.ForeignKeyField(
            column_name="ticket_id", field="id", model=migrator.orm["tickets"]
        )
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "moderator_actions"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""

    migrator.remove_model("moderator_actions")

    migrator.remove_model("flags")

    migrator.remove_model("tickets")
