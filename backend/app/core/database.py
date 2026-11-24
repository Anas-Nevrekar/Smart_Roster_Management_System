"""Lifecycle-managed MongoDB connection with redacted failures."""
from __future__ import annotations

import logging

from app.core.database_indexes import ensure_indexes

logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    def __init__(self, uri: str | None, database_name: str, *, client_factory=None):
        self.uri = uri
        self.database_name = database_name
        self._client_factory = client_factory
        self.client = None
        self.database = None
        self.last_error: str | None = None
        self.indexes_ready = False
        self._connected = False

    def connect(self, *, force_check: bool = False) -> bool:
        if not self.uri:
            self.last_error = "MongoDB is not configured. Set MONGODB_URI."
            return False
        if self._connected and self.indexes_ready and not force_check:
            return True
        try:
            if self.client is None:
                factory = self._client_factory
                if factory is None:
                    from pymongo import MongoClient
                    factory = MongoClient
                self.client = factory(
                    self.uri,
                    appname="Smart Roster API",
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    tz_aware=True,
                )
                self.database = self.client[self.database_name]
            self.client.admin.command("ping")
            if not self.indexes_ready:
                ensure_indexes(self.database)
                self.indexes_ready = True
            self.last_error = None
            self._connected = True
            return True
        except Exception as exc:
            self._connected = False
            if isinstance(exc, ModuleNotFoundError) and exc.name == "pymongo":
                self.last_error = "PyMongo is not installed. Install backend requirements before using MongoDB."
                logger.error("MongoDB startup failed because PyMongo is not installed.")
            elif type(exc).__name__ == "DuplicateKeyError" or (isinstance(exc, RuntimeError) and str(exc).startswith("Cannot create unique index ")):
                self.last_error = str(exc)
                logger.error("%s", self.last_error)
            else:
                self.last_error = "MongoDB is unavailable or its indexes could not be verified."
                logger.error("MongoDB connection/index initialization failed (%s).", type(exc).__name__)
            return False

    def require_database(self):
        if self.database is None or not self.connect():
            from app.core.errors import ServiceError
            raise ServiceError(503, "DATABASE_UNAVAILABLE", self.last_error or "MongoDB is unavailable.")
        return self.database

    def check_ready(self) -> tuple[bool, str | None]:
        if not self.connect(force_check=True):
            return False, self.last_error
        return True, None

    def mark_unavailable(self) -> None:
        self._connected = False
        self.last_error = "MongoDB is unavailable. Check the configured connection and network access."

    def close(self) -> None:
        client, self.client = self.client, None
        self.database = None
        self.indexes_ready = False
        self._connected = False
        if client is not None:
            client.close()
