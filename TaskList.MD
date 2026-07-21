# TaskList.MD

# CloseAndKeep — Build Checklist

Use `- [ ]` for todo and `- [x]` for done. Work top-to-bottom within each section unless you’re parallelizing.

Deeper context: `README.md`, `Architecture.MD`, `SoftwareRequirements.MD`, `Test.MD` (**full recursive test catalog** — implement and check off tests there; cite anchors **`TEST-REG`** / **`TEST-LAUNCH`** / **`TEST-RISK`** for release gates).

---

## How to use

- [ ] Skim the whole list once so you know what’s coming
- [ ] Check items off as you finish them (keep the `[x]` in the same line)
- [x] After completing work (in chat or locally), update this file so completed tasks stay checked off
- [ ] If a task is too big, split it into sub-bullets under that item locally until it feels like one session of work

---

## Current status (refreshed 2026-07-21)

**Built and working:**
- Backend (FastAPI) with app-managed sessions: signup, login, logout, guest, `/auth/me`, admin-role sync via `ADMIN_EMAILS`.
- Password policy (min length + letter/digit) and anti-enumeration on duplicate signup.
- Postgres (Neon) schema + Alembic migrations through `0011_address_request_expiry`.
- Prospects: list / create / get / **update (deal outcome)**, all user-scoped.
- Dashboard summary metrics (open / won / lost / total) wired to live data.
- Gift orders: create / list / get + **one-time Stripe Checkout** + webhook + amount verification vs catalog prices.
- Deferred recipient address (authorize hold + public token + capture) with token TTL.
- CSV gift-order import (template/example + size/row caps).
- API keys (create / list / revoke) with rate limits.
- **Admin fulfillment:** `/admin` order queue + order detail; cancel of authorized orders fails closed if Stripe cancel fails.
- Frontend (Next.js) wired via `apiFetch`; gift labels in `gift-catalog.ts`; `/ship/[token]` address form.
- Rate limits: in-process + optional Redis (`REDIS_URL`); `SESSION_COOKIE_SECURE` defaults true in production.
- Automated API pytest suite (`api/tests/`, including medium-hardening coverage).

**Deferred (explicitly on hold):**
- Follow-ups feature backend (table, reminder email job); UI scaffold remains.
- Status-change emails to customers (only the internal new-order email exists).
- Auth gaps: password reset and account settings.

**Placeholder / pre-launch:** legal pages (real copy), E2E browser suite, production monitoring polish.

---

## Product (locked / planning)

- [x] Product name: **CloseAndKeep**
- [x] Write one-sentence value proposition (see `README.md`, `SoftwareRequirements.MD` §1.1)
- [x] Define first ideal customer (ICP): SaaS salespeople (AEs / reps)
- [x] Decide MVP: manual fulfillment vs any automation — **MVP = manual fulfillment + tracking;** automation not a near-term customer or build focus
- [x] Decide pricing model: **one-time payment per gift order** (see `DECISIONS.md`; no subscription in MVP)
- [x] List pricing presentation: per-order cookie packs on `/pricing` (no subscription plan names in product)

---

## Planning documentation hygiene (from planning review)

- [x] Record finalized stack, auth, DB, email, and hosting choices in one place when decided (`README.md` / `DECISIONS.md`)
- [x] Confirm MVP stays **solo-user-first**; optional `company`/team schema is scaffolding only until teams are in scope ([SoftwareRequirements.MD](SoftwareRequirements.MD) §2)
- [x] Implement **admin bootstrap** — `ADMIN_EMAILS` env allowlist syncs `role=admin` on signup/login
- [ ] **Milestone 0:** explicit stop/review after concierge or discovery validation—decide whether to proceed with full product build (ties to “Optional: manual concierge test” below)
- [x] Refresh [README.md](README.md) when planning or build phase advances

---

## Discovery (before or during early build)

- [ ] Discovery interview 1
- [ ] Discovery interview 2
- [ ] Discovery interview 3
- [ ] Discovery interview 4
- [ ] Discovery interview 5
- [ ] Discovery interview 6
- [ ] Discovery interview 7
- [ ] Discovery interview 8
- [ ] Discovery interview 9
- [ ] Discovery interview 10
- [ ] Summarize top 3 pains and top 3 must-have features from interviews

---

## Optional: manual concierge test (before full product)

