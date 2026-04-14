import uuid
from copy import deepcopy
from datetime import datetime, timezone

from pymongo import DESCENDING

from backend.db import get_collections, get_fallback_collections


KNOWN_HEALTH_PAYLOAD_FIELDS = {
    "entry_date",
    "sugar_free",
    "water_intake",
    "activity",
    "diet",
    "sleep",
    "stress",
    "menstrual_cycle",
    "menstrual_logged",
    "stool_passages",
    "stool_feel",
    "mood",
    "energy_level",
    "symptoms",
    "skin_concerns",
    "products_used",
    "medications",
    "supplements",
    "notes",
    "tags",
    "location",
    "weather",
    "humidity",
    "uv_index",
    "period_phase",
    "cycle_day",
    "sleep_quality",
    "workout_minutes",
    "source",
    "additional_context",
}


def _clean(document):
    if not document:
        return None
    cleaned = deepcopy(document)
    cleaned.pop("_id", None)
    return cleaned


def _clean_text(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _clean_list(values) -> list[str]:
    if not values:
        return []

    cleaned: list[str] = []
    for item in values:
        text = _clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _to_float_or_none(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_bool_or_none(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value

    normalized = _clean_text(value).lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None


def _mirror_to_fallback(
    collections: dict,
    collection_name: str,
    document: dict,
    query: dict | None = None,
    update: dict | None = None,
    upsert: bool = False,
    delete: bool = False,
):
    if collections.get("backend") != "mongodb":
        return

    fallback_collections = get_fallback_collections()
    target = fallback_collections[collection_name]

    if delete and query is not None:
        target.delete_many(query)
        return

    if query is not None and update is not None:
        target.update_one(query, update, upsert=upsert)
        return

    target.insert_one(_clean(document) or {})


def create_user(user_document: dict):
    collections = get_collections()
    document_to_store = deepcopy(user_document)
    collections["users"].insert_one(document_to_store)
    _mirror_to_fallback(collections, "users", document_to_store)
    return _clean(document_to_store)


def get_user_by_email(email: str):
    collections = get_collections()
    return _clean(collections["users"].find_one({"email": email}))


def get_user_by_id(user_id: str):
    collections = get_collections()
    return _clean(collections["users"].find_one({"user_id": user_id}))


def update_user_fields(user_id: str, fields: dict):
    collections = get_collections()
    now_iso = datetime.now(timezone.utc).isoformat()
    update_payload = {"$set": {**fields, "updated_at": now_iso}}
    collections["users"].update_one({"user_id": user_id}, update_payload)
    _mirror_to_fallback(collections, "users", {}, query={"user_id": user_id}, update=update_payload)
    return get_user_by_id(user_id)


def update_user_password_by_email(email: str, password_hash: str):
    collections = get_collections()
    now_iso = datetime.now(timezone.utc).isoformat()
    update_payload = {
        "$set": {
            "password_hash": password_hash,
            "updated_at": now_iso,
        }
    }
    collections["users"].update_one({"email": email}, update_payload)
    _mirror_to_fallback(collections, "users", {}, query={"email": email}, update=update_payload)
    return get_user_by_email(email)


def save_analysis(analysis_document: dict):
    collections = get_collections()
    document_to_store = deepcopy(analysis_document)
    collections["analyses"].insert_one(document_to_store)
    _mirror_to_fallback(collections, "analyses", document_to_store)
    return _clean(document_to_store)


def get_last_analysis(user_id: str):
    collections = get_collections()
    cursor = collections["analyses"].find({"user_id": user_id}).sort("date", DESCENDING).limit(1)
    for document in cursor:
        return _clean(document)
    return None


def get_recent_analyses(user_id: str, limit: int = 12):
    collections = get_collections()
    cursor = collections["analyses"].find({"user_id": user_id}).sort("date", DESCENDING).limit(limit)
    return [_clean(document) for document in cursor]


def get_analysis_by_report_id(user_id: str, report_id: str):
    collections = get_collections()
    return _clean(collections["analyses"].find_one({"user_id": user_id, "report.report_id": report_id}))


def save_health_log(log_document: dict):
    collections = get_collections()
    document_to_store = deepcopy(log_document)
    collections["health_logs"].insert_one(document_to_store)
    _mirror_to_fallback(collections, "health_logs", document_to_store)
    return _clean(document_to_store)


def get_recent_logs(user_id: str, limit: int = 5):
    collections = get_collections()
    cursor = collections["health_logs"].find({"user_id": user_id}).sort("date", DESCENDING).limit(limit)
    return [_clean(document) for document in cursor]


def delete_health_log(user_id: str, log_id: str) -> bool:
    collections = get_collections()
    query = {"user_id": user_id, "log_id": log_id}
    delete_result = collections["health_logs"].delete_many(query)
    _mirror_to_fallback(collections, "health_logs", {}, query=query, delete=True)
    return bool(getattr(delete_result, "deleted_count", 0))


def save_orchestration_event(event_document: dict):
    collections = get_collections()
    document_to_store = deepcopy(event_document)
    collections["orchestration_events"].insert_one(document_to_store)
    _mirror_to_fallback(collections, "orchestration_events", document_to_store)
    return _clean(document_to_store)


def get_recent_orchestration_events(user_id: str, limit: int = 6):
    collections = get_collections()
    cursor = collections["orchestration_events"].find({"user_id": user_id}).sort("created_at", DESCENDING).limit(limit)
    return [_clean(document) for document in cursor]


def get_latest_successful_orchestration_event(user_id: str):
    collections = get_collections()
    cursor = collections["orchestration_events"].find({"user_id": user_id, "status": "success"}).sort("created_at", DESCENDING).limit(1)
    for document in cursor:
        return _clean(document)
    return None


def build_health_log_document(user_id: str, payload: dict):
    now_iso = datetime.now(timezone.utc).isoformat()

    tags = _clean_list(payload.get("tags"))
    symptoms = _clean_list(payload.get("symptoms"))
    skin_concerns = _clean_list(payload.get("skin_concerns"))
    products_used = _clean_list(payload.get("products_used"))
    medications = _clean_list(payload.get("medications"))
    supplements = _clean_list(payload.get("supplements"))

    additional_context = payload.get("additional_context")
    if not isinstance(additional_context, dict):
        additional_context = {}

    unknown_fields = {
        key: value
        for key, value in payload.items()
        if key not in KNOWN_HEALTH_PAYLOAD_FIELDS and value is not None
    }
    merged_context = {**additional_context, **unknown_fields}

    return {
        "log_id": uuid.uuid4().hex,
        "user_id": user_id,
        "date": now_iso,
        "source": _clean_text(payload.get("source"), "manual") or "manual",
        "entry_date": _clean_text(payload.get("entry_date"), now_iso[:10]) or now_iso[:10],

        # Backward-compatible fields used by existing intelligence + UI
        "sugar_free": _to_bool_or_none(payload.get("sugar_free")),
        "water_intake": _to_float_or_none(payload.get("water_intake")),
        "activity": _clean_text(payload.get("activity")),
        "diet": _clean_text(payload.get("diet")),
        "sleep": _to_float_or_none(payload.get("sleep")),
        "stress": _clean_text(payload.get("stress")),
        "menstrual_cycle": _clean_text(payload.get("menstrual_cycle")),
        "menstrual_logged": bool(payload.get("menstrual_logged", False)),
        "stool_passages": _to_int_or_none(payload.get("stool_passages")),
        "stool_feel": _clean_text(payload.get("stool_feel")),

        # Expanded health logging payload
        "mood": _clean_text(payload.get("mood")),
        "energy_level": _to_int_or_none(payload.get("energy_level")),
        "sleep_quality": _clean_text(payload.get("sleep_quality")),
        "workout_minutes": _to_int_or_none(payload.get("workout_minutes")),
        "period_phase": _clean_text(payload.get("period_phase")),
        "cycle_day": _to_int_or_none(payload.get("cycle_day")),
        "notes": _clean_text(payload.get("notes")),
        "tags": tags,
        "symptoms": symptoms,
        "skin_concerns": skin_concerns,
        "products_used": products_used,
        "medications": medications,
        "supplements": supplements,

        "context": {
            "location": _clean_text(payload.get("location")),
            "weather": _clean_text(payload.get("weather")),
            "humidity": _to_float_or_none(payload.get("humidity")),
            "uv_index": _to_float_or_none(payload.get("uv_index")),
        },
        "additional_context": merged_context,
    }


def save_otp_verification(record: dict):
    collections = get_collections()
    query = {"email": record["email"], "purpose": record["purpose"]}
    update_payload = {"$set": record}
    collections["otp_verifications"].update_one(query, update_payload, upsert=True)
    _mirror_to_fallback(collections, "otp_verifications", {}, query=query, update=update_payload, upsert=True)


def get_otp_verification(email: str, purpose: str):
    collections = get_collections()
    return _clean(collections["otp_verifications"].find_one({"email": email, "purpose": purpose}))


def update_otp_verification(email: str, purpose: str, update: dict):
    collections = get_collections()
    collections["otp_verifications"].update_one({"email": email, "purpose": purpose}, update)
    _mirror_to_fallback(collections, "otp_verifications", {}, query={"email": email, "purpose": purpose}, update=update)


def delete_otp_verifications(email: str, purpose: str | None = None):
    collections = get_collections()
    query = {"email": email}
    if purpose:
        query["purpose"] = purpose
    collections["otp_verifications"].delete_many(query)
    _mirror_to_fallback(collections, "otp_verifications", {}, query=query, delete=True)

