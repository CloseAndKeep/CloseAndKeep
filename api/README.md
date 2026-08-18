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
| `ADMIN_EMAILS` | Extra emails granted `admin` on signup/login (`*@closeandkeep.com` is always admin) |
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

- `POST /auth/signup`, `POST /auth/login`, `POST /auth/verify-email`, `POST /auth/resend-verification`, `POST /auth/guest`, `POST /auth/logout`, `GET /auth/me`

**Catalog / health**

- `GET /health`
- `GET /gifts` — cookie packs with live Stripe unit amounts

**Prospects / dashboard**

- `GET|POST /prospects`, `GET|PATCH /prospects/{id}` — list accepts `q` (name/email) and `deal_status` (`open|won|lost`)
- `GET /dashboard/summary` — includes gifted vs ungifted close-rate counts
- `GET /dashboard/needs-attention` — unpaid, no-address, just-shipped (owner-scoped, capped)
- `GET|POST|PATCH|DELETE /note-templates` — per-user saved cookie-note templates (max 20)

**Gift orders**

- `POST /gift-orders` — create (+ optional Checkout URL)
- `GET /gift-orders`, `GET /gift-orders/{id}`
- `GET /gift-orders/expired-holds` — canceled address holds that can be resent
- `POST /gift-orders/{id}/resend-address` — new hold + Checkout (or monthly link)
- `POST /gift-orders/{id}/checkout` — retry unpaid checkout
- `GET /gift-orders/import/template`, `GET /gift-orders/import/example`
- `POST /gift-orders/import` — CSV batch (size/row capped)

**Public address request** (no session; token in URL)

- `GET|POST /public/address-requests/{token}` — expires after TTL; cleared after submit/cancel/auth expiry

**Billing**

- `POST /billing/webhook` — Stripe events (`checkout.session.completed`, `payment_intent.canceled`, …)

**API keys**

- `GET|POST /api-keys`, `DELETE /api-keys/{id}`

**Integrations (Salesforce + HubSpot)**

- `GET /integrations` — list CRM connections (includes `stage_recipes` + `token_status`)
- `GET /integrations/events` — last CRM journal events (stage hits + login expired); `?retryable=true` filters failed/held auto-orders
- `POST /integrations/events/{id}/retry` — retry a failed or held auto-order
- `GET /integrations/salesforce/connect` — OAuth authorize URL
- `GET /integrations/salesforce/callback` — OAuth callback (redirects to web)
- `POST /integrations/salesforce/events` — immediate stage-recipe webhook intake
- `POST /integrations/salesforce/sync` — poll Opportunities in recipe stages
- `POST /integrations/salesforce/check-setup` — advisory Cookie_* field + stage-label report
- `GET /integrations/hubspot/connect` — OAuth authorize URL
- `GET /integrations/hubspot/callback` — OAuth callback (redirects to web)
- `POST /integrations/hubspot/events` — immediate stage-recipe webhook intake
- `POST /integrations/hubspot/sync` — poll Deals in recipe stages
- `POST /integrations/hubspot/check-setup` — advisory cookie_* property + stage-label report
- `PATCH|DELETE /integrations/{id}` — update stage recipes / disconnect

**Admin**

- `GET /admin/gift-orders`, `GET|PATCH /admin/gift-orders/{id}`

## Payments behavior (as built)

- One-time Checkout (`mode: payment`) per order (or batch for CSV import).
- Before marking paid / capturing, reject Checkout amounts that **exceed** catalog Stripe prices (below catalog allowed for promos)
- Deferred address: authorize hold → recipient link → capture → `queued`.
- Admin cancel of an authorized order **fails closed** if Stripe cancel fails (local state unchanged, HTTP 502).
- `payment_intent.canceled` marks the order canceled and clears address tokens.
- Checkout already sets `allow_promotion_codes: True`. The app does **not** store a coupon code or env var; the seller types it in Stripe Checkout’s promo box.

### Test promotion code `TEST1C` (Dashboard, test mode only)

Stripe coupons are **amount off** or **percentage off**. There is no Dashboard field that sets the charge to $0.01. Percentage-off is wrong here because the 4- and 12-cookie packs have different prices and will not land on 1¢. Use a fixed **Discount amount** of `catalog_price − $0.01` (look up the live Price under **Product catalog** / **Products**). Stripe usually will not charge $0, so do not set amount-off ≥ the pack price.

One amount-off coupon cannot leave 1¢ on both packs. Prefer **Apply to specific products** = the 4-cookie product, and test with a 4-cookie order. Create a second test coupon if you also need 1¢ on the 12-pack.

1. In the Stripe Dashboard, turn on **Test mode** (toggle). Never create `TEST1C` in live mode.
2. Open **Product catalog → Coupons** (same page as **Products → Coupons**).
3. Click **+ New** / **Create a coupon**.
4. **Type:** Discount amount (fixed). **Discount amount:** pack price minus $0.01 (USD). **Duration:** once. Optionally limit with **Apply to specific products**.
5. Enable **Use customer-facing promotion codes** and set the **Code** to `TEST1C`.
6. Restrict if the Dashboard offers it: **Limit to a specific customer** (pick your existing Stripe Customer — there is no free-text email field), **Eligible for first-time order only**, and a low redemption limit.
7. Create any **live / customer** coupon as a **separate** coupon + promotion code. Never reuse `TEST1C` in live mode.

Webhooks already accept totals below catalog. See `DECISIONS.md` (promo / test codes row).

## Notes

- Session storage is database-backed (`sessions` table).
- Gift ids accepted by the API are defined in `app/config.py` (`GIFT_CATALOG`).
- Alembic migrations live in `alembic/versions/` (through `0028_notify_dead_letter`).
- Rate limits: in-process by default; set `REDIS_URL` when running multiple workers/instances.
- Ops new-order Resend failures for paid/authorized/owed orders are retried by `POST /internal/jobs/notify-dead-letters` (or `python -m app.jobs.notify_dead_letters`) using `CRON_SECRET`.
- `REGIFT_WINDOW_DAYS` (default 90) skips a second auto-order to the same person inside that window.
