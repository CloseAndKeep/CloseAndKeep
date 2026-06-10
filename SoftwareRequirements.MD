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
- User accounts
- One-time payment per gift order (no subscription)
- Manual prospect entry
- **Prospect pipeline / outcome tracking** (deal status on the prospect—no separate Pitch UI or pitch entity required)
- Gift selection
- Gift order request tracking (linked to prospect)
- Follow-up reminders (linked to prospect)
- Sales outcome tracking (on prospect)
- Basic analytics
- Admin fulfillment workflow

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
The record of a gift request, fulfillment status, and delivery status. Each gift order must include **recipient name**, **full shipping address**, and **note to leave on the gift** (text for the card or enclosure—required so fulfillment can attach or print it).

### Follow-Up
A reminder or email related to checking in with the **prospect** after a gift or touchpoint.

### Outcome
The result of the opportunity for a **prospect** (e.g., open, won, lost, no response), stored and updated on the prospect (or a prospect-scoped outcome record), not on a separate pitch entity.

---

## 4. Functional Requirements

## 4.1 User Accounts

### Requirement: User Signup
The system shall allow a new user to create an account.

Acceptance criteria:
- User can enter name, email, and password
- User receives confirmation or is redirected into onboarding
- Duplicate email addresses are not allowed
- Invalid emails are rejected

### Requirement: User Login
The system shall allow existing users to log in.

Acceptance criteria:
- User can log in with email and password
- Incorrect credentials show a safe error message
- Authenticated users can access the dashboard
- Unauthenticated users are redirected to login

### Requirement: Password Reset
The system shall allow users to reset forgotten passwords.

Acceptance criteria:
- User can request password reset by email
- Reset link expires after a defined time
- User can create a new password

### Requirement: User Profile
The system shall allow users to manage basic profile information.

Acceptance criteria:
- User can view name and email
- User can update name
- User can access billing settings
- User can log out

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
- Successful payment marks the order paid and moves it to `queued` for fulfillment
- Failed or canceled checkout leaves the order in `pending_payment` and does not start fulfillment
- The user can retry checkout for an unpaid order

### Requirement: Stripe Webhooks
The system shall listen for Stripe payment events.

Acceptance criteria:
- Webhook signatures are verified
- `checkout.session.completed` marks the matching gift order paid/queued
- A fetch-time fallback re-checks the Checkout session if the webhook is missed
- Failures are logged

> **Out of scope for MVP:** subscription plans, recurring billing, weekly order caps, and the Stripe customer billing portal. The `users.subscription_status` / `users.subscription_plan` columns are reserved scaffolding only.

---

## 4.3 Dashboard

### Requirement: User Dashboard
The system shall provide a dashboard after login.

Acceptance criteria:
- Dashboard shows **recent gift activity** and/or **prospects** the user cares about (not a separate “pitches” list)
- Dashboard shows gifts sent or queued
- Dashboard shows follow-up reminders
- Dashboard shows basic conversion metrics (prospect-based—see §4.11)
- Dashboard has clear navigation

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

Acceptance criteria:
- User can enter first name, last name, company, email, phone, and shipping address (prospect data can prefill a gift order; every **gift order** must still capture recipient name, full address, and note on the gift—see §4.7)
- Required fields are validated
- Prospect is associated with the correct user/company

### Requirement: View Prospects
The system shall allow users to view a list of prospects.

Acceptance criteria:
- User can see only their own or company-accessible prospects
- User can search or filter prospects
- User can open prospect detail page

### Requirement: Edit Prospect
The system shall allow users to edit prospect information.

Acceptance criteria:
- User can update prospect details
- Changes are saved to database
- User cannot edit prospects they do not have permission to access

### Requirement: Delete or Archive Prospect
The system should allow users to remove or archive a prospect.

Acceptance criteria:
- User can archive a prospect
- Archived prospects do not appear in default list
- Historical **gift orders** and prospect records remain intact (subject to your retention rules)

---

## 4.5 Prospect pipeline and outcomes

The product does **not** include a dedicated **Sales Pitch** screen or entity. Pipeline and closings are tracked **on the prospect** (and via gift orders / follow-ups tied to that prospect).

### Requirement: Prospect outcome and pipeline fields
The system shall allow users to record and update pipeline information **on the prospect**.

Acceptance criteria:
- User can set **deal status / outcome** (e.g., open, won, lost, no response—or equivalent enum fixed at implementation)
- User can enter optional fields such as estimated deal value, close date, and notes **on the prospect**
- User can see gift orders and follow-ups for that prospect on **prospect detail** (no separate pitch detail page)

### Requirement: Prospect detail
The prospect detail experience shall consolidate what the user needs in one place.

Acceptance criteria:
- Shows contact / company information
- Lists **gift orders** for this prospect with status
- Shows scheduled **follow-ups** linked to this prospect
- Shows current **outcome / deal status**

**Note:** CRM integrations may import external “deals” or “opportunities” later; that does not require a first-class **Pitch** table in CloseAndKeep as long as activity remains attributable to a **prospect**.

---

## 4.6 Gift Catalog

### Requirement: View Gift Catalog
The system shall allow users to browse available gifts.

Acceptance criteria:
- User can view gift name, image, description, and category
- Inactive gifts are hidden from normal users
- User can select a gift during the gift workflow

### Requirement: Manage Gifts
The admin shall be able to manage gift options.

Acceptance criteria:
- Admin can create gift
- Admin can edit gift
- Admin can activate/deactivate gift
- Admin can update gift price/cost
- Admin can add image URL

