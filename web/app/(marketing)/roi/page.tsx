import Link from "next/link";
import { RoiCalculator } from "@/components/roi/roi-calculator";

export default function RoiPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
      <header className="max-w-2xl">
        <h1 className="font-display text-4xl tracking-tight text-espresso sm:text-5xl">
          ROI Calculator
        </h1>
        <p className="mt-4 text-lg text-stone-600">
          Estimate your incremental revenue and ROI from cookie gifts after demos
          and for existing customers. Plug in your numbers and watch the estimate
          update live.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-stone-600">
          Teams often model a close-rate lift around{" "}
          <span className="font-medium text-espresso">10%</span> and a churn cut
          around <span className="font-medium text-espresso">15%</span> — adjust
          the inputs to match your pipeline.
        </p>
        <p className="mt-2 text-xs leading-relaxed text-stone-500">
          Estimates only — not guaranteed. Based on results we&apos;ve seen in the
          past. Default inputs below are illustrative starting points you can
          replace with your own figures.
        </p>
        <nav className="mt-6 flex flex-wrap gap-3 text-sm" aria-label="On this page">
          <a
            href="#calculator"
            className="rounded-full border border-wood/30 bg-white/80 px-3.5 py-1.5 font-medium text-wood-dark transition hover:border-wood hover:bg-wood/5"
          >
            Calculator
          </a>
          <a
            href="#sensitivity"
            className="rounded-full border border-wood/30 bg-white/80 px-3.5 py-1.5 font-medium text-wood-dark transition hover:border-wood hover:bg-wood/5"
          >
            Sensitivity
          </a>
        </nav>
      </header>

      <aside className="mt-10 max-w-2xl rounded-2xl border border-stone-200/90 bg-white/70 p-5 text-sm text-stone-600">
        <p className="font-medium text-espresso">How to use</p>
        <ol className="mt-3 list-decimal space-y-2 pl-5">
          <li>
            Edit the inputs with figures from discovery or your CRM.
          </li>
          <li>
            Close-rate lift and churn reduction are the core assumptions — replace
            the defaults with your own program results when you have them.
          </li>
          <li>
            Pause on the <span className="font-medium text-espresso">estimated</span>{" "}
            <span className="font-medium text-espresso">net revenue</span> and{" "}
            <span className="font-medium text-espresso">ROI %</span> as the numbers
            update.
          </li>
          <li>
            Breakeven answers “is this worth it?” — any deal or customer value
            above the threshold returns more revenue than the gift costs.
          </li>
          <li>
            Scroll to sensitivity to see the full curve relative to breakeven.
          </li>
        </ol>
        <p className="mt-4 text-xs leading-relaxed text-stone-500">
          Figures are revenue-based (no margin). Outputs are estimates, not
          guarantees — past results do not guarantee future performance.
        </p>
      </aside>

      <div className="mt-14">
        <RoiCalculator />
      </div>

      <div className="mt-16 border-t border-stone-200/80 pt-10 text-center">
        <p className="text-stone-600">Ready to send cookies after the pitch?</p>
        <Link
          href="/signup"
          className="mt-4 inline-flex rounded-full bg-wood px-6 py-3 text-sm font-medium text-white shadow-sm transition hover:bg-wood-dark"
        >
          Get started
        </Link>
      </div>
    </div>
  );
}
