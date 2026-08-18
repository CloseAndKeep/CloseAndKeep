"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export type IntegrationEvent = {
  id: number;
  provider: string;
  status: string;
  stage_name: string;
  prospect_id: number | null;
  prospect_name: string | null;
  created_at: string;
};

const PROVIDER_LABEL: Record<string, string> = {
  salesforce: "Salesforce",
  hubspot: "HubSpot",
};

function providerLabel(provider: string) {
  return PROVIDER_LABEL[provider] || provider;
}

export function eventHeadline(event: IntegrationEvent): string {
  if (event.status === "token_expired") {
    return `${providerLabel(event.provider)} login expired`;
  }
  const name = (event.prospect_name || "").trim() || "Deal";
  const stage = (event.stage_name || "").trim() || "stage";
  if (event.status === "auto_ordered") {
    return `${name} ${stage} → cookies ordered`;
  }
  if (event.status === "sent") {
    return `${name} ${stage} → reminder sent`;
  }
  if (event.status === "error") {
    return `${name} ${stage} → order failed`;
  }
  if (event.status === "held_junk") {
    return `${name} ${stage} → held (fix contact)`;
  }
  if (event.status === "skipped_regift") {
    return `${name} ${stage} → skipped (recent gift)`;
  }
  return `${name} ${stage}`;
}

function formatWhen(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function EventJournal({ reloadToken = 0 }: { reloadToken?: number }) {
  const [events, setEvents] = useState<IntegrationEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void apiFetch<IntegrationEvent[]>("/integrations/events", {
      errorMessage: "Unable to load recent CRM activity.",
    })
      .then((data) => {
        if (!cancelled) setEvents(data);
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load recent CRM activity.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  return (
    <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-espresso">Recent activity</h2>
      <p className="mt-1 text-sm text-stone-600">
        Latest CRM stage hits and connection alerts.
      </p>
      {loading ? (
        <p className="mt-4 text-sm text-stone-500">Loading…</p>
      ) : error ? (
        <p className="mt-4 text-sm text-rose-700">{error}</p>
      ) : events.length === 0 ? (
        <p className="mt-4 text-sm text-stone-500">No CRM activity yet.</p>
      ) : (
        <ul className="mt-4 divide-y divide-stone-100">
          {events.map((event) => (
            <li key={event.id} className="flex flex-col gap-0.5 py-3 first:pt-0 last:pb-0">
              <span className="text-sm font-medium text-espresso">{eventHeadline(event)}</span>
              <span className="text-xs text-stone-500">
                {providerLabel(event.provider)}
                {event.created_at ? ` · ${formatWhen(event.created_at)}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
