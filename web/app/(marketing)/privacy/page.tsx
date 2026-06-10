import Link from "next/link";

export const metadata = {
  title: "Privacy Policy — CloseAndKeep",
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl tracking-tight text-espresso">Privacy Policy</h1>
      <p className="mt-4 rounded-xl border border-amber-200/80 bg-amber-50/70 px-4 py-3 text-sm text-stone-700">
        Placeholder — this page needs real legal copy before launch. Replace the sections below
        with a reviewed privacy policy.
      </p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-stone-700">
        <section>
          <h2 className="font-display text-xl text-espresso">Information we collect</h2>
          <p className="mt-2">
            TODO: Describe account data, prospect data, shipping details, and payment metadata
            (handled by Stripe) that CloseAndKeep collects.
          </p>
        </section>
        <section>
          <h2 className="font-display text-xl text-espresso">How we use information</h2>
          <p className="mt-2">TODO: Describe fulfillment, notifications, and support use.</p>
        </section>
        <section>
          <h2 className="font-display text-xl text-espresso">Data retention and deletion</h2>
          <p className="mt-2">TODO: Describe retention windows and how users request deletion.</p>
        </section>
        <section>
          <h2 className="font-display text-xl text-espresso">Contact</h2>
          <p className="mt-2">TODO: Add a contact email for privacy requests.</p>
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
