import Link from "next/link";
import { Check } from "lucide-react";

const tiers = [
  {
    name: "Individual",
    audience: "Solo AE or rep",
    limit: "1 cookie order / week",
    price: "$—",
    period: "per month (placeholder)",
    highlighted: false,
    features: [
      "Dashboard + outcome tracking",
      "Cookie options",
      "Recipient name, address & note on every gift",
      "Follow-up reminders",
    ],
  },
  {
    name: "Enterprise",
    audience: "Team or org",
    limit: "5 cookie orders / week",
    price: "$—",
    period: "per month (placeholder)",
    highlighted: true,
    features: [
      "Everything in Individual",
      "Higher weekly send volume",
      "Priority support (planned)",
      "Billing & seats (planned)",
    ],
  },
];

export default function PricingPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl tracking-tight text-espresso">
        Pricing
      </h1>
      <p className="mt-4 max-w-2xl text-lg text-stone-600">
        Subscription-only direction; exact prices TBD. Limits are placeholders to
        keep fulfillment manageable early on.
      </p>

      <div className="mt-12 grid gap-8 md:grid-cols-2">
        {tiers.map((tier) => (
          <div
            key={tier.name}
            className={
              tier.highlighted
                ? "rounded-3xl border-2 border-wood bg-white p-8 shadow-lg ring-4 ring-wood/10"
                : "rounded-3xl border border-stone-200/90 bg-white/90 p-8 shadow-sm"
            }
          >
            <h2 className="font-display text-2xl text-espresso">{tier.name}</h2>
            <p className="mt-1 text-sm text-stone-500">{tier.audience}</p>
            <p className="mt-4 font-display text-4xl text-espresso">{tier.price}</p>
            <p className="text-sm text-stone-500">{tier.period}</p>
            <p className="mt-4 rounded-xl bg-cream px-3 py-2 text-sm font-medium text-wood-dark">
              Weekly limit: {tier.limit}
            </p>
            <ul className="mt-8 space-y-3">
              {tier.features.map((f) => (
                <li key={f} className="flex gap-2 text-sm text-stone-700">
                  <Check className="h-4 w-4 shrink-0 text-wood mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/dashboard"
              className={
                tier.highlighted
                  ? "mt-10 flex w-full justify-center rounded-full bg-wood py-3 text-sm font-medium text-white shadow hover:bg-wood-dark"
                  : "mt-10 flex w-full justify-center rounded-full border border-stone-300 bg-white py-3 text-sm font-medium text-espresso hover:bg-stone-50"
              }
            >
              Preview app
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
