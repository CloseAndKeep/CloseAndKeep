# CloseAndKeep — New user guide

CloseAndKeep helps sales teams send cookie gifts after a pitch, track prospects, and (optionally) trigger those gifts from Salesforce or HubSpot.

> Maintainers: when you change signup, orders, order status emails, CSV import, Integrations, Profile (photo, password, billing), or CRM-related settings, update this file in the same change. See `.cursor/rules/user-guide.mdc`.

---

## Getting started

1. Go to **Get started** → create an account (name, company, email, password — at least 12 characters with a letter and a number).
2. Verify your email from the link we send.
3. You’ll land on the **Dashboard**.
4. From the left nav you can use **Prospects**, **Orders**, **Integrations**, **Payments**, **API keys**, and **Profile**.

**Typical first gift (manual):**

1. **Prospects** → add someone you’re working.
2. **Orders** → **Send cookies** (or start from the prospect).
3. Choose pack size (**4** or **12** cookies), add a note, enter shipping (company is optional — use it for office / building delivery) or skip address so we email them for it. If they never reply, that link lasts about **7 days** (same window as the card hold); we email you if it expires and the order is canceled.
4. Pay at Stripe Checkout.

**After you send a gift:**

We email **you** (the person who sent the gift), not the prospect, when the order **ships** and again when it is **delivered**.

If you skipped the address and the recipient never sends one, the shipping link and card hold expire after about **7 days**. We email you that the link expired and the order was canceled. Place a new order if you still want to send cookies.

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
| **Email** | Recommended | Needed if you leave shipping blank (we email them for shipping) |
| **Cookies** | Yes | Pack size: **4** or **12** |
| **Company** | Optional | Workplace / building name (helps office deliveries) |
| **Street** | Optional* | Street address |
| **Street2** | Optional | Apt, suite, unit |
| **City** | Optional* | City |
| **State** | Optional* | 2-letter state (e.g. IL) |
| **Postal Code** | Optional* | ZIP / postal code |

\*Street, City, State, and Postal Code are required **together**. Leave all of them blank to request the address after you authorize payment. A single **Address** column still works for older files.

Example:

```csv
Name,Email,Cookies,Company,Street,Street2,City,State,Postal Code
Jane Smith,jane@example.com,4,,123 Main St,,Springfield,IL,62704
Bob Jones,bob@example.com,12,,,,,,
```

### Import steps

1. Choose your `.csv` file.
2. Click **Import CSV**.
3. If validation fails, **no orders are created** — fix the listed row errors and try again.
4. If it succeeds:
   - **Rows with an address** → one shared “pay together” Stripe checkout.
   - **Rows without street/city/state/ZIP** → authorize payment **per order**, then we email the recipient a shipping link. If they do not reply within about **7 days**, we email you that the hold expired and that order was canceled.

### Limits & notes

- Max about **100 data rows** and **256 KB** per file.
- Must be signed in (not guest).
- Default gift note on import: *“Enjoy these cookies — a small thank-you from us.”*
- CSV is for **importing gift orders only** (not exporting prospects/orders).

---

## Connecting to CRM (and options after connect)

Supported CRMs today: **Salesforce** and **HubSpot**. Custom CRMs use the **API** (see below).

When a deal/opportunity hits your configured stage (default **Demo Completed**), CloseAndKeep **auto-creates a cookie order** using **Cookie Note** and the cookie company/street/city/state/ZIP fields from the CRM (auto-order turns on when you first connect). If auto-order is later turned off on Profile, you get a reminder email instead.

### Connect (Salesforce / HubSpot)

1. In your CRM, add the **stage** and **Cookie Note / company / street / city / state / ZIP** fields (tables below).
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
| Company (optional) | **Cookie_Company__c** | **cookie_company** | Text |
| Street | **Cookie_Street__c** | **cookie_street** | Text |
| Apt / suite (optional) | **Cookie_Street2__c** | **cookie_street2** | Text |
| City | **Cookie_City__c** | **cookie_city** | Text |
| State | **Cookie_State__c** | **cookie_state** | Text (2-letter) |
| ZIP / postal code | **Cookie_Postal_Code__c** | **cookie_postal_code** | Text |

- If street, city, state, and ZIP are all filled → order is created ready to pay (and can ship after payment / monthly queue).
- If those fields are blank → we still create the order and email the recipient for shipping after you authorize/pay. A legacy **Cookie_Address__c** / **cookie_address** long-text field is still read if the split fields are empty.
- If **Cookie Note** is blank → we use: *“Thanks for meeting with us — enjoy these cookies!”*

