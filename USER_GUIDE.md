# CloseAndKeep — New user guide

CloseAndKeep helps sales teams send cookie gifts after a pitch, track prospects, and (optionally) trigger those gifts from Salesforce or HubSpot.

> Maintainers: when you change signup, orders, CSV import, Integrations, Profile (photo, password, billing), or CRM-related settings, update this file in the same change. See `.cursor/rules/user-guide.mdc`.

---

## Getting started

1. Go to **Get started** → create an account (name, company, email, password — at least 12 characters with a letter and a number).
2. Verify your email from the link we send.
3. You’ll land on the **Dashboard**.
4. From the left nav you can use **Prospects**, **Orders**, **Integrations**, **Payments**, **API keys**, and **Profile**.

**Typical first gift (manual):**

1. **Prospects** → add someone you’re working.
2. **Orders** → **Send cookies** (or start from the prospect).
3. Choose pack size (**4** or **12** cookies), add a note, enter shipping (or skip address so we email them for it).
4. Pay at Stripe Checkout.

Guest mode exists for a quick look, but guests can’t import CSVs or connect a CRM.

---

## CSV files

Use CSV when you want to create many cookie orders at once.

### Where to go

- **Orders** → **Import CSV** (`/orders/import`)
- Also linked from creating a new order

### Prepare the file

1. On the import page, click **Download template** or **Download example**.
2. Keep a **header row**.
3. Fill columns:

| Column | Required? | What to put |
|--------|-----------|-------------|
| **Name** | Yes | Recipient name |
| **Email** | Recommended | Needed if you leave Address blank (we email them for shipping) |
| **Cookies** | Yes | Pack size: **4** or **12** |
| **Address** | Optional | Full shipping address. Leave blank to request address after you authorize payment |

Example:

```csv
Name,Email,Cookies,Address
Jane Smith,jane@example.com,4,"123 Main St, Springfield, IL 62704"
Bob Jones,bob@example.com,12,
```

### Import steps

1. Choose your `.csv` file.
2. Click **Import CSV**.
3. If validation fails, **no orders are created** — fix the listed row errors and try again.
4. If it succeeds:
   - **Rows with an address** → one shared “pay together” Stripe checkout.
   - **Rows without an address** → authorize payment **per order**, then we email the recipient a shipping link.

### Limits & notes

- Max about **100 data rows** and **256 KB** per file.
- Must be signed in (not guest).
- Default gift note on import: *“Enjoy these cookies — a small thank-you from us.”*
- CSV is for **importing gift orders only** (not exporting prospects/orders).

---

## Connecting to CRM (and options after connect)

Supported CRMs today: **Salesforce** and **HubSpot**. Custom CRMs use the **API** (see below).

When a deal/opportunity hits your configured stage (default **Demo Completed**), CloseAndKeep **auto-creates a cookie order** using **Cookie Note** and **Cookie Address** from the CRM (auto-order turns on when you first connect). If auto-order is later turned off on Profile, you get a reminder email instead.

### Connect (Salesforce / HubSpot)

1. In your CRM, add the **stage** and **Cookie Note / Cookie Address** fields (tables below).
2. Open **Integrations** in CloseAndKeep.
3. Click **Connect Salesforce** or **Connect HubSpot**.
4. Approve access in the CRM OAuth screen.
5. You’ll return to Integrations with a success message — auto-order is enabled (default pack: **4 cookies**; change on Profile).
6. Confirm **Trigger stage name** matches your CRM stage → **Save stage**.
7. Put the deal in **Demo Completed** with note + address filled, then click **Sync now** (or wait for your webhook/Flow).

You can connect one org/portal per CRM per CloseAndKeep user.

### CRM fields you need

#### 1. Stage to add (if it doesn’t exist)

| What | Details |
|------|---------|
| **Stage name** | Default **Demo Completed** (or whatever you set under **Trigger stage name** in Integrations) |
| **Salesforce** | Add it on the Opportunity sales path / stage picklist so `StageName` can equal that value |
| **HubSpot** | Add it as a deal stage label in your deal pipeline (label must match exactly, ignoring case) |

#### 2. Custom fields to add (gift details)

Create these on the **Opportunity** (Salesforce) or **Deal** (HubSpot). Reps fill them before/when moving to Demo Completed.

| Purpose | Salesforce API name | HubSpot internal name | Type |
|---------|---------------------|-----------------------|------|
| Personal gift message | **Cookie_Note__c** | **cookie_note** | Long text / multi-line |
| Shipping address | **Cookie_Address__c** | **cookie_address** | Long text / multi-line |

- If **Cookie Address** is filled → order is created ready to pay (and can ship after payment / monthly queue).
- If **Cookie Address** is blank → we still create the order and email the recipient for shipping after you authorize/pay.
- If **Cookie Note** is blank → we use: *“Thanks for meeting with us — enjoy these cookies!”*

Field API names can be overridden with env vars (`SALESFORCE_COOKIE_NOTE_FIELD`, `SALESFORCE_COOKIE_ADDRESS_FIELD`, `HUBSPOT_COOKIE_NOTE_PROPERTY`, `HUBSPOT_COOKIE_ADDRESS_PROPERTY`).

#### 3. Standard fields we also read

