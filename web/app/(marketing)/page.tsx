import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";
import { getSiteUrl, siteDescription, siteName } from "@/lib/site";

export const metadata: Metadata = {
  title: {
    absolute: `${siteName} — Simple gifting follow-up for customer teams`,
  },
  description: siteDescription,
  alternates: {
    canonical: "/",
  },
  openGraph: {
    url: "/",
    title: `${siteName} — Simple gifting follow-up for customer teams`,
    description: siteDescription,
  },
};

const steps = [
  "Log who you’re following up with",
  "Start with a cookie gift that fits the moment",
  "We ship with your note on the gift — you stay human, not generic",
  "Remind yourself to follow up; track won, lost, or open",
];

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: siteName,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description: siteDescription,
  url: getSiteUrl(),
  offers: {
    "@type": "Offer",
    priceCurrency: "USD",
    description: "One-time payment per gift order",
  },
};

export default function HomePage() {
  return (
    <div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <section className="mx-auto max-w-5xl px-4 py-16 sm:px-6 sm:py-24">
        <p className="text-sm font-medium uppercase tracking-widest text-wood">
          For teams that send thoughtful follow-up gifts
        </p>
        <h1 className="mt-4 max-w-3xl font-display text-4xl leading-tight tracking-tight text-espresso sm:text-5xl">
          Close more deals.{" "}
          <span className="text-wood-dark">Keep more customers.</span>
        </h1>
        <p className="mt-6 max-w-xl text-lg text-stone-600">
          For people who want to send gifts to potential or current customers.
        </p>
        <div className="mt-10 flex justify-center">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 rounded-full bg-wood px-6 py-3 text-sm font-medium text-white shadow-md transition hover:bg-wood-dark"
          >
            Log in
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <section className="border-y border-stone-200/80 bg-white/40 py-16">
        <div className="mx-auto max-w-5xl px-4 sm:px-6">
          <h2 className="font-display text-2xl text-espresso sm:text-3xl">
            How it works
          </h2>
          <ol className="mt-10 grid gap-6 sm:grid-cols-2">
            {steps.map((text, i) => (
              <li
                key={i}
                className="flex gap-4 rounded-2xl border border-stone-200/90 bg-white/90 p-5 shadow-sm"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-wood/15 font-display text-lg text-wood-dark">
                  {i + 1}
                </span>
                <span className="text-stone-700 leading-relaxed">{text}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-16 sm:px-6">
        <h2 className="font-display text-2xl text-espresso sm:text-3xl">
          Why teams try it
        </h2>
        <ul className="mt-8 grid gap-4 sm:grid-cols-3">
          {[
            "Differentiated follow-up after crowded SaaS demos",
            "Everything you need to ship and track in one place",
            "Outcome tracking so you learn what actually moves deals",
          ].map((text) => (
            <li
              key={text}
              className="flex gap-3 rounded-2xl border border-stone-200/80 bg-white/70 p-4 text-sm text-stone-700"
            >
              <Check className="h-5 w-5 shrink-0 text-wood" strokeWidth={2} />
              {text}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
