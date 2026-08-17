# CloseAndKeep

Post-pitch cookie gifts for sales teams after the demo. Prefer this file and the matching `.cursor/rules/*.mdc` over re-reading the repo or long docs.

## Knowledge

**Owns:** repo-wide conventions. Area details live in glob-scoped `.cursor/rules/*.mdc`. HubSpot CLI: `hubspot-closeandkeep/AGENTS.md`.

- Stack: Next.js 14 / Vercel (`web/`), FastAPI / Render (`api/`), Neon Postgres + Alembic, Stripe Checkout per gift order (`mode: payment`), Resend, app-managed HttpOnly sessions.
- **Prefer `Architecture.MD` §0 and `DECISIONS.md` over speculative Architecture sections.**
- Pointers (open only if this summary is not enough): `Architecture.MD` §0, `DECISIONS.md`, `USER_GUIDE.md`, `Test.MD`, `api/README.md`, `web/README.md`.
- Local web: `NEXT_PUBLIC_API_BASE_URL`. Production: Vercel `/__cak_api` proxy via `BACKEND_URL`.

## Preferences

- Keep agent manuals compressed. Do not paste Architecture or USER_GUIDE into rules.
- After a durable mistake or better method, follow `.cursor/skills/lab-notes/SKILL.md`. Write the lesson in the matching `.mdc` Log (root Lab notes only if repo-wide). Cap 8 bullets per list; newest first; prune oldest.
- Harness: (1) prefer these manuals over rediscovering the codebase; (2) record the lesson after a mistake; (3) parallelize independent work (Task fan-out, then one synthesizer); (4) do not self-QA — Bugbot, Security Review, or a fresh pass; (5) if a metric is cheap to measure, loop change → test → score; (6) prototype messy automation in the browser, then replace repeats with HTTP/API; (7) keep docs portable (`AGENTS.md`); never put secrets or card data in agent context; Stripe holds payments.

## Capabilities

- `web/`: `npm run dev`. `api/`: `python -m alembic upgrade head` then `python -m uvicorn app.main:app --reload --port 8000`. Tests: `python -m pytest tests/ -q` (isolated SQLite, Stripe stubbed).
- Stripe CLI: `tools/stripe-cli/`. HubSpot CLI only under `hubspot-closeandkeep/`.
- Do not commit `.env` / `.env.local`. Do not call live Stripe/Resend from tests. Do not store PAN/card data.

## Lab notes

### Successes
- One-time Checkout per gift order (not subscriptions) matched the product and avoided billing-portal scope.
- Cards stay with Stripe; the app never stores PAN.

### Failures
- Speculative Architecture sections below §0 go stale; as-built + `DECISIONS.md` win.
- Growing this file into a diary burns tokens; keep area logs in the matching `.mdc`.
