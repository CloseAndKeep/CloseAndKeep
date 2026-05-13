"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { getApiBaseUrl } from "@/lib/api";

type Prospect = {
  id: number;
  name: string;
  title: string;
  company: string;
  email: string;
  deal_status: "open" | "won" | "lost";
};

export default function ProspectDetailPage() {
  const params = useParams<{ id: string }>();
  const [prospect, setProspect] = useState<Prospect | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadProspect() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${getApiBaseUrl()}/prospects/${params.id}`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Prospect not found.");
        }
        const data = (await response.json()) as Prospect;
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
        description={`${prospect.title} · ${prospect.company}`}
        action={
          <Link
            href="/orders/new"
            className="rounded-full bg-wood px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-wood-dark"
          >
            Send cookies
          </Link>
        }
      />

      <div className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
          Contact
        </h2>
        <p className="mt-2 text-espresso">{prospect.email}</p>
        <p className="mt-4 text-sm text-stone-600">
          <span className="font-medium text-espresso">Deal status (placeholder):</span>{" "}
          <span className="capitalize">{prospect.deal_status}</span>
        </p>
      </div>

      <section className="mt-8 rounded-2xl border border-stone-200/90 bg-white/90 p-6 text-sm text-stone-600 shadow-sm">
        Gift orders for this prospect are next; this detail page is now reading live prospect data.
      </section>

      <p className="mt-8 text-sm text-stone-500">
        <Link href="/prospects" className="text-wood-dark hover:underline">
          ← Back to prospects
        </Link>
      </p>
    </>
  );
}
