"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export type NeedsAttentionItem = {
  id: number;
  recipient_name: string;
  status: string;
  href: string;
};

export type NeedsAttentionResponse = {
  unpaid: NeedsAttentionItem[];
  no_address: NeedsAttentionItem[];
  just_shipped: NeedsAttentionItem[];
};

const EMPTY: NeedsAttentionResponse = {
  unpaid: [],
  no_address: [],
  just_shipped: [],
};

const BUCKETS = [
  {
    key: "unpaid",
    title: "Unpaid",
    hint: "Finish checkout so the gift can move.",
  },
  {
    key: "no_address",
    title: "No address",
    hint: "Waiting on the recipient — nudge if needed.",
  },
  {
    key: "just_shipped",
    title: "Just shipped",
    hint: "A good moment to ping the prospect.",
  },
] as const;

function itemHref(item: NeedsAttentionItem): string {
  return item.href || `/orders/${item.id}`;
}

function AttentionBucket({
  title,
  hint,
  items,
}: {
  title: string;
  hint: string;
  items: NeedsAttentionItem[];
}) {
  return (
    <div>
      <h3 className="text-sm font-medium text-espresso">{title}</h3>
      <p className="mt-1 text-xs text-stone-500">{hint}</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-stone-500">None right now</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={item.id}>
              <Link
                href={itemHref(item)}
                className="text-sm font-medium text-wood-dark hover:underline"
              >
                {item.recipient_name}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function NeedsYouToday() {
  const [data, setData] = useState<NeedsAttentionResponse>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAttention() {
      setLoading(true);
      setError(null);
      try {
        const payload = await apiFetch<NeedsAttentionResponse>("/dashboard/needs-attention", {
          errorMessage: "Unable to load what needs you today.",
        });
        setData(payload);
      } catch (loadError) {
        const message =
          loadError instanceof Error
            ? loadError.message
            : "Unable to load what needs you today.";
        setError(message);
      } finally {
        setLoading(false);
      }
    }
    void loadAttention();
  }, []);

  const total = data.unpaid.length + data.no_address.length + data.just_shipped.length;

  return (
    <section className="mt-10 rounded-2xl border border-stone-200/90 bg-white/80 p-6 shadow-sm">
      <h2 className="font-display text-xl text-espresso">Needs you today</h2>
      <p className="mt-2 text-sm text-stone-600">
        Unpaid checkouts, gifts waiting on an address, and orders that just shipped.
      </p>

      {error ? (
        <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : loading ? (
        <p className="mt-4 text-sm text-stone-500">Loading…</p>
      ) : total === 0 ? (
        <p className="mt-4 text-sm text-stone-600">Nothing needs you right now.</p>
      ) : (
        <div className="mt-5 grid gap-6 sm:grid-cols-3">
          {BUCKETS.map((bucket) => (
            <AttentionBucket
              key={bucket.key}
              title={bucket.title}
              hint={bucket.hint}
              items={data[bucket.key]}
            />
          ))}
        </div>
      )}
    </section>
  );
}
