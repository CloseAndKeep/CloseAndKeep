# SoftwareRequirements.MD

# CloseAndKeep — Software Requirements

## 1. Purpose

This document defines the software requirements for CloseAndKeep, a sales gift website where users pay once per gift order (no subscription).

CloseAndKeep will help salespeople send small gifts after customer conversations (e.g., demos, calls), schedule follow-ups, and track whether **prospects** convert—using **prospect-level** outcomes rather than a separate “pitch” workflow in the product.

### 1.1 Product positioning (canonical)

**Value proposition:** CloseAndKeep helps SaaS sellers close more deals and keep more customers by turning post-pitch follow-up into simple, trackable gift sends that keep you memorable without sounding robotic.

**Initial ideal customer:** SaaS salespeople (e.g., account executives and sales reps) who run demos and need differentiated follow-up.

**Messaging:** Customer-facing copy should not lead with “automation” until automation is a primary shipped focus.

**Billing model (locked for MVP): one-time payment per gift order.** Users pay once, via Stripe Checkout (`mode: payment`), each time they submit a gift order. There is **no subscription, no recurring billing, and no weekly order cap** in the MVP. Recurring/subscription tiers may be reconsidered later but are explicitly out of scope today.

## 2. Scope

The initial product will focus on individual salespeople and small teams.

**MVP v1 focus:** optimize for **solo salespeople** (one login per paid seat). `company` / team entities and shared data may exist in the schema as optional scaffolding for later, but **team collaboration and company dashboards are not required to ship the first paid MVP** unless you explicitly move them into scope.

The first version should support:
- User accounts (signup / login / logout; password reset deferred)
- One-time payment per gift order (no subscription)
- Manual prospect entry (`name`, `title`, `company`, `email`, `deal_status`)
- **Prospect pipeline / outcome tracking** (`open` / `won` / `lost`)
- Gift selection (static cookie packs)
- Gift order request tracking (linked to prospect; optional deferred address)
- CSV gift-order import (capped)
- Basic dashboard metrics
- Admin fulfillment workflow

Deferred within MVP product surface (explicitly on hold):
- Follow-up reminders (API, jobs, emails)
- Password reset / profile settings
- Customer-facing status emails

Future versions may support:
- CRM integrations
- Company API integrations
- Automated vendor fulfillment
- Team management
- Advanced analytics
- Public API
- Webhooks
- Enterprise features

---

## 3. Definitions

### User
A person using the application, usually a salesperson.

### Company
A business or team account that can contain one or more users.

### Prospect
The person or company contact the user is working. The user may send gifts to this contact and track **deal status / outcome** on the prospect record. (Marketing may still say “post-pitch” or “after the demo”; the product does **not** require logging a separate pitch object.)

### Gift
A small physical item sent to the prospect, such as chocolate, cookies, coffee, or another thoughtful item.

### Gift Order
The record of a gift request, fulfillment status, and delivery status. Each gift order must include **recipient name** and **note to leave on the gift**. **Full shipping address** is required before fulfillment; it may be entered by the seller at create time or collected later via a time-limited recipient address-request link.

### Follow-Up
A reminder or email related to checking in with the **prospect** after a gift or touchpoint.

### Outcome
The result of the opportunity for a **prospect** (`open`, `won`, or `lost`), stored on the prospect. Additional statuses (e.g. no response) and deal-value fields are deferred.

---

## 4. Functional Requirements

## 4.1 User Accounts

### Requirement: User Signup
The system shall allow a new user to create an account.

Acceptance criteria:
- User can enter email and password (name optional / deferred for MVP profile)
- Password meets policy: minimum length (default 12; `PASSWORD_MIN_LENGTH`) and includes at least one letter and one digit
- User receives confirmation or is redirected into onboarding
- Duplicate email addresses are not allowed
- Duplicate signup returns a **generic** client error (no “email already in use” enumeration)
- Invalid emails are rejected

### Requirement: User Login
The system shall allow existing users to log in.

Acceptance criteria:
- User can log in with email and password
- Incorrect credentials show a safe error message
- Authenticated users can access the dashboard
- Unauthenticated users are redirected to login

