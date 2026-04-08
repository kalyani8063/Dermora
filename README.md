# Dermora Starter

AI-powered skin and health intelligence starter with a modular FastAPI backend and a mobile-first frontend.

## Run

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`.

## MongoDB

Set `MONGODB_URI` to connect to MongoDB. If it is not set or cannot be reached, the app falls back to an in-memory store so the starter still runs locally.

## JWT

Set `JWT_SECRET_KEY` in production to replace the development secret.

## ML swap point

When you are ready to integrate a real model, replace the placeholder logic in `backend/services/ml_model.py`. The rest of the app is designed to stay unchanged.
