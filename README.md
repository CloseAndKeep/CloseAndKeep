# CloseAndKeep

Post-pitch gifting for sales teams who want to stand out after the demo.

## Repo layout

- `web/` - Next.js 14 frontend deployed on Vercel
- `api/` - FastAPI backend
- `Architecture.MD`, `DECISIONS.md`, `SoftwareRequirements.MD`, `TaskList.MD`, `Test.MD` - project docs

## Local development

Frontend:

```bash
cd web
npm install
copy .env.example .env.local
npm run dev
```

Backend:

```bash
cd api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Deployment

The frontend deploys to Vercel from `web/`. The backend deploys to Render from `api/` via the `render.yaml` Blueprint at the repo root.

### Backend (Render)

1. Push the repo to GitHub (the Blueprint reads from there).
2. In Render: **New > Blueprint**, select this repo. Render detects `render.yaml` and creates a service called `closeandkeep-api`.
3. When prompted, fill in the `sync: false` env vars:
   - `DATABASE_URL` - Neon Postgres connection string (use `postgresql://...?sslmode=require`; the app rewrites it to `postgresql+psycopg://` at runtime).
   - `CORS_ORIGINS` - comma-separated list of your Vercel origins (for example `https://closeandkeep.com,https://www.closeandkeep.com`). Required even when using the proxy, because the browser forwards its `Origin` header through Vercel.
   - `WEB_BASE_URL` - public URL of the Vercel app (used in Stripe redirects).
   - `API_BASE_URL` - public URL of this Render service (for example `https://closeandkeep-api.onrender.com`).
   - `ADMIN_EMAILS`, `RESEND_API_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID` - leave blank or fill in as available.
   - **Order emails:** set `RESEND_API_KEY` (replace the `re_xxxxxxxxx` placeholder with your real key). For internal alerts only, the default `RESEND_FROM` is `onboarding@resend.dev`. For customer-facing mail, verify your domain in Resend and set `RESEND_FROM` to something like `orders@yourdomain.com`. Each new gift order emails `ORDER_NOTIFICATION_TO` (defaults to `CloseAndKeep@gmail.com` if unset).
4. The build runs `pip install -r requirements.txt && python -m alembic upgrade head`, so each deploy runs migrations against Neon before the new code starts serving.
5. After the first successful deploy, verify with `curl https://<your-render-host>/health`.

### Frontend (Vercel)

- Deploy from the `web/` directory (Vercel Project Settings > Root Directory = `web`).
- Set **`BACKEND_URL`** on Vercel to the Render service URL (for example `https://closeandkeep-api.onrender.com`, no trailing slash). The Next app rewrites browser calls from `https://yourdomain.com/__cak_api/...` to that backend, so you do not need `NEXT_PUBLIC_API_BASE_URL` and cookies stay first-party on the Vercel origin.
- Alternative (not recommended): set **`NEXT_PUBLIC_API_BASE_URL`** to the API origin to have the browser call Render directly. With this setup, `CORS_ORIGINS` on Render must include the exact Vercel origins, and you should change the API's session cookie to `SameSite=None; Secure` so cross-site requests carry it.

## Product overview

CloseAndKeep helps SaaS sellers close more deals and keep more customers by turning post-pitch follow-up into simple, trackable gift sends.

The MVP focuses on:

- landing page and pricing
- signup and login
- dashboard
- prospect tracking
- gift ordering workflow
- follow-up reminders
- deal outcome tracking

## Project notes

- Frontend: Next.js 14, React, TypeScript, Tailwind CSS
- Backend: FastAPI, Python
- Database: Neon Postgres
- Auth: secure server-managed sessions
- Billing: Stripe

See `DECISIONS.md` for locked technical choices and `Architecture.MD` for system design details.
