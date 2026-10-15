# HubSpot Projects

## Overview

HubSpot projects are file-based build-and-deploy frameworks that allow you to develop apps and CMS content locally using the HubSpot CLI. Projects contain your app's configuration, source code, and assets, which are built and deployed to your HubSpot account.

## Project Structure

- **`hsproject.json`**: Defines your project's name, source directory, and platform version
- **`src/`**: Contains your project's source code organized by feature type (apps, cards, functions, etc.)
- **`*-hsmeta.json` files**: Configuration files that define metadata for each component
- **`hsprofile.*.json` files**: Profile configuration containing a target account ID and variables

## CloseAndKeep components in this project

- **App** (`src/app/app-hsmeta.json`) — private OAuth; stays private until sandbox proof (see `docs/hubspot-marketplace-prep.md`).
- **Deal card** (`src/app/cards/`) — sidebar card to edit `cookie_*` and queue a gift.
- **Workflow action** (`src/app/workflow-actions/`) — “Send CloseAndKeep cookies” → API `workflow-action` (no Data Hub DIY webhook required).
- **Webhooks** — dealstage subscription stub is **inactive**; primary trigger is the workflow action.

## Getting Started

1. **Upload your project**: Run `hs project upload` to build and deploy your project in your HubSpot account
2. **Local development**: Run `hs project dev` to start a local development server with hot reloading for app cards
3. Connect the portal in CloseAndKeep **Integrations** (OAuth), then prove card + workflow action before Marketplace

## Next Steps

1. Developer test account / sandbox → upload/dev as above.
2. Follow Marketplace checklist in [`docs/hubspot-marketplace-prep.md`](../docs/hubspot-marketplace-prep.md). Do **not** set `distribution: marketplace` until that checklist passes.

### Documentation
- [Quickstart Guide](https://developers.hubspot.com/docs/getting-started/quickstart) - Get up and running with a demo app
- [Developer Platform Overview](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/overview) - Learn about building apps on version 2026.03
- [Project Commands Reference](https://developers.hubspot.com/docs/developer-tooling/local-development/hubspot-cli/project-commands) - Complete CLI command reference
- [Custom workflow actions](https://developers.hubspot.com/docs/apps/developer-platform/add-features/custom-workflow-actions)
- [App cards](https://developers.hubspot.com/docs/apps/developer-platform/add-features/ui-extensions/extension-points/app-cards/reference)

### Resources
- [HubSpot Developer Documentation](https://developers.hubspot.com/docs)
- [Developer Community Slack](https://developers.hubspot.com/slack)
- [HubSpot CLI Documentation](https://developers.hubspot.com/docs/developer-tooling/local-development/hubspot-cli/install-the-cli)
