# Architecture.MD

# CloseAndKeep — Architecture

## 0. As-built (current MVP)

This section reflects what is shipped today. Speculative options below remain useful for future planning; **prefer this section and `DECISIONS.md` when they conflict.**

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 14 (App Router) on Vercel; same-origin `/__cak_api` proxy to Render |
| Backend | FastAPI on Render (`api/`), single uvicorn worker by default |
| Database | Neon Postgres + Alembic (through `0011_address_request_expiry`) |
| Auth | App-managed sessions (HttpOnly cookie); `ADMIN_EMAILS` → admin role |
| Billing | **One-time Stripe Checkout per gift order** (`mode: payment`). No subscriptions. |
| Catalog | API `GIFT_CATALOG` + `GET /gifts`; web labels in `web/lib/gift-catalog.ts` |
| Email | Resend (internal new-order notification) |
| Rate limits | In-process sliding window; optional `REDIS_URL` for shared counters |
| Hardening | CSV size/row caps; Checkout amount vs catalog price check; fail-closed admin cancel of auth holds; address-request TTL; password letter+digit + min length; production `Secure` cookie default |

Primary money flow:

```text
User creates gift order
  → Stripe Checkout (payment or authorize/hold if address deferred)
  → webhook / sync verifies amount_total vs catalog prices
  → paid → queued  OR  authorized → recipient submits address → capture → queued
  → admin fulfills (manual) → shipped / delivered
```

Deferred address: public token at `/ship/[token]` → `GET|POST /public/address-requests/{token}` (expires ~7 days with the card hold).

---

## 1. Architecture Goals

The goal of this architecture is to keep the application modular, scalable, and easy to change as the business grows.

This product should start simple, but it should be designed so future features like CRM integrations, company APIs, gift vendor APIs, team accounts, and advanced analytics can be added without rebuilding the whole application.

## 2. Core Principles

### Keep Modules Separate
Each major part of the system should have a clear responsibility.

Main modules:
- Authentication
- Billing
- User and company management
- Prospect management (includes pipeline / **outcome on the prospect**—no separate pitch module)
- Gift catalog
- Gift ordering
- Fulfillment
- Follow-up reminders
- Analytics
- Admin dashboard
- Integrations

### Start Simple
The first version should not over-engineer infrastructure.

For MVP:
- Manual prospect entry
- Manual or semi-manual gift fulfillment
- **One-time Stripe Checkout per gift order** (not subscriptions)
- Basic dashboard
- Basic follow-up reminders (UI first; reminder jobs deferred)
- Basic analytics

### Build for Future Integrations
CRM and vendor integrations should be added as plug-in style modules later.

Future integrations should not be hardcoded directly into core business logic.

### Prioritize UX
The users are salespeople, not technical users.

The architecture should support:
- Fast page loads
- Clear dashboard data
- Simple workflows
- Helpful error messages
- Smooth onboarding

---

## 3. Suggested High-Level Architecture

## Frontend
The frontend is the user-facing web application.

Recommended stack:
- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui

Main responsibilities:
- Landing page
- Pricing page
- Signup/login screens
- Dashboard
- Prospect management screens
- Gift catalog
- Gift order flow
- Follow-up reminders
- Analytics
- Admin dashboard

---

## Backend API
The backend API handles business logic, security, database access, Stripe webhooks, and future integrations.

Recommended stack options:
- Node.js with NestJS
- Node.js with Express
- Python with FastAPI

Recommended choice:
- FastAPI if you want strong Python/data comfort
- NestJS if you want a structured TypeScript backend

Main responsibilities:
- User authentication support
- Authorization and permissions
- Per-order payment status (Checkout + webhooks; amount verification)
- Prospect CRUD (including deal status / outcome on prospect)
- Gift order processing (including CSV import and address-request tokens)
- Follow-up scheduling (deferred for MVP backend)
- Analytics aggregation
- Admin workflows
- Webhook handling
- Future CRM integration layer

---

## Database
Recommended database:
- PostgreSQL

Recommended hosting:
- Amazon RDS PostgreSQL
- Supabase PostgreSQL for a simpler early version
- Neon PostgreSQL as another simple hosted option

Why PostgreSQL:
- Strong relational data support
- Good for reporting
- Good for users, orders, and analytics
- Easier to reason about than NoSQL for this product