**Salesforce**

| Object | Field | Required? | Why |
|--------|-------|-----------|-----|
| Opportunity | **Id** | Yes | Unique deal key |
| Opportunity | **Name** | Fallback | Used if contact name is blank |
| Opportunity | **StageName** | Yes | Must match your trigger stage |
| Opportunity | **ContactId** (primary contact) | Strongly recommended | Who we gift |
| Contact | **Name** | Strongly recommended | Recipient name |
| Contact | **Email** | Strongly recommended | Address-request email when address is blank |

**HubSpot**

| Object | Property | Required? | Why |
|--------|----------|-----------|-----|
| Deal | **dealname** | Fallback | Used if contact name is blank |
| Deal | **dealstage** | Yes | Must be your trigger stage |
| Deal | **Associated contact** | Strongly recommended | We take the first associated contact |
| Contact | **firstname** / **lastname** | Strongly recommended | Recipient name |
| Contact | **email** | Strongly recommended | Address-request email when address is blank |

#### 4. Webhook / Flow payload (optional admin setup)

If your admin posts stage events to CloseAndKeep instead of relying only on **Sync now**, include:

| Field | Salesforce event | HubSpot event |
|-------|------------------|---------------|
| Deal id | `opportunity_id` | `deal_id` |
| Stage | `stage_name` | `stage_name` |
| Contact name | `contact_name` | `contact_name` |
| Contact email | `contact_email` | `contact_email` |
| Gift note | `cookie_note` (optional) | `cookie_note` (optional) |
| Shipping | `cookie_address` (optional) | `cookie_address` (optional) |

Map `cookie_note` / `cookie_address` from the custom CRM fields above.

### Options on Integrations (after connect)

| Option | What it does |
|--------|----------------|
| **Trigger stage name** | Stage that fires the cookie flow (default **Demo Completed**). Must match your CRM stage name. Click **Save stage**. |
| **Sync now** | Manually poll recent matching opportunities/deals (reads Cookie Note / Cookie Address). |
| **Disconnect** | Remove the CRM connection. |
| Status / last poll / org or portal | Connection health info |

After you connect a CRM, billing and auto-order controls also appear on **Profile**.

### Custom CRM (your own system)

There is no OAuth “Connect” for a home-grown CRM. Use the API:

1. **API keys** → create a `cak_…` key.
2. See **/developers** for examples.
3. When the rep marks the deal done in your CRM, call:
   - `POST /prospects` with name + email
   - `POST /gift-orders` with `gift_id`, `recipient_name`, **`note`**, and either **`shipping_address`** or `request_recipient_address: true`
4. Open the returned `checkout_url` to pay (or use monthly billing on Profile if you also connect SF/HS — monthly is CRM-gated today).

---

## Profile

Open **Profile** from the nav to manage your account, photo, password, and (if CRM is connected) monthly billing.

### Account details

Your profile shows:

| Field | Notes |
|-------|--------|
| **Name** | From signup (display only on Profile today) |
| **Email** | From signup (display only on Profile today) |
| **Company** | Shown when you entered one at signup |

### Profile photo

1. On **Profile**, click **Upload photo** (or **Change photo** if one is already set).
2. Choose a **JPEG**, **PNG**, or **WebP** image up to **2 MB**.
3. To clear it, click **Remove**.

Your photo can appear in recipient emails (for example address-request messages) so the gift feels more personal. Without a photo, initials are shown on your Profile instead.

Guests do not use this full Profile flow the same way as registered accounts.

### Change password

1. Scroll to **Change password** on Profile.
2. Enter your current password and a new one.
3. New password rules: at least **12 characters**, with at least **one letter** and **one number**, and different from the current password.

### Monthly billing & auto-order (CRM must be connected)

After Salesforce or HubSpot is connected, Profile shows **Monthly billing & auto-order**:

| Option | What it does |
|--------|----------------|
| **Pay monthly** | Accrue cookie orders during the month; charge your saved card at month end (orders can still ship before that charge). Requires a card on file first. |
| **Add / Update card** | Save a payment method via Stripe (card is stored by Stripe, not on CloseAndKeep servers). |
| **Open balance / Pay now** | See what’s owed for the month and pay early. |
| **Max spending limit** | Cap open monthly balance; when hit, new monthly-billed orders are blocked and you’re emailed to pay or raise the limit. Leave blank for no limit. |
| **Auto-order on CRM stage** | Automatically create a cookie order from CRM Cookie Note / Cookie Address when the trigger stage hits (on by default after first CRM connect). |
| **Auto-order pack size** | Choose **4 cookies** or **12 cookies** for those auto-orders. |

Turn **Pay monthly** off anytime to go back to paying per order.

---

## Quick checklist for a new account

1. Sign up and verify email
2. On **Profile**: upload a photo (optional) so recipients see you on gift emails
3. Add a prospect and send one test order
4. (Optional) Import a small CSV to learn batch checkout
5. (Optional) In your CRM: add the **Demo Completed** stage (or your chosen name) and make sure deals have a contact with name + email
6. (Optional) Connect Salesforce or HubSpot → set trigger stage → try **Sync now**
7. (Optional) On Profile: add a card, enable monthly billing and/or auto-order
