# Architecture.MD

# CloseAndKeep — Architecture

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
- Stripe subscriptions
- Basic dashboard
- Basic follow-up reminders
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
- Subscription status checks
- Prospect CRUD (including deal status / outcome on prospect)
- Gift order processing
- Follow-up scheduling
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
- Good for subscriptions, users, orders, and analytics
- Easier to reason about than NoSQL for this product

---

## Payments
Recommended provider:
- Stripe Billing

Stripe components:
- Stripe Checkout
- Stripe Customer Portal
- Stripe Subscriptions
- Stripe Webhooks

The application should not assume a user has access just because they created an account. Access should be based on subscription status.

---

## Email and Notifications
Recommended providers:
- Resend
- Postmark
- SendGrid
- Amazon SES

Email types:
- Account verification
- Password reset
- Gift request confirmation
- Gift shipped notification
- Gift delivered notification
- Follow-up reminder
- Payment failure notification

For MVP, follow-up emails should likely be reminders sent to the salesperson, not direct emails to the prospect.

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

```text
User Browser
    |
    v
Frontend Web App
Next.js / React
    |
    v
Backend API
FastAPI, Express, or NestJS
    |
    |---- Authentication Service
    |---- Billing Service
    |---- Prospect Service
    |---- Gift Service
    |---- Fulfillment Service
    |---- Follow-Up Service
    |---- Analytics Service
    |---- Admin Service
    |---- Integration Service
    |
    v
PostgreSQL Database
    |
    |---- Users
    |---- Companies
    |---- Subscriptions
    |---- Prospects
    |---- Gifts
    |---- Gift Orders
    |---- Follow-Ups
    |---- Outcomes
    |
    v
External Services
    |---- Stripe
    |---- Email Provider
    |---- Gift Vendors
    |---- CRM APIs
```

---

## 5. Main Modules

## Authentication Module

Responsibilities:
- User signup
- User login
- Password reset
- Session management
- Role management
- Account access

Possible providers:
- Auth.js
- Clerk
- Auth0
- AWS Cognito
- Supabase Auth

MVP recommendation:
Use a managed authentication provider if speed matters.

---

## Billing Module

Responsibilities:
- Create checkout sessions
- Manage subscription plans
- Receive Stripe webhook events
- Store customer ID
- Store subscription ID
- Store subscription status
- Restrict feature access based on plan

Important Stripe webhook events:
- checkout.session.completed
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- invoice.payment_failed
- invoice.payment_succeeded

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
- Store **deal status / outcome** and pipeline notes on the prospect (no separate `sales_pitch` workflow)
- Store default contact and shipping information (gift orders will still capture **recipient name**, **full delivery address**, and **note on the gift** at send time when those may differ or must be reconfirmed)

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
- Validate subscription/usage limits
- Store **recipient name** and **full shipping address** (required for fulfillment)
- Store **note to leave on the gift** (card or enclosure text; required so fulfillment can print or attach it)
- Store selected gift
- Track order status
- Support manual fulfillment
- Support automated fulfillment later

Order statuses:
- Draft
- Queued
- Ordered
- Shipped
- Delivered
- Failed
- Canceled

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
- Count prospects and **terminal outcomes** (won / lost / no response)
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
- Manage companies
- Manage gift catalog
- Manage orders
- Update fulfillment status
- View subscription status
- View failed orders
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

Core tables:
- users
- companies
- company_users
- subscriptions
- prospects (include deal status / outcome columns, or rely on `sales_outcomes` keyed by `prospect_id` only)
- gifts
- gift_orders (FK to **prospect**; optional FK to `follow_ups` later if needed)
- follow_ups (FK to **prospect**; optional FK to `gift_orders`)
- sales_outcomes (optional normalized table; if used, **prospect_id** only—no `pitch_id`)
- admin_notes
- integration_connections
- audit_logs

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

Example endpoints:
```text
POST   /api/auth/signup
POST   /api/auth/login

GET    /api/dashboard

GET    /api/prospects
POST   /api/prospects
GET    /api/prospects/:id
PUT    /api/prospects/:id
DELETE /api/prospects/:id

GET    /api/gifts
POST   /api/gift-orders
GET    /api/gift-orders
GET    /api/gift-orders/:id

GET    /api/follow-ups
POST   /api/follow-ups
PUT    /api/follow-ups/:id

GET    /api/analytics/summary

POST   /api/stripe/create-checkout-session
POST   /api/stripe/webhook
GET    /api/billing/customer-portal

GET    /api/admin/orders
PUT    /api/admin/orders/:id
POST   /api/admin/gifts
PUT    /api/admin/gifts/:id
```

---

## 9. Security Architecture

Security priorities:
- HTTPS everywhere
- Secure authentication
- Role-based access control
- Input validation
- Database access through backend only
- Environment variables for secrets
- Webhook signature validation
- Stripe webhook verification
- Rate limiting for public endpoints
- Audit logs for admin actions
- Backups for database

Important:
Never trust frontend-only checks for subscription status or permissions.

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

- Choose frontend framework
- Choose backend language/framework
- Choose authentication provider
- Choose database host
- Choose email provider
- Choose initial gift fulfillment process
- Choose hosting platform
- Choose whether subscriptions include gift credits
- Choose first CRM integration after validation

---

## 13. Recommended MVP Architecture

For a practical first version:

```text
Next.js Frontend
    |
FastAPI or NestJS Backend
    |
PostgreSQL Database
    |
Stripe for Billing
Resend/Postmark for Email
Manual Admin Fulfillment
```

This is enough to validate the product without spending months building integrations nobody has paid for yet.

---

## 14. Testing and verification

**Test.MD** is the authoritative **recursive test catalog**: features are decomposed into unit, integration, and end-to-end rows that you check off as coverage is added. Prefer mapping automated tests (file names or test IDs) to those rows so requirements stay traceable.

- **Unit tests** — validators, pricing helpers, status transitions, analytics formulas.
- **Integration tests** — HTTP APIs with real DB (or testcontainers), Stripe webhook signatures, email adapters with fakes.
- **End-to-end tests** — browser flows for signup, billing, **prospect → gift order** (recipient name, address, note on gift), prospect outcome update, admin fulfillment, follow-ups.

Continuous integration should run the unit suite on every change; run integration and E2E on merge to main or on a nightly schedule as volume grows. Before production, execute the regression gate in **Test.MD** (anchor **`TEST-REG`**, also titled “Regression gate” there).

---

## 15. Admin bootstrap (MVP)

Internal admins (order queue, gift catalog management) need a **first admin** without a self-serve “promote to admin” product. See **Admin bootstrap (MVP)** in [SoftwareRequirements.MD](SoftwareRequirements.MD) for acceptable options: env email allowlist, one-time seed/migration, or manual runbook. Production should document which option is used and how to add a second admin if needed.
