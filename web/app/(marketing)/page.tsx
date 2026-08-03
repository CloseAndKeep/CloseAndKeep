import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";
import { getSiteUrl, siteDescription, siteName } from "@/lib/site";

export const metadata: Metadata = {
  title: {
    absolute: `${siteName}: Simple gifting follow-up for customer teams`,
  },
  description: siteDescription,
  alternates: {
    canonical: "/",
  },
  openGraph: {
    url: "/",
    title: `${siteName}: Simple gifting follow-up for customer teams`,
    description: siteDescription,
  },
};

const steps = [
  "Add a few CloseAndKeep fields to the CRM your reps already use",
  "We collect the shipping address automatically — no manual entry required",
  "We ship quality cookies with your personal note so you stay human, not generic",
  "Track every send and watch conversion rates rise",
];

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: siteName,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description: siteDescription,
  url: getSiteUrl(),
  sameAs: [
    "https://www.facebook.com/profile.php?id=61592292207936",
    "https://www.linkedin.com/company/closeandkeep/about/",
  ],
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

      <section className="relative overflow-hidden border-b border-stone-200/80">
        <div
          className="absolute inset-0 bg-[radial-gradient(ellipse_at_20%_0%,rgba(124,90,58,0.18),transparent_55%),radial-gradient(ellipse_at_90%_40%,rgba(92,64,40,0.12),transparent_50%),linear-gradient(180deg,#f5f0e8_0%,#ebe4d8_100%)]"
          aria-hidden
        />
        <div className="relative mx-auto grid max-w-5xl gap-10 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:gap-12 lg:py-24">
          <div>
            <p className="font-display text-3xl tracking-tight text-espresso sm:text-4xl">
              CloseAndKeep
            </p>
            <h1 className="mt-4 max-w-xl font-display text-4xl leading-tight tracking-tight text-espresso sm:text-5xl">
              Close more deals.{" "}
              <span className="text-wood-dark">Keep more customers.</span>
            </h1>
            <p className="mt-6 max-w-lg text-lg text-stone-600">
              Pay once to send cookies after a pitch — with a personal note and address
              collection built in. No subscription.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-3">
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-full bg-wood px-6 py-3 text-sm font-medium text-white shadow-md transition hover:bg-wood-dark"
              >
                Get started
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/redeem"
                className="inline-flex items-center gap-2 rounded-full border border-wood/40 bg-white/80 px-6 py-3 text-sm font-medium text-wood-dark shadow-sm transition hover:border-wood hover:bg-wood/5"
              >
                Redeem a gift
              </Link>
            </div>
          </div>

          <div className="relative min-h-[280px] sm:min-h-[320px]">
            <div className="absolute inset-0 rounded-[2rem] bg-gradient-to-br from-wood/25 via-wood-dark/15 to-espresso/20 shadow-inner" />
            <div className="absolute inset-4 flex flex-col justify-between rounded-[1.5rem] border border-white/50 bg-white/75 p-6 shadow-lg backdrop-blur-sm sm:inset-6 sm:p-8">
              <Image
                src="/brand/mark.png"
                alt=""
                width={48}
                height={62}
                className="h-12 w-auto self-start object-contain"
                priority
              />
              <div>
                <p className="font-display text-2xl text-espresso sm:text-3xl">
                  Cookies + a note that sounds like you
                </p>
                <p className="mt-3 text-sm leading-relaxed text-stone-600">
                  Track the prospect, collect their address, ship once — all without leaving
                  your workflow.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-stone-200/80 bg-white/40 py-16">
        <div className="mx-auto max-w-5xl px-4 sm:px-6">
          <h2 className="font-display text-2xl text-espresso sm:text-3xl">
            How it works
          </h2>
          <ol className="mt-10 grid gap-6 sm:grid-cols-2">
            {steps.map((text, i) => (
              <li key={i} className="flex gap-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-wood/15 font-display text-lg text-wood-dark">
                  {i + 1}
                </span>
                <span className="pt-1.5 text-stone-700 leading-relaxed">{text}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-16 sm:px-6">
        <h2 className="font-display text-2xl text-espresso sm:text-3xl">
          Why teams use us
        </h2>
        <ul className="mt-8 grid gap-6 sm:grid-cols-3">
          {[
            "Stand out in a market flooded with AI-generated outreach",
            "Built for reps, right inside the CRM they already use",
            "450% average ROI, driven by higher close rates and stronger retention",
          ].map((text) => (
            <li key={text} className="flex gap-3 text-sm text-stone-700">
              <Check className="h-5 w-5 shrink-0 text-wood" strokeWidth={2} />
              {text}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
