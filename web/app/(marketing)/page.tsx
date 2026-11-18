import type { Metadata } from "next";
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
  "Create an account here",
  "Upload a CSV with your recipients (try asking your internal AI product to identify targets for you)",
  "CloseAndKeep asks your contact for a shipping address or gathers it automatically",
  "You stay human with a physical gift and a real note — and watch conversion rise",
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
              Send a box of cookies to{" "}
              <span className="text-wood-dark">clients and prospects.</span>
            </h1>
            <p className="mt-6 max-w-lg text-lg text-stone-600">
              CloseAndKeep gathers their address and fulfills the order with a couple of
              clicks. No subscription, only ROI.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-3">
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-full bg-wood px-6 py-3 text-sm font-medium text-white shadow-md transition hover:bg-wood-dark"
              >
                Send cookies
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

          <div className="relative lg:justify-self-end">
            <div
              className="absolute -inset-3 rounded-[1.75rem] bg-gradient-to-br from-wood/25 via-wood-dark/15 to-espresso/20 sm:-inset-4"
              aria-hidden
            />
            <div className="relative rounded-[1.25rem] border border-white/50 bg-white/80 p-6 shadow-lg backdrop-blur-sm sm:p-7">
              <p className="font-display text-2xl text-espresso sm:text-3xl">
                Cookies + a personal note from you
              </p>
              <p className="mt-3 text-sm leading-relaxed text-stone-600">
                Increase close rates by 10% and reduce churn by 15%.
              </p>
              <p className="mt-2 text-xs leading-relaxed text-stone-500">
                Not guaranteed — based on results we&apos;ve seen in the past.
              </p>
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
            {
              text: "Stand out in a market flooded with AI-generated outreach",
            },
            {
              text: "Built for reps, right inside the CRM they already use",
            },
            {
              text: "450% average ROI, driven by higher close rates and stronger retention",
              href: "/roi",
              linkLabel: "Try the ROI calculator",
              note: "Estimate based on past results — not guaranteed.",
            },
          ].map(({ text, href, linkLabel, note }) => (
            <li key={text} className="flex gap-3 text-sm text-stone-700">
              <Check className="h-5 w-5 shrink-0 text-wood" strokeWidth={2} />
              <span>
                {text}
                {href && linkLabel ? (
                  <>
                    {" "}
                    <Link
                      href={href}
                      className="font-medium text-wood-dark underline-offset-2 hover:underline"
                    >
                      {linkLabel}
                    </Link>
                  </>
                ) : null}
                {note ? (
                  <span className="mt-1 block text-xs text-stone-500">{note}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
