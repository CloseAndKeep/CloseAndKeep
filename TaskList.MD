# TaskList.MD

# CloseAndKeep — Build Checklist

Use `- [ ]` for todo and `- [x]` for done. Work top-to-bottom within each section unless you’re parallelizing.

Deeper context: `ReadMe.MD`, `Architecture.MD`, `SoftwareRequirements.MD`, `Test.MD` (**full recursive test catalog** — implement and check off tests there; cite anchors **`TEST-REG`** / **`TEST-LAUNCH`** / **`TEST-RISK`** for release gates).

---

## How to use

- [ ] Skim the whole list once so you know what’s coming
- [ ] Check items off as you finish them (keep the `[x]` in the same line)
- [x] After completing work (in chat or locally), update this file so completed tasks stay checked off
- [ ] If a task is too big, split it into sub-bullets under that item locally until it feels like one session of work

---

## Current status (refreshed 2026-06-10)

**Built and working:**
- Backend (FastAPI) with app-managed sessions: signup, login, logout, `/auth/me`, admin-role sync via `ADMIN_EMAILS`.
- Postgres (Neon) schema + Alembic migrations `0001`–`0006`.
- Prospects: list / create / get / **update (deal outcome)**, all user-scoped.
- Dashboard summary metrics (open / won / lost / total) wired to live data.
- Gift orders: create / list / get + **one-time Stripe Checkout per order** and webhook (no subscription).
- **Admin fulfillment:** `/admin` order queue + order detail with status, tracking number, and internal notes (admin endpoints + admin guard).
- Frontend (Next.js) wired to the API for all of the above; legal placeholder pages + dashboard loading/error patterns.

**Deferred (explicitly on hold):**
- Follow-ups feature (table, API, UI, reminder email).
- Status-change emails to customers (only the internal new-order email exists).
- Auth gaps: password reset and account settings.

**Placeholder / pre-launch:** legal pages, error/loading patterns, automated tests, this checklist.

---

## Product (locked / planning)

- [x] Product name: **CloseAndKeep**
- [x] Write one-sentence value proposition (see `ReadMe.MD`, `SoftwareRequirements.MD` §1.1)
- [x] Define first ideal customer (ICP): SaaS salespeople (AEs / reps)
- [x] Decide MVP: manual fulfillment vs any automation — **MVP = manual fulfillment + tracking;** automation not a near-term customer or build focus
- [x] Decide pricing model: **subscription** (not leading with per-gift or credits for positioning)
- [x] List subscription plan names and limits (even if rough): **Individual** (1 box/week), **Enterprise** (5 boxes/week) — placeholders in `ReadMe.MD` / `SoftwareRequirements.MD`

---

## Planning documentation hygiene (from planning review)

- [x] Record finalized stack, auth, DB, email, and hosting choices in one place when decided (`ReadMe.MD` “Technical decisions” block or `DECISIONS.md`)
- [x] Confirm MVP stays **solo-user-first**; optional `company`/team schema is scaffolding only until teams are in scope ([SoftwareRequirements.MD](SoftwareRequirements.MD) §2)
- [x] Implement **admin bootstrap** — `ADMIN_EMAILS` env allowlist syncs `role=admin` on signup/login
- [ ] **Milestone 0:** explicit stop/review after concierge or discovery validation—decide whether to proceed with full product build (ties to “Optional: manual concierge test” below)
- [x] Refresh [ReadMe.MD](ReadMe.MD) **Current Status** when planning or build phase advances

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
- [x] Users table (with role + reserved subscription columns)
- [ ] Companies table (if using teams later; optional for MVP)
- [x] Prospects table
- [ ] *(Optional)* Sales pitches / touchpoints table — **not** required if prospect-only model stays
- [ ] Gifts (catalog) table — gifts are static cookie packs in `web/lib/mock-data.ts` for now
- [x] Gift orders table (recipient name, full shipping address, note, FK to prospect, status, payment, tracking, admin notes)
- [ ] Follow-ups table — **deferred**
- [x] Stripe fields on user/order — per-order payment fields on `gift_orders`; subscription columns on `users` are reserved scaffolding (unused)
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
- [x] Landing page: **Preview app** CTA instead of signup/login (auth skipped for UI preview)
- [ ] Email waitlist or direct signup (pick one for MVP)
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
- [ ] Persist Stripe customer ID (currently uses `customer_email`; optional)
- [x] Mark order paid → queued on `checkout.session.completed`
- [ ] Test: successful payment
- [ ] Test: canceled checkout leaves order unpaid
- [ ] Test: failed payment handling
- [ ] Refund / cancel policy wired (admin can set `canceled`; refunds still manual in Stripe)

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
- [x] `/follow-ups` — UI only, still mock data (**deferred** backend)
- [x] `/billing` (payment history, wired to API)
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

- [ ] API: list active gifts
- [ ] API: admin create gift
- [ ] API: admin update gift
- [ ] API: admin activate/deactivate gift
- [ ] UI: user catalog grid or list
- [ ] UI: gift detail or modal
- [ ] Placeholder images or real assets for first gifts

---

## Gift orders (user flow)

- [x] Select prospect
- [x] Select gift (cookie pack)
- [x] Enter or confirm **recipient name**
- [x] Enter or confirm **full shipping address** (required)
- [x] Enter **note to leave on the gift** (required)
- [x] Validate: block submit if name, address, or note is missing/blank
- [x] Review step shows recipient, address, and note clearly
- [x] Submit creates order (`pending_payment` → `queued` after payment)
- [x] User-facing confirmation / order detail state
- [x] User can see order status on the orders list and order detail

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

- [ ] Dashboard: count of prospects or open deals (time range optional)
- [ ] Dashboard: gifts sent count
- [ ] Dashboard: follow-ups due
- [ ] Dashboard: won vs lost vs pending
- [ ] Dashboard: conversion rate matches **SoftwareRequirements.MD** §4.11 definition (and note formula in code comments)
- [ ] Empty state for new accounts

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
- [ ] Admin: view subscription status per user
- [ ] Admin: handle failed orders list (optional)

---

## Security and reliability

- [ ] HTTPS in production
- [ ] Secrets only in env / secret manager
- [ ] Rate limit auth and webhook routes
- [ ] Validate and sanitize all API inputs
- [ ] Authorization checks on every id-scoped resource
- [ ] Stripe webhook signature verification
- [ ] Database backups enabled (provider settings)
- [ ] Basic error logging (Sentry or provider logs)

---

## Legal and trust

- [~] Privacy policy page — **placeholder added** (`/privacy`); needs real legal copy
- [~] Terms of service page — **placeholder added** (`/terms`); needs real legal copy
- [x] Footer links on marketing pages

---

## Launch prep

- [~] Automated test scaffold — placeholder `api/tests/` + `requirements-dev.txt` added; expand against `Test.MD`
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

- [ ] CSV import for prospects
- [ ] Email templates editable in admin
- [ ] Saved gift message templates
- [ ] Export reports CSV
- [ ] Team / company accounts and roles beyond solo user
- [ ] In-app notification center

---

## Future (do not start until MVP is paid-for / validated)

- [ ] Pick first CRM (HubSpot, Salesforce, etc.)
- [ ] OAuth and CRM connection settings page
- [ ] Import contacts / deals from CRM
- [ ] Push gift activity to CRM
- [ ] Public API design
- [ ] API keys and developer docs
- [ ] Webhooks outbound to customer systems
- [ ] Automated vendor API for gifts

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

- [ ] Define where you log signups and paying subscribers
- [ ] Define how you measure gifts sent per month
- [ ] Define how you measure gift-to-close rate
- [ ] Review metrics monthly