- [ ] Simple landing or form to capture gift requests
- [ ] Process to manually buy and ship gifts
- [ ] Spreadsheet (or simple tracker) for requests and status
- [ ] Manual follow-up reminders (calendar or email)
- [ ] Note lessons learned; decide what to automate first

---

## Stack decisions (document in the project when chosen)

- [x] Choose frontend framework — **Next.js 14** (`web/`)
- [x] Choose backend framework (e.g. FastAPI / NestJS)
- [x] Choose PostgreSQL host (local dev + staging + prod plan)
- [x] Choose auth approach (managed vs self-hosted)
- [x] Choose email provider for transactional mail
- [x] Choose app hosting (frontend + API)

---

## Repository and local dev

**Git is in use** — the CloseAndKeep folder is a Git repository with a root `.gitignore`.

- [x] Initialize or connect a repository and add a suitable `.gitignore`
- [x] Add `.env.example` (no secrets) — `api/.env.example`, `web/.env.example`
- [x] Document how to run frontend locally (`web/README.md`)
- [x] Document how to run backend locally
- [x] Document how to run database migrations locally (`alembic upgrade head`; see `README.md`)

---

## Database

- [x] Create dev database (Neon Postgres)
- [x] Pick migration tool — **Alembic**
- [x] Users table (with role; subscription scaffolding removed in `0007`)
- [ ] Companies table (if using teams later; optional for MVP)
- [x] Prospects table
- [ ] *(Optional)* Sales pitches / touchpoints table — **not** required if prospect-only model stays
- [x] Gifts (catalog) — static cookie packs in API `GIFT_CATALOG` + `web/lib/gift-catalog.ts` (prices from Stripe via `GET /gifts`)
- [x] Gift orders table (recipient name, shipping address or address-request token+expiry, note, FK to prospect, status, payment, tracking, admin notes)
- [ ] Follow-ups table — **deferred**
- [x] Stripe fields on user/order — per-order payment fields on `gift_orders`; `users.stripe_customer_id` populated at checkout
- [ ] Seed script or admin SQL for first test gifts (optional)

---

## Design system and UI base

- [x] Install UI stack — **Tailwind** + small local UI primitives (`components/ui/`); shadcn/ui optional later
- [x] Set base colors (brand) — cream / wood / espresso in `tailwind.config.ts` + `globals.css`
- [x] Set fonts — **DM Sans** + **Fraunces** (`app/layout.tsx`)
- [x] App shell: layout with nav / header (`AppShell` + `MarketingShell`)
- [x] Reusable page header (`PageHeader`) — empty-state pattern still generic
- [~] Toast or inline error pattern — inline error pattern in use; route-level `error.tsx` placeholder added; no toast yet
- [x] Loading state pattern — route-level `loading.tsx` + per-page loading states

---

## Brand and marketing surface

- [ ] Logo or wordmark decision
- [x] Landing page: hero and primary CTA (`app/(marketing)/page.tsx`)
- [x] Landing page: how it works (3–5 steps)
- [x] Landing page: pricing teaser or link to pricing
- [x] Landing page: primary CTA is **Log in** → `/login`
- [ ] Email waitlist or direct signup CTA on landing (signup exists at `/signup`)
- [x] Basic page title (metadata in root `layout.tsx`) — custom favicon still TODO

---

## Authentication

- [x] Choose auth provider or implement auth — **app-managed server sessions**
- [x] Signup API / server action
- [x] Signup page (form + validation)
- [x] Login API / server action
- [x] Login page
- [x] Logout
- [ ] Forgot password flow — **deferred**
- [x] Session handling verified (protected routes work via `AuthGuard` + `/auth/me`)
- [ ] Account settings page: profile fields — **deferred**

---

## Payments (one-time per gift order — NOT subscription)

Billing is **one-time per gift order** via Stripe Checkout (`mode: payment`). No subscription, no plan tiers, no weekly caps. See `DECISIONS.md`.

