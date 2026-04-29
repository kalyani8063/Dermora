from pathlib import Path
import os
import uuid
import logging

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
    ProfileUpdateRequest,
    RegisterOtpSendRequest,
    RegisterRequest,
)
from backend.schemas.health import HealthLogRequest, HealthLogResponse, HealthTextRequest
from backend.schemas.response import (
    AnalysisHistoryResponse,
    AnalyzeResultResponse,
    OrchestrationEventResponse,
    OrchestrationLatestResponse,
)
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
    delete_health_log,
    get_analysis_by_report_id,
    get_last_analysis,
    get_latest_successful_orchestration_event,
    get_recent_analyses,
    get_recent_logs,
    get_recent_orchestration_events,
    get_user_by_email,
    save_analysis,
    save_health_log,
    update_user_fields,
    update_user_password_by_email,
)
from backend.services.workflow import process_orchestration_event

BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent
FRONTEND_DIR = BASE_DIR / "frontend"
LOGGER = logging.getLogger(__name__)
UPLOAD_CHUNK_SIZE = 1024 * 1024


def _resolve_runtime_path(env_name: str, default_relative_path: str) -> Path:
    configured_path = os.getenv(env_name, "").strip()
    target = Path(configured_path) if configured_path else Path(default_relative_path)
    if target.is_absolute():
        return target
    return BASE_DIR / target


UPLOAD_DIR = _resolve_runtime_path("DERMORA_UPLOAD_DIR", "backend/uploads")
PROCESSED_DIR = _resolve_runtime_path("DERMORA_PROCESSED_DIR", "backend/processed")
REPORT_DIR = _resolve_runtime_path("DERMORA_REPORT_DIR", "backend/reports")


def _safe_process_orchestration_event(
    source_event: str,
    user_profile: dict,
    latest_scan: dict | None = None,
    previous_scan: dict | None = None,
    recent_logs: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict | None:
    try:
        return process_orchestration_event(
            source_event=source_event,
            user_profile=user_profile,
            latest_scan=latest_scan,
            previous_scan=previous_scan,
            recent_logs=recent_logs or [],
            metadata=metadata,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Could not process orchestration event '%s': %s", source_event, exc)
        return None


def _queue_health_log_orchestration(
    source_event: str,
    user_profile: dict,
    metadata: dict | None = None,
) -> None:
    user_snapshot = dict(user_profile)
    user_id = str(user_snapshot.get("user_id", "")).strip()
    if not user_id:
        return

    latest_scan = get_last_analysis(user_id)
    recent_logs = get_recent_logs(user_id, limit=8)
    _safe_process_orchestration_event(
        source_event=source_event,
        user_profile=user_snapshot,
        latest_scan=latest_scan,
        previous_scan=None,
        recent_logs=recent_logs,
        metadata=metadata,
    )


def _queue_analysis_orchestration(
    user_profile: dict,
    latest_scan: dict,
    previous_scan: dict | None,
    recent_logs: list[dict],
    metadata: dict | None = None,
) -> None:
    _safe_process_orchestration_event(
        source_event="analysis_completed",
        user_profile=dict(user_profile),
        latest_scan=latest_scan,
        previous_scan=previous_scan,
        recent_logs=recent_logs,
        metadata=metadata,
    )


def _build_orchestration_refresh_event(
    current_user: dict,
    source_event: str = "dashboard_refresh",
    metadata: dict | None = None,
) -> dict | None:
    recent_scans = get_recent_analyses(current_user["user_id"], limit=2)
    latest_scan = recent_scans[0] if recent_scans else None
    previous_scan = recent_scans[1] if len(recent_scans) > 1 else None
    recent_logs = get_recent_logs(current_user["user_id"], limit=8)
    return _safe_process_orchestration_event(
        source_event=source_event,
        user_profile=current_user,
        latest_scan=latest_scan,
        previous_scan=previous_scan,
        recent_logs=recent_logs,
        metadata=metadata,
    )


def _max_image_upload_mb() -> int:
    raw_value = os.getenv("MAX_IMAGE_UPLOAD_MB", "25").strip()
    try:
        parsed = int(raw_value)
    except ValueError:
        parsed = 25
    return max(parsed, 1)


async def _store_uploaded_image(file: UploadFile, destination: Path) -> int:
    max_upload_mb = _max_image_upload_mb()
    max_bytes = max_upload_mb * 1024 * 1024
    bytes_written = 0

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Image is too large. Upload an image up to {max_upload_mb} MB.",
                    )
                buffer.write(chunk)
    except Exception:
        if destination.exists():
            destination.unlink()
        raise
    finally:
        await file.close()

    return bytes_written


UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    LOGGER.exception("Unhandled error for %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": str(exc) or "Internal server error."})


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


