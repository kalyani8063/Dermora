from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets

from fastapi import HTTPException, status

from backend.services.email_service import email_enabled, send_otp_email
from backend.services.storage import (
    delete_otp_verifications,
    get_otp_verification,
    save_otp_verification,
    update_otp_verification,
)


def _safe_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


OTP_EXPIRE_MINUTES = _safe_int_env("OTP_EXPIRE_MINUTES", 5)
OTP_RESEND_SECONDS = _safe_int_env("OTP_RESEND_SECONDS", 30)
OTP_MAX_ATTEMPTS = _safe_int_env("OTP_MAX_ATTEMPTS", 5)
EXPOSE_DEV_OTP = os.getenv("DERMORA_EXPOSE_DEV_OTP", "true").lower() == "true"
OTP_SECRET = os.getenv("OTP_SECRET_KEY", os.getenv("JWT_SECRET_KEY", "dermora-otp-secret"))


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _otp_signature(email: str, purpose: str, otp: str) -> str:
    payload = f"{email}:{purpose}:{otp}:{OTP_SECRET}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _seconds_remaining(now: datetime, future_time: datetime) -> int:
    return max(0, int((future_time - now).total_seconds()))


def _as_utc_datetime(value) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def request_otp(email: str, purpose: str) -> dict:
    normalized_email = _normalize_email(email)
    now = datetime.now(timezone.utc)

    current = get_otp_verification(normalized_email, purpose)
    if current:
        resend_after = _as_utc_datetime(current.get("resend_after"))
        if resend_after and now < resend_after:
            remaining_seconds = _seconds_remaining(now, resend_after)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining_seconds}s before requesting another OTP.",
            )

    otp = generate_otp()
    otp_signature = _otp_signature(normalized_email, purpose, otp)
    expires_at = now + timedelta(minutes=OTP_EXPIRE_MINUTES)
    resend_after = now + timedelta(seconds=OTP_RESEND_SECONDS)

    save_otp_verification(
        {
            "email": normalized_email,
            "purpose": purpose,
            "otp_signature": otp_signature,
            "expires_at": expires_at,
            "resend_after": resend_after,
            "attempts": 0,
            "verified_at": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    email_sent = send_otp_email(normalized_email, otp, purpose=purpose)
    if not email_sent and not EXPOSE_DEV_OTP and email_enabled():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP email.")

    return {
        "message": "OTP sent to your email.",
        "expires_in_seconds": OTP_EXPIRE_MINUTES * 60,
        "resend_in_seconds": OTP_RESEND_SECONDS,
        "development_code": otp if EXPOSE_DEV_OTP else None,
    }


def verify_otp(email: str, purpose: str, otp: str) -> bool:
    normalized_email = _normalize_email(email)
    normalized_otp = otp.strip()

    if len(normalized_otp) != 6 or not normalized_otp.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter the 6-digit OTP.")

    record = get_otp_verification(normalized_email, purpose)
    if not record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request a new OTP to continue.")

    now = datetime.now(timezone.utc)
    expires_at = _as_utc_datetime(record.get("expires_at"))
    if not expires_at or now > expires_at:
        delete_otp_verifications(normalized_email, purpose)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired. Request a new code.")

    attempts = int(record.get("attempts", 0))
    if attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many OTP attempts. Request a new OTP.")

    expected_signature = record.get("otp_signature", "")
    candidate_signature = _otp_signature(normalized_email, purpose, normalized_otp)
    if not hmac.compare_digest(expected_signature, candidate_signature):
        update_otp_verification(
            normalized_email,
            purpose,
            {
                "$set": {"updated_at": now},
                "$inc": {"attempts": 1},
            },
        )
        remaining = max(0, OTP_MAX_ATTEMPTS - (attempts + 1))
        if remaining == 0:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="OTP attempt limit reached. Request a new OTP.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid OTP. {remaining} attempts left.")

    update_otp_verification(
        normalized_email,
        purpose,
        {
            "$set": {
                "verified_at": now,
                "updated_at": now,
            }
        },
    )
    return True


def ensure_verified(email: str, purpose: str) -> None:
    normalized_email = _normalize_email(email)
    record = get_otp_verification(normalized_email, purpose)
    if not record or not record.get("verified_at"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verify OTP before continuing.")

    now = datetime.now(timezone.utc)
    expires_at = _as_utc_datetime(record.get("expires_at"))
    if not expires_at or now > expires_at:
        delete_otp_verifications(normalized_email, purpose)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP verification expired. Please verify again.")


def clear_otp(email: str, purpose: str) -> None:
    normalized_email = _normalize_email(email)
    delete_otp_verifications(normalized_email, purpose)
