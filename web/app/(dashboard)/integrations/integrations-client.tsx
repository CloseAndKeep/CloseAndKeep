"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckSetup } from "@/components/integrations/check-setup";
import { EventJournal } from "@/components/integrations/event-journal";
import { RetryAutoOrder } from "@/components/integrations/retry-auto-order";
import { StageRecipes, type StageRecipe } from "@/components/integrations/stage-recipes";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

type IntegrationRow = {
  id: number;
  provider: string;
  enabled: boolean;
  trigger_stage_name: string;
  stage_recipes: StageRecipe[];
  external_org_id: string | null;
  instance_url: string | null;
  last_polled_at: string | null;
  token_status: string;
  token_error_at: string | null;
  created_at: string;
  updated_at: string;
};

type RetryableEvent = {
  id: number;
  provider: string;
  external_event_key: string;
  status: string;
  retryable: boolean;
};

type ProviderKey = "salesforce" | "hubspot";

const PROVIDERS: {
  key: ProviderKey;
  label: string;
  objectLabel: string;
  connectPath: string;
  syncPath: string;
}[] = [
  {
    key: "salesforce",
    label: "Salesforce",
    objectLabel: "opportunity",
    connectPath: "/integrations/salesforce/connect",
    syncPath: "/integrations/salesforce/sync",
  },
  {
    key: "hubspot",
    label: "HubSpot",
    objectLabel: "deal",
    connectPath: "/integrations/hubspot/connect",
    syncPath: "/integrations/hubspot/sync",
  },
];

