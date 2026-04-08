from copy import deepcopy
from datetime import datetime, timezone

from pymongo import DESCENDING

from backend.db import get_collections


def _clean(document):
    if not document:
        return None
    cleaned = deepcopy(document)
    cleaned.pop("_id", None)
    return cleaned


def create_user(user_document: dict):
    collections = get_collections()
    collections["users"].insert_one(user_document)
    return _clean(user_document)


def get_user_by_email(email: str):
    collections = get_collections()
    return _clean(collections["users"].find_one({"email": email}))


def get_user_by_id(user_id: str):
    collections = get_collections()
    return _clean(collections["users"].find_one({"user_id": user_id}))


def save_analysis(analysis_document: dict):
    collections = get_collections()
    collections["analyses"].insert_one(analysis_document)
    return _clean(analysis_document)


def get_last_analysis(user_id: str):
    collections = get_collections()
    cursor = collections["analyses"].find({"user_id": user_id}).sort("date", DESCENDING).limit(1)
    for document in cursor:
        return _clean(document)
    return None


def save_health_log(log_document: dict):
    collections = get_collections()
    collections["health_logs"].insert_one(log_document)
    return _clean(log_document)


def get_recent_logs(user_id: str, limit: int = 5):
    collections = get_collections()
    cursor = collections["health_logs"].find({"user_id": user_id}).sort("date", DESCENDING).limit(limit)
    return [_clean(document) for document in cursor]


def build_health_log_document(user_id: str, payload: dict):
    return {
        "user_id": user_id,
        "date": datetime.now(timezone.utc).isoformat(),
        "water_intake": payload.get("water_intake"),
        "activity": payload.get("activity", ""),
        "diet": payload.get("diet", ""),
        "sleep": payload.get("sleep"),
        "stress": payload.get("stress", ""),
        "menstrual_cycle": payload.get("menstrual_cycle", ""),
    }
