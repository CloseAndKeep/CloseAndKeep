# CloseAndKeep — next-feature brief

Paste this into a new chat. Do not rediscover the product from Architecture.MD unless this brief is not enough.

## Product (as built)

CloseAndKeep is post-pitch cookie gifts for salespeople. Solo-user first.

- Web: Next.js 14 on Vercel (`web/`). API: FastAPI on Render (`api/`). DB: Neon + Alembic.
- Billing: **one-time Stripe Checkout per gift order** (`mode: payment`). No subscriptions.
- Deferred address: authorize/hold → public `/ship/[token]` → capture → `queued`. Token/hold ~7 days.
- Checkout already has `allow_promotion_codes: True`. Amounts **below** catalog are allowed (promos). Amounts **above** catalog are rejected.
- CRM: Salesforce + HubSpot OAuth auto-order on a trigger stage (default Demo Completed). Custom CRM = API keys + Send cookies. Auto-order-on-stage is OAuth-only.
- Fulfillment is **manual** via `/admin`. Do not start a bakery vendor API. Parked ops idea (not an API): Crumbl-first Cursor autofill — `docs/bakery-fulfill-later.md`.
- Cards stay with Stripe. Never store PAN. Tests must not call live Stripe.
- Prefer `AGENTS.md`, `DECISIONS.md`, and `Architecture.MD` §0 over speculative Architecture sections.

## How this list was made

Four independent idea passes (growth, seller UX, fulfillment, CRM) produced 32 raw ideas. Duplicates were merged. The owner then vetoed several items. Numbers below are the original IDs; gaps are cuts.

## Next build (do this)

Pick from **Still in play** below (or Dashboard `TEST1C`). Seller status emails (#1) and the headless AI skill (H) are shipped.

## Done recently

**#1 — Seller pings: shipped, delivered, and address-hold expired** — Shipped. AE emails on admin shipped/delivered and on address-hold expiry (`api/app/fulfillment.py`, `order_email.py`, address-request jobs). Documented in `USER_GUIDE.md`.

**H — Headless AI orders** — Pivot: seller-facing **AI Helper: Order Cookies** (paste instructions → prefill `/orders/new` link; no API key). Plan + naming: [`docs/ai-helper-order-cookies.md`](ai-helper-order-cookies.md), instructions: [`ai-helper-order-cookies/`](../ai-helper-order-cookies/). API skill [`skills/closeandkeep-orders/`](../skills/closeandkeep-orders/) demoted to Advanced. Earlier design notes: [`docs/headless-ai-orders.md`](headless-ai-orders.md).

**M — MCP Connect (v1 shipped)** — Hosted remote MCP + OAuth Connect so sellers place orders from Claude / ChatGPT / Cursor without API keys. Plan + as-built: [`docs/mcp-orders.md`](mcp-orders.md). AI Helper stays the no-Connect fallback. Homepage CTA still later. Parked bakery autofill unchanged.

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

## Security hygiene

History scan (2026-11-16): [`docs/security-history-scan.md`](security-history-scan.md) — no live secret keys in git; strip personal ops emails from defaults; delete stale price-id branch when locking the repo down.

## Parked (remind on next steps; do not build now)

**Bakery autofill — Crumbl first, Levain if out of area.** Cursor on the owner’s machine fills bakery checkout from a **queued** order with a **full address**, then pays on the logged-in Crumbl (or Levain) account. Not a vendor API; do not change bakery websites. Full write-up: [`docs/bakery-fulfill-later.md`](bakery-fulfill-later.md).

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

- Next: MCP Connect plan [`docs/mcp-orders.md`](mcp-orders.md) (OAuth; Claude + ChatGPT + Cursor UI) when ready to build; else Still in play / Dashboard `TEST1C`
- Done: #1 seller status emails; H → AI Helper: Order Cookies (`/developers/ai`); API skill demoted
- Like: discount / 1¢ test code (app/docs done; Dashboard `TEST1C` remaining); MCP Connect as a future main Use with AI story
- Parked: Crumbl-first / Levain-fallback Cursor fulfill (`docs/bakery-fulfill-later.md`)
- Do not like: 2, 9, 13, 16, 17, 18, 20
- Lockdown (you): make the GitHub repo private + protect `main` (stale price-id branch deleted)
