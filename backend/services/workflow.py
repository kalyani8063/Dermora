from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib import error, request

from backend.services.storage import save_orchestration_event

LOGGER = logging.getLogger(__name__)

N8N_ENABLED = os.getenv("N8N_ENABLED", "false").strip().lower() == "true"
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()
N8N_AUTH_HEADER = os.getenv("N8N_AUTH_HEADER", "").strip()
N8N_AUTH_HEADER_NAME = os.getenv("N8N_AUTH_HEADER_NAME", "").strip() or "Authorization"
N8N_TIMEOUT_SECONDS = max(int(os.getenv("N8N_TIMEOUT_SECONDS", "10") or "10"), 1)
N8N_RETRY_ATTEMPTS = max(int(os.getenv("N8N_RETRY_ATTEMPTS", "3") or "3"), 1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        normalized = []
        for item in value:
            text = str(item).strip()
            if text:
                normalized.append(text)
        return normalized
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _flatten_nested_dicts(payload: Any, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 4:
        return []
    if isinstance(payload, dict):
        nested = [payload]
        for key in ("json", "body", "data", "output", "result", "response"):
            if key in payload:
                nested.extend(_flatten_nested_dicts(payload.get(key), depth + 1))
        return nested
    if isinstance(payload, list):
        nested: list[dict[str, Any]] = []
        for item in payload[:5]:
            nested.extend(_flatten_nested_dicts(item, depth + 1))
        return nested
    return []


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _extract_nested_text_list(payload: Any, *keys: str) -> list[str]:
    values: list[str] = []
    for candidate in _flatten_nested_dicts(payload):
        for key in keys:
            if key in candidate:
                values.extend(_normalize_text_list(candidate.get(key)))
    return _dedupe_preserve_order(values)


def _extract_nested_summary(payload: Any) -> str:
    for candidate in _flatten_nested_dicts(payload):
        for key in ("summary", "message", "text"):
            value = candidate.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
    return ""


def _normalize_n8n_error_message(message: str) -> str:
    normalized = str(message or "").strip()
    if "not registered" in normalized and "webhook" in normalized.lower():
        return (
            "The configured n8n production webhook is not active or the URL is wrong. "
            "Activate the workflow in n8n and confirm the production webhook URL in backend/.env."
        )
    return normalized


def _sanitize_user_profile(user_profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "anonymized_user_id": user_profile.get("user_id", ""),
        "age": user_profile.get("age"),
        "gender": user_profile.get("gender", ""),
        "skin_type": user_profile.get("skin_type", ""),
        "acne_type": list(user_profile.get("acne_type", []) or []),
        "stress_level": user_profile.get("stress_level", ""),
        "diet_type": user_profile.get("diet_type", ""),
        "activity_level": user_profile.get("activity_level", ""),
    }


def _active_zones(zone_counts: dict[str, Any]) -> list[dict[str, Any]]:
    zones = [
        {
            "zone": str(zone_name),
            "count": int(count or 0),
        }
        for zone_name, count in (zone_counts or {}).items()
    ]
    zones = [zone for zone in zones if zone["count"] > 0]
    zones.sort(key=lambda item: item["count"], reverse=True)
    return zones[:3]


def _sanitize_scan(scan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not scan:
        return None

    return {
        "date": scan.get("date", ""),
        "image_url": scan.get("image_url", ""),
        "processed_image_url": scan.get("processed_image_url", ""),
        "acne_count": int(scan.get("acne_count", 0) or 0),
        "lesion_source": scan.get("lesion_source", ""),
        "region_count": int(scan.get("region_count", 0) or 0),
        "coverage_percentage": float(scan.get("coverage_percentage", 0) or 0),
        "pigmentation_severity": scan.get("pigmentation_severity", ""),
        "face_detected": bool(scan.get("face_detected", False)),
        "active_zones": _active_zones(scan.get("zone_counts", {})),
        "zone_counts": scan.get("zone_counts", {}) or {},
        "acne_type_counts": scan.get("acne_type_counts", {}) or {},
        "acne_type_available": bool(scan.get("acne_type_available", False)),
    }


def _sanitize_log(log: dict[str, Any]) -> dict[str, Any]:
    return {
        "log_id": log.get("log_id", ""),
        "date": log.get("date", ""),
        "entry_date": log.get("entry_date", ""),
        "source": log.get("source", ""),
        "water_intake": log.get("water_intake"),
        "sugar_free": log.get("sugar_free"),
        "activity": log.get("activity", ""),
        "diet": log.get("diet", ""),
        "sleep": log.get("sleep"),
        "stress": log.get("stress", ""),
        "mood": log.get("mood", ""),
        "energy_level": log.get("energy_level"),
        "symptoms": list(log.get("symptoms", []) or []),
        "skin_concerns": list(log.get("skin_concerns", []) or []),
        "tags": list(log.get("tags", []) or []),
        "notes": log.get("notes", ""),
    }


def build_orchestration_payload(
    source_event: str,
    user_profile: dict[str, Any],
    latest_scan: dict[str, Any] | None,
    previous_scan: dict[str, Any] | None,
    recent_logs: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sanitized_latest_scan = _sanitize_scan(latest_scan)
    sanitized_previous_scan = _sanitize_scan(previous_scan)
    sanitized_logs = [_sanitize_log(log) for log in recent_logs[:8]]

    derived_metrics = {
        "acne_count": int((latest_scan or {}).get("acne_count", 0) or 0),
        "pigmentation_coverage": float((latest_scan or {}).get("coverage_percentage", 0) or 0),
        "active_facial_zones": _active_zones((latest_scan or {}).get("zone_counts", {})),
        "recent_log_count": len(sanitized_logs),
    }

    return {
        "timestamp": _now_iso(),
        "source_event": source_event,
        "metadata": metadata or {},
        "user": _sanitize_user_profile(user_profile),
        "latest_scan": sanitized_latest_scan,
        "previous_scan": sanitized_previous_scan,
        "recent_health_logs": sanitized_logs,
        "derived_metrics": derived_metrics,
    }


def _build_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if not N8N_AUTH_HEADER:
        return headers

    if ":" in N8N_AUTH_HEADER and not N8N_AUTH_HEADER.lower().startswith(("bearer ", "basic ")):
        header_name, header_value = N8N_AUTH_HEADER.split(":", 1)
        headers[header_name.strip() or N8N_AUTH_HEADER_NAME] = header_value.strip()
        return headers

    headers[N8N_AUTH_HEADER_NAME] = N8N_AUTH_HEADER
    return headers


def _parse_response_body(response_body: str) -> dict[str, Any]:
    if not response_body.strip():
        return {}

    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError:
        return {"raw_text": response_body}

    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return {"data": parsed}
    return {"data": parsed}


def send_to_n8n(payload: dict[str, Any]) -> dict[str, Any]:
    if not N8N_ENABLED:
        return {
            "status": "disabled",
            "attempts": 0,
            "response_payload": {},
            "error_message": "N8N orchestration is disabled.",
        }

    if not N8N_WEBHOOK_URL:
        return {
            "status": "failed",
            "attempts": 0,
            "response_payload": {},
            "error_message": "N8N_WEBHOOK_URL is not configured.",
        }

    encoded_payload = json.dumps(payload).encode("utf-8")
    headers = _build_headers()
    last_error_message = ""

    for attempt in range(1, N8N_RETRY_ATTEMPTS + 1):
        try:
            webhook_request = request.Request(
                N8N_WEBHOOK_URL,
                data=encoded_payload,
                headers=headers,
                method="POST",
            )
            with request.urlopen(webhook_request, timeout=N8N_TIMEOUT_SECONDS) as response:
                raw_body = response.read().decode("utf-8", errors="replace")
                return {
                    "status": "success",
                    "attempts": attempt,
                    "response_payload": _parse_response_body(raw_body),
                    "error_message": "",
                }
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            if response_body.strip():
                parsed_error = _parse_response_body(response_body)
                readable_error = _extract_nested_summary(parsed_error) or response_body or exc.reason
                last_error_message = f"HTTP {exc.code}: {_normalize_n8n_error_message(readable_error)}"
            else:
                last_error_message = f"HTTP {exc.code}: {_normalize_n8n_error_message(str(exc.reason or 'Request failed.'))}"
        except Exception as exc:  # noqa: BLE001
            last_error_message = _normalize_n8n_error_message(str(exc))

        LOGGER.warning("n8n orchestration attempt %s failed: %s", attempt, last_error_message)
        if attempt < N8N_RETRY_ATTEMPTS:
            time.sleep(0.6 * attempt)

    return {
        "status": "failed",
        "attempts": N8N_RETRY_ATTEMPTS,
        "response_payload": {},
        "error_message": last_error_message or "Unknown n8n orchestration failure.",
    }


def _extract_summary(response_payload: dict[str, Any]) -> str:
    return _extract_nested_summary(response_payload)


def process_orchestration_event(
    source_event: str,
    user_profile: dict[str, Any],
    latest_scan: dict[str, Any] | None = None,
    previous_scan: dict[str, Any] | None = None,
    recent_logs: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    recent_logs = recent_logs or []
    payload = build_orchestration_payload(
        source_event=source_event,
        user_profile=user_profile,
        latest_scan=latest_scan,
        previous_scan=previous_scan,
        recent_logs=recent_logs,
        metadata=metadata,
    )
    delivery_result = send_to_n8n(payload)
    response_payload = delivery_result.get("response_payload", {}) or {}

    event_document = {
        "event_id": uuid.uuid4().hex,
        "user_id": user_profile.get("user_id", ""),
        "source_event": source_event,
        "status": delivery_result.get("status", "failed"),
        "created_at": _now_iso(),
        "attempts": int(delivery_result.get("attempts", 0) or 0),
        "summary": _extract_summary(response_payload),
        "error_message": _normalize_n8n_error_message(str(delivery_result.get("error_message", "") or "")),
        "insights": _extract_nested_text_list(response_payload, "insights"),
        "recommendations": _extract_nested_text_list(response_payload, "recommendations", "next_steps"),
        "correlations": _extract_nested_text_list(response_payload, "correlations"),
        "alerts": _extract_nested_text_list(response_payload, "alerts", "warnings"),
        "request_payload": payload,
        "response_payload": response_payload,
    }
    saved_event = save_orchestration_event(event_document)

    if saved_event.get("status") != "success":
        LOGGER.warning(
            "Stored orchestration event %s with status %s: %s",
            saved_event.get("event_id"),
            saved_event.get("status"),
            saved_event.get("error_message", ""),
        )

    return saved_event
