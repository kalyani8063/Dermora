import os
import warnings


MIN_HS256_KEY_BYTES = 32
DEFAULT_JWT_SECRET = "dermora-development-secret-key-2026-strong"
DEFAULT_OTP_SECRET = "dermora-otp-development-secret-key-2026-strong"
PLACEHOLDER_SECRETS = {
    "",
    "change-this-in-production",
    "your-super-secret-key-change-this",
}


def resolve_secret(env_name: str, default_value: str, *, label: str) -> str:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value or raw_value in PLACEHOLDER_SECRETS:
        return default_value

    if len(raw_value.encode("utf-8")) < MIN_HS256_KEY_BYTES:
        warnings.warn(
            f"{label} is shorter than the recommended {MIN_HS256_KEY_BYTES} bytes for HS256.",
            RuntimeWarning,
            stacklevel=2,
        )
    return raw_value
