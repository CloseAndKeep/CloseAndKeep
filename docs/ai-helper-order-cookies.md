# AI Helper: Order Cookies — plan

Replaces the **seller-facing** “install skill + API key + host secrets/allowlist” story with pasteable **chat instructions**. The AI never calls CloseAndKeep; it only returns a prefill link. The seller clicks → confirms → pays on Stripe.

API skill `skills/closeandkeep-orders/` stays for power users / custom CRM — demoted under Developers, not the lead path.

Fulfillment bakery autofill remains parked: [`bakery-fulfill-later.md`](bakery-fulfill-later.md).

## Naming convention

| Use | Value |
|-----|--------|
| **Product name** | AI Helper: Order Cookies |
| **Short label** | AI Helper |
| **Slug / folder** | `ai-helper-order-cookies` |
| **Source file** | `ai-helper-order-cookies/INSTRUCTIONS.md` |
| **Public download** | `/ai-helper-order-cookies/INSTRUCTIONS.txt` |
| **Pack script** | `scripts/pack-ai-helper-order-cookies.sh` |
| **Marketing page** | `/developers/ai` (title: AI Helper: Order Cookies) |
| **Nav / footer** | Use with AI (unchanged href) |
| **Old API package** | `closeandkeep-orders` skill zip — label **Advanced: API skill** |

Do not call the helper a “skill” in seller copy. Skills imply tool/API access; this is instructions only.

## Seller flow (target)

1. Company admin opens `/developers/ai` → **Copy instructions** (or download `.txt`) → paste once into a shared Claude Project / ChatGPT custom GPT.
2. AE: “Send 4 cookies to Alyssa…” → AI replies with only a `/send?…` link (alias of `/orders/new`).
3. AE clicks → login if needed (`?next=` preserves the URL) → Review already filled → Pay.

No API key, no Connect, no Cloud Agent allowlist.

## Prefill URL contract

Base (preferred): `https://www.closeandkeep.com/send`  
Equivalent: `https://www.closeandkeep.com/orders/new` (`/send` redirects here, query preserved)

| Param | Meaning | Notes |
|-------|---------|--------|
| `name` | Recipient / prospect name | Required for helper links |
| `email` | Recipient email | Required for helper links |
| `pack` | `4` or `12` | Maps to `cookies-4` / `cookies-12`; default `4` |
| `gift_id` | `cookies-4` \| `cookies-12` | Alternate to `pack` (existing) |
| `note` | Gift note | URL-encoded; truncate to 150 chars |
| `ask_address` | `1` / `true` | Default **on** when name+email present and no street |
| `street`, `city`, `state`, `zip` | Optional known address | If all present, use known-address mode |
| `company`, `street2` | Optional | With known address |
| `prospect_id` | Existing | Keep for dashboard deep links |

When name + email + note are present and shipping mode is resolvable, open on **Review** (step 3). Match prospect by email (case-insensitive); if none, create the prospect on submit (not on page load).

## Website copy changes

- `/developers/ai` leads with AI Helper: how it works, Copy / Download, company setup, example.
- Advanced section: API skill zip + key for agents that call `api.closeandkeep.com`.
- `/developers` and API keys page: primary CTA → AI Helper; skill zip secondary.
- `USER_GUIDE.md` + `llms.txt`: helper first.

## Build checklist

1. [x] This plan + naming
2. [x] `ai-helper-order-cookies/INSTRUCTIONS.md` (+ public `.txt` via pack script)
3. [x] Rewrite `/developers/ai` (+ related CTAs / guide / llms)
4. [x] `/orders/new` query prefill → Review when complete
5. [x] `/send` alias + one-click **Copy instructions** on `/developers/ai`
6. [ ] Optional later: copy analytics; company-branded share page

## Out of scope (this helper)

- AI completing Stripe Checkout
- Bakery vendor API or parked Crumbl autofill
- Removing the API skill (demote only)

**MCP Connect** (OAuth for Claude / ChatGPT / Cursor) is a separate product track — see [`mcp-orders.md`](mcp-orders.md). This helper stays the no-Connect / paste-instructions path.