---

## Payments
Provider:
- Stripe Checkout (**one-time `mode: payment` per gift order**)

Stripe components used in MVP:
- Stripe Checkout Sessions
- PaymentIntents (authorize / capture when recipient address is deferred)
- Stripe Webhooks (`checkout.session.completed`, `payment_intent.canceled`, …)

Not used in MVP: Stripe Billing subscriptions, Customer Portal, invoice subscription lifecycle.

Access to create gift orders does **not** depend on a subscription status. Each order is paid (or authorized) individually. Fulfillment must never trust Checkout amounts without rejecting charges that **exceed** catalog Stripe prices (see `DECISIONS.md`).

---

## Email and Notifications
Provider (as shipped): **Resend** — internal new-order notification only.

Future email types (deferred):
- Account verification / password reset
- Gift shipped / delivered to the seller
- Follow-up reminder to the salesperson
- Payment failure notification

Address-request emails to recipients may already be sent when that path is configured; customer-facing status mail remains deferred.

---

## File and Image Storage
Recommended storage:
- Amazon S3

Possible files/images:
- Gift catalog images
- Company logos
- User-uploaded CSVs
- Future custom branding assets

---

## Background Jobs
Some actions should happen asynchronously.

Examples:
- Sending follow-up reminders
- Sending notification emails
- Processing Stripe webhook updates
- Syncing future CRM data
- Updating gift delivery status
- Running analytics summaries

Possible tools:
- AWS EventBridge
- AWS SQS
- Celery with Redis
- BullMQ with Redis
- Simple cron jobs for MVP

MVP recommendation:
Start with simple scheduled jobs before building a complex queue system.

---

## 4. Suggested System Diagram

> Prefer Architecture §0 for the as-built stack. The diagram below is a historical planning sketch; MVP has **no** `subscriptions` table and follow-ups are deferred.

```text
User Browser
    |
    v
Frontend Web App
Next.js / React
    |
    v
Backend API
FastAPI
    |
    |---- Authentication (app sessions)
    |---- Billing (Checkout + webhooks)
    |---- Prospect Service
    |---- Gift / Order Service
    |---- Fulfillment (admin)
    |---- Analytics (dashboard summary)
    |---- Admin Service
    |
    v
PostgreSQL Database
    |
    |---- Users
    |---- Sessions
    |---- Prospects
    |---- Gift Orders
    |---- Api Keys
    |
    v
External Services
    |---- Stripe
    |---- Resend
```

---

## 5. Main Modules

## Authentication Module

Responsibilities (as shipped):
- User signup / login / logout / guest
- Session management (DB-backed HttpOnly cookie)
- Role management (`user` / `admin` via `ADMIN_EMAILS`; guest)

Deferred: password reset, profile settings.

**Locked for MVP:** app-managed sessions (not Clerk/Auth.js). See `DECISIONS.md`.

---

## Billing Module

Responsibilities:
- Create Checkout sessions per gift order (or CSV batch)
- Receive Stripe webhook events
- Store Stripe customer ID on user (first checkout)
- Store checkout session / payment intent IDs on orders
- Verify `amount_total` against catalog prices before marking paid / capturing
- Release authorizations on cancel (fail closed if Stripe cancel fails)
- Handle authorization expiry via `payment_intent.canceled`

Important Stripe webhook events (MVP):
- `checkout.session.completed`
- `payment_intent.canceled` (and related terminal cancel paths)

Out of scope for MVP: subscription create/update/delete and invoice subscription events.

---

## User and Company Module

Responsibilities:
- Store user profile
- Store company profile
- Associate users with companies
- Manage roles
- Support future team accounts

Possible roles:
- Owner
- Admin
- Salesperson

---

## Prospect Module

Responsibilities:
- Create prospects
- Edit prospects
- View prospects
- Search prospects
- Store **deal status** on the prospect (`open` / `won` / `lost`; no separate `sales_pitch` workflow)
- Store contact fields (`name`, `title`, `company`, `email`). Shipping address and gift note live on the **gift order**, not the prospect.

Important consideration:
Prospect information may include personal/business contact data, so access controls and privacy policies matter.

---

## Gift Catalog Module

Responsibilities:
- Store gift options
- Display gift options to users
- Allow admin to manage gift options
- Support active/inactive gifts
- Support gift categories
- Store gift cost and display price

