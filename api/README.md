# API (FastAPI)

CloseAndKeep backend: auth, prospects, gift orders (Stripe Checkout), CSV import, public address-request links, admin fulfillment, and API keys.

## Local development

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
   - For tests: `pip install -r requirements-dev.txt`
3. Copy env template:
   - `copy .env.example .env` (Windows PowerShell)
4. Set `DATABASE_URL` in `.env` (Neon connection string for shared dev/staging, or local Postgres/SQLite for tests).
5. Run migrations:
   - `python -m alembic upgrade head`
6. Run the API:
   - `python -m uvicorn app.main:app --reload --port 8000`

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

Tests use an isolated DB and a Stripe stub (`tests/conftest.py`). They do not call live Stripe.

## Environment

See `.env.example` for the full list. Important knobs:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres (Neon) or SQLite for local/tests |
| `ADMIN_EMAILS` | Comma-separated emails granted `admin` on signup/login |
| `SESSION_COOKIE_SECURE` | Defaults **true** when `APP_ENV=production` |
| `TRUST_PROXY` | Trust first `X-Forwarded-For` hop (set on Render) |
| `REDIS_URL` | Optional shared rate-limit store (multi-worker / multi-instance) |
| `RATE_LIMIT_AUTH_*` | Login / signup / guest IP + email buckets |
| `RATE_LIMIT_ORDER_CREATE*` / `RATE_LIMIT_ORDER_CREATE_IP*` | Gift-order create limits |
| `RATE_LIMIT_API_KEY_CREATE*` | API-key create limits |
| `CSV_IMPORT_MAX_BYTES` / `CSV_IMPORT_MAX_ROWS` | Upload caps (defaults 256 KiB / 100 rows) |
| `ADDRESS_REQUEST_TTL_DAYS` | Public address-link lifetime (default 7) |
| `PASSWORD_MIN_LENGTH` | Signup minimum password length (default 12; letter + digit required) |
| `STRIPE_*` | Secret key, webhook secret, default / per-pack price IDs |
| `RESEND_*` / `ORDER_NOTIFICATION_TO` | Internal new-order email |

## Main routes

**Auth**

- `POST /auth/signup`, `POST /auth/login`, `POST /auth/guest`, `POST /auth/logout`, `GET /auth/me`

**Catalog / health**

- `GET /health`
- `GET /gifts` — cookie packs with live Stripe unit amounts

**Prospects / dashboard**

- `GET|POST /prospects`, `GET|PATCH /prospects/{id}`
- `GET /dashboard/summary`

**Gift orders**

- `POST /gift-orders` — create (+ optional Checkout URL)
- `GET /gift-orders`, `GET /gift-orders/{id}`
- `POST /gift-orders/{id}/checkout` — retry unpaid checkout
- `GET /gift-orders/import/template`, `GET /gift-orders/import/example`
- `POST /gift-orders/import` — CSV batch (size/row capped)

**Public address request** (no session; token in URL)

- `GET|POST /public/address-requests/{token}` — expires after TTL; cleared after submit/cancel/auth expiry

**Billing**

- `POST /billing/webhook` — Stripe events (`checkout.session.completed`, `payment_intent.canceled`, …)

**API keys**

- `GET|POST /api-keys`, `DELETE /api-keys/{id}`

**Integrations (Salesforce)**

- `GET /integrations` — list CRM connections
- `GET /integrations/salesforce/connect` — OAuth authorize URL
- `GET /integrations/salesforce/callback` — OAuth callback (redirects to web)
- `PATCH|DELETE /integrations/{id}` — update trigger stage / disconnect
- `POST /integrations/salesforce/events` — immediate Demo Completed webhook intake
- `POST /integrations/salesforce/sync` — poll Opportunities in trigger stage

**Admin**

- `GET /admin/gift-orders`, `GET|PATCH /admin/gift-orders/{id}`

## Payments behavior (as built)

- One-time Checkout (`mode: payment`) per order (or batch for CSV import).
- Before marking paid / capturing, reject Checkout amounts that **exceed** catalog Stripe prices (below catalog allowed for promos)
- Deferred address: authorize hold → recipient link → capture → `queued`.
- Admin cancel of an authorized order **fails closed** if Stripe cancel fails (local state unchanged, HTTP 502).
- `payment_intent.canceled` marks the order canceled and clears address tokens.

## Notes

- Session storage is database-backed (`sessions` table).
- Gift ids accepted by the API are defined in `app/config.py` (`GIFT_CATALOG`).
- Alembic migrations live in `alembic/versions/` (through `0012_salesforce_integrations`).
- Rate limits: in-process by default; set `REDIS_URL` when running multiple workers/instances.
