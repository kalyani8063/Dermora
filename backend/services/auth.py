from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.schemas.auth import UserProfile
from backend.services.security_settings import DEFAULT_JWT_SECRET, resolve_secret
from backend.services.storage import get_user_by_email, get_user_by_id

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
SECRET_KEY = resolve_secret("JWT_SECRET_KEY", DEFAULT_JWT_SECRET, label="JWT secret")
security = HTTPBearer(auto_error=False)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password_legacy_pbkdf2(password: str, stored_password: str) -> bool:
    try:
        salt, expected_hash = stored_password.split("$", maxsplit=1)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return hmac.compare_digest(digest.hex(), expected_hash)


def verify_password(password: str, stored_password: str) -> bool:
    if not stored_password:
        return False

    if stored_password.startswith("$2a$") or stored_password.startswith("$2b$") or stored_password.startswith("$2y$"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_password.encode("utf-8"))
        except ValueError:
            return False

    return _verify_password_legacy_pbkdf2(password, stored_password)


def authenticate_user(email: str, password: str):
    user = get_user_by_email(normalize_email(email))
    if not user or not verify_password(password, user.get("password_hash", "")):
        return None
    return user


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def to_public_user(user: dict) -> UserProfile:
    return UserProfile(
        user_id=user["user_id"],
        email=user["email"],
        name=user.get("name", ""),
        age=user.get("age"),
        gender=user.get("gender", ""),
        birthdate=user.get("birthdate"),
        skin_type=user.get("skin_type", ""),
        lifestyle=user.get("lifestyle", {}),
        menstrual_health=user.get("menstrual_health", {}),
        onboarding_completed=bool(user.get("onboarding_completed", False)),
        acne_type=user.get("acne_type", []),
        stress_level=user.get("stress_level", ""),
        hormonal_issues=user.get("hormonal_issues", ""),
        diet_type=user.get("diet_type", ""),
        activity_level=user.get("activity_level", ""),
    )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from error

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user
