# CloseAndKeep — next-feature brief

Paste this into a new chat. Do not rediscover the product from Architecture.MD unless this brief is not enough.

## Product (as built)

CloseAndKeep is post-pitch cookie gifts for salespeople. Solo-user first.

- Web: Next.js 14 on Vercel (`web/`). API: FastAPI on Render (`api/`). DB: Neon + Alembic.
- Billing: **one-time Stripe Checkout per gift order** (`mode: payment`). No subscriptions.
- Deferred address: authorize/hold → public `/ship/[token]` → capture → `queued`. Token/hold ~7 days.
- Checkout already has `allow_promotion_codes: True`. Amounts **below** catalog are allowed (promos). Amounts **above** catalog are rejected.
- CRM: Salesforce + HubSpot OAuth auto-order on a trigger stage (default Demo Completed). Custom CRM = API keys + Send cookies. Auto-order-on-stage is OAuth-only.
- Fulfillment is **manual** via `/admin`. Do not start a bakery vendor API.
- Cards stay with Stripe. Never store PAN. Tests must not call live Stripe.
- Prefer `AGENTS.md`, `DECISIONS.md`, and `Architecture.MD` §0 over speculative Architecture sections.

## How this list was made

Four independent idea passes (growth, seller UX, fulfillment, CRM) produced 32 raw ideas. Duplicates were merged. The owner then vetoed several items. Numbers below are the original IDs; gaps are cuts.

## Next build (do this)

**#1 — Seller pings: shipped, delivered, and address-hold expired**

The AE is not emailed when admin marks shipped/delivered, or when the `/ship/[token]` hold dies. Only the internal new-order Resend exists.

- Email the **seller (AE)**, not the prospect.
- Hook Resend into admin status transitions (`api/app/fulfillment.py` / admin PATCH) and address-token expiry (`api/app/jobs/address_request_followups.py`). Existing mail helpers live near `api/app/order_email.py`.
- Update `USER_GUIDE.md` in the same change (see `.cursor/rules/user-guide.mdc`).
- After a durable pitfall, record a lab note via `.cursor/skills/lab-notes/SKILL.md`.

## Liked, later (not this build)

**D — Discount / 1¢ test code** — App/docs/tests done; Dashboard remaining (`TEST1C` amount-off = catalog − 1¢, test mode).

Checkout already accepts Stripe promotion codes. A `TEST1C` (or similar) code that leaves **$0.01** on the charge is created in the **Stripe Dashboard** as a fixed amount-off (catalog − 1¢; Stripe has no “set charge to $0.01” type). Restrict it to test mode / a specific customer if possible. Keep a real customer coupon separate so the 1¢ code cannot leak into production volume.

App hint (“Have a code? Enter it on the Stripe checkout page.”) sits next to pay CTAs only — no in-app code field.

## Still in play (later)

3. Address-hold expiry queue + one-click resend (in-app, not just the email in #1)
4. Gifted vs ungifted close-rate on the dashboard
5. Dashboard “needs you today” (unpaid, no-address, just shipped)
6. Prospect search and Open / Won / Lost filters
7. Prefill `/orders/new` from the prospect
8. Saved cookie-note templates
10. CRM stage recipes (Demo / Closed Won / Renewal → different packs)
11. Integration event journal + dead-token reconnect — show last CRM events on Integrations (“Acme Demo Completed → cookies ordered” or “HubSpot login expired”) and email “reconnect your CRM” after failed token refreshes
12. Post-connect “Check setup” (missing Cookie_* fields, bad stage label)
14. Hold auto-order when email/address is junk
15. Re-gift policy + retry failed auto-order
19. Failed-notify dead letter + retry (paid order, Resend to ops died)

## Cut (do not build)

- 2 CRM write-back (status/tracking onto the Salesforce/HubSpot deal)
- 9 Full follow-ups product (API + reminder job). `/follow-ups` stays a placeholder.
- 13 Map Account/Contact billing address instead of custom Cookie_* fields. Auto-order stays on Cookie_* fields.
- 16 Same-day bakery pick list
- 17 Cookie freshness SLA aging on `/admin`
- 18 Admin claim lock
- 20 Landing “mail me a sample pack”

Also out of scope unless the owner reopens them: team/pod wallets, shared CRM org owner routing, bakery vendor API, recipient viral signup loop.

## Owner calls

- Next: **#1 seller status emails**
- Like: discount / 1¢ test code (app/docs done; Dashboard `TEST1C` remaining)
- Do not like: 2, 9, 13, 16, 17, 18, 20
