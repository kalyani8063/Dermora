import logging
import os
import smtplib
from email.message import EmailMessage


logger = logging.getLogger(__name__)
PLACEHOLDER_EMAIL_VALUES = {
    "your-email@gmail.com",
    "your-16-digit-app-password",
}


def _clean_email_setting(value: str) -> str:
    cleaned = value.strip()
    if cleaned in PLACEHOLDER_EMAIL_VALUES:
        return ""
    return cleaned

SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
SMTP_USERNAME = _clean_email_setting(os.getenv("EMAIL_SMTP_USERNAME", ""))
SMTP_PASSWORD = _clean_email_setting(os.getenv("EMAIL_SMTP_PASSWORD", ""))
SMTP_FROM = _clean_email_setting(os.getenv("EMAIL_FROM", SMTP_USERNAME or "no-reply@dermora.local"))
SMTP_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
SMTP_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() == "true"
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "5"))


def email_enabled() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not email_enabled():
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = to_email
    message.set_content(body)

    try:
        if SMTP_USE_SSL:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=12) as server:
                if SMTP_USERNAME and SMTP_PASSWORD:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(message)
            return True

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=12) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send email to %s using SMTP host '%s'.", to_email, SMTP_HOST or "<unset>")
        return False


def send_otp_email(email: str, otp: str, purpose: str = "verification") -> bool:
    subject = "Dermora OTP Verification"
    body = (
        f"Your Dermora OTP is: {otp}\n\n"
        f"Purpose: {purpose}\n"
        f"This OTP expires in {OTP_EXPIRE_MINUTES} minutes.\n"
        "If you did not request this, you can ignore this message."
    )
    return send_email(email, subject, body)


def send_welcome_email(email: str, name: str) -> bool:
    subject = "Welcome to Dermora"
    body = (
        f"Hi {name or 'there'},\n\n"
        "Welcome to Dermora. Your account is ready, and your skin intelligence dashboard is waiting for you.\n"
        "We are excited to support your skin-awareness journey.\n\n"
        "Team Dermora"
    )
    return send_email(email, subject, body)
