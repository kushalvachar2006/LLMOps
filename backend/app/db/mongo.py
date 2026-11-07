"""MongoDB connection lifecycle and health check."""
import logging

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import Settings

log = logging.getLogger(__name__)


def create_client(settings: Settings) -> MongoClient:
    # MongoClient connects lazily, so creating it never blocks or crashes startup.
    return MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=settings.mongodb_timeout_ms)


def get_database(client: MongoClient, settings: Settings) -> Database:
    return client[settings.mongodb_db_name]


def ping(db: Database) -> tuple[bool, str | None]:
    """Return (ok, error_type). Never leaks the connection string."""
    try:
        db.command("ping")
        return True, None
    except Exception as exc:  # noqa: BLE001 - any failure means "database down"
        log.warning("mongo ping failed", extra={"ctx": {"error_type": type(exc).__name__}})
        return False, type(exc).__name__
