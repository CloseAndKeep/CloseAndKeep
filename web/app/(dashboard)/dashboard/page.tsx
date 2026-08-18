"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ExpiredHolds } from "@/components/dashboard/expired-holds";
import { GiftedCloseRate } from "@/components/dashboard/gifted-close-rate";
import { NeedsYouToday } from "@/components/dashboard/needs-you-today";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { apiFetch } from "@/lib/api";

export default function DashboardPage() {
  const [summary, setSummary] = useState({
    open_deals: 0,
    won: 0,
    lost: 0,
    total_prospects: 0,
    gifted_won: 0,
    gifted_lost: 0,
    ungifted_won: 0,
    ungifted_lost: 0,
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

  const isEmpty = !loading && summary.total_prospects === 0;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Your prospect pipeline and next gift sends."
        action={
          <Link
            href="/orders/new"
            className="inline-flex items-center rounded-full bg-wood px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-wood-dark"
          >
            Send cookies
          </Link>
        }
      />

      {error ? (
        <div className="mb-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      {isEmpty ? (
        <div className="mb-8 rounded-2xl border border-dashed border-stone-300 bg-white/80 px-6 py-10 text-center">
          <p className="font-display text-xl text-espresso">Start with a prospect</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-stone-600">
            Add someone you&apos;re working, then send cookies after the pitch — pay once at
            checkout.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/prospects"
              className="inline-flex rounded-full bg-wood px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-wood-dark"
            >
              Add a prospect
            </Link>
            <Link
              href="/orders/new"
              className="inline-flex rounded-full border border-wood/40 bg-white px-5 py-2.5 text-sm font-medium text-wood-dark hover:bg-wood/5"
            >
              Send cookies
            </Link>
          </div>
        </div>
      ) : (
        <div className="mb-8 rounded-2xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-sm text-stone-700">
          {loading
            ? "Loading summary..."
            : `Tracking ${summary.total_prospects} prospect${summary.total_prospects === 1 ? "" : "s"} in your pipeline.`}
        </div>
      )}

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
          hint={
            summary.won + summary.lost > 0
              ? `${summary.won} won / ${summary.lost} lost`
              : "No closed deals yet"
          }
        />
      </div>

      <NeedsYouToday />

      <ExpiredHolds />

      <GiftedCloseRate
        gifted_won={summary.gifted_won}
        gifted_lost={summary.gifted_lost}
        ungifted_won={summary.ungifted_won}
        ungifted_lost={summary.ungifted_lost}
      />

      <div className="mt-10 grid gap-8 lg:grid-cols-2">
        <section className="rounded-2xl border border-stone-200/90 bg-white/80 p-6 shadow-sm">
          <h2 className="font-display text-xl text-espresso">Prospects</h2>
          <p className="mt-4 text-sm text-stone-600">
            Keep the people you&apos;re working in one list, then gift from their record.
          </p>
          <Link
            href="/prospects"
            className="mt-4 inline-block text-sm font-medium text-wood-dark hover:underline"
          >
            View prospects →
          </Link>
        </section>

        <section className="rounded-2xl border border-stone-200/90 bg-white/80 p-6 shadow-sm">
          <h2 className="font-display text-xl text-espresso">Gift orders</h2>
          <p className="mt-4 text-sm text-stone-600">
            Place a cookie order after a pitch, or check status on what you&apos;ve already sent.
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
