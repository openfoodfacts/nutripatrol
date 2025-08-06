import os
from sentry_sdk.integrations import Integration
from sentry_sdk.integrations.logging import LoggingIntegration
import sentry_sdk
import logging
from pathlib import Path

# local Redis, used as a backend for rq tasks
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")

# Remote Redis where Product Opener publishes product updates in a stream
REDIS_UPDATE_HOST = os.environ.get("REDIS_UPDATE_HOST", "localhost")
REDIS_UPDATE_PORT = os.environ.get("REDIS_UPDATE_PORT", 6379)

# Name of the Redis stream where Product Opener publishes product updates
REDIS_STREAM_NAME = os.environ.get("REDIS_STREAM_NAME", "product_updates")
REDIS_LATEST_ID_KEY = os.environ.get(
    "REDIS_LATEST_ID_KEY", "nutriaptrol:product_updates:latest_id"
)

# Number of rq workers running, this is used to know the number of high
# priority queues that exist
NUM_RQ_WORKERS = int(os.environ.get("NUM_RQ_WORKERS", 4))


# Nutripatrol instance gives the environment, either `prod` or `dev`
# (`dev` by default).
# If `prod` is used, openfoodfacts.org domain will be used by default,
# and openfoodfacts.net if `dev` is used.
def _nutripatrol_instance():
    return os.environ.get("NUTRIPATROL_INSTANCE", "dev")


# Sentry for error reporting
_sentry_dsn = os.environ.get("SENTRY_DSN")


def init_sentry(integrations: list[Integration] | None = None):
    nutripatrol_instance = _nutripatrol_instance()
    if _sentry_dsn:
        integrations = integrations or []
        integrations.append(
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above as breadcrumbs
                event_level=logging.WARNING,  # Send warning and errors as events
            )
        )
        sentry_sdk.init(  # type:ignore # mypy say it's abstract
            _sentry_dsn,
            environment=nutripatrol_instance,
            integrations=integrations,
            release=get_package_version(),
        )
    elif nutripatrol_instance == "prod":
        raise ValueError("No SENTRY_DSN specified for prod NutriPatrol")


def get_package_version(package_name: str, file_path: Path = Path("requirements.txt")) -> str | None:
    """Return the version of a given package from requirements.txt."""
    if not file_path.exists():
        raise FileNotFoundError(f"{file_path} not found")

    with file_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Remove extras: e.g., package[extra]==1.2.3 -> package
            name_only = line.split("[")[0].split("==")[0].strip()
            if name_only.lower() == package_name.lower():
                # Extract version after '==' or '~=' or '>=' etc.
                for operator in ["==", "~=", ">=", "<=", ">", "<"]:
                    if operator in line:
                        return line.split(operator)[1].split()[0].strip()
                return None  # Found package, but no version pinned
    return None  # Not found