Field API names can be overridden with env vars (`SALESFORCE_COOKIE_NOTE_FIELD`, `SALESFORCE_COOKIE_COMPANY_FIELD`, `SALESFORCE_COOKIE_STREET_FIELD`, `SALESFORCE_COOKIE_CITY_FIELD`, `SALESFORCE_COOKIE_STATE_FIELD`, `SALESFORCE_COOKIE_POSTAL_CODE_FIELD`, and the HubSpot `HUBSPOT_COOKIE_*_PROPERTY` equivalents).

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
| Company | `cookie_company` (optional) | `cookie_company` (optional) |
| Street | `cookie_street` (optional) | `cookie_street` (optional) |
| Apt / suite | `cookie_street2` (optional) | `cookie_street2` (optional) |
| City | `cookie_city` (optional) | `cookie_city` (optional) |
| State | `cookie_state` (optional) | `cookie_state` (optional) |
| ZIP | `cookie_postal_code` (optional) | `cookie_postal_code` (optional) |
| Shipping (legacy) | `cookie_address` (optional) | `cookie_address` (optional) |

Map these from the custom CRM fields above. Split street/city/state/ZIP is preferred; `cookie_address` is only used if the split fields are blank.

### Options on Integrations (after connect)

| Option | What it does |
|--------|----------------|
| **Trigger stage name** | Stage that fires the cookie flow (default **Demo Completed**). Must match your CRM stage name. Click **Save stage**. |
| **Sync now** | Manually poll recent matching opportunities/deals (reads Cookie Note and company/street/city/state/ZIP). |
| **Disconnect** | Remove the CRM connection. |
| Status / last poll / org or portal | Connection health info |

After you connect a CRM, billing and auto-order controls also appear on **Profile**.

### Custom CRM (your own system)

There is no OAuth “Connect” for a home-grown CRM. Use the API:

1. Sign up at closeandkeep.com (not guest), verify email, then **API keys** → create a `cak_…` key (shown once).
2. See **/developers** for examples. Full walkthrough with screenshots: `docs/custom-crm-setup.md`.
3. In your CRM, add a **Send cookies** button plus **Cookie note**, optional **company**, and street / city / state / ZIP fields. Do not require a deal-stage change. When the rep clicks the button, call:
   - `POST /prospects` with name + email
   - `POST /gift-orders` with `gift_id`, `recipient_name`, **`note`**, and either **`shipping_street` + `shipping_city` + `shipping_state` + `shipping_postal_code`** (optional **`shipping_company`**) or `request_recipient_address: true` (and `recipient_email` so we can ask for shipping)
4. If the response has `checkout_url`, open it to pay. If `checkout_url` is null, monthly billing is on (Profile → **Pay monthly** after you create an API key).

---

## Profile

Open **Profile** from the nav to manage your account, photo, password, and (if a CRM or API key is connected) monthly billing.

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

### Monthly billing & auto-order (CRM or API key)

After Salesforce or HubSpot is connected, **or** after you create an **API key**, Profile shows billing controls:

| Option | What it does |
|--------|----------------|
| **Pay monthly** | Accrue cookie orders during the month; charge your saved card at month end (orders can still ship before that charge). Requires a card on file first. |
| **Add / Update card** | Save a payment method via Stripe (card is stored by Stripe, not on CloseAndKeep servers). |
| **Open balance / Pay now** | See what’s owed for the month and pay early. |
| **Max spending limit** | Cap open monthly balance; when hit, new monthly-billed orders are blocked and you’re emailed to pay or raise the limit. Leave blank for no limit. |
| **Auto-order on CRM stage** | Salesforce/HubSpot only. Automatically create a cookie order from CRM Cookie Note and street/city/state/ZIP when the trigger stage hits (on by default after first CRM connect). Custom CRMs use a **Send cookies** button instead. |
| **Auto-order pack size** | Choose **4 cookies** or **12 cookies** for those auto-orders (Salesforce/HubSpot). |

Turn **Pay monthly** off anytime to go back to paying per order.

---

## Quick checklist for a new account

1. Sign up and verify email
2. On **Profile**: upload a photo (optional) so recipients see you on gift emails
3. Add a prospect and send one test order
4. (Optional) Import a small CSV to learn batch checkout
5. (Optional) Custom CRM: add a **Send cookies** button plus Cookie note and street/city/state/ZIP. Salesforce/HubSpot: add the **Demo Completed** stage (or your chosen name) and make sure deals have a contact with name + email
6. (Optional) Connect Salesforce or HubSpot → set trigger stage → try **Sync now**
7. (Optional) On Profile: add a card and enable monthly billing (after an API key or Salesforce/HubSpot connect). Auto-order is Salesforce/HubSpot only.