### Requirement: Password Reset
**Deferred for MVP.** No forgot-password flow, reset tokens, or reset emails are shipped. Users who lose access must be helped manually (or re-signup is blocked by email uniqueness).

### Requirement: User Profile
**Partial for MVP.** Logout and session `/auth/me` are shipped. There is no profile name field or Stripe customer portal. `/billing` shows the user’s gift-order payment history only.

---

## 4.2 Payments (one-time per gift order)

The MVP bills **per gift order**, not via subscription. A user pays once, at checkout, for each gift they send.

### Requirement: Pricing Page
The system shall display per-order pricing.

Acceptance criteria:
- Per-order price is clearly shown
- It is clear there is no subscription required
- Included features are listed
- User can start a gift order from the pricing page

### Requirement: Stripe Checkout (one-time)
The system shall allow users to pay for a gift order through Stripe Checkout in `mode: payment`.

Acceptance criteria:
- User submits a gift order and is redirected to Stripe Checkout
- Successful payment marks the order paid and moves it to `queued` for fulfillment (unless address is deferred — see below)
- Before advancing payment state, the API rejects Checkout amounts that **exceed** the sum of catalog Stripe prices for the linked order(s) (amounts below catalog are allowed for promos)
- Failed or canceled checkout leaves the order in `pending_payment` and does not start fulfillment
- The user can retry checkout for an unpaid order

### Requirement: Deferred recipient address (authorize / capture)
The system shall support collecting shipping address from the recipient after payment authorization.

Acceptance criteria:
- Seller may request recipient address at order create (email + public token link)
- Card is authorized (not captured) until a valid address is submitted
- Address-request tokens expire after a configured TTL (default 7 days, aligned with Stripe hold)
- Tokens are cleared after successful submit, order cancel, or authorization expiry (`payment_intent.canceled`)
- Expired or already-used tokens are rejected

### Requirement: Stripe Webhooks
The system shall listen for Stripe payment events.

Acceptance criteria:
- Webhook signatures are verified
- `checkout.session.completed` marks the matching gift order paid/queued (or authorized/`no_address` when deferring address), subject to amount verification
- `payment_intent.canceled` cancels the matching authorized order and clears address tokens
- A fetch-time fallback re-checks the Checkout session if the webhook is missed (also subject to amount verification)
- Amount mismatches do not advance payment state; failures are logged
- Failures are logged

### Requirement: Admin cancel of authorized orders
When an admin cancels an order with an open card authorization, the system shall cancel the Stripe PaymentIntent before updating local payment state.

Acceptance criteria:
- If Stripe cancel fails for an open hold, the API returns an error and leaves local status unchanged (fail closed)
- If Stripe already shows a terminal status (`canceled` / `succeeded`), local cancel may proceed

> **Out of scope for MVP:** subscription plans, recurring billing, weekly order caps, and the Stripe customer billing portal. The unused `users.subscription_status` / `users.subscription_plan` columns were dropped (migration `0007`); `users.stripe_customer_id` is retained and populated at first checkout.

---

## 4.3 Dashboard

### Requirement: User Dashboard
The system shall provide a dashboard after login.

Acceptance criteria (as shipped):
- Dashboard shows prospect outcome counts: open, won, lost, and total
- Dashboard shows a simple win rate: `won / (won + lost)` when the denominator is non-zero
- Dashboard has clear navigation into prospects and orders

Deferred dashboard items: gifts-sent count, follow-up due list, time-ranged analytics, and the richer §4.11 conversion definition.

### Requirement: Empty States
The system shall show helpful empty states for new users.

Acceptance criteria:
- New users see clear next actions
- Empty dashboard encourages adding a first **prospect** and/or **gift order**
- Empty states use friendly language

---

## 4.4 Prospect Management

### Requirement: Create Prospect
The system shall allow users to create a prospect.

Acceptance criteria (as shipped):
- User can enter **name**, **title**, **company**, and **email**
- Required fields are validated
- Prospect is associated with the owning user
- Gift orders store their own recipient name / address / note (prospect does not store shipping address)
### Requirement: View Prospects
The system shall allow users to view a list of prospects.

