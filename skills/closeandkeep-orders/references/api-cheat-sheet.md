# CloseAndKeep API cheat sheet

Base: `https://api.closeandkeep.com`  
Auth: `Authorization: Bearer cak_…`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/gifts` | Public. Pack ids + live prices. |
| GET | `/prospects` | List owned prospects; reuse by email before create. |
| POST | `/prospects` | `{ name, email, deal_status: open\|won\|lost }` |
| POST | `/gift-orders` | See skill body; returns `checkout_url` or null. |
| GET | `/gift-orders` | List owned orders. |
| GET | `/gift-orders/{id}` | Status / payment_status. |

Gift ids: `cookies-4`, `cookies-12`. Note max 150 characters.