Possible categories:
- Chocolate
- Cookies
- Coffee
- Tea
- Snack box
- Seasonal gift
- Branded gift

---

## Gift Order Module

Responsibilities:
- Create gift order requests **linked to a prospect** (required FK)
- Charge **one-time** via Stripe Checkout (no plan usage limits in MVP)
- Store **recipient name** and **full shipping address** (or collect later via address-request token)
- Store **note to leave on the gift** (required)
- Store selected gift (must be in `GIFT_CATALOG`)
- Track order + payment status
- CSV import with size/row caps
- Support manual fulfillment
- Support automated fulfillment later

Order statuses (as used):
- `pending_payment`, `no_address`, `queued`, `ordered`, `shipped`, `delivered`, `canceled` (plus failure paths as implemented)

Payment statuses (as used):
- `pending`, `authorized`, `paid`, `canceled`

---

## Fulfillment Module

MVP responsibility:
- Allow admin to view gift requests with **recipient name**, **shipping address**, and **note to leave on the gift** for each order
- Allow admin to manually place gift orders
- Allow admin to update tracking and delivery status

Future responsibility:
- Connect to gift vendor APIs
- Automatically place orders
- Automatically retrieve shipping status
- Handle delivery failures

---

## Follow-Up Module

Responsibilities:
- Schedule follow-up reminders **linked to a prospect** (required)
- Send reminder emails
- Track completion
- Allow users to mark follow-up as done
- Connect follow-up activity to **prospect** outcomes (optional link to a gift order)

MVP recommendation:
Start with reminders to the salesperson.

---

## Analytics Module

Responsibilities:
- Count gifts sent
- Count prospects and outcomes (`open` / `won` / `lost`)
- Track outcomes
- Calculate conversion rate
- Estimate influenced revenue
- Track follow-up completion
- Show simple dashboard metrics

Future analytics:
- Compare gifted vs. non-gifted **prospects** (or opportunities)
- Gift type performance
- Average deal value by gift type
- CRM-based attribution

---

## Admin Module

Responsibilities:
- Manage users
- Manage companies (future)
- Manage gift catalog (static packs for MVP)
- Manage orders
- Update fulfillment status
- View payment status per order
- View failed / stuck authorized orders
- Handle support/admin notes

---

## Integration Module

This should be built later after the MVP is validated.

Future responsibilities:
- CRM OAuth connections
- Import contacts
- Import deals/opportunities
- Push gift activity back to CRM
- Push follow-up reminders to CRM
- Sync outcomes

Important rule:
Do not tightly couple CRM logic with core **prospect** (and order) logic.

Create a generic integration interface first, then implement specific CRMs.

Example interface:
```text
CRMIntegration
    connect()
    disconnect()
    importContacts()
    importDeals()
    pushGiftActivity()
    syncOutcomes()
```

---

## 6. Suggested Database Tables

Core tables (as-built):
- users
- sessions
- prospects (`deal_status`: open / won / lost)
- gift_orders (payment + fulfillment + address-request fields)
- api_keys

Future / deferred tables:
- companies / company_users
- follow_ups
- gifts (if catalog moves off static config)
- sales_outcomes (only if normalized separately from prospect.deal_status)
- admin_notes / audit_logs / integration_connections

---

## 7. Data Ownership Model

### Individual Plan
A user owns their own data.

### Team Plan
A company owns shared data.

Users belong to a company through a company_users table.

### Admin Access
Internal admins can access customer records only for support, fulfillment, and operations.

Admin actions should be logged.

---

## 8. API Design

Recommended API style:
- REST for MVP
- GraphQL only if the frontend becomes complex enough to justify it

Example endpoints (illustrative historical sketch — **as-built routes have no `/api` prefix**; see `api/README.md` and Architecture §0):

```text
POST   /auth/signup
POST   /auth/login
GET    /auth/me

GET    /dashboard/summary

GET    /prospects
POST   /prospects
GET    /prospects/:id
PATCH  /prospects/:id

GET    /gifts
POST   /gift-orders
GET    /gift-orders
GET    /gift-orders/:id
POST   /gift-orders/:id/checkout
POST   /gift-orders/import

GET|POST /public/address-requests/:token

POST   /billing/webhook

GET|POST /api-keys
DELETE /api-keys/:id

GET    /admin/gift-orders
GET|PATCH /admin/gift-orders/:id
```