- [x] Create Stripe account (test mode)
- [x] Create one-time Price in Stripe (`STRIPE_PRICE_ID`)
- [x] Pricing page shows per-order pricing correctly
- [x] Checkout: start one-time session from app (on order submit + retry)
- [x] Checkout: success and cancel URLs handled (`/orders/[id]?payment=...`)
- [x] Webhook endpoint implemented and secured (signature) + fetch-time fallback sync
- [x] Persist Stripe customer ID on first checkout (`users.stripe_customer_id`)
- [x] Mark order paid → queued on `checkout.session.completed` (with catalog amount verification)
- [x] Test: successful payment / webhook sync (API integration suite)
- [x] Test: canceled checkout / unpaid remains unpaid
- [x] Test: amount mismatch does not mark paid
- [x] Test: admin cancel fails closed when Stripe cancel fails
- [x] Test: `payment_intent.canceled` expires authorization + clears address token
- [ ] Refund policy UX (admin can set `canceled`; card refunds still manual in Stripe Dashboard)

---

## Core pages — routing

- [x] `/` landing
- [x] `/pricing`
- [x] `/signup` and `/login`
- [x] `/privacy` and `/terms` (placeholder copy)
- [x] `/dashboard` (auth-gated)
- [x] `/prospects` and `/prospects/[id]` (inline create on list)
- [x] `/gifts` (redirects to `/orders/new`)
- [x] `/orders`, `/orders/new`, `/orders/[id]` (wired to API)
- [x] `/follow-ups` — placeholder “coming soon” (**deferred** backend; no mock data)
- [x] `/billing` (payment history, wired to API)
- [x] `/api-keys` (create / list / revoke)
- [x] `/ship/[token]` (public recipient address form)
- [x] `/support` and `/developers` (marketing)
- [x] `/admin` and `/admin/orders/[id]` (admin-only)

---

## Prospects

- [x] API: create prospect
- [x] API: list prospects (scoped to user)
- [x] API: get prospect by id
- [x] API: update prospect (incl. deal outcome)
- [ ] API: archive or delete (per your rules)
- [x] UI: add prospect form with validation
- [x] UI: prospect list
- [ ] UI: prospect list search or filter
- [x] UI: prospect detail page (with deal-status editor)
- [ ] Prospect address/contact can prefill gift order fields (order still stores its own copy for fulfillment)

---

## Sales pitches

**Not in the app UI** — no dedicated Pitches section. Gift orders link to **prospects**; pipeline/outcome can live on the prospect (or follow-ups) instead.

---

## Gift catalog

- [x] API: list active gifts (`GET /gifts` with live prices)
- [ ] API: admin create gift
- [ ] API: admin update gift
- [ ] API: admin activate/deactivate gift
- [x] UI: pack selection in gift-order wizard (labels from `gift-catalog.ts`)
- [ ] UI: standalone gift detail or modal
- [ ] Placeholder images or real assets for first gifts

---

## Gift orders (user flow)

- [x] Select prospect
- [x] Select gift (cookie pack)
- [x] Enter or confirm **recipient name**
- [x] Enter or confirm **full shipping address**, or request recipient address by email
- [x] Enter **note to leave on the gift** (required)
- [x] Validate: block submit if name, note, or (when not deferred) address is missing/blank
- [x] Review step shows recipient, address (or address-request), and note clearly
- [x] Submit creates order (`pending_payment` → paid/`queued`, or authorize/`no_address` then capture)
- [x] User-facing confirmation / order detail state
- [x] User can see order status on the orders list and order detail
- [x] CSV import at `/orders/import` (API capped by bytes/rows)

---

## Fulfillment (admin)

- [x] Admin bootstrap configured (`ADMIN_EMAILS` allowlist syncs role on signup/login)
- [x] Admin role or flag on user
- [x] Admin-only middleware / guard (`get_current_admin` API dep + `AdminGuard` UI)
- [x] Admin: order queue list (filter by status) at `/admin`
- [x] Admin: order detail view (recipient name, full address, note, prospect + account info)
- [x] Admin: update status (queued → ordered → shipped → delivered / canceled)
- [x] Admin: add tracking number
- [x] Internal notes on order
- [ ] User notified on status changes (email) — **deferred**

---

## Follow-ups

- [ ] API: create scheduled follow-up linked to prospect (or gift order)
- [ ] API: list upcoming follow-ups for user
- [ ] API: mark follow-up complete or skip
- [ ] UI: schedule date picker on follow-up or prospect page
- [ ] Dashboard widget: due follow-ups
- [ ] Email: reminder to salesperson (not prospect, if that’s your MVP rule)
- [ ] Job or cron: due reminders sent daily/hourly

---

## Analytics and dashboard

