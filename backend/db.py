import os
from copy import deepcopy
from typing import Any

from pymongo import DESCENDING, MongoClient


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

    def insert_one(self, document: dict[str, Any]):
        self._documents.append(deepcopy(document))

    def find_one(self, query: dict[str, Any] | None = None):
        query = query or {}
        for document in reversed(self._documents):
            if all(document.get(key) == value for key, value in query.items()):
                return deepcopy(document)
        return None

    def find(self, query: dict[str, Any] | None = None):
        query = query or {}
        matches = [
            deepcopy(document)
            for document in self._documents
            if all(document.get(key) == value for key, value in query.items())
        ]
        return InMemoryCursor(matches)


class InMemoryDatabase:
    def __init__(self):
        self.users = InMemoryCollection()
        self.analyses = InMemoryCollection()
        self.health_logs = InMemoryCollection()


_collections = None
_last_connection_error = None


def get_collections() -> dict[str, Any]:
    global _collections, _last_connection_error
    if _collections is not None:
        return _collections

    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB", "dermora")

    if mongo_uri:
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
            client.admin.command("ping")
            database = client[db_name]
            _collections = {
                "backend": "mongodb",
                "users": database.users,
                "analyses": database.analyses,
                "health_logs": database.health_logs,
            }
            _last_connection_error = None
            return _collections
        except Exception as error:
            _last_connection_error = str(error)

    fallback_db = InMemoryDatabase()
    _collections = {
        "backend": "memory",
        "users": fallback_db.users,
        "analyses": fallback_db.analyses,
        "health_logs": fallback_db.health_logs,
    }
    return _collections


def get_database_status() -> dict[str, Any]:
    collections = get_collections()
    return {
        "backend": collections["backend"],
        "database": os.getenv("MONGODB_DB", "dermora"),
        "has_mongodb_uri": bool(os.getenv("MONGODB_URI")),
        "connection_error": _last_connection_error,
    }
