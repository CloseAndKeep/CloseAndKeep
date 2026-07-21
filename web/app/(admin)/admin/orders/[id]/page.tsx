"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { getApiBaseUrl } from "@/lib/api";
import { labelForGiftId } from "@/lib/mock-data";

type AdminGiftOrder = {
  id: number;
  prospect_id: number;
  gift_id: string;
  recipient_name: string;
  shipping_address: string | null;
  recipient_email?: string | null;
  note: string;
  status: string;
  payment_status: string;
  tracking_number: string | null;
  admin_notes: string | null;
  requested_at: string;
  owner_email: string;
  prospect_name: string;
  prospect_company: string;
  prospect_email: string;
};

const STATUS_OPTIONS = [
  "no_address",
  "pending_payment",
  "queued",
  "ordered",
  "shipped",
  "delivered",
  "canceled",
];

export default function AdminOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const [order, setOrder] = useState<AdminGiftOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);

  const [status, setStatus] = useState("queued");
  const [trackingNumber, setTrackingNumber] = useState("");
  const [adminNotes, setAdminNotes] = useState("");

  const loadOrder = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/admin/gift-orders/${params.id}`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Unable to load order.");
      }
      const data = (await response.json()) as AdminGiftOrder;
      setOrder(data);
      setStatus(data.status);
      setTrackingNumber(data.tracking_number ?? "");
      setAdminNotes(data.admin_notes ?? "");
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

  async function onSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!order) return;
    setSaving(true);
    setError(null);
    setSavedNotice(false);
    try {
      const response = await fetch(`${getApiBaseUrl()}/admin/gift-orders/${order.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          status,
          tracking_number: trackingNumber,
          admin_notes: adminNotes,
        }),
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(data?.detail ?? "Unable to update order.");
      }
      const data = (await response.json()) as AdminGiftOrder;
      setOrder(data);
      setStatus(data.status);
      setTrackingNumber(data.tracking_number ?? "");
      setAdminNotes(data.admin_notes ?? "");
      setSavedNotice(true);
    } catch (saveError) {
      const message =
        saveError instanceof Error ? saveError.message : "Unable to update order.";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-stone-500">Loading order...</p>;
  }

  if (!order) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {error ?? "Order not found."}
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title={`Order #${order.id}`}
        description={`Placed by ${order.owner_email} · ${new Date(order.requested_at).toLocaleString()}`}
      />

      {savedNotice ? (
        <p className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          Order updated.
        </p>
      ) : null}
      {error ? (
        <p className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
            Recipient
          </h2>
          <p className="mt-2 font-medium text-espresso">{order.recipient_name}</p>
          {order.recipient_email ? (
            <p className="mt-1 text-sm text-stone-500">{order.recipient_email}</p>
          ) : null}
          <p className="mt-3 whitespace-pre-line text-sm text-stone-700">
            {order.shipping_address || "No address yet"}
          </p>
          <p className="mt-4 text-sm text-stone-600">
            Status:{" "}
            <span className="rounded-full bg-stone-100 px-2 py-0.5 text-xs font-medium capitalize text-stone-700">
              {order.status.replace("_", " ")}
            </span>
          </p>
          <p className="mt-4 text-sm text-stone-600">Cookies: {labelForGiftId(order.gift_id)}</p>
          <p className="mt-1 text-sm text-stone-600">
            Payment:{" "}
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
                order.payment_status === "paid"
                  ? "bg-emerald-100 text-emerald-800"
                  : order.payment_status === "authorized"
                    ? "bg-sky-100 text-sky-800"
                    : "bg-amber-100 text-amber-900"
              }`}
            >
              {order.payment_status}
            </span>
          </p>
        </section>

        <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
            Prospect
          </h2>
          <p className="mt-2 font-medium text-espresso">{order.prospect_name}</p>
          <p className="text-stone-600">{order.prospect_company}</p>
          <p className="text-sm text-stone-500">{order.prospect_email}</p>

          <h3 className="mt-5 text-sm font-semibold uppercase tracking-wide text-stone-500">
            Note on gift
          </h3>
          <p className="mt-2 whitespace-pre-line text-sm text-stone-700">{order.note}</p>
        </section>
      </div>

      <form
        onSubmit={onSave}
        className="mt-6 rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
          Fulfillment
        </h2>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="font-medium text-espresso">Status</span>
            <select
              className="mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option} className="capitalize">
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="font-medium text-espresso">Tracking number</span>
            <input
              className="mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
              placeholder="e.g. 1Z999AA10123456784"
              value={trackingNumber}
              onChange={(event) => setTrackingNumber(event.target.value)}
            />
          </label>
        </div>

        <label className="mt-4 block text-sm">
          <span className="font-medium text-espresso">Internal notes</span>
          <textarea
            className="mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
            rows={3}
            placeholder="Vendor order ID, exceptions, etc. (not shown to the customer)"
            value={adminNotes}
            onChange={(event) => setAdminNotes(event.target.value)}
          />
        </label>

        <Button type="submit" variant="primary" className="mt-4" disabled={saving}>
          {saving ? "Saving..." : "Save changes"}
        </Button>
      </form>

      <p className="mt-8 text-sm text-stone-500">
        <Link href="/admin" className="text-wood-dark hover:underline">
          ← Back to queue
        </Link>
      </p>
    </>
  );
}
