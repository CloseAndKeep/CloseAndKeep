"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { getApiBaseUrl } from "@/lib/api";
import { labelForGiftId } from "@/lib/mock-data";

type AdminGiftOrder = {
  id: number;
  gift_id: string;
  recipient_name: string;
  status: string;
  payment_status: string;
  tracking_number: string | null;
  requested_at: string;
  owner_email: string;
  prospect_name: string;
  prospect_company: string;
};

const FILTERS = [
  { value: "queued", label: "Queued" },
  { value: "no_address", label: "No address" },
  { value: "pending_payment", label: "Pending payment" },
  { value: "ordered", label: "Ordered" },
  { value: "shipped", label: "Shipped" },
  { value: "delivered", label: "Delivered" },
  { value: "canceled", label: "Canceled" },
  { value: "all", label: "All" },
];

function statusClasses(status: string): string {
  switch (status) {
    case "delivered":
      return "bg-emerald-100 text-emerald-800";
    case "shipped":
      return "bg-sky-100 text-sky-800";
    case "ordered":
      return "bg-indigo-100 text-indigo-800";
    case "canceled":
      return "bg-rose-100 text-rose-800";
    case "no_address":
      return "bg-orange-100 text-orange-900";
    case "pending_payment":
      return "bg-stone-100 text-stone-700";
    default:
      return "bg-amber-100 text-amber-900";
  }
}

export default function AdminQueuePage() {
  const [orders, setOrders] = useState<AdminGiftOrder[]>([]);
  const [filter, setFilter] = useState<string>("queued");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/admin/gift-orders?status=${filter}`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Unable to load orders.");
      }
      const data = (await response.json()) as AdminGiftOrder[];
      setOrders(data);
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : "Unable to load orders.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void loadOrders();
  }, [loadOrders]);

  return (
    <>
      <PageHeader
        title="Order queue"
        description="Gift orders awaiting fulfillment. Filter by status — including orders still waiting on a shipping address."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {FILTERS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilter(value)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === value
                ? "bg-wood/20 text-wood-dark"
                : "bg-stone-100 text-stone-700 hover:bg-stone-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error ? (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-2xl border border-stone-200/90 bg-white/90 shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-stone-200 bg-stone-50/80 text-xs font-semibold uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-4 py-3">Order</th>
              <th className="px-4 py-3 hidden sm:table-cell">Recipient</th>
              <th className="px-4 py-3 hidden md:table-cell">Cookies</th>
              <th className="px-4 py-3 hidden lg:table-cell">Placed by</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-3 text-stone-500">
                  Loading orders...
                </td>
              </tr>
            ) : null}
            {!loading && orders.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-3 text-stone-500">
                  No orders in this view.
                </td>
              </tr>
            ) : null}
            {orders.map((order) => (
              <tr key={order.id} className="hover:bg-cream/40">
                <td className="px-4 py-3">
                  <Link
                    href={`/admin/orders/${order.id}`}
                    className="font-medium text-wood-dark hover:underline"
                  >
                    #{order.id}
                  </Link>
                  <div className="text-xs text-stone-500">
                    {new Date(order.requested_at).toLocaleDateString()}
                  </div>
                </td>
                <td className="px-4 py-3 text-stone-700 hidden sm:table-cell">
                  {order.recipient_name}
                </td>
                <td className="px-4 py-3 text-stone-600 hidden md:table-cell">
                  {labelForGiftId(order.gift_id)}
                </td>
                <td className="px-4 py-3 text-stone-500 hidden lg:table-cell">
                  {order.owner_email}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${statusClasses(
                      order.status,
                    )}`}
                  >
                    {order.status.replace("_", " ")}
                  </span>
                  {order.payment_status !== "paid" ? (
                    <span className="ml-1 rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-500">
                      {order.payment_status === "authorized" ? "authorized" : "unpaid"}
                    </span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
