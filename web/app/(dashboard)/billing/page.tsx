"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { getApiBaseUrl } from "@/lib/api";
import { labelForGiftId } from "@/lib/mock-data";

type GiftOrder = {
  id: number;
  gift_id: string;
  status: string;
  payment_status: string;
  requested_at: string;
};

export default function BillingPage() {
  const [orders, setOrders] = useState<GiftOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadOrders() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${getApiBaseUrl()}/gift-orders`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Unable to load payment history.");
        }
        const data = (await response.json()) as GiftOrder[];
        setOrders(data);
      } catch (loadError) {
        const message =
          loadError instanceof Error ? loadError.message : "Unable to load payment history.";
        setError(message);
      } finally {
        setLoading(false);
      }
    }
    void loadOrders();
  }, []);

  const pending = orders.filter((o) => o.payment_status === "pending");
  const paid = orders.filter((o) => o.payment_status === "paid");

  return (
    <>
      <PageHeader
        title="Payments"
        description="Pay per gift order at checkout. Each cookie send is a one-time Stripe payment."
      />

      <div className="rounded-2xl border border-stone-200/90 bg-white/90 p-8 shadow-sm">
        <h2 className="font-display text-xl text-espresso">How billing works</h2>
        <p className="mt-3 text-sm text-stone-600">
          When you submit a gift order, you are redirected to Stripe to pay once for that order.
          Fulfillment starts after payment succeeds. Subscriptions may be added later.
        </p>
        <Link
          href="/orders/new"
          className="mt-6 inline-flex rounded-full bg-wood px-6 py-3 text-sm font-medium text-white hover:bg-wood-dark"
        >
          Send a gift (pay at checkout)
        </Link>
      </div>

      {error ? (
        <p className="mt-6 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      <section className="mt-8">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
          Awaiting payment ({pending.length})
        </h3>
        {loading ? (
          <p className="mt-3 text-sm text-stone-500">Loading...</p>
        ) : pending.length === 0 ? (
          <p className="mt-3 text-sm text-stone-500">No unpaid orders.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {pending.map((order) => (
              <li
                key={order.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-200/80 bg-amber-50/50 px-4 py-3 text-sm"
              >
                <span>
                  Order #{order.id} — {labelForGiftId(order.gift_id)}
                </span>
                <Link
                  href={`/orders/${order.id}`}
                  className="font-medium text-wood-dark hover:underline"
                >
                  Complete payment →
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-8">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
          Paid orders ({paid.length})
        </h3>
        {loading ? (
          <p className="mt-3 text-sm text-stone-500">Loading...</p>
        ) : paid.length === 0 ? (
          <p className="mt-3 text-sm text-stone-500">No paid orders yet.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {paid.slice(0, 10).map((order) => (
              <li
                key={order.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-stone-200/90 bg-white px-4 py-3 text-sm"
              >
                <span>
                  Order #{order.id} — {labelForGiftId(order.gift_id)}
                </span>
                <Link href={`/orders/${order.id}`} className="text-wood-dark hover:underline">
                  View
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="mt-8 text-sm text-stone-500">
        <Link href="/orders" className="text-wood-dark hover:underline">
          View all gift orders
        </Link>
      </p>
    </>
  );
}
