import os
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient


@dataclass
class InMemoryUpdateResult:
    modified_count: int
    matched_count: int


@dataclass
class InMemoryDeleteResult:
    deleted_count: int


class InMemoryCursor:
    def __init__(self, documents: list[dict[str, Any]]):
        self._documents = documents

    def sort(self, field: str, direction: int):
        reverse = direction == DESCENDING
        self._documents = sorted(
            self._documents,
            key=lambda item: item.get(field, ""),
            reverse=reverse,
        )
        return self

    def limit(self, size: int):
        self._documents = self._documents[:size]
        return self

    def __iter__(self):
        return iter(deepcopy(self._documents))


class InMemoryCollection:
    def __init__(self):
        self._documents: list[dict[str, Any]] = []

    @staticmethod
    def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
        return all(document.get(key) == value for key, value in query.items())

    def insert_one(self, document: dict[str, Any]):
        self._documents.append(deepcopy(document))

    def find_one(self, query: dict[str, Any] | None = None):
        query = query or {}
        for document in reversed(self._documents):
            if self._matches(document, query):
                return deepcopy(document)
        return None

    def find(self, query: dict[str, Any] | None = None):
        query = query or {}
        matches = [
            deepcopy(document)
            for document in self._documents
            if self._matches(document, query)
        ]
        return InMemoryCursor(matches)

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False):
        matched_idx = None
        for index, document in enumerate(self._documents):
            if self._matches(document, query):
                matched_idx = index
                break

        if matched_idx is None and upsert:
            base = deepcopy(query)
            base.update(deepcopy(update.get("$set", {})))
            self._documents.append(base)
            return InMemoryUpdateResult(modified_count=1, matched_count=0)

        if matched_idx is None:
            return InMemoryUpdateResult(modified_count=0, matched_count=0)

        doc = self._documents[matched_idx]
        for key, value in update.get("$set", {}).items():
            doc[key] = deepcopy(value)
        for key, value in update.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + value
        return InMemoryUpdateResult(modified_count=1, matched_count=1)

    def delete_many(self, query: dict[str, Any]):
        before = len(self._documents)
        self._documents = [document for document in self._documents if not self._matches(document, query)]
        deleted_count = before - len(self._documents)
        return InMemoryDeleteResult(deleted_count=deleted_count)

    def create_index(self, *args, **kwargs):
        # In-memory fallback does not persist indexes; keep API parity with pymongo.
        return None


class InMemoryDatabase:
    def __init__(self):
        self.users = InMemoryCollection()
        self.analyses = InMemoryCollection()
        self.health_logs = InMemoryCollection()
        self.otp_verifications = InMemoryCollection()


_collections = None
_mongo_client = None
_fallback_db = InMemoryDatabase()
_indexes_ready = False
_last_connection_error = None
_last_attempted_uri = None
_last_uri_sources: list[str] = []
_last_connection_attempt_at = 0.0


def _safe_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value else default
    except (TypeError, ValueError):
        return default


def _mask_uri(uri: str) -> str:
    if "://" not in uri or "@" not in uri:
        return uri

    scheme, rest = uri.split("://", 1)
    auth, host = rest.split("@", 1)
    username = auth.split(":", 1)[0] if auth else "user"
    return f"{scheme}://{username}:***@{host}"


def _mongo_uri_candidates() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for env_key in ("MONGODB_URI", "MONGODB_URI_FALLBACK", "MONGO_URI"):
        value = os.getenv(env_key, "").strip()
        if not value:
            continue
        if any(existing_uri == value for _, existing_uri in candidates):
            continue
        candidates.append((env_key, value))
    return candidates


def _ensure_mongo_indexes(database):
    global _indexes_ready, _last_connection_error
    if _indexes_ready:
        return

    try:
        database.users.create_index("email", unique=True)
        database.users.create_index("user_id", unique=True)
        database.analyses.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
        database.health_logs.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
        database.health_logs.create_index([("user_id", ASCENDING), ("tags", ASCENDING)])
        database.otp_verifications.create_index([("email", ASCENDING), ("purpose", ASCENDING)], unique=True)
        database.otp_verifications.create_index("expires_at")
        _indexes_ready = True
    except Exception as error:
        message = f"Index creation warning: {error}"
        _last_connection_error = f"{_last_connection_error} | {message}" if _last_connection_error else message


def _can_skip_reconnect() -> bool:
    if _collections is None:
        return False

    if _collections.get("backend") == "mongodb":
        return True

    retry_seconds = max(_safe_int(os.getenv("MONGODB_RETRY_INTERVAL_SECONDS"), 30), 0)
    if retry_seconds == 0:
        return False

    elapsed = time.monotonic() - _last_connection_attempt_at
    return elapsed < retry_seconds


def get_collections() -> dict[str, Any]:
    global _collections, _mongo_client, _last_connection_error, _last_attempted_uri, _last_uri_sources, _last_connection_attempt_at

    if _can_skip_reconnect():
        return _collections

    _last_connection_attempt_at = time.monotonic()

    db_name = os.getenv("MONGODB_DB", "dermora")
    app_name = os.getenv("MONGODB_APP_NAME", "DermoraApp")

    server_selection_timeout_ms = _safe_int(os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS"), 3500)
    connect_timeout_ms = _safe_int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS"), 3500)
    socket_timeout_ms = _safe_int(os.getenv("MONGODB_SOCKET_TIMEOUT_MS"), 6500)

    uri_candidates = _mongo_uri_candidates()
    _last_uri_sources = [name for name, _ in uri_candidates]

    connection_errors: list[str] = []
    for env_name, mongo_uri in uri_candidates:
        _last_attempted_uri = _mask_uri(mongo_uri)
        try:
            _mongo_client = MongoClient(
                mongo_uri,
                appname=app_name,
                serverSelectionTimeoutMS=server_selection_timeout_ms,
                connectTimeoutMS=connect_timeout_ms,
                socketTimeoutMS=socket_timeout_ms,
                tz_aware=True,
            )
            _mongo_client.admin.command("ping")
            database = _mongo_client[db_name]
            _ensure_mongo_indexes(database)
            _collections = {
                "backend": "mongodb",
                "users": database.users,
                "analyses": database.analyses,
                "health_logs": database.health_logs,
                "otp_verifications": database.otp_verifications,
            }
            _last_connection_error = None
            return _collections
        except Exception as error:
            connection_errors.append(f"{env_name}: {error}")

    _collections = {
        "backend": "memory",
        "users": _fallback_db.users,
        "analyses": _fallback_db.analyses,
        "health_logs": _fallback_db.health_logs,
        "otp_verifications": _fallback_db.otp_verifications,
    }

    if uri_candidates:
        _last_connection_error = " | ".join(connection_errors)
    else:
        _last_connection_error = "No MongoDB URI configured. Set MONGODB_URI or MONGODB_URI_FALLBACK."

    return _collections


def get_database_status() -> dict[str, Any]:
    collections = get_collections()
    return {
        "backend": collections["backend"],
        "database": os.getenv("MONGODB_DB", "dermora"),
        "has_mongodb_uri": bool(_mongo_uri_candidates()),
        "configured_uri_sources": _last_uri_sources,
        "active_uri": _last_attempted_uri,
        "retry_interval_seconds": max(_safe_int(os.getenv("MONGODB_RETRY_INTERVAL_SECONDS"), 30), 0),
        "connection_error": _last_connection_error,
    }