@app.get("/progress", include_in_schema=False)
async def serve_progress_page() -> FileResponse:
    return serve_page("progress.html")


@app.get("/health-logs", include_in_schema=False)
async def serve_health_logs_page() -> FileResponse:
    return serve_page("health-logs.html")


@app.get("/profile", include_in_schema=False)
async def serve_profile_page() -> FileResponse:
    return serve_page("profile.html")


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


@app.put("/me", response_model=dict)
def update_me(payload: ProfileUpdateRequest, current_user=Depends(get_current_user)):
    normalized_email = normalize_email(payload.email)
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Please enter your full name.")

    existing_user = get_user_by_email(normalized_email)
    if existing_user and existing_user.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Another account already uses that email.")

    updated_user = update_user_fields(
        current_user["user_id"],
        {
            "email": normalized_email,
            "name": payload.name.strip(),
            "age": payload.age,
            "gender": payload.gender,
            "birthdate": payload.birthdate,
        },
    )
    return {"message": "Profile updated successfully.", "user": to_public_user(updated_user).model_dump()}


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

    recent_logs = get_recent_logs(current_user["user_id"], limit=8)
    latest_scan = get_last_analysis(current_user["user_id"])
    orchestration_event = _safe_process_orchestration_event(
        source_event="onboarding_skipped" if payload.skipped else "onboarding_completed",
        user_profile=updated_user,
        latest_scan=latest_scan,
        previous_scan=None,
        recent_logs=recent_logs,
        metadata={
            "skipped": bool(payload.skipped),
            "has_onboarding_log": not payload.skipped,
        },
    )

    return {
        "message": "Onboarding completed.",
        "user": to_public_user(updated_user).model_dump(),
        "orchestration_event": orchestration_event,
    }


@app.get("/health-logs-data", response_model=dict)
def health_logs_data(
    limit: int = Query(default=12, ge=1, le=180),
    current_user=Depends(get_current_user),
):
    return {"logs": get_recent_logs(current_user["user_id"], limit=limit)}


@app.post("/log-health", response_model=HealthLogResponse)
def log_health(
    payload: HealthLogRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
) -> HealthLogResponse:
    log_document = build_health_log_document(current_user["user_id"], payload.model_dump())
    saved_log = save_health_log(log_document)
    background_tasks.add_task(
        _queue_health_log_orchestration,
        source_event="health_log_saved",
        user_profile=dict(current_user),
        metadata={
            "log_id": saved_log.get("log_id", ""),
            "log_source": saved_log.get("source", ""),
        },
    )
    return HealthLogResponse(message="Health log stored.", log=saved_log, orchestration_event=None)


@app.delete("/health-logs/{log_id}", response_model=dict)
def remove_health_log(log_id: str, current_user=Depends(get_current_user)) -> dict:
    if not delete_health_log(current_user["user_id"], log_id):
        raise HTTPException(status_code=404, detail="Health log not found.")
    return {"message": "Health log deleted.", "log_id": log_id}


