# CloseAndKeep frontend

Next.js 14 (App Router) + TypeScript + Tailwind. Dashboard and domain screens call the backend API via `lib/api.ts`. Gift pack labels live in `lib/gift-catalog.ts`; live prices come from `GET /gifts`. This app lives in the `web/` workspace of the main **CloseAndKeep** repo.

## Run locally

```bash
cd web
npm install
copy .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Use `/login` to create a session against the local API and access dashboard routes.

## Structure

- `app/(marketing)/` — landing (`/`) and pricing (`/pricing`)
- `app/(dashboard)/` — app shell routes: `/dashboard`, `/prospects`, `/gifts`, `/orders/new`, `/follow-ups`, `/billing`
- `components/layout/` — marketing shell + sidebar app shell
- `lib/gift-catalog.ts` — cookie pack ids/labels (prices from the API)
- `lib/api.ts` — shared `apiFetch` client (credentials + error handling)

Typography uses **DM Sans** + **Fraunces** (Google Fonts) with a warm cream / wood palette aligned to product docs.
