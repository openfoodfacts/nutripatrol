import typer

app = typer.Typer()


@app.command()
def migrate_db():
    """Run unapplied DB migrations."""
    from openfoodfacts.utils import get_logger

    from app.models import db, run_migration

    get_logger()

    with db.connection_context():
        run_migration()


@app.command()
def add_revision(
    name: str = typer.Argument(..., help="name of the revision"),
):
    """Create a new migration file using peewee_migrate."""
    from openfoodfacts.utils import get_logger

    from app.models import add_revision, db

    get_logger()

    with db.connection_context():
        add_revision(name)


@app.command()
def run_update_listener():
    """Launch a process that listens to product updates published on Redis
    stream."""
    from app.settings import init_sentry
    from app.utils.logger import get_logger
    from app.workers.update_listener import run_update_listener

    get_logger()
    init_sentry()
    run_update_listener()


def main() -> None:
    app()
