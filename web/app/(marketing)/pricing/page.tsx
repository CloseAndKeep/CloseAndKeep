import Link from "next/link";
import { Check } from "lucide-react";
import { GIFT_ORDER_PRICE_USD, cookiePacks, cookiePackLineTotal } from "@/lib/mock-data";

export default function PricingPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl tracking-tight text-espresso">Pricing</h1>
      <p className="mt-4 max-w-2xl text-lg text-stone-600">
        Pay once per gift order at checkout. No subscription required to get started—send
        cookies when you need them.
      </p>

      <div className="mt-12 rounded-3xl border border-stone-200/90 bg-white/90 p-8 shadow-sm">
        <h2 className="font-display text-2xl text-espresso">Per order</h2>
        <p className="mt-2 text-sm text-stone-500">
          Choose how many cookies to send; you pay that amount once via Stripe when you submit
          the order.
        </p>
        <ul className="mt-8 space-y-3">
          {cookiePacks.map((pack) => (
            <li
              key={pack.id}
              className="flex items-center justify-between gap-4 rounded-xl bg-cream/80 px-4 py-3 text-sm"
            >
              <span className="font-medium text-espresso">
                {pack.cookieCount === 1 ? "1 cookie" : `${pack.cookieCount} cookies`}
              </span>
              <span className="text-stone-600">
                ${cookiePackLineTotal(pack)}
                <span className="text-stone-400"> (${GIFT_ORDER_PRICE_USD} per order)</span>
              </span>
            </li>
          ))}
        </ul>
        <ul className="mt-8 space-y-3 border-t border-stone-100 pt-8">
          {[
            "Dashboard and prospect tracking",
            "Recipient name, address, and note on every gift",
            "Fulfillment after payment succeeds",
            "Follow-up reminders",
          ].map((f) => (
            <li key={f} className="flex gap-2 text-sm text-stone-700">
              <Check className="h-4 w-4 shrink-0 text-wood mt-0.5" />
              {f}
            </li>
          ))}
        </ul>
        <Link
          href="/signup"
          className="mt-10 flex w-full justify-center rounded-full bg-wood py-3 text-sm font-medium text-white shadow hover:bg-wood-dark"
        >
          Get started
        </Link>
      </div>
    </div>
  );
}

