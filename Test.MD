# Test.MD

# CloseAndKeep — Recursive test catalog

This file is the **master checklist** of tests for CloseAndKeep. **Recursive** means each area is broken down **feature → scenario → layer** (unit, integration, end-to-end) until every case is an atomic `- [ ]` line you can check off when automated coverage exists or a manual run passes.

**Convention**

- **Unit (U):** pure logic, validators, helpers—no network or DB unless mocked.
- **Integration (I):** API + DB, webhooks, email adapter with test doubles—real persistence where practical.
- **End-to-end (E):** browser or full-stack smoke against staging-like env.

Track automation by renaming `[ ]` → `[x]` when that row is covered.

### Stable anchor IDs (do not rename without updating cross-references)

These IDs stay fixed even if section numbers shift. Other docs should cite **`TEST-REG`**, **`TEST-LAUNCH`**, and **`TEST-RISK`** instead of §14–§16 only.

| ID | Gate |
|----|------|
| **`TEST-REG`** | Regression gate (before every production deploy) |
| **`TEST-LAUNCH`** | MVP launch gate (beta / GA) |
| **`TEST-RISK`** | High-risk scenarios (must never regress) |

---

## Meta (strategy, tools, environments)

### Goals

Confirm signup/login, one-time Checkout, **prospect → gift** flows (including recipient name, address or address-request, note on the gift), prospect outcomes, admin fulfillment, authz, and regression before release. Follow-up reminders are deferred and are not part of the current MVP gate.

### Suggested tools

- **Frontend / E2E:** Playwright or Cypress; React Testing Library; Vitest or Jest.
- **Backend:** Pytest (FastAPI) or Jest + Supertest (Node).
- **DB:** dedicated test database; transactions or reset between tests; seed fixtures.
- **Stripe:** test mode + Stripe CLI for webhooks.
- **Email:** mock in CI; Mailtrap/Resend test in staging.

### Environments

- **Local:** fast unit + selected integration.
- **Staging:** full E2E, Stripe test, email test, admin paths.
- **Production:** only safe checks; no destructive tests.

### Reference fixtures (build data for tests)

- [x] Fixture: authenticated user (pytest `auth_client`)
- [ ] Fixture: individual unpaid order path (pending_payment)
- [ ] Fixture: team owner + team member (if applicable)
- [x] Fixture: internal admin (`admin_client`)
- [x] Fixture: prospect with contact fields (`name` / `title` / `company` / `email`)
- [ ] Fixture: prospect with minimal fields
- [x] Fixture: gift order payment/status variants exercised in checkout + address-request suites
- [ ] ~~Fixture: subscription states~~ — N/A (MVP is pay-per-order; no subscription gate)

---

## 1. Authentication

### 1.1 Signup

**Unit**

- [x] (U) Email format validation rejects invalid addresses
- [x] (U) Password rules enforced when configured (length, complexity)
- [x] (U) Duplicate email detection uses same normalization as persistence (e.g. lowercased)

**Integration**

- [x] (I) Valid signup creates user (or auth provider user) and DB row
- [x] (I) Duplicate email returns 4xx without leaking which field failed
- [x] (I) Invalid payload returns 4xx with field errors

**End-to-end**

- [ ] (E) User completes signup with valid data and lands in expected post-signup state
- [ ] (E) User cannot sign up with duplicate email (message is safe and clear)
- [ ] (E) User is redirected or guided per product rules after signup

### 1.2 Login

**Unit**

- [x] (U) Session or token expiry logic behaves as configured

**Integration**

- [x] (I) Valid credentials return session/JWT and match user id
- [x] (I) Invalid password returns generic failure
- [x] (I) Unknown email returns same failure class as bad password (no enumeration)

**End-to-end**

- [ ] (E) User logs in and reaches dashboard (or intended landing)
- [ ] (E) Wrong password shows safe error
- [ ] (E) Logged-in user hitting `/login` is redirected away if applicable

### 1.3 Logout

- [x] (I) Logout invalidates session server-side or clears refresh token path
- [ ] (E) After logout, protected routes redirect to login

### 1.4 Password reset

**Deferred** — no reset tokens/emails/routes. Keep rows unchecked until the feature ships.

- [ ] (I) Reset request creates token or provider flow with expiry
- [ ] (I) Expired token cannot set password
- [ ] (I) Used token cannot be reused
- [ ] (E) User completes reset and logs in with new password

