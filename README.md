# CloseAndKeep — frontend (preview)

Next.js 14 (App Router) + TypeScript + Tailwind. Dashboard routes now call the backend session endpoints, while domain screens still use placeholder data from `lib/mock-data.ts`. The parent **CloseAndKeep** project is **not** under Git for now (optional later).

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
- `lib/mock-data.ts` — placeholder prospects, pitches, gifts, etc.

Typography uses **DM Sans** + **Fraunces** (Google Fonts) with a warm cream / wood palette aligned to product docs.
