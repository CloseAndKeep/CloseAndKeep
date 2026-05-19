"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { getApiBaseUrl } from "@/lib/api";
import { GIFT_ORDER_PRICE_USD, cookiePackById, labelForGiftId } from "@/lib/mock-data";

type GiftOrder = {
  id: number;
  prospect_id: number;
  gift_id: string;
  recipient_name: string;
  shipping_address: string;
  note: string;
  status: string;
  payment_status: string;
  requested_at: string;
};

type Prospect = {
  id: number;
  name: string;
  company: string;
};

export default function OrderDetailPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const paymentNotice = searchParams.get("payment");
  const [order, setOrder] = useState<GiftOrder | null>(null);
  const [prospect, setProspect] = useState<Prospect | null>(null);
  const [loading, setLoading] = useState(true);
  const [payLoading, setPayLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadOrder = useCallback(async () => {
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
  }, [params.id]);

  useEffect(() => {
    if (params.id) {
      void loadOrder();
    }
  }, [params.id, loadOrder]);

  async function completePayment() {
    if (!order) return;
    setPayLoading(true);
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/gift-orders/${order.id}/checkout`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(data?.detail ?? "Unable to start checkout.");
      }
      const data = (await response.json()) as { checkout_url: string };
      window.location.href = data.checkout_url;
    } catch (payError) {
      const message =
        payError instanceof Error ? payError.message : "Unable to start checkout.";
      setError(message);
      setPayLoading(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-stone-500">Loading order...</p>;
  }

  if (error && !order) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {error}
      </div>
    );
  }

  if (!order) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        Order not found.
      </div>
    );
  }

  const cookiePack = cookiePackById(order.gift_id);
  const needsPayment = order.payment_status === "pending";

  return (
    <>
      <PageHeader
        title={`Order #${order.id}`}
        description={`Submitted ${new Date(order.requested_at).toLocaleString()}`}
      />

      {paymentNotice === "success" && order.payment_status === "paid" ? (
        <p className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          Payment received. Your order is queued for fulfillment.
        </p>
      ) : null}
      {paymentNotice === "success" && needsPayment ? (
        <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Payment is processing. Refresh in a moment if status does not update.
        </p>
      ) : null}
      {paymentNotice === "cancel" ? (
        <p className="mb-4 rounded-xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-700">
          Checkout was canceled. You can complete payment when ready.
        </p>
      ) : null}
      {error ? (
        <p className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      {needsPayment ? (
        <div className="mb-6 rounded-2xl border border-amber-200/90 bg-amber-50/60 p-6">
          <h2 className="font-medium text-espresso">Payment required</h2>
          <p className="mt-2 text-sm text-stone-600">
            This order is saved but not queued until you pay once via Stripe.
          </p>
          <Button
            type="button"
            variant="primary"
            className="mt-4"
            disabled={payLoading}
            onClick={completePayment}
          >
            {payLoading ? "Redirecting..." : "Complete payment"}
          </Button>
        </div>
      ) : null}

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
            Prospect
          </h2>
          <p className="mt-2 font-medium text-espresso">{prospect?.name ?? "Unknown prospect"}</p>
          <p className="text-stone-600">{prospect?.company ?? "—"}</p>
        </section>

        <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
            Status
          </h2>
          <p className="mt-2 flex flex-wrap gap-2">
            <span className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-700 capitalize">
              {order.status.replace("_", " ")}
            </span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                order.payment_status === "paid"
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-amber-100 text-amber-900"
              }`}
            >
              Payment: {order.payment_status}
            </span>
          </p>
          <p className="mt-4 text-sm text-stone-600">Cookies: {labelForGiftId(order.gift_id)}</p>
          {cookiePack ? (
            <p className="mt-1 text-xs text-stone-500">
              Order total: ${GIFT_ORDER_PRICE_USD} (Stripe at checkout)
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
