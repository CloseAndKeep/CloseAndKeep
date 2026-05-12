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
- [ ] Implement **admin bootstrap** (env email allowlist, seed/migration, or documented manual runbook) per [SoftwareRequirements.MD](SoftwareRequirements.MD) before relying on the admin queue in production
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

**Git is not in use for now** — the CloseAndKeep folder is not a Git repository. When you adopt Git, add a root `.gitignore` and initialize (or connect a remote) then.

- [ ] *(When using Git)* Initialize or connect a repository and add a suitable `.gitignore`
- [ ] Add `.env.example` (no secrets)
- [x] Document how to run frontend locally (`web/README.md`)
- [x] Document how to run backend locally
- [ ] Document how to run database migrations locally

---

## Database

- [ ] Create dev database
- [ ] Pick migration tool (Prisma, Alembic, etc.)
- [ ] Users table (or equivalent)
- [ ] Companies table (if using teams later; optional for MVP)
- [ ] Prospects table
- [ ] *(Optional)* Sales pitches / touchpoints table — **not** required if prospect-only model stays
- [ ] Gifts (catalog) table
- [ ] Gift orders table (recipient name, full shipping address, note on the gift, FK to prospect + gift, status)
- [ ] Follow-ups table
- [ ] Subscriptions / Stripe fields on user or company
- [ ] Seed script or admin SQL for first test gifts (optional)

---

## Design system and UI base

- [x] Install UI stack — **Tailwind** + small local UI primitives (`components/ui/`); shadcn/ui optional later
- [x] Set base colors (brand) — cream / wood / espresso in `tailwind.config.ts` + `globals.css`
- [x] Set fonts — **DM Sans** + **Fraunces** (`app/layout.tsx`)
- [x] App shell: layout with nav / header (`AppShell` + `MarketingShell`)
- [x] Reusable page header (`PageHeader`) — empty-state pattern still generic
- [ ] Toast or inline error pattern
- [ ] Loading state pattern

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

- [ ] Choose auth provider or implement auth
- [ ] Signup API / server action
- [ ] Signup page (form + validation)
- [ ] Login API / server action
- [ ] Login page
- [ ] Logout
- [ ] Forgot password flow
- [ ] Session handling verified (protected routes work)
- [ ] Account settings page: profile fields

---

## Stripe billing

- [ ] Create Stripe account (test mode)
- [ ] Create Product(s) and Price(s) in Stripe
- [ ] Pricing page lists plans correctly
- [ ] Checkout: start session from app
- [ ] Checkout: success and cancel URLs handled
- [ ] Webhook endpoint implemented and secured (signature)
- [ ] Persist Stripe customer ID
- [ ] Persist subscription ID and status in DB
- [ ] Gate paid routes/features on active subscription
- [ ] Customer billing portal link from app
- [ ] Test: successful subscription
- [ ] Test: cancel subscription
- [ ] Test: failed payment / past_due handling

---

## Core pages — routing

- [x] `/` landing (preview UI)
- [x] `/pricing`
- [ ] `/signup` and `/login` — deferred (browse app without auth)
- [x] `/dashboard` (open preview; no auth gate yet)
- [x] `/prospects` and `/prospects/[id]` — `/prospects/new` not built yet
- [x] `/gifts` (catalog)
- [x] `/orders/new` (wizard; submit disabled until API)
- [x] `/follow-ups`
- [x] `/billing` (placeholder)
- [ ] `/admin` (admin-only)

---

## Prospects

- [ ] API: create prospect
- [ ] API: list prospects (scoped to user/company)
- [ ] API: get prospect by id
- [ ] API: update prospect
- [ ] API: archive or delete (per your rules)
- [ ] UI: add prospect form with validation
- [ ] UI: prospect list with search or filter
- [ ] UI: prospect detail page
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

- [ ] Select prospect (or create inline)
- [ ] Select gift
- [ ] Enter or confirm **recipient name** (delivery name; prefill from prospect if helpful)
- [ ] Enter or confirm **full shipping address** (required)
- [ ] Enter **note to leave on the gift** (required—card or enclosure message)
- [ ] Validate: block submit if name, address, or note is missing/blank
- [ ] Review step shows recipient, address, and note clearly
- [ ] Submit creates order in `queued` (or equivalent)
- [ ] User-facing confirmation page or state
- [ ] User can see order status on dashboard / prospect

---

## Fulfillment (admin)

- [ ] Admin bootstrap deployed/configured (see SoftwareRequirements.MD — Admin bootstrap; Architecture.MD §15)
- [ ] Admin role or flag on user
- [ ] Admin-only middleware / guard
- [ ] Admin: order queue list (filter by status)
- [ ] Admin: order detail view (recipient name, full address, note on the gift, internal history)
- [ ] Admin: update status (ordered → shipped → delivered, etc.)
- [ ] Admin: add tracking number
- [ ] Internal notes on order (optional)
- [ ] User notified on status changes (email — see Notifications)

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

- [ ] Send email: gift request submitted
- [ ] Send email: gift shipped (when admin sets shipped)
- [ ] Send email: gift delivered
- [ ] Send email: follow-up reminder
- [ ] Send email: payment failed
- [ ] Log failed sends for debugging

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

- [ ] Privacy policy page
- [ ] Terms of service page
- [ ] Footer links on marketing pages

---

## Launch prep

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

- [ ] Gifts included in subscription vs billed per gift
- [x] Monthly gift credits vs unlimited tiers — **direction:** weekly order caps per tier (not an credits wallet); see Business Model in `ReadMe.MD`
- [x] Individuals vs teams first — **GTM:** individual SaaS sellers first; **product:** Individual + Enterprise subscription tiers
- [ ] Auto-send gift vs admin approval each time
- [ ] Prospects receive email from app vs only salesperson outreach
- [ ] Primary gift vendor or fulfillment partner

---

## Success metrics (track when you have users)

- [ ] Define where you log signups and paying subscribers
- [ ] Define how you measure gifts sent per month
- [ ] Define how you measure gift-to-close rate
- [ ] Review metrics monthly
