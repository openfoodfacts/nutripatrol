"""Peewee migrations -- 004_flag_extra_data.py."""

import peewee as pw
from peewee_migrate import Migrator

from app.models import JSONBField


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""

    migrator.add_fields("flags", extra_data=JSONBField(null=True))


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""

    migrator.remove_fields("flags", "extra_data")