- [x] Dashboard: open / won / lost / total prospect counts (`GET /dashboard/summary`)
- [x] Dashboard: simple win rate `won / (won + lost)`
- [ ] Dashboard: gifts sent count
- [ ] Dashboard: follow-ups due — blocked on follow-ups feature
- [ ] Dashboard: time-ranged conversion matching a documented formula
- [ ] Empty state polish for new accounts

---

## Notifications (email)

- [x] Send email: new gift order placed (internal ops notification on payment, via Resend)
- [ ] Send email: gift shipped (when admin sets shipped) — **deferred**
- [ ] Send email: gift delivered — **deferred**
- [ ] Send email: follow-up reminder — **deferred**
- [ ] Send email: payment failed — **deferred**
- [x] Log failed sends for debugging (logged in `order_email.py`)

---

## Admin: catalog and users (as needed for MVP)

- [ ] Admin: full gift CRUD UI
- [ ] Admin: view users list
- [ ] Admin: view payment / order health per user (no subscription status in MVP)
- [ ] Admin: handle failed orders list (optional)

---

## Security and reliability

- [x] Confirm TLS terminated in production (Vercel + Render) — verify headers / HSTS as needed
- [x] Secrets only in env / secret manager
- [x] Rate limit auth, order create, API-key create (optional Redis)
- [x] Validate and sanitize all API inputs (incl. password policy)
- [x] Authorization checks on every id-scoped resource
- [x] Stripe webhook signature verification + amount verification
- [x] CSV import size/row caps; address-request token TTL
- [ ] Database backups enabled (provider settings)
- [ ] Basic error logging (Sentry or provider logs)

---

## Legal and trust

- [~] Privacy policy page — **placeholder added** (`/privacy`); needs real legal copy
- [~] Terms of service page — **placeholder added** (`/terms`); needs real legal copy
- [x] Footer links on marketing pages

---

## Launch prep

- [x] Automated API test suite — `api/tests/` (pytest); expand E2E against `Test.MD`
- [ ] Staging environment matches prod setup
- [ ] Run through `Test.MD` regression gate (**`TEST-REG`**) in staging
- [ ] Production Stripe keys and webhook URL
- [ ] Production database and migrations applied
- [ ] Monitoring / alerts for API errors (minimal)
- [ ] Invite beta users 1
- [ ] Invite beta users 2
- [ ] Invite beta users 3
- [ ] Invite beta users 4
- [ ] Invite beta users 5
- [ ] Collect feedback doc or board
- [ ] Fix top 3 UX issues from beta

---

## Nice-to-have (after core MVP)

- [x] CSV import for gift orders (prospect CSV still nice-to-have)
- [ ] CSV import for prospects
- [ ] Email templates editable in admin
- [ ] Saved gift message templates
- [ ] Export reports CSV
- [ ] Team / company accounts and roles beyond solo user
- [ ] In-app notification center

---

## Future (do not start until MVP is paid-for / validated)

- [x] Pick first CRM — **Salesforce** (HubSpot next only if requested)
- [x] OAuth and CRM connection settings page — `/integrations` + Salesforce OAuth
- [x] Demo Completed → immediate cookie reminder email + prospect upsert (deduped)
- [ ] Import contacts / deals from CRM (beyond reminder upsert)
- [ ] Push gift activity to CRM
- [x] API keys (user-scoped create/list/revoke) — expand with public developer docs later
- [ ] Public API design docs / versioning
- [ ] Webhooks outbound to customer systems
- [ ] Automated vendor API for gifts
- [x] HubSpot adapter (same trigger pattern as Salesforce) — OAuth, Demo Completed webhook/poll, reminder email, UI

---

## Open decisions (check when resolved)

- [x] Gifts included in subscription vs billed per gift — **RESOLVED: one-time payment per gift order; no subscription** (see `DECISIONS.md`)
- [x] Monthly gift credits vs unlimited tiers — **RESOLVED: not applicable; pay per order** (no credits, no weekly caps)
- [x] Individuals vs teams first — **GTM:** individual SaaS sellers first
- [ ] Auto-send gift vs admin approval each time
- [ ] Prospects receive email from app vs only salesperson outreach
- [ ] Primary gift vendor or fulfillment partner

---

## Success metrics (track when you have users)

- [ ] Define where you log signups and paying customers (per-order revenue, not subscribers)
- [ ] Define how you measure gifts sent per month
- [ ] Define how you measure gift-to-close rate
- [ ] Review metrics monthly
