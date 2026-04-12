# Dermora Starter

AI-powered skin and health intelligence starter with a modular FastAPI backend and a mobile-first frontend.

## Run

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`.

For local development with environment variables, copy `.env.example` to `.env`, fill in your real values, and run:

```bash
uvicorn backend.main:app --reload --env-file .env
```

## OTP Email Setup

To send real OTP emails instead of showing the development code on screen:

1. Copy `.env.example` to `.env`
2. Replace the email placeholders with your real SMTP credentials
3. Start the server with `--env-file .env`

For Gmail:

- `EMAIL_SMTP_HOST=smtp.gmail.com`
- `EMAIL_SMTP_PORT=587`
- `EMAIL_SMTP_USERNAME=your-email@gmail.com`
- `EMAIL_SMTP_PASSWORD=your Google App Password`
- `EMAIL_FROM=your-email@gmail.com`
- `EMAIL_USE_TLS=true`
- `EMAIL_USE_SSL=false`
- `DERMORA_EXPOSE_DEV_OTP=false` once SMTP is working

Local setup tip:

- Keep `DERMORA_EXPOSE_DEV_OTP=true` while SMTP is not configured yet so the API can return the development OTP in the response instead of failing registration.

Important:

- Do not commit your real `.env`
- For deployment, add the same variables in your hosting provider's environment settings instead of creating a `.env` file on the server
- In production, set a strong `JWT_SECRET_KEY`

## MongoDB

Set one of the following to connect to MongoDB:

- `MONGODB_URI` (primary)
- `MONGODB_URI_FALLBACK` (optional fallback, useful for non-SRV/direct hosts)
- `MONGO_URI` (legacy alias)

Optional connection tuning:

- `MONGODB_DB` (default: `dermora`)
- `MONGODB_APP_NAME` (default: `DermoraApp`)
- `MONGODB_SERVER_SELECTION_TIMEOUT_MS` (default: `3500`)
- `MONGODB_CONNECT_TIMEOUT_MS` (default: `3500`)
- `MONGODB_SOCKET_TIMEOUT_MS` (default: `6500`)
- `MONGODB_RETRY_INTERVAL_SECONDS` (default: `30`, set `0` to retry every call while in memory fallback)

Health logs, users, and analyses are indexed automatically when MongoDB is available.

Use `GET /health/db` to inspect the active backend (`mongodb` or `memory`) and connection diagnostics.

If MongoDB cannot be reached, the app falls back to an in-memory store so development can continue.

## Health Log Schema

`POST /log-health` now supports richer optional fields beyond the core fields (`water_intake`, `sleep`, `stress`, `activity`, `diet`, `menstrual_cycle`), including:

- `mood`, `energy_level`, `sleep_quality`, `workout_minutes`
- `symptoms`, `skin_concerns`, `tags`
- `products_used`, `medications`, `supplements`
- `location`, `weather`, `humidity`, `uv_index`
- `period_phase`, `cycle_day`, `notes`, `source`, `additional_context`

Unknown extra fields are preserved under `additional_context` for future extensibility.

## JWT

Set `JWT_SECRET_KEY` in production to a value that is at least 32 bytes long to replace the development secret.

## ML swap point

When you are ready to integrate a real model, replace the placeholder logic in `backend/services/ml_model.py`. The rest of the app is designed to stay unchanged.

