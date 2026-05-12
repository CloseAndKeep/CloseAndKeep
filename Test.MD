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

Confirm signup/login, billing gates, **prospect → gift** flows (including recipient name, address, note on the gift), prospect outcomes, admin fulfillment, follow-ups, analytics, authz, and regression before release.

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

- [ ] Fixture: individual paid user
- [ ] Fixture: individual unpaid / lapsed user
- [ ] Fixture: team owner + team member (if applicable)
- [ ] Fixture: internal admin
- [ ] Fixture: prospect with full address
- [ ] Fixture: prospect with minimal fields
- [ ] Fixture: gift order in each status (draft, queued, ordered, shipped, delivered, failed, canceled) as needed
- [ ] Fixture: subscription active, trialing, past_due, canceled, incomplete

---

## 1. Authentication

### 1.1 Signup

**Unit**

- [ ] (U) Email format validation rejects invalid addresses
- [ ] (U) Password rules enforced when configured (length, complexity)
- [ ] (U) Duplicate email detection uses same normalization as persistence (e.g. lowercased)

**Integration**

- [ ] (I) Valid signup creates user (or auth provider user) and DB row
- [ ] (I) Duplicate email returns 4xx without leaking which field failed
- [ ] (I) Invalid payload returns 4xx with field errors

**End-to-end**

- [ ] (E) User completes signup with valid data and lands in expected post-signup state
- [ ] (E) User cannot sign up with duplicate email (message is safe and clear)
- [ ] (E) User is redirected or guided per product rules after signup

### 1.2 Login

**Unit**

- [ ] (U) Session or token expiry logic behaves as configured

**Integration**

- [ ] (I) Valid credentials return session/JWT and match user id
- [ ] (I) Invalid password returns generic failure
- [ ] (I) Unknown email returns same failure class as bad password (no enumeration)

**End-to-end**

- [ ] (E) User logs in and reaches dashboard (or intended landing)
- [ ] (E) Wrong password shows safe error
- [ ] (E) Logged-in user hitting `/login` is redirected away if applicable

### 1.3 Logout

- [ ] (I) Logout invalidates session server-side or clears refresh token path
- [ ] (E) After logout, protected routes redirect to login

### 1.4 Password reset

- [ ] (I) Reset request creates token or provider flow with expiry
- [ ] (I) Expired token cannot set password
- [ ] (I) Used token cannot be reused
- [ ] (E) User completes reset and logs in with new password

---

## 2. Authorization and tenancy

### 2.1 Prospect / order scope

**Integration**

- [ ] (I) `GET /prospects/:id` returns 404 or 403 for another user’s id
- [ ] (I) `PATCH` on foreign prospect fails
- [ ] (I) Gift order listing returns only current user (or company) rows

**End-to-end**

- [ ] (E) User cannot open another user’s prospect by changing URL id

### 2.2 Admin

- [ ] (I) Non-admin receives 403 on admin API routes
- [ ] (E) Non-admin cannot open admin UI routes
- [ ] (I) Admin actions logged where required

### 2.3 Subscription gate

- [ ] (I) Gift order POST returns 402/403 when subscription inactive per rules
- [ ] (E) Unpaid user cannot complete gift request past review/submit

---

## 3. Stripe billing

### 3.1 Checkout

- [ ] (I) Checkout session created with correct price id for plan
- [ ] (I) Successful checkout webhook updates DB subscription fields
- [ ] (E) User completes test checkout and gains paid access

### 3.2 Webhooks

- [ ] (I) Signature invalid → 400 and no DB change
- [ ] (I) `customer.subscription.updated` updates status
- [ ] (I) `invoice.payment_failed` marks past_due or equivalent
- [ ] (I) `customer.subscription.deleted` revokes paid access per rules

### 3.3 Billing portal

- [ ] (E) User opens portal and returns without breaking session
- [ ] (I) Cancellation webhook aligns app state

---

## 4. Prospects

### 4.1 Create

**Unit**

- [ ] (U) Required fields validated; optional fields optional

**Integration**

