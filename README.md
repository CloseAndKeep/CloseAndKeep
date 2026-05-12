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

- Vercel should deploy from the `web` root directory.
- The backend is intended for a separate Python host such as Render or Fly.io.

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
