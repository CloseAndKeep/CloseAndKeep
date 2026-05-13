"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { getApiBaseUrl } from "@/lib/api";
import { labelForGiftId } from "@/lib/mock-data";

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

export default function OrdersPage() {
  const [orders, setOrders] = useState<GiftOrder[]>([]);
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [ordersResponse, prospectsResponse] = await Promise.all([
          fetch(`${getApiBaseUrl()}/gift-orders`, { credentials: "include" }),
          fetch(`${getApiBaseUrl()}/prospects`, { credentials: "include" }),
        ]);

        if (!ordersResponse.ok) {
          throw new Error("Unable to load orders.");
        }
        if (!prospectsResponse.ok) {
          throw new Error("Unable to load prospects.");
        }

        const ordersData = (await ordersResponse.json()) as GiftOrder[];
        const prospectsData = (await prospectsResponse.json()) as Prospect[];
        setOrders(ordersData);
        setProspects(prospectsData);
      } catch (loadError) {
        const message =
          loadError instanceof Error ? loadError.message : "Unable to load orders.";
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    void loadData();
  }, []);

  const prospectMap = useMemo(
    () => new Map(prospects.map((prospect) => [prospect.id, prospect])),
    [prospects],
  );
  const statuses = useMemo(
    () => Array.from(new Set(orders.map((order) => order.status))),
    [orders],
  );
  const filteredOrders = useMemo(
    () =>
      statusFilter === "all"
        ? orders
        : orders.filter((order) => order.status === statusFilter),
    [orders, statusFilter],
  );

  return (
    <>
      <PageHeader
        title="Gift orders"
        description="All cookie orders submitted from the live flow."
        action={
          <Link
            href="/orders/new"
            className="rounded-full bg-wood px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-wood-dark"
          >
            New cookie order
          </Link>
        }
      />

      {error ? (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setStatusFilter("all")}
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            statusFilter === "all"
              ? "bg-wood/20 text-wood-dark"
              : "bg-stone-100 text-stone-700 hover:bg-stone-200"
          }`}
        >
          All ({orders.length})
        </button>
        {statuses.map((status) => {
          const count = orders.filter((order) => order.status === status).length;
          return (
            <button
              key={status}
              type="button"
              onClick={() => setStatusFilter(status)}
              className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${
                statusFilter === status
                  ? "bg-wood/20 text-wood-dark"
                  : "bg-stone-100 text-stone-700 hover:bg-stone-200"
              }`}
            >
              {status} ({count})
            </button>
          );
        })}
      </div>

      <div className="overflow-hidden rounded-2xl border border-stone-200/90 bg-white/90 shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-stone-200 bg-stone-50/80 text-xs font-semibold uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-4 py-3">Requested</th>
              <th className="px-4 py-3">Prospect</th>
              <th className="px-4 py-3 hidden sm:table-cell">Cookies</th>
              <th className="px-4 py-3 hidden md:table-cell">Recipient</th>
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
            {!loading && filteredOrders.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-3 text-stone-500">
                  {orders.length === 0
                    ? "No orders yet. Create your first cookie order."
                    : "No orders match this status filter."}
                </td>
              </tr>
            ) : null}
            {filteredOrders.map((order) => {
              const prospect = prospectMap.get(order.prospect_id);
              return (
                <tr key={order.id} className="hover:bg-cream/40">
                  <td className="px-4 py-3 text-stone-600">
                    <Link href={`/orders/${order.id}`} className="hover:underline">
                      {new Date(order.requested_at).toLocaleDateString()}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-espresso">
                      <Link href={`/orders/${order.id}`} className="hover:underline">
                        {prospect?.name ?? "Unknown prospect"}
                      </Link>
                    </div>
                    <div className="text-xs text-stone-500">{prospect?.company ?? "—"}</div>
                  </td>
                  <td className="px-4 py-3 text-stone-600 hidden sm:table-cell">
                    {labelForGiftId(order.gift_id)}
                  </td>
                  <td className="px-4 py-3 text-stone-600 hidden md:table-cell">{order.recipient_name}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-700 capitalize">
                      {order.status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
