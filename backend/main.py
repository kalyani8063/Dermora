from pathlib import Path
import shutil
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.db import get_database_status
from backend.schemas.auth import (
    AuthResponse,
    EmailOtpRequest,
    LoginRequest,
    OnboardingRequest,
    OtpRequestResponse,
    OtpVerifyRequest,
    PasswordResetConfirmRequest,
    RegisterOtpSendRequest,
    RegisterRequest,
)
from backend.schemas.health import HealthLogRequest, HealthLogResponse, HealthTextRequest
from backend.schemas.response import AnalysisResponse
from backend.services.analyzer import process_skin_analysis
from backend.services.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    normalize_email,
    to_public_user,
)
from backend.services.email_service import send_welcome_email
from backend.services.nlp_parser import parse_health_text
from backend.services.otp_service import clear_otp, ensure_verified, request_otp, verify_otp
from backend.services.storage import (
    build_health_log_document,
    create_user,
    get_last_analysis,
    get_recent_logs,
    get_user_by_email,
    save_analysis,
    save_health_log,
    update_user_fields,
    update_user_password_by_email,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
PROCESSED_DIR = Path(__file__).resolve().parent / "processed"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Dermora Skin Analysis API",
    version="0.5.0",
    description="AI-powered skin and health intelligence starter with modular services.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/processed", StaticFiles(directory=PROCESSED_DIR), name="processed")


def serve_page(filename: str) -> FileResponse:
    return FileResponse(FRONTEND_DIR / filename)


@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    return serve_page("index.html")


@app.get("/login", include_in_schema=False)
async def serve_login_page() -> FileResponse:
    return serve_page("login.html")


@app.get("/register", include_in_schema=False)
async def serve_register_page() -> FileResponse:
    return serve_page("register.html")


@app.get("/reset-password", include_in_schema=False)
async def serve_reset_password_page() -> FileResponse:
    return serve_page("reset-password.html")


@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard_page() -> FileResponse:
    return serve_page("dashboard.html")


@app.get("/health-logs", include_in_schema=False)
async def serve_health_logs_page() -> FileResponse:
    return serve_page("health-logs.html")


@app.get("/health/db", response_model=dict)
def health_db():
    return get_database_status()


@app.post("/auth/register/send-otp", response_model=OtpRequestResponse)
def auth_register_send_otp(payload: RegisterOtpSendRequest) -> OtpRequestResponse:
    normalized_email = normalize_email(payload.email)
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Please enter your full name.")
    if get_user_by_email(normalized_email):
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    otp_payload = request_otp(normalized_email, purpose="register")
    return OtpRequestResponse(**otp_payload)


@app.post("/auth/register/verify-otp", response_model=dict)
def auth_register_verify_otp(payload: OtpVerifyRequest):
    verify_otp(payload.email, purpose="register", otp=payload.otp)
    return {"message": "OTP verified. You can now complete registration."}


