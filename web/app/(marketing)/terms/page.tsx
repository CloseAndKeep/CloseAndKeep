import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Terms for using CloseAndKeep, payments, and fulfillment.",
  alternates: {
    canonical: "/terms",
  },
};

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl tracking-tight text-espresso">Terms of Service</h1>
      <p className="mt-4 rounded-xl border border-amber-200/80 bg-amber-50/70 px-4 py-3 text-sm text-stone-700">
        Placeholder — this page needs real legal copy before launch. Replace the sections below
        with reviewed terms of service.
      </p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-stone-700">
        <section>
          <h2 className="font-display text-xl text-espresso">Using CloseAndKeep</h2>
          <p className="mt-2">TODO: Describe acceptable use and account responsibilities.</p>
        </section>
        <section>
          <h2 className="font-display text-xl text-espresso">Payments and refunds</h2>
          <p className="mt-2">
            TODO: Describe one-time per-order pricing, payment via Stripe, and the refund/cancel
            policy for orders that have not shipped.
          </p>
        </section>
        <section>
          <h2 className="font-display text-xl text-espresso">Fulfillment and delivery</h2>
          <p className="mt-2">TODO: Describe fulfillment timelines and limitations.</p>
        </section>
        <section>
          <h2 className="font-display text-xl text-espresso">Liability and changes</h2>
          <p className="mt-2">TODO: Add liability limitations and how terms may change.</p>
        </section>
      </div>

      <p className="mt-10 text-sm text-stone-500">
        <Link href="/" className="text-wood-dark hover:underline">
          ← Back home
        </Link>
      </p>
    </div>
  );
}
