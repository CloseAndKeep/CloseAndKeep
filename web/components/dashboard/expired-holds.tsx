"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { labelForGiftId } from "@/lib/gift-catalog";

type ExpiredHold = {
  id: number;
  gift_id: string;
  recipient_name: string;
  recipient_email: string | null;
  status: string;
  payment_status: string;
  requested_at: string;
};

type ResendResponse = ExpiredHold & {
  checkout_url: string | null;
};

export function ExpiredHolds() {
  const [holds, setHolds] = useState<ExpiredHold[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resendingId, setResendingId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadHolds = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<ExpiredHold[]>("/gift-orders/expired-holds", {
        errorMessage: "Unable to load expired address holds.",
      });
      setHolds(data);
    } catch (loadError) {
      const message =
        loadError instanceof Error
          ? loadError.message
          : "Unable to load expired address holds.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHolds();
  }, [loadHolds]);

  async function resend(orderId: number) {
    setResendingId(orderId);
    setNotice(null);
    setError(null);
    try {
      const result = await apiFetch<ResendResponse>(
        `/gift-orders/${orderId}/resend-address`,
        {
          method: "POST",
          errorMessage: "Unable to resend the address request.",
        },
      );
      if (result.checkout_url) {
        window.location.href = result.checkout_url;
        return;
      }
      setNotice(`New shipping link sent to ${result.recipient_name}.`);
      await loadHolds();
    } catch (resendError) {
      const message =
        resendError instanceof Error
          ? resendError.message
          : "Unable to resend the address request.";
      setError(message);
    } finally {
      setResendingId(null);
    }
  }

  if (loading && holds.length === 0 && !error) {
    return null;
  }
  if (!loading && holds.length === 0 && !error && !notice) {
    return null;
  }

  return (
    <section className="mt-8 rounded-2xl border border-amber-200/80 bg-amber-50/70 p-6 shadow-sm">
      <h2 className="font-display text-xl text-espresso">Expired address holds</h2>
      <p className="mt-2 text-sm text-stone-600">
        These gifts never got a shipping address before the hold expired. Resend
        places a new hold and sends a new link — you do not need to rebuild the
        order.
      </p>

      {error ? (
        <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {notice}
        </div>
      ) : null}

      {holds.length > 0 ? (
        <ul className="mt-4 divide-y divide-amber-200/80">
          {holds.map((hold) => (
            <li
              key={hold.id}
              className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
            >
              <div>
                <Link
                  href={`/orders/${hold.id}`}
                  className="font-medium text-espresso hover:underline"
                >
                  {hold.recipient_name}
                </Link>
                <p className="text-xs text-stone-500">
                  {labelForGiftId(hold.gift_id)}
                  {hold.recipient_email ? ` · ${hold.recipient_email}` : ""}
                  {` · ${new Date(hold.requested_at).toLocaleDateString()}`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void resend(hold.id)}
                disabled={resendingId === hold.id}
                className="inline-flex items-center rounded-full bg-wood px-4 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-wood-dark disabled:opacity-60"
              >
                {resendingId === hold.id ? "Resending…" : "Resend"}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
