# DECISIONS.md

# CloseAndKeep - Technical decisions

Last updated: 2026-07-21

## Architecture direction

- Hosting model: **split hosting**
- Frontend: **Next.js 14** on **Vercel**
- Backend: **FastAPI (Python)**
- API hosting: **Render** (primary choice for MVP simplicity)
- Database: **Neon Postgres**
- Email provider: **Resend**
- Auth approach: **app-managed sessions** (server-side sessions via secure HttpOnly cookie)
- Billing model: **one-time payment per gift order** (Stripe Checkout in `mode: payment`). **Subscriptions are not used in the MVP.**

## Billing model (locked: one-time payments)

CloseAndKeep charges **per gift order**, not via subscription. When a user submits a gift order, the API creates a Stripe Checkout session in `mode: payment`; the order stays
`pending_payment` until Stripe confirms payment (via webhook, with a fetch-time fallback that
re-checks the Checkout session), at which point it moves to `queued` for fulfillment.

- No subscription tiers, no weekly order caps, no billing portal are in scope for the MVP.
- The unused `users.subscription_status` / `users.subscription_plan` scaffolding columns were
  removed (migration `0007`). `users.stripe_customer_id` is kept and is now populated the first
  time a user checks out, so their orders group under one Stripe customer. Reintroduce
  subscription columns if/when a recurring plan is introduced.

### Authorize-then-capture (recipient address deferred)

When the seller requests the recipient address (`request_recipient_address`), Checkout uses
manual capture (`defer_capture`). After Checkout completes:

- Local `payment_status` becomes `authorized` (card hold; not captured yet).
- Order status is `no_address` until the recipient submits via `/public/address-requests/{token}`.
- Capture runs after a valid address is submitted; then the order moves to `queued`.

## Security and payments hardening (2026-07)

Locked behaviors after medium-severity review:

| Area | Decision |
|------|----------|
| CSV import | Cap upload size (`CSV_IMPORT_MAX_BYTES`, default 256 KiB) and data rows (`CSV_IMPORT_MAX_ROWS`, default 100). |
| Fulfill amounts | Before marking paid / capturing, reject Checkout `amount_total` that **exceeds** the sum of catalog Stripe prices for linked orders (amounts below catalog are allowed for promos). Over-amount → do not advance payment state (webhook still returns 200 so Stripe does not retry forever). |
| Admin cancel | Fail closed: if Stripe cannot cancel an open `requires_capture` PaymentIntent, return 502 and leave local `payment_status` / status unchanged. |
| Auth expiry | Handle `payment_intent.canceled` (and equivalent terminal cancels): mark order payment/status canceled and clear address-request tokens. |
| Rate limits | Prefer shared store via `REDIS_URL` when scaling workers/instances; in-process limiter is fine for single-worker Render. |
| Address tokens | Tokens expire after `ADDRESS_REQUEST_TTL_DAYS` (default 7, aligned with Stripe hold). Cleared after use, cancel, or auth expiry. |
| Passwords | Min length `PASSWORD_MIN_LENGTH` (default 12); must include a letter and a digit. Duplicate signup returns a generic 400 (`unable to create account`) — no email enumeration. |
| Session cookie | `SESSION_COOKIE_SECURE` defaults to **true** when `APP_ENV=production` (override explicitly for local HTTP). |
| Gift catalog (web) | Pack ids/labels live in `web/lib/gift-catalog.ts`; live prices from `GET /gifts`. |
| Web client | Dashboard/domain screens use shared `apiFetch` from `web/lib/api.ts` (credentials + consistent errors). |

## Why these choices

- Split hosting keeps frontend and API independently scalable.
- FastAPI fits current team familiarity with Python and speeds MVP delivery.
- Render keeps backend deploys and environment setup simple for first production launches.
- Neon gives fast setup, managed Postgres, and a clean developer workflow.
- Resend offers simple transactional email integration for MVP notifications.
- App-managed session auth keeps control in-app and supports straightforward logout and session invalidation behavior.
- Amount checks and fail-closed cancel prevent local state from diverging from Stripe money movement.
- Redis-backed rate limits avoid per-process counters when running more than one worker or instance.

## Implementation order (historical / complete for MVP core)

1. Scaffold backend service (`api/`) with FastAPI app, env loading, health route.
2. Connect Neon Postgres and set up migrations (Alembic).
3. Implement app-managed session auth (signup/login/logout/session check).
4. Wire frontend auth calls to backend and protect dashboard routes.
5. Configure Resend for the internal new-order notification (customer status / auth emails deferred).
6. Deploy frontend to Vercel and backend to Render with staging env vars.
7. Gift orders + Stripe Checkout + admin fulfillment + CSV import + address-request flow.
8. Medium hardening (caps, amount verification, Redis rate limits, token TTL, password policy).

## Schema notes

- Alembic revisions through `0011_address_request_expiry` (`gift_orders.address_request_expires_at`).
- API keys: `0010_api_keys` — user-scoped keys for programmatic create paths.
