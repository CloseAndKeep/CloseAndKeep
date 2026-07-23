import type { Metadata } from "next";
import Link from "next/link";
import { getSiteUrl } from "@/lib/site";

export const metadata: Metadata = {
  title: "API",
  description:
    "Create CloseAndKeep gift orders from agents or scripts. API keys open Checkout links — card data stays with Stripe.",
  alternates: {
    canonical: "/developers",
  },
  openGraph: {
    url: "/developers",
    title: "CloseAndKeep API",
    description:
      "Create gift orders via API. Humans pay on Stripe Checkout; fulfillment stays separate for a future bakery integration.",
  },
};

export default function DevelopersDocsPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "https://api.closeandkeep.com";
  const siteUrl = getSiteUrl();

  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl tracking-tight text-espresso">API</h1>
      <p className="mt-4 max-w-2xl text-lg text-stone-600">
        Create prospects and gift orders from an agent or script. CloseAndKeep returns a Stripe
        Checkout URL — a human completes payment. Card numbers never touch your key or our API.
      </p>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">How it works</h2>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            Sign in and create a key under{" "}
            <Link href="/api-keys" className="font-medium text-wood-dark hover:underline">
              API keys
            </Link>{" "}
            in the dashboard.
          </li>
          <li>
            Call the API with{" "}
            <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs">Authorization: Bearer cak_…</code>
            . Keys cannot call admin routes; create/order endpoints are rate-limited.
          </li>
          <li>Create a prospect, then a gift order. Open the returned Checkout URL to pay.</li>
          <li>
            After payment succeeds the order becomes <code className="text-xs">queued</code> for
            fulfillment (manual today; bakery API can plug in later without changing this flow).
          </li>
        </ol>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Base URL</h2>
        <p>
          API host:{" "}
          <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs">{apiBase}</code>
        </p>
        <p className="text-stone-500">
          Public site: {siteUrl}. Gift ids:{" "}
          <code className="text-xs">cookies-4</code>, <code className="text-xs">cookies-12</code>{" "}
          (confirm live prices with <code className="text-xs">GET /gifts</code>).
        </p>
      </section>

      <section className="mt-12 space-y-4 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Create a prospect</h2>
        <pre className="overflow-x-auto rounded-2xl bg-espresso px-4 py-4 text-xs leading-relaxed text-cream">
{`curl -s -X POST "${apiBase}/prospects" \\
  -H "Authorization: Bearer cak_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Dana Buyer",
    "email": "dana@acme.example",
    "deal_status": "open"
  }'`}
        </pre>
      </section>

      <section className="mt-12 space-y-4 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Create an order + Checkout URL</h2>
        <pre className="overflow-x-auto rounded-2xl bg-espresso px-4 py-4 text-xs leading-relaxed text-cream">
{`curl -s -X POST "${apiBase}/gift-orders" \\
  -H "Authorization: Bearer cak_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "prospect_id": 123,
    "gift_id": "cookies-4",
    "recipient_name": "Dana Buyer",
    "shipping_address": "123 Main St\\nSpringfield, IL 62704",
    "note": "Thanks for the great meeting!"
  }'`}
        </pre>
        <p>
          Response includes <code className="text-xs">checkout_url</code>. Open it in a browser to
          pay. Poll <code className="text-xs">GET /gift-orders/{"{id}"}</code> for{" "}
          <code className="text-xs">payment_status</code> and <code className="text-xs">status</code>.
        </p>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">What this API does not do</h2>
        <ul className="list-disc space-y-2 pl-5">
          <li>It does not accept or store credit card numbers.</li>
          <li>It does not charge a saved card without Checkout (that would be a later option).</li>
          <li>
            It does not call the bakery yet — paid orders queue for fulfillment so a vendor API can
            be added without changing how partners create orders.
          </li>
        </ul>
      </section>
    </div>
  );
}