function formatWhen(value: string | null) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function IntegrationsClient() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<IntegrationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<ProviderKey | null>(null);
  const [syncing, setSyncing] = useState<ProviderKey | null>(null);
  const [saving, setSaving] = useState<ProviderKey | null>(null);
  const [journalTick, setJournalTick] = useState(0);
  const [retryableEvents, setRetryableEvents] = useState<RetryableEvent[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<IntegrationRow[]>("/integrations", {
        errorMessage: "Unable to load integrations.",
      });
      setRows(data);
      setJournalTick((n) => n + 1);
      try {
        const events = await apiFetch<RetryableEvent[]>("/integrations/events?retryable=true", {
          errorMessage: "Unable to load failed auto-orders.",
        });
        setRetryableEvents(events.filter((event) => event.retryable));
      } catch {
        setRetryableEvents([]);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load integrations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const connected = searchParams.get("connected");
    const oauthError = searchParams.get("error");
    if (connected === "salesforce" || connected === "hubspot") {
      const label = connected === "hubspot" ? "HubSpot" : "Salesforce";
      setMessage(
        `${label} connected. Cookie reminders will send when a deal hits a stage in your recipes.`,
      );
      void load();
    } else if (oauthError) {
      setError(`CRM connection failed: ${oauthError}`);
    }
  }, [searchParams, load]);

  async function connect(provider: (typeof PROVIDERS)[number]) {
    setConnecting(provider.key);
    setError(null);
    setMessage(null);
    try {
      const data = await apiFetch<{ authorize_url: string }>(provider.connectPath, {
        errorMessage: `Unable to start ${provider.label} connection.`,
      });
      window.location.href = data.authorize_url;
    } catch (connectError) {
      setError(
        connectError instanceof Error
          ? connectError.message
          : `Unable to start ${provider.label} connection.`,
      );
      setConnecting(null);
    }
  }

  async function disconnect(provider: (typeof PROVIDERS)[number], row: IntegrationRow) {
    setError(null);
    try {
      await apiFetch(`/integrations/${row.id}`, {
        method: "DELETE",
        errorMessage: `Unable to disconnect ${provider.label}.`,
      });
      setMessage(`${provider.label} disconnected.`);
      await load();
    } catch (disconnectError) {
      setError(
        disconnectError instanceof Error
          ? disconnectError.message
          : `Unable to disconnect ${provider.label}.`,
      );
    }
  }

  async function saveRecipes(
    provider: (typeof PROVIDERS)[number],
    row: IntegrationRow,
    recipes: StageRecipe[],
  ) {
    setSaving(provider.key);
    setError(null);
    try {
      await apiFetch(`/integrations/${row.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage_recipes: recipes }),
        errorMessage: "Unable to update stage recipes.",
      });
      setMessage("Stage recipes saved.");
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to update stage recipes.");
    } finally {
      setSaving(null);
    }
  }

  async function syncNow(provider: (typeof PROVIDERS)[number]) {
    setSyncing(provider.key);
    setError(null);
    try {
      const data = await apiFetch<{ count: number }>(provider.syncPath, {
        method: "POST",
        errorMessage: `${provider.label} sync failed.`,
      });
      setMessage(
        `Sync finished (${data.count} ${provider.objectLabel} update${data.count === 1 ? "" : "s"}).`,
      );
      await load();
    } catch (syncError) {
      setError(
        syncError instanceof Error ? syncError.message : `${provider.label} sync failed.`,
      );
    } finally {
      setSyncing(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Integrations"
        description="Connect Salesforce or HubSpot so matching deal stages create cookie orders from your CRM Cookie Note and street / city / state / ZIP fields (or send a reminder if auto-order is off). Use stage recipes to send a 4-pack after a demo and a 12-pack on Closed Won."
      />

      {error ? (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
      {message ? (
        <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {message}
        </div>
      ) : null}

      <div className="flex max-w-2xl flex-col gap-6">
        {PROVIDERS.map((provider) => {
          const row = rows.find((r) => r.provider === provider.key) ?? null;
          return (
            <section
              key={provider.key}
              className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm"
            >
              <h2 className="text-lg font-semibold text-espresso">{provider.label}</h2>
              <p className="mt-1 text-sm text-stone-600">
                When a {provider.objectLabel} moves to a stage in your recipes (defaults:{" "}
                <strong>Demo Completed</strong> → 4 cookies, <strong>Closed Won</strong> → 12
                cookies, <strong>Renewal</strong> → 4 cookies), Close&nbsp;&amp;&nbsp;Keep reads
                your CRM <strong>Cookie Note</strong> and street / city / state / ZIP fields and
                auto-creates an order (enabled when you first connect). If auto-order is off, you
                get a reminder email instead.
              </p>

              {loading ? (
                <p className="mt-4 text-sm text-stone-500">Loading…</p>
              ) : row ? (
                <div className="mt-5 space-y-4">
                  {row.token_status === "needs_reconnect" ? (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
                      <p>
                        {provider.label} login expired. Reconnect to resume cookie
                        orders and reminders.
                      </p>
                      <button
                        type="button"
                        onClick={() => void connect(provider)}
                        disabled={connecting === provider.key}
                        className="mt-2 rounded-full bg-wood px-4 py-1.5 text-sm font-medium text-white hover:bg-wood-dark disabled:opacity-50"
                      >
                        {connecting === provider.key
                          ? "Redirecting…"
                          : `Reconnect ${provider.label}`}
                      </button>
                    </div>
                  ) : null}
                  <dl className="grid gap-2 text-sm text-stone-700 sm:grid-cols-2">
                    <div>
                      <dt className="text-stone-500">Status</dt>
                      <dd className="font-medium text-espresso">
                        {row.token_status === "needs_reconnect"
                          ? "Needs reconnect"
                          : row.enabled
                            ? "Connected"
                            : "Disabled"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-stone-500">Last poll</dt>
                      <dd>{formatWhen(row.last_polled_at)}</dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-stone-500">
                        {provider.key === "hubspot" ? "Portal" : "Org"}
                      </dt>
                      <dd className="truncate">
                        {row.external_org_id || row.instance_url || ""}
                      </dd>
                    </div>
                  </dl>

                  <StageRecipes
                    recipes={row.stage_recipes || []}
                    saving={saving === provider.key}
                    onSave={(recipes) => saveRecipes(provider, row, recipes)}
                  />

                  <div className="flex flex-wrap items-start gap-2 pt-1">
                    <CheckSetup provider={provider.key} label={provider.label} />
                    <button
                      type="button"
                      onClick={() => void syncNow(provider)}
                      disabled={syncing === provider.key}
                      className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-espresso hover:bg-stone-50 disabled:opacity-50"
                    >
                      {syncing === provider.key ? "Syncing…" : "Sync now"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void disconnect(provider, row)}
                      className="rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-800 hover:bg-rose-100"
                    >
                      Disconnect
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-5">
                  <button
                    type="button"
                    onClick={() => void connect(provider)}
                    disabled={connecting === provider.key}
                    className="rounded-full bg-wood px-5 py-2.5 text-sm font-medium text-white hover:bg-wood-dark disabled:opacity-50"
                  >
                    {connecting === provider.key
                      ? "Redirecting…"
                      : `Connect ${provider.label}`}
                  </button>
                </div>
              )}
            </section>
          );
        })}

        {retryableEvents.length > 0 ? (
          <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-espresso">Failed auto-orders</h2>
            <p className="mt-1 text-sm text-stone-600">
              Retry a failed or held CRM auto-order. We still will not send another box to the same
              person within 90 days.
            </p>
            <ul className="mt-4 space-y-3">
              {retryableEvents.map((event) => (
                <li
                  key={event.id}
                  className="flex flex-wrap items-center justify-between gap-3 text-sm text-stone-700"
                >
                  <span>
                    {event.provider === "hubspot" ? "HubSpot" : "Salesforce"}{" "}
                    <span className="font-medium text-espresso">{event.external_event_key}</span>
                    <span className="text-stone-500"> · {event.status}</span>
                  </span>
                  <RetryAutoOrder
                    eventId={event.id}
                    onDone={() => {
                      setMessage("Auto-order retried.");
                      void load();
                    }}
                  />
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <EventJournal reloadToken={journalTick} />
      </div>
    </>
  );
}
