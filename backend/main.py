from pathlib import Path
import shutil
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.db import get_database_status
from backend.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from backend.schemas.health import HealthLogRequest, HealthLogResponse, HealthTextRequest
from backend.schemas.response import AnalysisResponse
from backend.services.analyzer import process_skin_analysis
from backend.services.auth import authenticate_user, create_access_token, get_current_user, hash_password, to_public_user
from backend.services.nlp_parser import parse_health_text
from backend.services.storage import (
    build_health_log_document,
    create_user,
    get_last_analysis,
    get_recent_logs,
    get_user_by_email,
    save_analysis,
    save_health_log,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
PROCESSED_DIR = Path(__file__).resolve().parent / "processed"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Dermora Skin Analysis API",
    version="0.3.0",
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


@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health/db", response_model=dict)
def health_db():
    return get_database_status()


@app.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    existing_user = get_user_by_email(payload.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user_document = {
        "user_id": uuid.uuid4().hex,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "age": payload.age,
        "gender": payload.gender,
        "skin_type": payload.skin_type,
        "lifestyle": payload.lifestyle,
        "menstrual_health": payload.menstrual_health,
    }
    saved_user = create_user(user_document)
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