- [ ] (I) Create persists with correct `user_id` / `company_id`
- [ ] (I) Invalid email rejected

**End-to-end**

- [ ] (E) Create form shows validation errors
- [ ] (E) Shipping address saved and shown on detail

### 4.2 List / search / detail

- [ ] (I) List scoped to owner; search does not leak others’ rows
- [ ] (E) Detail page matches list selection

### 4.3 Edit / archive

- [ ] (I) User cannot update another user’s prospect
- [ ] (E) Archived prospect hidden from default list; **gift orders** remain per retention rules

---

## 5. Prospect outcomes and pipeline

*(No separate pitch entity—deal status and outcomes live on the prospect.)*

### 5.1 Outcome and pipeline fields

- [ ] (I) Deal status / outcome updates persist on **prospect** with correct owner scope
- [ ] (I) User cannot update another user’s prospect outcome
- [ ] (E) User edits outcome on prospect detail; dashboard metrics update

### 5.2 Prospect detail aggregation

- [ ] (E) Prospect detail shows contact, **gift orders**, follow-ups, and outcome

---

## 6. Gift catalog

### 6.1 User-facing

- [ ] (I) Inactive gifts excluded from catalog API
- [ ] (E) Catalog displays name, image, description, category

### 6.2 Admin

- [ ] (I) Admin CRUD gift; non-admin forbidden
- [ ] (E) Deactivated gift disappears from user catalog after refresh

---

## 7. Gift orders (critical path)

### 7.1 Validation

**Unit**

- [ ] (U) Submit rejected when recipient name blank
- [ ] (U) Submit rejected when address blank/incomplete per rules
- [ ] (U) Submit rejected when note-on-gift blank or whitespace-only

**Integration**

- [ ] (I) Order row stores recipient name, full address, note on gift, **FK to prospect** (and gift)
- [ ] (I) Idempotent or duplicate-submit behavior defined and tested

**End-to-end**

- [ ] (E) Prefill from prospect works; user can override
- [ ] (E) Review step shows all three before submit
- [ ] (E) Submit creates queued order and confirmation UI

### 7.2 Status lifecycle

- [ ] (I) Status transitions only from allowed states
- [ ] (E) User sees status updates after admin changes

### 7.3 Plan limits

- [ ] (I) At-limit user cannot queue another gift
- [ ] (E) Clear messaging when limit hit

---

## 8. Fulfillment (admin)

### 8.1 Queue and detail

- [ ] (E) Admin sees queued orders with recipient name, address, note on gift
- [ ] (I) Status update persists; optional tracking number saved

### 8.2 Notifications

- [ ] (I) Email job triggered on ship/deliver with template data
- [ ] (E) User receives expected emails in staging (or assert mock calls)

---

## 9. Follow-up reminders

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

- [ ] (U) Conversion rate matches `SoftwareRequirements.MD` §4.11 (won ÷ terminal outcomes in period) for controlled fixtures
- [ ] (I) Dashboard API matches DB aggregates for seed data
- [ ] (E) Changing outcome updates visible metrics

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

- [ ] (I) XSS payloads stored do not execute in rendered pages (escape/limit)
- [ ] (I) SQL injection strings do not alter unintended rows (parameterized queries)

### 12.2 Secrets and transport

- [ ] (I) Webhook raw body used for signature verification
- [ ] (E) No API keys in browser bundle

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
- [ ] (E) Create prospect → gift order with name, address, note (optional: set prospect outcome)
- [ ] (E) Admin moves order to shipped; user sees update
- [ ] (E) Follow-up reminder path (or verify job in logs)
- [ ] (E) Logout and authz spot-check

**Automated suite**

- [ ] Full unit suite green
- [ ] Integration suite green (or agreed subset + nightly full)
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

- [ ] Unpaid user never gains paid-only behavior without subscription
- [ ] Paid user never blocked incorrectly by stale subscription row
- [ ] Gift never ships with wrong address or missing note on gift for fulfillment
- [ ] No cross-tenant data in API responses
- [ ] Webhook replay or duplicate does not double-charge state
- [ ] Duplicate follow-up emails not sent for same completed reminder