@app.get("/reports/{report_id}")
def download_report(report_id: str, current_user=Depends(get_current_user)) -> FileResponse:
    analysis = get_analysis_by_report_id(current_user["user_id"], report_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Report not found.")

    report = analysis.get("report") or {}
    report_path_value = report.get("path")
    report_path = Path(report_path_value) if report_path_value else Path()
    if not report_path_value or not report_path.is_file():
        raise HTTPException(status_code=404, detail="Report file is unavailable.")

    filename = report.get("filename") or "Dermora_Report.pdf"
    return FileResponse(report_path, media_type="application/pdf", filename=filename)


@app.get("/orchestration/latest", response_model=OrchestrationLatestResponse)
def read_orchestration_latest(
    limit: int = Query(default=6, ge=1, le=20),
    current_user=Depends(get_current_user),
) -> OrchestrationLatestResponse:
    latest_success = get_latest_successful_orchestration_event(current_user["user_id"])
    events = get_recent_orchestration_events(current_user["user_id"], limit=limit)
    return OrchestrationLatestResponse(latest_success=latest_success, events=events)


@app.post("/orchestration/recompute", response_model=OrchestrationEventResponse)
def recompute_orchestration(current_user=Depends(get_current_user)):
    event = _build_orchestration_refresh_event(
        current_user,
        source_event="dashboard_refresh",
        metadata={"trigger": "frontend_poll"},
    )
    if event is None:
        raise HTTPException(status_code=503, detail="Could not recompute orchestration insights right now.")
    return event


@app.get("/analysis-history", response_model=AnalysisHistoryResponse)
def read_analysis_history(
    limit: int = Query(default=24, ge=1, le=60),
    current_user=Depends(get_current_user),
) -> AnalysisHistoryResponse:
    scans = get_recent_analyses(current_user["user_id"], limit=limit)
    return AnalysisHistoryResponse(scans=scans)


@app.post("/log-text", response_model=HealthLogResponse)
def log_text(
    payload: HealthTextRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
) -> HealthLogResponse:
    parsed = parse_health_text(payload.message)
    log_document = build_health_log_document(current_user["user_id"], parsed)
    log_document["source_text"] = payload.message
    saved_log = save_health_log(log_document)
    background_tasks.add_task(
        _queue_health_log_orchestration,
        source_event="text_health_log_saved",
        user_profile=dict(current_user),
        metadata={
            "log_id": saved_log.get("log_id", ""),
            "message_length": len(payload.message.strip()),
        },
    )
    return HealthLogResponse(
        message="Text log parsed and stored.",
        log=saved_log,
        orchestration_event=None,
    )


@app.post("/analyze", response_model=AnalyzeResultResponse)
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
) -> AnalyzeResultResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    extension = Path(file.filename or "").suffix or ".jpg"
    file_id = uuid.uuid4().hex
    filename = f"{file_id}{extension}"
    destination = UPLOAD_DIR / filename
    processed_destination = PROCESSED_DIR / f"{file_id}_processed.jpg"
    acne_type_processed_destination = PROCESSED_DIR / f"{file_id}_acne_type.jpg"
    await _store_uploaded_image(file, destination)

    image_url = f"/uploads/{filename}"
    processed_image_url = f"/processed/{file_id}_processed.jpg"
    acne_type_processed_image_url = f"/processed/{file_id}_acne_type.jpg"
    previous_analysis = get_last_analysis(current_user["user_id"])
    recent_logs = get_recent_logs(current_user["user_id"])

    response, analysis_document = process_skin_analysis(
        image_path=destination,
        image_url=image_url,
        processed_image_path=processed_destination,
        processed_image_url=processed_image_url,
        acne_type_processed_image_path=acne_type_processed_destination,
        acne_type_processed_image_url=acne_type_processed_image_url,
        user_profile=current_user,
        previous_analysis=previous_analysis,
        recent_logs=recent_logs,
    )
    save_analysis(analysis_document)
    background_tasks.add_task(
        _queue_analysis_orchestration,
        user_profile=dict(current_user),
        latest_scan=analysis_document,
        previous_scan=previous_analysis,
        recent_logs=recent_logs,
        metadata={
            "file_id": file_id,
            "filename": file.filename or filename,
            "content_type": file.content_type or "",
        },
    )
    return AnalyzeResultResponse(**response, orchestration_event=None)
