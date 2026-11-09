"""Peewee migrations -- 005_ticket_comments.py."""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""

    @migrator.create_model
    class TicketCommentModel(pw.Model):
        id = pw.AutoField()
        ticket = pw.ForeignKeyField(
            column_name="ticket_id",
            field="id",
            model=migrator.orm["tickets"],
            index=True,
        )
        moderator_action = pw.ForeignKeyField(
            column_name="moderator_action_id",
            field="id",
            model=migrator.orm["moderator_actions"],
            unique=True,
        )
        user_id = pw.TextField()
        text = pw.TextField()
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "ticket_comments"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""

    migrator.remove_model("ticket_comments")
