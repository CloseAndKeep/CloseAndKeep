# API (FastAPI)

This folder contains the CloseAndKeep backend API.

## Local development

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy env template:
   - `copy .env.example .env` (Windows PowerShell)
4. Set `DATABASE_URL` in `.env` (Neon connection string for shared dev/staging).
5. Run migrations:
   - `python -m alembic upgrade head`
6. Run the API:
   - `python -m uvicorn app.main:app --reload --port 8000`

## Endpoints scaffolded

- `GET /health`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`

## Notes

- Session storage is database-backed (`sessions` table).
- Alembic migration files are in `alembic/versions/`.
