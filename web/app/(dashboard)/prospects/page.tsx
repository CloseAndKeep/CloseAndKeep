"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

type DealStatus = "open" | "won" | "lost";
type StatusFilter = "all" | DealStatus;

type Prospect = {
  id: number;
  name: string;
  email: string;
  deal_status: DealStatus;
};

const inputClass = "field-input";

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

const STATUS_LABELS: Record<DealStatus, string> = {
  open: "Open",
  won: "Won",
  lost: "Lost",
};

export default function ProspectsPage() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [form, setForm] = useState({
    name: "",
    email: "",
  });

  const hasActiveFilters = search.trim() !== "" || statusFilter !== "all";

  const loadProspects = useCallback(async () => {
    const params = new URLSearchParams();
    const q = search.trim();
    if (q) {
      params.set("q", q);
    }
    if (statusFilter !== "all") {
      params.set("deal_status", statusFilter);
    }
    const qs = params.toString();
    return apiFetch<Prospect[]>(`/prospects${qs ? `?${qs}` : ""}`, {
      errorMessage: "Unable to load prospects.",
    });
  }, [search, statusFilter]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    (async () => {
      try {
        const data = await loadProspects();
        if (!cancelled) {
          setProspects(data);
        }
      } catch (loadError) {
        if (!cancelled) {
          const message =
            loadError instanceof Error ? loadError.message : "Unable to load prospects.";
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadProspects]);

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setCreating(true);
    try {
      await apiFetch("/prospects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, deal_status: "open" }),
        errorMessage: "Unable to create prospect.",
      });
      setForm({ name: "", email: "" });
      setProspects(await loadProspects());
    } catch (createError) {
      const message =
        createError instanceof Error ? createError.message : "Unable to create prospect.";
      setError(message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Prospects"
        description="People and companies you're actively working."
        action={
          prospects.length > 0 || hasActiveFilters ? (
            <Link
              href="/orders/new"
              className="inline-flex items-center rounded-full bg-wood px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-wood-dark"
            >
              Send a gift
            </Link>
          ) : undefined
        }
      />

      <form
        className="mb-6 grid gap-3 rounded-2xl border border-stone-200/90 bg-white/90 p-4 md:grid-cols-3 md:items-end"
        onSubmit={onCreate}
      >
        <div>
          <label className="block text-sm font-medium text-espresso" htmlFor="prospect-name">
            Name
          </label>
          <input
            id="prospect-name"
            className={`mt-1.5 ${inputClass}`}
            placeholder="Alex Rivera"
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            required
            autoComplete="name"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-espresso" htmlFor="prospect-email">
            Email
          </label>
          <input
            id="prospect-email"
            type="email"
            className={`mt-1.5 ${inputClass}`}
            placeholder="alex@company.com"
            value={form.email}
            onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
            required
            autoComplete="email"
          />
        </div>
        <Button type="submit" className="w-full md:w-auto" disabled={creating}>
          {creating ? "Saving..." : "Add prospect"}
        </Button>
      </form>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="block min-w-0 flex-1 sm:max-w-sm">
          <span className="sr-only">Search prospects</span>
          <input
            id="prospect-search"
            type="search"
            className={inputClass}
            placeholder="Search name or email"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            autoComplete="off"
          />
        </label>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by deal status">
          {STATUS_FILTERS.map(({ value, label }) => {
            const active = statusFilter === value;
            return (
              <button
                key={value}
                type="button"
                onClick={() => setStatusFilter(value)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                  active
                    ? "bg-wood text-white shadow-sm"
                    : "bg-stone-100 text-stone-700 hover:bg-stone-200"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {error ? (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-2xl border border-stone-200/90 bg-white/90 shadow-sm">
        <table className="w-full min-w-[20rem] text-left text-sm">
          <thead className="border-b border-stone-200 bg-stone-50/80 text-xs font-semibold uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-stone-500" colSpan={3}>
                  Loading prospects...
                </td>
              </tr>
            ) : null}
            {!loading && prospects.length === 0 && !hasActiveFilters ? (
              <tr>
                <td className="px-4 py-8 text-center" colSpan={3}>
                  <p className="font-medium text-espresso">No prospects yet</p>
                  <p className="mt-1 text-sm text-stone-500">
                    Add someone above, then send cookies after your next pitch.
                  </p>
                  <Link
                    href="/orders/new"
                    className="mt-4 inline-flex text-sm font-medium text-wood-dark hover:underline"
                  >
                    Or start a gift order →
                  </Link>
                </td>
              </tr>
            ) : null}
            {!loading && prospects.length === 0 && hasActiveFilters ? (
              <tr>
                <td className="px-4 py-8 text-center" colSpan={3}>
                  <p className="font-medium text-espresso">No matching prospects</p>
                  <p className="mt-1 text-sm text-stone-500">
                    Try a different name, email, or Open / Won / Lost filter.
                  </p>
                </td>
              </tr>
            ) : null}
            {!loading
              ? prospects.map((p) => (
                  <tr key={p.id} className="hover:bg-cream/40">
                    <td className="px-4 py-3">
                      <Link
                        href={`/prospects/${p.id}`}
                        className="font-medium text-wood-dark hover:underline"
                      >
                        {p.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-stone-500">{p.email}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-700">
                        {STATUS_LABELS[p.deal_status]}
                      </span>
                    </td>
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>
    </>
  );
}