@app.post("/auth/password-reset/send-otp", response_model=OtpRequestResponse)
def auth_password_reset_send_otp(payload: EmailOtpRequest) -> OtpRequestResponse:
    normalized_email = normalize_email(payload.email)
    user = get_user_by_email(normalized_email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found for that email.")

    otp_payload = request_otp(normalized_email, purpose="password_reset")
    return OtpRequestResponse(**otp_payload)


@app.post("/auth/password-reset/verify-otp", response_model=dict)
def auth_password_reset_verify_otp(payload: OtpVerifyRequest):
    verify_otp(payload.email, purpose="password_reset", otp=payload.otp)
    return {"message": "OTP verified. You can now set a new password."}


@app.post("/auth/password-reset/confirm", response_model=dict)
def auth_password_reset_confirm(payload: PasswordResetConfirmRequest):
    normalized_email = normalize_email(payload.email)
    user = get_user_by_email(normalized_email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found for that email.")

    if len(payload.new_password.strip()) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    ensure_verified(normalized_email, purpose="password_reset")
    update_user_password_by_email(normalized_email, hash_password(payload.new_password))
    clear_otp(normalized_email, purpose="password_reset")
    return {"message": "Password updated successfully."}


@app.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    normalized_email = normalize_email(payload.email)
    existing_user = get_user_by_email(normalized_email)
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    if len(payload.password.strip()) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    ensure_verified(normalized_email, purpose="register")

    user_document = {
        "user_id": uuid.uuid4().hex,
        "email": normalized_email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "age": payload.age,
        "gender": payload.gender,
        "birthdate": payload.birthdate,
        "skin_type": payload.skin_type,
        "lifestyle": payload.lifestyle,
        "menstrual_health": payload.menstrual_health,
        "onboarding_completed": False,
        "acne_type": [],
        "stress_level": "",
        "hormonal_issues": "",
        "diet_type": "",
        "activity_level": "",
    }
    saved_user = create_user(user_document)
    clear_otp(normalized_email, purpose="register")

    # Welcome email is best-effort so registration is not blocked if SMTP is unavailable.
    try:
        send_welcome_email(normalized_email, payload.name)
    except Exception:
        pass

    token = create_access_token(saved_user["user_id"])
    return AuthResponse(access_token=token, user=to_public_user(saved_user))


@app.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    user = authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user["user_id"])
    return AuthResponse(access_token=token, user=to_public_user(user))


@app.get("/me", response_model=dict)
def me(current_user=Depends(get_current_user)):
    return {"user": to_public_user(current_user).model_dump()}


@app.post("/onboarding", response_model=dict)
def complete_onboarding(payload: OnboardingRequest, current_user=Depends(get_current_user)):
    onboarding_data = {
        "onboarding_completed": True,
        "acne_type": payload.acne_type,
        "stress_level": payload.stress_level,
        "hormonal_issues": payload.hormonal_issues,
        "diet_type": payload.diet_type,
        "activity_level": payload.activity_level,
    }
    updated_user = update_user_fields(current_user["user_id"], onboarding_data)

    if not payload.skipped:
        onboarding_log = build_health_log_document(
            current_user["user_id"],
            {
                "stress": payload.stress_level,
                "activity": payload.activity_level,
                "diet": payload.diet_type,
                "symptoms": payload.acne_type,
                "tags": ["onboarding"],
                "source": "onboarding_quiz",
                "additional_context": {"hormonal_issues": payload.hormonal_issues},
            },
        )
        save_health_log(onboarding_log)

    return {
        "message": "Onboarding completed.",
        "user": to_public_user(updated_user).model_dump(),
    }


@app.get("/health-logs-data", response_model=dict)
def health_logs_data(current_user=Depends(get_current_user)):
    return {"logs": get_recent_logs(current_user["user_id"], limit=12)}


@app.post("/log-health", response_model=HealthLogResponse)
def log_health(payload: HealthLogRequest, current_user=Depends(get_current_user)) -> HealthLogResponse:
    log_document = build_health_log_document(current_user["user_id"], payload.model_dump())
    saved_log = save_health_log(log_document)
    return HealthLogResponse(message="Health log stored.", log=saved_log)


@app.post("/log-text", response_model=HealthLogResponse)
def log_text(payload: HealthTextRequest, current_user=Depends(get_current_user)) -> HealthLogResponse:
    parsed = parse_health_text(payload.message)
    log_document = build_health_log_document(current_user["user_id"], parsed)
    log_document["source_text"] = payload.message
    saved_log = save_health_log(log_document)
    return HealthLogResponse(message="Text log parsed and stored.", log=saved_log)


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(file: UploadFile = File(...), current_user=Depends(get_current_user)) -> AnalysisResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    extension = Path(file.filename or "").suffix or ".jpg"
    file_id = uuid.uuid4().hex
    filename = f"{file_id}{extension}"
    destination = UPLOAD_DIR / filename
    processed_destination = PROCESSED_DIR / f"{file_id}_processed.jpg"

    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_url = f"/uploads/{filename}"
    processed_image_url = f"/processed/{file_id}_processed.jpg"
    previous_analysis = get_last_analysis(current_user["user_id"])
    recent_logs = get_recent_logs(current_user["user_id"])

    response, analysis_document = process_skin_analysis(
        image_path=destination,
        image_url=image_url,
        processed_image_path=processed_destination,
        processed_image_url=processed_image_url,
        user_profile=current_user,
        previous_analysis=previous_analysis,
        recent_logs=recent_logs,
    )
    save_analysis(analysis_document)
    return response
