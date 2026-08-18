"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";

type RetryResult = {
  status: string;
};

export function RetryAutoOrder({
  eventId,
  onDone,
}: {
  eventId: number;
  onDone?: (result: RetryResult) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function retry() {
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<RetryResult>(`/integrations/events/${eventId}/retry`, {
        method: "POST",
        errorMessage: "Unable to retry this auto-order.",
      });
      onDone?.(result);
    } catch (retryError) {
      setError(
        retryError instanceof Error ? retryError.message : "Unable to retry this auto-order.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={() => void retry()}
        disabled={busy}
        className="rounded-full border border-stone-200 bg-white px-3 py-1.5 text-sm font-medium text-espresso hover:bg-stone-50 disabled:opacity-50"
      >
        {busy ? "Retrying…" : "Retry"}
      </button>
      {error ? <span className="text-xs text-rose-700">{error}</span> : null}
    </span>
  );
}
