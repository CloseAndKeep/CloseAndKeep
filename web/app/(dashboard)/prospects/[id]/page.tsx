"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

type Prospect = {
  id: number;
  name: string;
  email: string;
  deal_status: "open" | "won" | "lost";
};

const DEAL_STATUSES: { value: Prospect["deal_status"]; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

export default function ProspectDetailPage() {
  const params = useParams<{ id: string }>();
  const [prospect, setProspect] = useState<Prospect | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingStatus, setSavingStatus] = useState<Prospect["deal_status"] | null>(null);

  useEffect(() => {
    async function loadProspect() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<Prospect>(`/prospects/${params.id}`, {
          errorMessage: "Prospect not found.",
        });
        setProspect(data);
      } catch (loadError) {
        const message =
          loadError instanceof Error ? loadError.message : "Unable to load prospect.";
        setError(message);
      } finally {
        setLoading(false);
      }
    }
    if (params.id) {
      void loadProspect();
    }
  }, [params.id]);

  async function updateDealStatus(next: Prospect["deal_status"]) {
    if (!prospect || prospect.deal_status === next) {
      return;
    }
    setSavingStatus(next);
    setError(null);
    try {
      const data = await apiFetch<Prospect>(`/prospects/${prospect.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deal_status: next }),
        errorMessage: "Unable to update deal status.",
      });
      setProspect(data);
    } catch (updateError) {
      const message =
        updateError instanceof Error ? updateError.message : "Unable to update deal status.";
      setError(message);
    } finally {
      setSavingStatus(null);
    }
  }

  if (loading) {
    return <p className="text-sm text-stone-500">Loading prospect...</p>;
  }

  if (error || !prospect) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {error ?? "Prospect not found."}
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title={prospect.name}
        description={prospect.email}
        action={
          <Link
            href="/orders/new"
            className="rounded-full bg-wood px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-wood-dark"
          >
            Send cookies
          </Link>
        }
      />

      {error ? (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
          Contact
        </h2>
        <p className="mt-2 text-espresso">{prospect.email}</p>
      </div>

      <div className="mt-6 rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
          Deal status
        </h2>
        <p className="mt-2 text-sm text-stone-600">
          Mark the outcome so your dashboard win rate stays accurate.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {DEAL_STATUSES.map(({ value, label }) => {
            const active = prospect.deal_status === value;
            return (
              <button
                key={value}
                type="button"
                onClick={() => updateDealStatus(value)}
                disabled={savingStatus !== null}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition disabled:opacity-60 ${
                  active
                    ? "bg-wood text-white shadow-sm"
                    : "bg-stone-100 text-stone-700 hover:bg-stone-200"
                }`}
              >
                {savingStatus === value ? "Saving..." : label}
              </button>
            );
          })}
        </div>
      </div>

      <p className="mt-8 text-sm text-stone-500">
        <Link href="/prospects" className="text-wood-dark hover:underline">
          ← Back to prospects
        </Link>
      </p>
    </>
  );
}