Acceptance criteria:
- User can see only their own prospects
- User can open prospect detail page
- Search / filter on the list is nice-to-have (not required for MVP)
### Requirement: Edit Prospect
The system shall allow users to edit prospect information.

Acceptance criteria:
- User can update prospect details
- Changes are saved to database
- User cannot edit prospects they do not have permission to access

### Requirement: Delete or Archive Prospect
**Deferred for MVP.** No archive/delete prospect API or UI is shipped yet.

---

## 4.5 Prospect pipeline and outcomes

The product does **not** include a dedicated **Sales Pitch** screen or entity. Pipeline and closings are tracked **on the prospect** (and via gift orders / follow-ups tied to that prospect).

### Requirement: Prospect outcome and pipeline fields
The system shall allow users to record and update pipeline information **on the prospect**.

Acceptance criteria (as shipped):
- User can set **deal status** to one of: `open`, `won`, `lost`
- Deal status updates are scoped to the owning user

Deferred: estimated deal value, close date, prospect notes, `no_response` status.

### Requirement: Prospect detail
The prospect detail experience shall show contact fields and deal status.

Acceptance criteria (as shipped):
- Shows name, title, company, email
- Shows and edits current **deal status**

Deferred on detail: gift-order list for the prospect, follow-ups list.
**Note:** CRM integrations may import external “deals” or “opportunities” later; that does not require a first-class **Pitch** table in CloseAndKeep as long as activity remains attributable to a **prospect**.

---

## 4.6 Gift Catalog

### Requirement: View Gift Catalog
The system shall expose the cookie-pack catalog for ordering.

Acceptance criteria (as shipped):
- `GET /gifts` returns known pack ids with live Stripe unit amounts when configured
- Web UI labels packs via `web/lib/gift-catalog.ts`
- User selects a pack during the gift-order wizard

### Requirement: Manage Gifts
**Deferred for MVP.** Catalog is static in API config + Stripe Price env vars. No admin gift CRUD UI/API.
---

## 4.7 Gift Ordering

### Requirement: Create Gift Order
The system shall allow a user to request a gift for a prospect.

Acceptance criteria:
- User selects **prospect**
- User selects gift (must be a known catalog id)
- User enters or confirms **recipient name** (delivery name)
- User enters or confirms **full shipping address**, **or** elects recipient address request (email + public link)
- User enters **note to leave on the gift** (required text for the card or enclosure; empty or whitespace-only is invalid)
- Order is saved; payment via Checkout; fulfillment status becomes `queued` after paid capture (or after address submit when deferred)
- User sees confirmation

### Requirement: CSV gift-order import
The system shall allow authenticated users to import multiple gift orders from CSV.

Acceptance criteria:
- Template and example CSV are available from the API
- Uploads exceeding configured byte or row caps are rejected
- Invalid rows are reported without creating partial Stripe sessions for those rows (per implemented error contract)
- Successful rows create orders and Checkout as for single create

### Requirement: Gift Order Status
The system shall track gift order status.

Acceptance criteria:
- Gift order can be `pending_payment`, `no_address`, `queued`, `ordered`, `shipped`, `delivered`, or `canceled` (as implemented)
- User can view current status
- Admin can update status

### Requirement: Usage Limits
**Not applicable to the MVP.** Because billing is one-time per gift order, there is no plan-based weekly cap to enforce — each order is paid for individually at checkout. Usage limits would only return if a recurring subscription tier is introduced later. Sensitive create paths are still **rate-limited** (per user / IP; optional Redis-backed shared store).

---

## 4.8 Fulfillment

### Requirement: Admin Order Queue
The system shall provide an admin order queue.

Acceptance criteria:
- Admin can view queued orders
- Admin can view **recipient name**, **full shipping address**, and **note to leave on the gift** for each order
- Admin can update order status
- Admin can add tracking number
- Admin can mark order as shipped or delivered

### Requirement: Manual Fulfillment
The MVP shall support manual fulfillment.

Acceptance criteria:
- Admin can manually place gift order outside the system
- Admin can record tracking / status / internal notes
- Customer-facing status-change emails are **deferred** (only the internal new-order Resend notification is shipped)

