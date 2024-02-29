from enum import StrEnum
from pathlib import Path

from openfoodfacts import Environment
from pydantic import Field
from pydantic_settings import BaseSettings

PROJECT_DIR = Path(__file__).parent.parent


class LoggingLevel(StrEnum):
    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def to_int(self):
        if self is LoggingLevel.NOTSET:
            return 0
        elif self is LoggingLevel.DEBUG:
            return 10
        elif self is LoggingLevel.INFO:
            return 20
        elif self is LoggingLevel.WARNING:
            return 30
        elif self is LoggingLevel.ERROR:
            return 40
        elif self is LoggingLevel.CRITICAL:
            return 50


class Settings(BaseSettings):
    sentry_dns: str | None = None
    log_level: LoggingLevel = LoggingLevel.INFO
    postgres_host: str = "localhost"
    postgres_db: str = "postgres"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_port: int = 5432
    cors_allow_origins: list[str] = Field(default=[])
    off_tld: Environment = Environment.net
    environment: str = "dev"
    migration_dir: Path = PROJECT_DIR / "migrations"


settings = Settings()