---

## 2. Authorization and tenancy

### 2.1 Prospect / order scope

**Integration**

- [x] (I) `GET /prospects/:id` returns 404 or 403 for another user’s id
- [x] (I) `PATCH` on foreign prospect fails
- [x] (I) Gift order listing returns only current user (or company) rows

**End-to-end**

- [ ] (E) User cannot open another user’s prospect by changing URL id

### 2.2 Admin

- [x] (I) Non-admin receives 403 on admin API routes
- [ ] (E) Non-admin cannot open admin UI routes
- [ ] (I) Admin actions logged where required

### 2.3 Subscription gate

- [x] (I) N/A for MVP — no subscription gate; gift create requires auth + payment at Checkout (covered by gift-order / checkout suites)
- [ ] (E) Unpaid / abandoned Checkout leaves order unfulfilled (staging smoke)

---

## 3. Stripe billing

### 3.1 Checkout

- [x] (I) Checkout session created with correct price id for gift pack
- [x] (I) Successful checkout webhook / fulfill marks order paid (or authorized when deferring address)
- [x] (I) Amount above catalog price is rejected (order stays unpaid / not advanced)
- [ ] (E) User completes test checkout in browser

### 3.2 Webhooks

- [x] (I) Signature invalid → 400 and no DB change
- [x] (I) `payment_intent.canceled` cancels authorized order and clears address token
- [x] (I) Replay / duplicate `checkout.session.completed` is idempotent (`test_webhook_replay_does_not_double_process`)

### 3.3 Authorize / capture and admin cancel

- [x] (I) Deferred-address path authorizes then captures after address submit
- [x] (I) Admin cancel fails closed when Stripe PaymentIntent.cancel fails
- [ ] (E) Recipient completes `/ship/[token]` and order becomes queued

### 3.4 Billing portal / subscriptions

- [x] Out of scope for MVP (no Customer Portal / subscription webhooks)

---

## 4. Prospects

### 4.1 Create

**Unit**

- [x] (U) Required fields validated; optional fields optional

**Integration**

- [x] (I) Create persists with correct `owner_user_id`
- [x] (I) Invalid email rejected

**End-to-end**

- [ ] (E) Create form shows validation errors
- [ ] (E) Contact fields saved and shown on detail (prospects have no shipping address)

### 4.2 List / search / detail

- [x] (I) List scoped to owner; search does not leak others’ rows
- [ ] (E) Detail page matches list selection

### 4.3 Edit / archive

- [x] (I) User cannot update another user’s prospect
- [ ] (E) Archived prospect hidden from default list; **gift orders** remain per retention rules

---

## 5. Prospect outcomes and pipeline

*(No separate pitch entity—deal status and outcomes live on the prospect.)*

### 5.1 Outcome and pipeline fields

- [x] (I) Deal status / outcome updates persist on **prospect** with correct owner scope
- [x] (I) User cannot update another user’s prospect outcome
- [ ] (E) User edits outcome on prospect detail; dashboard metrics update

### 5.2 Prospect detail aggregation

- [ ] (E) Prospect detail shows contact + deal status (gift-order / follow-up lists deferred)

---

## 6. Gift catalog

### 6.1 User-facing

- [x] (I) `GET /gifts` returns known packs with prices
- [ ] (E) Catalog / wizard displays pack labels from `gift-catalog.ts`

### 6.2 Admin

- [ ] (I) Admin CRUD gift; non-admin forbidden — deferred (static catalog)
- [ ] (E) Deactivated gift disappears from user catalog after refresh — deferred

---

## 7. Gift orders (critical path)

### 7.1 Validation

**Unit**

- [x] (U) Submit rejected when recipient name blank
- [x] (U) Submit rejected when address blank/incomplete unless address-request path
- [x] (U) Submit rejected when note-on-gift blank or whitespace-only

**Integration**

- [x] (I) Order row stores recipient name, full address, note on gift, **FK to prospect** (and gift)
- [x] (I) Idempotent or duplicate-submit behavior defined and tested

**End-to-end**

- [ ] (E) Prefill from prospect works; user can override
- [ ] (E) Review step shows all three before submit
- [ ] (E) Submit creates queued order and confirmation UI

### 7.2 Status lifecycle

- [x] (I) Status transitions only from allowed states
- [ ] (E) User sees status updates after admin changes

### 7.3 Plan limits / CSV caps

