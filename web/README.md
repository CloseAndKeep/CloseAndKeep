# CloseAndKeep frontend

Next.js 14 (App Router) + TypeScript + Tailwind. Dashboard and domain screens call the backend API via `lib/api.ts` (`apiFetch`). Gift pack labels live in `lib/gift-catalog.ts`; live prices come from `GET /gifts`. Address collection for deferred orders uses `/ship/[token]`. This app lives in the `web/` workspace of the main **CloseAndKeep** repo.

## Run locally

```bash
cd web
npm install
copy .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Use `/login` or `/signup` to create a session against the local API and access dashboard routes.

## Structure

- `app/(marketing)/` — landing (`/`), pricing (`/pricing`), ship form (`/ship/[token]`), privacy / terms / support / developers
- `app/(dashboard)/` — `/dashboard`, `/prospects`, `/orders`, `/orders/import`, `/follow-ups` (placeholder), `/billing`, `/api-keys`
- `app/(admin)/` — `/admin` fulfillment queue
- `app/login`, `app/signup` — auth pages
- `components/layout/` — marketing shell + sidebar app shell
- `lib/gift-catalog.ts` — cookie pack ids/labels (prices from the API)
- `lib/api.ts` — shared `apiFetch` client (credentials + error handling)
- `lib/gifts.ts` — helpers that compose catalog + API prices

Typography uses **DM Sans** + **Fraunces** (Google Fonts) with a warm cream / wood palette aligned to product docs.

See root `DECISIONS.md` and `Architecture.MD` §0 for as-built backend behavior (Checkout, address TTL, rate limits).
