import json
from datetime import datetime
import os
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
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
    def _lookup(document: dict[str, Any], key: str):
        value: Any = document
        for part in key.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    @classmethod
    def _matches(cls, document: dict[str, Any], query: dict[str, Any]) -> bool:
        return all(cls._lookup(document, key) == value for key, value in query.items())

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


class PersistentFallbackCollection(InMemoryCollection):
    def __init__(self, store: "PersistentFallbackDatabase", collection_name: str):
        self._store = store
        self._collection_name = collection_name

    @property
    def _documents(self) -> list[dict[str, Any]]:
        return self._store._data.setdefault(self._collection_name, [])

    @_documents.setter
    def _documents(self, value: list[dict[str, Any]]):
        self._store._data[self._collection_name] = value

    def insert_one(self, document: dict[str, Any]):
        self._documents.append(deepcopy(document))
        self._store.save()

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False):
        result = super().update_one(query, update, upsert=upsert)
        if result.modified_count > 0 or (upsert and result.matched_count == 0):
            self._store.save()
        return result

    def delete_many(self, query: dict[str, Any]):
        result = super().delete_many(query)
        if result.deleted_count > 0:
            self._store.save()
        return result


class PersistentFallbackDatabase:
    COLLECTION_NAMES = (
        "users",
        "analyses",
        "health_logs",
        "otp_verifications",
        "orchestration_events",
    )

    def __init__(self, storage_path: Path):
        self._storage_path = storage_path
        self._lock = RLock()
        self._data = self._load()

        for collection_name in self.COLLECTION_NAMES:
            setattr(self, collection_name, PersistentFallbackCollection(self, collection_name))

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if not self._storage_path.is_file():
            return {name: [] for name in self.COLLECTION_NAMES}

        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {name: [] for name in self.COLLECTION_NAMES}

        if not isinstance(payload, dict):
            return {name: [] for name in self.COLLECTION_NAMES}

        normalized: dict[str, list[dict[str, Any]]] = {}
        for name in self.COLLECTION_NAMES:
            values = payload.get(name, [])
            normalized[name] = values if isinstance(values, list) else []
        return normalized
    
    def _json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    def save(self):
        with self._lock:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._storage_path.with_suffix(f"{self._storage_path.suffix}.tmp")
            serialized = json.dumps(self._data, ensure_ascii=True, indent=2, default=self._json_serial)
            temp_path.write_text(serialized, encoding="utf-8")
            temp_path.replace(self._storage_path)


_collections = None
_mongo_client = None
_fallback_db = PersistentFallbackDatabase(Path(__file__).resolve().parent / ".fallback_db.json")
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
        database.orchestration_events.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        database.orchestration_events.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
        database.otp_verifications.create_index([("email", ASCENDING), ("purpose", ASCENDING)], unique=True)
        database.otp_verifications.create_index("expires_at")
        _indexes_ready = True
    except Exception as error:
        message = f"Index creation warning: {error}"
        _last_connection_error = f"{_last_connection_error} | {message}" if _last_connection_error else message


def _snapshot_mongodb_to_fallback(database):
    snapshot = {}
    for collection_name in PersistentFallbackDatabase.COLLECTION_NAMES:
        collection = getattr(database, collection_name)
        documents: list[dict[str, Any]] = []
        for document in collection.find({}):
            cleaned = dict(document)
            cleaned.pop("_id", None)
            documents.append(cleaned)
        snapshot[collection_name] = documents

    _fallback_db._data = snapshot
    _fallback_db.save()


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
            _snapshot_mongodb_to_fallback(database)
            _collections = {
                "backend": "mongodb",
                "users": database.users,
                "analyses": database.analyses,
                "health_logs": database.health_logs,
                "orchestration_events": database.orchestration_events,
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
        "orchestration_events": _fallback_db.orchestration_events,
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
        "fallback_persistence": "disk" if collections["backend"] == "memory" else "mongodb",
        "fallback_storage_path": str(_fallback_db._storage_path),
    }


def get_fallback_collections() -> dict[str, Any]:
    return {
        "backend": "memory",
        "users": _fallback_db.users,
        "analyses": _fallback_db.analyses,
        "health_logs": _fallback_db.health_logs,
        "orchestration_events": _fallback_db.orchestration_events,
        "otp_verifications": _fallback_db.otp_verifications,
    }


