# Git history hygiene scan

Scanned 2026-11-16 across all local refs (~98 commits). Goal: find credentials or sensitive material that should not have lived in a **public** repo.

## Verdict

**No live secret keys found** in text history (`sk_live_*`, real `sk_test_*`, `whsec_*`, Resend `re_*`, `cak_*`, Neon URLs with passwords, private keys, OAuth client secrets). Placeholders only (`sk_live_xxx`, `sk_test_xxx` / `sk_test_dummy`, `whsec_xxx` / `whsec_test_dummy`, `re_xxxxxxxxx`).

No committed `.env` / `.env.local` / `.pem` files in history.

## Code hardening from the same pass

Applied on the hygiene branch (not history rewrite):

- `INTEGRATION_TOKEN_FERNET_KEY` required when `APP_ENV=production` (no public Fernet fallback in prod)
- OAuth state HMAC no longer uses `"dev"` in production
- CRM webhook secrets fail closed unless `APP_ENV=development`
- FastAPI `/docs` / OpenAPI disabled in production
- CSV fixture address anonymized

## Findings (non-secret but worth knowing)

### 1. Live Stripe Price IDs on an unmerged branch (low)

Branch `origin/cursor/stripe-pack-price-ids-4d7d` (closed PR #11) embeds real Price ids in `api/.env.example` and `render.yaml`:

- `price_1TwRUwGkVCOXYyTsBAQ8B8Na` (4-pack / fallback)
- `price_1TwRWdGkVCOXYyTsE3I8j1h9` (12-pack)

These are **not** secret keys (they cannot charge alone), but they identify your live catalog and should not sit in a public example file. **Not on `main`.** Prefer dashboard/`sync: false` only.

**Action:** Delete the remote branch after making the repo private (or leave it private-only). No Stripe key rotation required for this alone.

### 2. Ops personal emails in `main` (medium / hygiene)

Hardcoded in source and blueprint (being removed in the same change set as this note):

- `api/app/config.py` default `ORDER_NOTIFICATION_TO`
- `api/.env.example`
- `render.yaml` (API + notify-dead-letters cron)

**Action:** Keep real ops inboxes in Render env only; default/example → `agent@closeandkeep.com` (or empty).

### 3. Vendor binary in git (low)

`tools/stripe-cli/stripe.exe` (~27 MB) is tracked. Binary string matches for `sk_`/`whsec_` are noise from the Stripe CLI build, not your keys. Consider stopping tracking of the binary (download in docs / CI) to shrink the repo; optional.

### 4. Screenshots / CRM PDF

Docs screenshots use placeholders / guest UI. Large `docs/CloseAndKeep-custom-CRM-setup.pdf` is process docs, not credentials.

## What we did *not* do

- History rewrite / `git filter-repo` (unnecessary without leaked secret keys)
- Rotating Stripe/Resend/Neon/CRM secrets (no evidence they were committed)
- Making the GitHub repo private (owner GitHub UI)

## Owner checklist

1. Make the repository **private**
2. Delete remote branch `cursor/stripe-pack-price-ids-4d7d` if you no longer need PR #11’s tip
3. Confirm Render `ORDER_NOTIFICATION_TO` still lists the inboxes you want after Blueprint no longer hardcodes personal addresses
4. Optional: enable GitHub secret scanning / push protection
5. Optional: drop `tools/stripe-cli/stripe.exe` from version control