- [x] (I) N/A plan weekly limits — pay per order
- [x] (I) CSV import rejects oversized upload
- [x] (I) CSV import rejects too many rows
- [ ] (E) Clear messaging when CSV import fails validation

---

## 8. Fulfillment (admin)

### 8.1 Queue and detail

- [ ] (E) Admin sees queued orders with recipient name, address, note on gift
- [x] (I) Status update persists; optional tracking number saved

### 8.2 Notifications

- [ ] (I) Email job triggered on ship/deliver with template data
- [ ] (E) User receives expected emails in staging (or assert mock calls)

---

## 9. Follow-up reminders

**Deferred** — no API/table/jobs. Keep rows unchecked until the feature ships.

### 9.1 Scheduling

- [ ] (I) Follow-up stored with **prospect** id and due date
- [ ] (E) Dashboard lists due follow-ups

### 9.2 Reminder job

- [ ] (I) Due reminders enqueue email to salesperson (not prospect if MVP says so)
- [ ] (I) Completed/skipped reminders not resent
- [ ] (I) Failure logged on email bounce

---

## 10. Analytics and dashboard

### 10.1 Counts

- [ ] (U) Win rate `won / (won + lost)` — computed in web dashboard UI (no API unit test yet)
- [x] (I) Dashboard API matches DB aggregates for seed data (`open_deals` / `won` / `lost` / `total_prospects`)
- [ ] (E) Changing outcome updates visible metrics
- [ ] (U) Time-ranged conversion formula — deferred until analytics expands

### 10.2 Edge cases

- [ ] (I) Archived prospect does not corrupt historical totals per product rules

---

## 11. UX and accessibility (baseline)

- [ ] (E) Empty dashboard has clear primary action
- [ ] (E) Primary flows keyboard-accessible where applicable
- [ ] (E) Mobile: dashboard, forms, gift flow usable

---

## 12. Security

### 12.1 Input / output

- [x] (I) XSS payloads stored do not execute in rendered pages (escape/limit)
- [x] (I) SQL injection strings do not alter unintended rows (parameterized queries)

### 12.2 Secrets and transport

- [x] (I) Webhook raw body used for signature verification
- [x] (I) Production default enables Secure session cookie (`SESSION_COOKIE_SECURE`)
- [ ] (E) No API secrets in browser bundle

### 12.3 Auth / tokens / rate limits

- [x] (I) Signup password complexity enforced
- [x] (I) Duplicate signup does not enumerate emails
- [x] (I) Address-request token expires after TTL
- [x] (I) Auth / sensitive routes rate-limited (see `test_rate_limit.py`)

---

## 13. Landing and marketing (if shipped)

- [ ] (E) CTA leads to signup or login
- [ ] (E) Legal links present in footer

---

## 14. Regression gate (before every production deploy)

**Anchor ID:** `TEST-REG` — cite this ID from Architecture.MD and TaskList.MD.

**Smoke — run in staging**

- [ ] (E) Signup or login
- [ ] (E) Stripe checkout (test mode)
- [ ] (E) Create prospect → gift order with name, address (or address-request), note
- [ ] (E) Admin moves order to shipped; user sees update
- [ ] (E) Logout and authz spot-check
- [ ] Follow-up reminder path — **N/A until follow-ups ship**

**Automated suite**

- [x] Full API unit/integration suite green locally (`python -m pytest tests/` — 166+ as of 2026-07-21)
- [ ] Integration suite green in CI on every PR
- [ ] Critical E2E suite green

---

## 15. MVP launch gate (beta / GA)

**Anchor ID:** `TEST-LAUNCH`

- [ ] Priority requirements from `SoftwareRequirements.MD` verified against sections above
- [ ] Stripe live-mode smoke on minimal transaction (if applicable) after staging sign-off
- [ ] Privacy policy and terms published and linked
- [ ] Monitoring and error logging on
- [ ] Database backups verified

---

## 16. High-risk scenarios (must never regress)

**Anchor ID:** `TEST-RISK`

Double-check after billing or auth changes:

- [x] Unpaid / amount-mismatched Checkout never advances to fulfilled payment state
- [x] Authorized hold cancel fails closed if Stripe cancel fails
- [ ] Gift never ships with wrong address or missing note on gift for fulfillment
- [x] No cross-tenant data in API responses
- [x] Webhook replay or duplicate does not double-charge state
- [ ] Duplicate follow-up emails not sent for same completed reminder