### Future Requirement: Automated Vendor Fulfillment
The system may later connect to gift vendor APIs.

Acceptance criteria:
- System can send order to vendor
- System can receive vendor order ID
- System can update shipping status automatically

---

## 4.9 Follow-Up Reminders

**Deferred for MVP.** The `/follow-ups` page is an honest “coming soon” placeholder. There is no follow-up table, API, reminder job, or reminder email yet.

### Future requirement: Schedule Follow-Up
When implemented, the system shall allow a user to schedule a follow-up reminder linked to a prospect (optional link to a gift order), show due items on the dashboard, and email the salesperson.

---

## 4.10 Sales outcome tracking (prospect)

### Requirement: Mark outcome
The system shall allow users to mark an **outcome for the prospect** (same fields as §4.5; may be implemented as one flow).

Acceptance criteria (as shipped):
- User can mark `open`, `won`, or `lost`
- Outcome updates dashboard open / won / lost / total metrics

---

## 4.11 Analytics

### Requirement: Basic Dashboard Metrics
The system shall show basic analytics.

Acceptance criteria (as shipped):
- Open / won / lost / total prospect counts
- Win rate = `won / (won + lost)` when `(won + lost) > 0` (else empty / zero display)

**Target conversion definition (not yet implemented):** in a selected time range, **won ÷ terminal outcomes** where terminal means `won` or `lost`. Product, code, and **Test.MD** must stay aligned when time-ranged analytics ship.

### Requirement: Gift Impact Metrics
**Deferred.** Gifted vs non-gifted close-rate and revenue influence are not shipped.

---

## 4.12 Admin Dashboard

### Requirement: Admin Access
The system shall provide admin-only pages.

Acceptance criteria:
- Only admin users can access admin dashboard / APIs
- Admin can view and update gift orders (status, tracking, notes)
- Admin gift-catalog CRUD and user list are deferred

### Requirement: Admin bootstrap (MVP)

The system must support **at least one internal admin** who can use the admin order queue and admin APIs. The product does not need a self-serve “become an admin” flow for MVP, but it **must** define how the first admin exists.

**Acceptable MVP approaches** (choose one; document the choice in [Architecture.MD](Architecture.MD) and deployment runbooks):

- **Env allowlist:** e.g. `ADMIN_EMAILS` (comma-separated); on signup or each login, if the user’s email matches, set or sync `role=admin` (or equivalent).
- **Seed / migration:** one-time script or migration that sets a designated user id or email to admin in non-production and production (with a runbook for the first production admin).
- **Manual SQL / provider dashboard:** document the exact command or steps for the operator to grant admin once (acceptable only if paired with a clear runbook and access control to the database).

**Out of scope for MVP unless you need it:** invite-only admin portal, multiple admin roles, or self-service promotion to admin.

---

## 5. Non-Functional Requirements

## 5.1 Usability
The system shall be easy for non-technical salespeople to use.

Requirements:
- Clear language
- Minimal setup
- Simple forms
- Helpful empty states
- Mobile-friendly layout
- Fast primary workflows
- Professional coffee-house visual style

## 5.2 Performance
The system should feel fast to users.

Requirements:
- Dashboard should load quickly
- Common pages should respond within a few seconds
- Slow background tasks should not block the UI
- Database queries should be indexed as data grows

## 5.3 Security
The system shall protect user and prospect data.

Requirements:
- HTTPS required
- Secure authentication (HttpOnly session cookie; `Secure` default when `APP_ENV=production`)
- Role-based access control
- Input validation
- Secure password storage (bcrypt) with min length + letter/digit policy
- No email enumeration on duplicate signup
- Environment variables for secrets
- Stripe webhook signature verification
- Checkout amount verification against catalog prices
- Rate limiting for sensitive endpoints (auth, order create, API-key create; optional Redis)
- CSV import size and row caps
- Address-request token expiry
- Regular database backups

## 5.4 Privacy
The system shall handle prospect data responsibly.

Requirements:
- Privacy policy
- Terms of service
- User data deletion process
- Do not collect unnecessary sensitive information
- Limit admin access to necessary operational tasks
- Consider gift compliance policies for companies

