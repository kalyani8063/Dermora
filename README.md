# Dermora

Dermora is a full-stack skin health intelligence platform that combines facial image analysis with structured lifestyle tracking. It is designed to help users monitor visible skin concerns, capture daily health context, and review results through a single web dashboard.

The project uses a FastAPI backend, a lightweight mobile-friendly frontend, MongoDB-backed persistence with in-memory fallback, and a dual-model computer vision pipeline:

- a region detector for broader facial concern areas
- an acne-type detector for lesion-level classification

## Core Capabilities

- Secure user registration with email OTP verification
- Login, password reset, JWT-based protected routes, and profile management
- Onboarding flow for acne type, stress, hormonal issues, diet, and activity
- Daily health logging for hydration, sleep, stress, diet, activity, mood, menstrual context, symptoms, products, medications, supplements, and more
- Natural-language health log parsing through a text-entry workflow
- Facial analysis with:
  - lesion detection from the acne-type model
  - broader region detection from a secondary model
  - MediaPipe face landmark extraction
  - facial zone mapping
  - hyperpigmentation contour estimation
- Multi-view dashboard overlays for:
  - Everything
  - Region Detected
  - Acne Type
  - Facial Mesh
  - Hyperpigmentation Zones
- Camera capture and image upload from the dashboard
- MongoDB persistence with automatic fallback to an in-memory store for development continuity

## Architecture

Dermora is organized as a simple frontend + API backend application.

### Frontend

- Plain HTML, CSS, and JavaScript
- Multi-page flow for landing, login, registration, dashboard, health logs, reset password, and profile
- Dashboard visualization layer for image previews, overlays, and analysis switching

### Backend

- FastAPI application serving both API endpoints and frontend pages
- Modular services for authentication, OTP, email, storage, NLP parsing, ML inference, and face analysis
- Pydantic schemas for request and response validation

### Data and Inference Flow

1. A user uploads or captures a face image.
2. The backend runs:
   - the region detector
   - the acne-type detector
   - MediaPipe-based face landmark analysis
3. Acne-type detections are treated as the primary lesion source for counts and zone mapping.
4. The backend returns processed overlays, lesion metadata, region metadata, pigmentation contours, and facial zone information.
5. The frontend renders different overlay modes on the dashboard.
6. Health logs are stored alongside analyses to support broader skin-health context.

## Tech Stack

### Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- PyJWT
- bcrypt
- pymongo

### Computer Vision and ML

- Ultralytics YOLO
- OpenCV
- MediaPipe
- NumPy

### Frontend

- HTML5
- CSS3
- Vanilla JavaScript

### Reporting and Utilities

- ReportLab
- python-multipart
- python-dotenv

## Project Structure

```text
Dermora/
├── backend/
│   ├── main.py
│   ├── db.py
│   ├── models/
│   ├── schemas/
│   └── services/
├── frontend/
│   ├── app.js
│   ├── styles.css
│   ├── dashboard.html
│   ├── health-logs.html
│   ├── login.html
│   ├── profile.html
│   ├── register.html
│   └── reset-password.html
├── requirements.txt
└── README.md
```

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
uvicorn backend.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

To run with environment variables from a local file:

```bash
uvicorn backend.main:app --reload --env-file .env
```

## Environment Configuration

Copy `.env.example` to `.env` and update values for your environment.

### Authentication and Email

Recommended keys:

```env
JWT_SECRET_KEY=change-this-in-production-with-at-least-32-bytes
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=your-email@gmail.com
EMAIL_SMTP_PASSWORD=your-16-digit-app-password
EMAIL_FROM=your-email@gmail.com
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DERMORA_EXPOSE_DEV_OTP=true
```

Notes:

- Keep `DERMORA_EXPOSE_DEV_OTP=true` for local development if SMTP is not configured.
- Set it to `false` once real email delivery is working.
- Never commit your real `.env`.

### MongoDB

Supported variables:

- `MONGODB_URI`
- `MONGODB_URI_FALLBACK`
- `MONGO_URI`
- `MONGODB_DB`
- `MONGODB_APP_NAME`
- `MONGODB_SERVER_SELECTION_TIMEOUT_MS`
- `MONGODB_CONNECT_TIMEOUT_MS`
- `MONGODB_SOCKET_TIMEOUT_MS`
- `MONGODB_RETRY_INTERVAL_SECONDS`

Dermora automatically falls back to an in-memory datastore if MongoDB is unavailable, which keeps local development unblocked.

You can inspect the active backend with:

```text
GET /health/db
```

## Local Model Setup

Dermora expects model files under `backend/models/`.

Recommended local setup:

- `backend/models/best.pt`
  Region detector
- `backend/models/acne_type.pt`
  Acne-type detector
- `backend/models/face_landmarker.task`
  MediaPipe face landmark model

Recommended environment variables:

```env
DERMORA_MODEL_PATH=models/best.pt
DERMORA_ACNE_TYPE_MODEL_PATH=models/acne_type.pt
DERMORA_ACNE_TYPE_MODEL_CONFIDENCE=0.25
DERMORA_FACE_LANDMARKER_MODEL=backend/models/face_landmarker.task
```

Important:

- `.pt` files are intentionally ignored by Git in this repository.
- This keeps large model binaries out of normal GitHub history.
- If you need to distribute large weights, use Git LFS or external storage.

See [backend/models/README.md](backend/models/README.md) for local model file notes.

## Analysis Output

`POST /analyze` returns the data required for both UI rendering and downstream storage, including:

- primary lesion boxes
- lesion count
- lesion source
- region boxes and region count
- processed overlay image URL
- acne-type processed image URL
- acne-type detection metadata and counts
- face detection status
- face landmarks
- zone geometry and zone counts
- pigmentation contour geometry
- pigmentation coverage and severity

In the current pipeline:

- acne-type detections are treated as lesions
- broader region detections remain available as separate region metadata

## Key API Routes

### Auth and Account

- `POST /auth/register/send-otp`
- `POST /auth/register/verify-otp`
- `POST /register`
- `POST /login`
- `GET /me`
- `PUT /me`
- `POST /auth/password-reset/send-otp`
- `POST /auth/password-reset/verify-otp`
- `POST /auth/password-reset/confirm`

### User Workflow

- `POST /onboarding`
- `GET /health-logs-data`
- `POST /log-health`
- `POST /log-text`
- `POST /analyze`
- `GET /reports/{report_id}`

### Frontend Pages

- `/`
- `/login`
- `/register`
- `/reset-password`
- `/dashboard`
- `/health-logs`
- `/profile`

## Health Logging Model

The health log pipeline supports both structured form input and natural-language input. Stored fields can include:

- water intake
- sleep
- stress
- activity
- diet
- sugar-free status
- menstrual context
- stool tracking
- mood and energy
- symptoms and skin concerns
- products, medications, and supplements
- notes, tags, location, weather, humidity, and UV index

Unknown extra fields are preserved under `additional_context` for future extensibility.

## Security Notes

- Use a strong `JWT_SECRET_KEY` in production.
- Do not commit real SMTP credentials or deployment secrets.
- OTP verification is rate-limited and time-bound.
- Passwords are hashed using `bcrypt`.

## Development Notes

- Uploaded images are stored under `backend/uploads/`
- Processed images are stored under `backend/processed/`
- Reports are stored under `backend/reports/`
- Runtime-generated assets and local model binaries are excluded from version control where appropriate

## Future Extension Points

The codebase already contains modular entry points for:

- richer recommendation generation
- report generation workflows
- external workflow automation
- future model swaps without needing to redesign the frontend

## License

This project is distributed under the repository's existing license. See `LICENSE` for details.