---

## 4.7 Gift Ordering

### Requirement: Create Gift Order
The system shall allow a user to request a gift for a prospect.

Acceptance criteria:
- User selects **prospect**
- User selects gift
- User enters or confirms **recipient name** (delivery name)
- User enters or confirms **full shipping address** (required for delivery)
- User enters **note to leave on the gift** (required text for the card or enclosure; empty or whitespace-only is invalid)
- Order is saved with queued status
- User sees confirmation

### Requirement: Gift Order Status
The system shall track gift order status.

Acceptance criteria:
- Gift order can be draft, queued, ordered, shipped, delivered, failed, or canceled
- User can view current status
- Admin can update status

### Requirement: Usage Limits
**Not applicable to the MVP.** Because billing is one-time per gift order, there is no plan-based weekly cap to enforce — each order is paid for individually at checkout. Usage limits would only return if a recurring subscription tier is introduced later.

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
- Admin can record vendor/order details
- User is notified when status changes

### Future Requirement: Automated Vendor Fulfillment
The system may later connect to gift vendor APIs.

Acceptance criteria:
- System can send order to vendor
- System can receive vendor order ID
- System can update shipping status automatically

---

## 4.9 Follow-Up Reminders

### Requirement: Schedule Follow-Up
The system shall allow a user to schedule a follow-up reminder.

Acceptance criteria:
- User can choose a follow-up date
- Follow-up is linked to **prospect** (optional link to a specific **gift order** if useful)
- Reminder appears on dashboard
- Reminder can be marked complete

### Requirement: Email Reminder
The system should send reminder emails to the salesperson.

Acceptance criteria:
- Email sends on or before scheduled date
- Email includes **prospect** context (and gift order context if applicable)
- Failed emails are logged

---

## 4.10 Sales outcome tracking (prospect)

### Requirement: Mark outcome
The system shall allow users to mark an **outcome for the prospect** (same fields as §4.5; may be implemented as one flow).

Acceptance criteria:
- User can mark won, lost, open/pending, no response, or unknown
- User can enter final deal value
- User can enter close date
- Outcome updates dashboard metrics

---

## 4.11 Analytics

### Requirement: Basic Dashboard Metrics
The system shall show basic analytics.

Acceptance criteria:
- Total **prospects** (or open deals) shown as appropriate
- Gifts sent shown
- Follow-ups due shown
- Won deals shown
- Lost deals shown
- Pending / open deals shown
- Basic conversion rate shown (see definition below)

**Definition — conversion rate (dashboard, default):** in the selected time range, **number of prospects with outcome “won”** divided by **number of prospects with a terminal outcome** (outcome is **won**, **lost**, or **no response**—exclude prospects still open or pending a final outcome). If the denominator is zero, the UI should show `0%`, an em dash, or another agreed empty state (document the choice in the app). Product, code, and **Test.MD** analytics checks must use the same formula so metrics and tests do not drift.

### Requirement: Gift Impact Metrics
The system should estimate whether gifting helps sales.

Acceptance criteria:
- System can show close rate for **prospects** who received gifts vs those who did not (when data supports it)
- System can show estimated revenue won after gifts
- Future system can compare gifted vs non-gifted **opportunities** (still prospect-centric)

---

## 4.12 Admin Dashboard

### Requirement: Admin Access
The system shall provide admin-only pages.

Acceptance criteria:
- Only admin users can access admin dashboard
- Admin can view users
- Admin can view companies
- Admin can view gift orders
- Admin can manage gift catalog
- Admin actions are logged where appropriate

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
- Secure authentication
- Role-based access control
- Input validation
- Secure password storage if passwords are managed directly
- Environment variables for secrets
- Stripe webhook signature verification
- Rate limiting for sensitive endpoints
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
- Payment webhooks (`checkout.session.completed`)
- Per-order payment status

## Email Provider
Used for:
- Follow-up reminders
- Gift status updates
- Account emails
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

- A user can create an account
- A logged-in user can access the dashboard
- A user can pay for a gift order with Stripe (one-time, at checkout)
- A user can create a prospect
- A user can update **prospect outcome / deal status** (pipeline without a separate pitch record)
- A user can choose a gift
- A user can submit a gift request with recipient name, shipping address, and note on the gift
- Admin can view and manage gift orders
- Admin can update gift order status
- User can schedule a follow-up reminder
- User can mark a sales outcome
- Dashboard shows basic metrics
- Basic email notifications work
- Unauthorized users cannot access protected data

### Verification traceability

MVP acceptance is demonstrated against **Test.MD**, the recursive test checklist (unit, integration, end-to-end). Each Priority 1 behavior should map to explicit rows there; check items off as automated tests pass or as manual runs are recorded for sign-off. For release gates, use the **stable anchor IDs** in Test.MD (**`TEST-REG`**, **`TEST-LAUNCH`**, **`TEST-RISK`**) so cross-references do not break if section numbers change.

---

## 8. Out of Scope for MVP

The following are not required for the first version:

- CRM integrations
- Public API
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
- Signup/login
- Stripe one-time payment per gift order
- Dashboard
- Prospects (including outcome / deal status on prospect)
- Gift requests
- Admin order queue
- Follow-up reminders
- Outcome tracking

## Priority 2
- Better analytics
- Team accounts
- CSV import
- Gift templates
- Improved onboarding
- Better admin tools

## Priority 3
- CRM integration
- Gift vendor API integration
- Public API
- Webhooks
- Advanced reporting
- Enterprise features
