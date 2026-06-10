# DECISIONS.md

# CloseAndKeep - Technical decisions

Last updated: 2026-06-10

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

CloseAndKeep charges **per gift order**, not via subscription. When a user submits a gift
order, the API creates a Stripe Checkout session in `mode: payment`; the order stays
`pending_payment` until Stripe confirms payment (via webhook, with a fetch-time fallback that
re-checks the Checkout session), at which point it moves to `queued` for fulfillment.

- No subscription tiers, no weekly order caps, no billing portal are in scope for the MVP.
- The `users.subscription_status` / `users.subscription_plan` columns remain in the schema as
  **reserved scaffolding** only; nothing reads or enforces them today. Revisit if/when a
  recurring plan is introduced.

## Why these choices

- Split hosting keeps frontend and API independently scalable.
- FastAPI fits current team familiarity with Python and speeds MVP delivery.
- Render keeps backend deploys and environment setup simple for first production launches.
- Neon gives fast setup, managed Postgres, and a clean developer workflow.
- Resend offers simple transactional email integration for MVP notifications.
- App-managed session auth keeps control in-app and supports straightforward logout and session invalidation behavior.

## Implementation order (active)

1. Scaffold backend service (`api/`) with FastAPI app, env loading, health route.
2. Connect Neon Postgres and set up migrations (Alembic).
3. Implement app-managed session auth (signup/login/logout/session check).
4. Wire frontend auth calls to backend and protect dashboard routes.
5. Configure Resend for transactional emails (auth and order/status notifications).
6. Deploy frontend to Vercel and backend to Render with staging env vars.
