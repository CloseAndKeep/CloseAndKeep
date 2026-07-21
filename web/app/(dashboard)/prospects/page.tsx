"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

type Prospect = {
  id: number;
  name: string;
  title: string;
  company: string;
  email: string;
  deal_status: "open" | "won" | "lost";
};

export default function ProspectsPage() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    title: "",
    company: "",
    email: "",
  });

  async function loadProspects() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Prospect[]>("/prospects", {
        errorMessage: "Unable to load prospects.",
      });
      setProspects(data);
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : "Unable to load prospects.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProspects();
  }, []);

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
      setForm({ name: "", title: "", company: "", email: "" });
      await loadProspects();
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
      />

      <form
        className="mb-6 grid gap-3 rounded-2xl border border-stone-200/90 bg-white/90 p-4 md:grid-cols-5"
        onSubmit={onCreate}
      >
        <input
          className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
          placeholder="Name"
          value={form.name}
          onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
          required
        />
        <input
          className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
          placeholder="Title"
          value={form.title}
          onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
          required
        />
        <input
          className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
          placeholder="Company"
          value={form.company}
          onChange={(event) => setForm((prev) => ({ ...prev, company: event.target.value }))}
          required
        />
        <input
          type="email"
          className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
          placeholder="Email"
          value={form.email}
          onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
          required
        />
        <button
          type="submit"
          className="rounded-xl bg-wood px-3 py-2 text-sm font-semibold text-white transition hover:bg-wood-dark disabled:opacity-70"
          disabled={creating}
        >
          {creating ? "Saving..." : "Add prospect"}
        </button>
      </form>

      {error ? (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-2xl border border-stone-200/90 bg-white/90 shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-stone-200 bg-stone-50/80 text-xs font-semibold uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3 hidden sm:table-cell">Title</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3 hidden md:table-cell">Email</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {!loading && prospects.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-stone-500" colSpan={4}>
                  No prospects yet.
                </td>
              </tr>
            ) : null}
            {prospects.map((p) => (
              <tr key={p.id} className="hover:bg-cream/40">
                <td className="px-4 py-3">
                  <Link
                    href={`/prospects/${p.id}`}
                    className="font-medium text-wood-dark hover:underline"
                  >
                    {p.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-stone-600 hidden sm:table-cell">{p.title}</td>
                <td className="px-4 py-3 text-stone-700">{p.company}</td>
                <td className="px-4 py-3 text-stone-500 hidden md:table-cell">{p.email}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
