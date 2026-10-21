# CloseAndKeep on the HubSpot Marketplace

The HubSpot project in `hubspot-closeandkeep/` is the Marketplace app. It is OAuth-only (`distribution: marketplace`) and adds a deal card, a settings page, and a deal-stage webhook. CloseAndKeep still connects from **Integrations → Connect HubSpot**. The Marketplace path lets someone start in HubSpot instead.

This repository cannot submit the listing. That happens in the HubSpot developer account that owns the app, after the API is deployed and the project is uploaded.

## What customers get

1. They install **CloseAndKeep** in HubSpot and approve read access to deals, contacts, and companies.
2. HubSpot redirects to `/integrations/hubspot/callback` without CloseAndKeep’s signed user id.
3. The API stores the encrypted tokens for 30 minutes and sends the person to `/integrations/hubspot/finish/{code}`.
4. After they sign in, that portal is linked to their CloseAndKeep user. A portal already linked to someone else is refused.
5. Moving a deal into a recipe stage (defaults: Demo Completed, Closed Won, Renewal) posts to `POST /integrations/hubspot/webhooks`. CloseAndKeep creates the cookie order the same way **Sync now** does.
6. The **CloseAndKeep** card on a deal shows which cookie fields are filled and the latest cookie action. The app settings page shows whether the portal is linked.

Scopes stay read-only. The app does not write status back onto the deal.

## Before you upload

1. Deploy the API so these routes are live:
   - `GET /integrations/hubspot/callback`
   - `POST /integrations/hubspot/claim`
   - `GET /integrations/hubspot/card`
   - `POST /integrations/hubspot/webhooks`
2. Set `HUBSPOT_CLIENT_ID` and `HUBSPOT_CLIENT_SECRET` to this Marketplace app. `HUBSPOT_CLIENT_SECRET` verifies HubSpot’s signature on the card and the webhook. `API_BASE_URL` must be the public API origin HubSpot calls (`https://closeandkeep-api.onrender.com` unless you change the project URLs).
3. Run `python -m alembic upgrade head` so `hubspot_pending_installs` exists.
4. In the project, the webhook `targetUrl` and the card fetch URL are that same public API. Change them together if the API host changes.
5. Put a square logo at `hubspot-closeandkeep/src/app/app-logo.png` (the gift mark is already there).

Upload only after the API is deployed. The deal-stage subscription is active, so HubSpot will call the webhook as soon as the project is live.

## Upload

From `hubspot-closeandkeep/`, with the [HubSpot CLI](https://developers.hubspot.com/docs/developer-tooling/local-development/hubspot-cli/install-the-cli) authenticated to the developer account:

```shell
hs account auth
hs project upload
```

Install the build in a developer test account from the project’s Distribution tab, add the CloseAndKeep card to a deal view, and run `hs project dev` while you edit the card. To proxy card requests at a local API, copy `src/app/local.json.example` to `src/app/local.json` and start `hs project dev` with `CLIENT_SECRET` set to the same value as `HUBSPOT_CLIENT_SECRET`.

`local.json` is gitignored.

## Listing

HubSpot reviews Marketplace listings by hand. The current bar includes:

- OAuth as the only auth method, on this app id (already set).
- Only the scopes the app uses (deals, contacts, and companies, read).
- At least three active installs in production HubSpot accounts that are not affiliated with you, with successful API activity in the prior 30 days. Test accounts do not count.
- Agreement to the HubSpot Technology Partner Program terms.
- A separate app-card review before you resubmit the listing. HubSpot asks for the production app id, the build id installed in the test account, and whether the app is new. Do not resubmit the listing before that review says the card is approved.
- Capitalize HubSpot in the listing and on closeandkeep.com. Do not combine the HubSpot name into the product name.

Suggested listing copy:

- **Name:** CloseAndKeep
- **Tagline:** Send cookie gifts when a deal hits Demo Completed.
- **Description:** CloseAndKeep sends a cookie gift after a sales pitch. Install it, link your CloseAndKeep account, and fill cookie note plus street, city, state, and ZIP on the deal. When the deal reaches Demo Completed, Closed Won, or Renewal, CloseAndKeep creates the cookie order. A card on the deal shows what is filled and whether cookies already went out.

In the developer account, open the app listing flow and paste that copy, the support email `closeandkeep@gmail.com`, and `https://www.closeandkeep.com/support`. The in-repo support block matches those values.
