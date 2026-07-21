"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { apiFetch } from "@/lib/api";

export default function DashboardPage() {
  const [summary, setSummary] = useState({
    open_deals: 0,
    won: 0,
    lost: 0,
    total_prospects: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSummary() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<typeof summary>("/dashboard/summary", {
          errorMessage: "Unable to load dashboard summary.",
        });
        setSummary(data);
      } catch (loadError) {
        const message =
          loadError instanceof Error ? loadError.message : "Unable to load dashboard summary.";
        setError(message);
      } finally {
        setLoading(false);
      }
    }
    void loadSummary();
  }, []);

  const rate = useMemo(() => {
    if (summary.won + summary.lost === 0) {
      return null;
    }
    return Math.round((summary.won / (summary.won + summary.lost)) * 100);
  }, [summary.lost, summary.won]);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Snapshot of your live prospect pipeline."
      />

      <div className="mb-8 rounded-2xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm text-stone-700">
        {loading
          ? "Loading summary..."
          : `Tracking ${summary.total_prospects} prospect${summary.total_prospects === 1 ? "" : "s"} in your pipeline.`}
        {error ? <span className="ml-2 text-rose-700">{error}</span> : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Open deals"
          value={summary.open_deals}
          hint="Prospects marked in progress"
        />
        <StatCard label="Total prospects" value={summary.total_prospects} hint="All active records" />
        <StatCard label="Won deals" value={summary.won} hint="Closed won prospects" />
        <StatCard
          label="Win rate (closed)"
          value={rate !== null ? `${rate}%` : "—"}
          hint={summary.won + summary.lost > 0 ? `${summary.won} won / ${summary.lost} lost` : "No closed deals yet"}
        />
      </div>

      <div className="mt-10 grid gap-8 lg:grid-cols-2">
        <section className="rounded-2xl border border-stone-200/90 bg-white/80 p-6 shadow-sm">
          <h2 className="font-display text-xl text-espresso">Prospects</h2>
          <p className="mt-4 text-sm text-stone-600">
            Your live prospects flow is now active from the API.
          </p>
          <Link
            href="/prospects"
            className="mt-4 inline-block text-sm font-medium text-wood-dark hover:underline"
          >
            View prospects →
          </Link>
        </section>

        <section className="rounded-2xl border border-stone-200/90 bg-white/80 p-6 shadow-sm">
          <h2 className="font-display text-xl text-espresso">Next up</h2>
          <p className="mt-4 text-sm text-stone-600">
            Gift order and follow-up flows can now build on real prospect records.
          </p>
          <div className="mt-4 flex flex-wrap gap-4 text-sm font-medium">
            <Link href="/orders/new" className="text-wood-dark hover:underline">
              Start a cookie order →
            </Link>
            <Link href="/orders" className="text-wood-dark hover:underline">
              View submitted orders →
            </Link>
          </div>
        </section>
      </div>
    </>
  );
}
