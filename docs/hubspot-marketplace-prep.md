# HubSpot Marketplace prep (do not flip distribution yet)

CloseAndKeep’s HubSpot app stays **`distribution: "private"`** until a developer test account / sandbox has proven the Deal card and workflow action end-to-end. This checklist is the gate before Marketplace.

## Already in the repo

| Piece | Location |
|--------|----------|
| Private OAuth app | [`hubspot-closeandkeep/src/app/app-hsmeta.json`](../hubspot-closeandkeep/src/app/app-hsmeta.json) |
| Deal sidebar card | [`hubspot-closeandkeep/src/app/cards/`](../hubspot-closeandkeep/src/app/cards/) |
| Workflow action “Send CloseAndKeep cookies” | [`hubspot-closeandkeep/src/app/workflow-actions/send-cookies-hsmeta.json`](../hubspot-closeandkeep/src/app/workflow-actions/send-cookies-hsmeta.json) |
| Action / card API | `POST /integrations/hubspot/workflow-action`, `.../card/properties`, `.../card/send` |
| Legacy DIY events + Sync | `POST /integrations/hubspot/events`, `POST /integrations/hubspot/sync` (kept) |
| Dealstage app webhook stub | inactive in `webhooks-hsmeta.json` (optional later; not required for Marketplace trigger) |

## Before listing

1. Create a **HubSpot developer account** and a **test / sandbox portal**.
2. Auth CLI: `hs account auth` → `hs project upload` / `hs project dev` from `hubspot-closeandkeep/`.
3. Install the private app on the test portal; **Connect HubSpot** in CloseAndKeep (OAuth) so `external_org_id` = portal id.
4. Re-consent if scopes changed (now includes `crm.objects.deals.write`).
5. Create `cookie_*` deal properties; add recipe stages (Demo Completed / Closed Won / Renewal).
6. Confirm **Deal card**: save fields → values on the deal; **Queue cookie gift** → CloseAndKeep event.
7. Confirm **workflow**: enroll deal on stage → action “Send CloseAndKeep cookies” → same pipeline (no Data Hub “Send a webhook”).
8. Confirm **Sync now** still works as fallback.
9. Only then change `distribution` to `marketplace`, align redirect/permitted URLs with production API host, and start HubSpot’s listing review.

## What not to depend on

- Customer **Data Hub Pro** workflow “Send a webhook” — optional DIY only (`/events` + `HUBSPOT_WEBHOOK_SECRET`).
- Flipping Marketplace while card/action are untested in a sandbox.
- Storing card / PAN data in HubSpot.

## Parked GTM (after native install works)

ROI calculator, “cookies with your face,” onboarding/training fee — see [`next-feature-brief.md`](next-feature-brief.md) Parked section. Not part of this HubSpot surface.