Not in MVP: customer billing portal, follow-up CRUD, subscription webhooks, admin gift CRUD.

---

## 9. Security Architecture

Security priorities:
- HTTPS everywhere
- Secure authentication (HttpOnly session cookie; `Secure` default in production)
- Role-based access control (`user` / `admin` via `ADMIN_EMAILS`)
- Input validation (including password letter + digit + min length)
- Database access through backend only
- Environment variables for secrets
- Webhook signature validation
- Checkout amount verification vs catalog prices
- Rate limiting for auth, order create, and API-key create (Redis optional for multi-instance)
- CSV import size/row caps
- Address-request token expiry and single-use clearing
- Audit logs for admin actions (future)
- Backups for database

Important:
Never trust frontend-only checks for permissions or payment amounts.

---

## 10. Deployment Architecture

## MVP Option
Simple and fast:
- Frontend: Vercel
- Backend: Render, Railway, Fly.io, or AWS Elastic Beanstalk
- Database: AWS RDS, Supabase, or Neon
- Email: Resend or Postmark
- Payments: Stripe

## More AWS-Centered Option
- Frontend: AWS Amplify or S3 + CloudFront
- Backend: AWS ECS Fargate or Lambda
- Database: Amazon RDS PostgreSQL
- File storage: S3
- Email: Amazon SES
- Background jobs: EventBridge and SQS
- Secrets: AWS Secrets Manager
- Monitoring: CloudWatch

Recommendation:
Use the simplest deployment that lets you validate demand quickly. Move deeper into AWS after revenue justifies the complexity.

---

## 11. Scaling Plan

## Stage 1 — MVP
- Manual fulfillment
- Single database
- Basic app server
- Simple scheduled reminders

## Stage 2 — Beta Customers
- More reliable background jobs
- Better admin tooling
- Better analytics
- Improved database indexes
- Error monitoring

## Stage 3 — Paid Growth
- CRM integration module
- Gift vendor API integrations
- Team accounts
- Usage limits
- More robust billing logic
- Audit logs

## Stage 4 — Larger Customers
- Enterprise roles and permissions
- SSO
- Advanced reporting
- Public API
- Webhooks
- Compliance settings
- Data export tools

---

## 12. Architecture Decisions to Make

Most stack choices are locked in `DECISIONS.md`. Remaining product decisions:

- Choose initial gift fulfillment process / vendor partner
- Choose first CRM integration after validation
- Whether prospects ever receive email from the app (beyond address-request links)

---

## 13. Recommended MVP Architecture

For the practical first version (matches as-built):

```text
Next.js Frontend (Vercel)
    |
    |  /__cak_api proxy
    v
FastAPI Backend (Render)
    |
PostgreSQL (Neon)
    |
Stripe Checkout (one-time per order)
Resend (internal order email)
Manual Admin Fulfillment
Optional Redis (shared rate limits)
```

This is enough to validate the product without spending months building integrations nobody has paid for yet.

---

## 14. Testing and verification

**Test.MD** is the authoritative **recursive test catalog**: features are decomposed into unit, integration, and end-to-end rows that you check off as coverage is added. Prefer mapping automated tests (file names or test IDs) to those rows so requirements stay traceable.

- **Unit tests** — validators, pricing helpers, status transitions, analytics formulas.
- **Integration tests** — HTTP APIs with real DB (or testcontainers), Stripe webhook signatures, email adapters with fakes.
- **End-to-end tests** — browser flows for signup, Checkout, **prospect → gift order** (recipient name, address or address-request, note on gift), prospect outcome update, admin fulfillment.

Continuous integration should run the unit suite on every change; run integration and E2E on merge to main or on a nightly schedule as volume grows. Before production, execute the regression gate in **Test.MD** (anchor **`TEST-REG`**, also titled “Regression gate” there).

---

## 15. Admin bootstrap (MVP)

Internal admins (order queue) need a **first admin** without a self-serve “promote to admin” product. See **Admin bootstrap (MVP)** in [SoftwareRequirements.MD](SoftwareRequirements.MD) for acceptable options: env email allowlist, one-time seed/migration, or manual runbook. Production should document which option is used and how to add a second admin if needed. Gift catalog management is **not** required for MVP (static packs).
