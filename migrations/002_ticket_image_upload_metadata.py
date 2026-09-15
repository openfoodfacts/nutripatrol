"""Peewee migrations -- 002_ticket_image_upload_metadata.py."""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""

    migrator.add_fields(
        "tickets",
        image_uploader=pw.TextField(null=True, index=True),
        image_uploaded_at=pw.DateTimeField(null=True),
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""

    # Postgres drops the index with the column, but drop it explicitly so that
    # the rollback also works on databases that do not (e.g. SQLite).
    migrator.drop_index("tickets", "image_uploader")
    migrator.remove_fields("tickets", "image_uploader", "image_uploaded_at")
