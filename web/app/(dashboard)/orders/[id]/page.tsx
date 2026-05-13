"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { getApiBaseUrl } from "@/lib/api";
import { COOKIE_UNIT_PRICE_USD, cookiePackById, labelForGiftId } from "@/lib/mock-data";

type GiftOrder = {
  id: number;
  prospect_id: number;
  gift_id: string;
  recipient_name: string;
  shipping_address: string;
  note: string;
  status: string;
  requested_at: string;
};

type Prospect = {
  id: number;
  name: string;
  company: string;
};

export default function OrderDetailPage() {
  const params = useParams<{ id: string }>();
  const [order, setOrder] = useState<GiftOrder | null>(null);
  const [prospect, setProspect] = useState<Prospect | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadOrder() {
      setLoading(true);
      setError(null);
      try {
        const orderResponse = await fetch(`${getApiBaseUrl()}/gift-orders/${params.id}`, {
          credentials: "include",
        });
        if (!orderResponse.ok) {
          throw new Error("Unable to load order.");
        }
        const orderData = (await orderResponse.json()) as GiftOrder;
        setOrder(orderData);

        const prospectResponse = await fetch(`${getApiBaseUrl()}/prospects/${orderData.prospect_id}`, {
          credentials: "include",
        });
        if (prospectResponse.ok) {
          const prospectData = (await prospectResponse.json()) as Prospect;
          setProspect(prospectData);
        }
      } catch (loadError) {
        const message =
          loadError instanceof Error ? loadError.message : "Unable to load order.";
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    if (params.id) {
      void loadOrder();
    }
  }, [params.id]);

  if (loading) {
    return <p className="text-sm text-stone-500">Loading order...</p>;
  }

  if (error || !order) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {error ?? "Order not found."}
      </div>
    );
  }

  const cookiePack = cookiePackById(order.gift_id);

  return (
    <>
      <PageHeader
        title={`Order #${order.id}`}
        description={`Submitted ${new Date(order.requested_at).toLocaleString()}`}
      />

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
            Prospect
          </h2>
          <p className="mt-2 font-medium text-espresso">{prospect?.name ?? "Unknown prospect"}</p>
          <p className="text-stone-600">{prospect?.company ?? "—"}</p>
          <p className="mt-4 text-xs text-stone-500">Prospect ID: {order.prospect_id}</p>
        </section>

        <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
            Order status
          </h2>
          <p className="mt-2">
            <span className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-700 capitalize">
              {order.status}
            </span>
          </p>
          <p className="mt-4 text-sm text-stone-600">Cookies: {labelForGiftId(order.gift_id)}</p>
          {cookiePack ? (
            <p className="mt-1 text-xs text-stone-500">
              Temporary estimate: ${cookiePack.cookieCount * COOKIE_UNIT_PRICE_USD} (
              {COOKIE_UNIT_PRICE_USD}/cookie)
            </p>
          ) : null}
          <p className="mt-1 text-sm text-stone-600">Recipient: {order.recipient_name}</p>
        </section>
      </div>

      <section className="mt-6 rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
          Shipping address
        </h2>
        <p className="mt-2 whitespace-pre-line text-sm text-stone-700">{order.shipping_address}</p>
      </section>

      <section className="mt-6 rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
          Note on gift
        </h2>
        <p className="mt-2 whitespace-pre-line text-sm text-stone-700">{order.note}</p>
      </section>

      <p className="mt-8 text-sm text-stone-500">
        <Link href="/orders" className="text-wood-dark hover:underline">
          ← Back to orders
        </Link>
      </p>
    </>
  );
}