## 5.5 Reliability
The system should be reliable enough for paid users.

Requirements:
- Database backups
- Error logging
- Monitoring
- Failed email logs
- Failed payment handling
- Retry logic for background jobs where appropriate

## 5.6 Scalability
The system should support growth without major rewrites.

Requirements:
- Modular services
- PostgreSQL schema designed for teams
- Integration layer kept separate
- Background job system can be added later
- Gift fulfillment can move from manual to API-based later

---

## 6. External System Requirements

## Stripe
Used for:
- One-time Checkout (`mode: payment`) per gift order
- Authorize / capture when recipient address is deferred
- Payment webhooks (`checkout.session.completed`, `payment_intent.canceled`, …)
- Per-order payment status with catalog amount verification

## Email Provider
Used for (as shipped):
- Internal new-order notification (Resend)

Deferred:
- Follow-up reminders
- Gift status updates to the seller
- Account / password-reset emails
- Payment issue notices

## Gift Vendors
MVP:
- Manual ordering

Future:
- Gift vendor API integration

## CRM Systems
Future:
- HubSpot
- Salesforce
- Pipedrive
- Zoho
- Other CRMs based on customer demand

---

## 7. MVP Acceptance Criteria

The MVP is complete when:

- A user can create an account (password policy enforced; no email enumeration on duplicate)
- A logged-in user can access the dashboard
- A user can pay for a gift order with Stripe (one-time, at checkout; amount cannot exceed catalog)
- A user can create a prospect and set deal status (`open` / `won` / `lost`)
- A user can choose a cookie pack and submit a gift order (address now or via recipient link)
- Admin can view and manage gift orders (status / tracking / notes)
- Dashboard shows open / won / lost / total and a simple win rate
- Internal new-order email works when Resend is configured
- Unauthorized users cannot access protected data

Explicitly **not** required to call MVP complete: follow-up reminders, password reset, customer status emails, admin gift CRUD.

### Verification traceability

MVP acceptance is demonstrated against **Test.MD**, the recursive test checklist (unit, integration, end-to-end). Each Priority 1 behavior should map to explicit rows there; check items off as automated tests pass or as manual runs are recorded for sign-off. For release gates, use the **stable anchor IDs** in Test.MD (**`TEST-REG`**, **`TEST-LAUNCH`**, **`TEST-RISK`**) so cross-references do not break if section numbers change.

---

## 8. Out of Scope for MVP

The following are not required for the first version:

- Follow-up reminder backend / emails
- Password reset
- Customer-facing order status emails
- Admin gift catalog CRUD
- CRM integrations
- Broad public API / outbound webhooks (user API keys exist; docs/versioning deferred)
- Automated gift vendor API ordering
- Advanced analytics
- AI recommendations
- Native mobile app
- SSO
- Enterprise compliance controls
- Complex team permissions
- Multi-language support

---

## 9. Open Requirements Questions

- **Resolved:** Billing is one-time per gift order (no subscription, no gift credits) for the MVP.
- What is the first gift vendor?
- Will fulfillment be manual at launch?
- Which CRM should be integrated first later?
- Should prospects ever receive emails directly from the app?
- What is the expected price range per gift?
- Should users be able to customize cards/messages?
- Should companies set gift spending limits?
- Should admin approve every gift before fulfillment?

---

## 10. Recommended Requirement Priority

## Priority 1
- Signup/login (password policy + anti-enumeration)
- Stripe one-time payment per gift order (incl. deferred address + amount checks)
- Dashboard (open / won / lost / total)
- Prospects (deal status on prospect)
- Gift requests + admin order queue
- Outcome tracking (`open` / `won` / `lost`)

## Priority 2
- Follow-up reminders
- Password reset / account settings
- Customer status emails
- Better analytics (time range, gifts sent)
- Team accounts
- Gift templates
- Improved onboarding
- Better admin tools (user list, gift CRUD)

## Priority 3
- CRM integration
- Gift vendor API integration
- Broader public API / outbound webhooks
- Advanced reporting
- Enterprise features

> Gift-order CSV import and user API keys are already implemented (see `api/README.md`).
