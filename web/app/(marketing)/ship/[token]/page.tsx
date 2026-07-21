"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { getApiBaseUrl } from "@/lib/api";
import { labelForGiftId } from "@/lib/mock-data";

type AddressRequest = {
  recipient_name: string;
  gift_id: string;
  note: string;
  already_submitted: boolean;
};

export default function ShipAddressPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [request, setRequest] = useState<AddressRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const [recipientName, setRecipientName] = useState("");
  const [address, setAddress] = useState("");

  const loadRequest = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/public/address-requests/${token}`);
      if (!response.ok) {
        throw new Error("This link is invalid or has expired.");
      }
      const data = (await response.json()) as AddressRequest;
      setRequest(data);
      setRecipientName(data.recipient_name);
      setDone(data.already_submitted);
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : "Unable to load this link.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadRequest();
  }, [loadRequest]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !address.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/public/address-requests/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shipping_address: address.trim(),
          recipient_name: recipientName.trim() || undefined,
        }),
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(
          typeof data?.detail === "string" ? data.detail : "Unable to save address.",
        );
      }
      const data = (await response.json()) as AddressRequest;
      setRequest(data);
      setDone(true);
    } catch (submitError) {
      const message =
        submitError instanceof Error ? submitError.message : "Unable to save address.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-12 sm:px-6">
      <h1 className="font-display text-3xl text-espresso">Shipping address</h1>
      <p className="mt-2 text-sm text-stone-600">
        Enter where we should send your cookie gift. The person who ordered will be notified.
      </p>

      {loading ? <p className="mt-8 text-sm text-stone-500">Loading…</p> : null}

      {error && !request ? (
        <div className="mt-8 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      {request && done ? (
        <div className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50/80 p-6">
          <p className="font-medium text-emerald-900">Thank you — address received.</p>
          <p className="mt-2 text-sm text-emerald-800">
            The sender has been notified and payment is complete so we can ship your gift.
          </p>
        </div>
      ) : null}

      {request && !done ? (
        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          {error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          <div className="rounded-xl bg-cream/80 p-4 text-sm">
            <p className="text-xs font-semibold uppercase text-stone-500">Gift</p>
            <p className="mt-1 font-medium text-espresso">{labelForGiftId(request.gift_id)}</p>
            {request.note ? (
              <p className="mt-3 whitespace-pre-line text-stone-600">
                <span className="font-medium text-espresso">Note: </span>
                {request.note}
              </p>
            ) : null}
          </div>

          <div>
            <label className="block text-sm font-medium text-espresso">Your name</label>
            <input
              className="mt-2 w-full rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm"
              value={recipientName}
              onChange={(e) => setRecipientName(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-espresso">Full shipping address</label>
            <textarea
              className="mt-2 w-full min-h-[120px] rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Street, city, state, ZIP / postal code"
              required
            />
          </div>

          <Button type="submit" variant="primary" disabled={submitting || !address.trim()}>
            {submitting ? "Saving…" : "Submit address"}
          </Button>
        </form>
      ) : null}
    </div>
  );
}
