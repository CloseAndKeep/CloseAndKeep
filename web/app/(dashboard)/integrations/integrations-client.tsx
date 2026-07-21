"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

type IntegrationRow = {
  id: number;
  provider: string;
  enabled: boolean;
  trigger_stage_name: string;
  external_org_id: string | null;
  instance_url: string | null;
  last_polled_at: string | null;
  created_at: string;
  updated_at: string;
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
  if (!value) return "—";
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
  const [stageDrafts, setStageDrafts] = useState<Record<ProviderKey, string>>({
    salesforce: "Demo Completed",
    hubspot: "Demo Completed",
  });
  const [saving, setSaving] = useState<ProviderKey | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<IntegrationRow[]>("/integrations", {
        errorMessage: "Unable to load integrations.",
      });
      setRows(data);
      setStageDrafts((prev) => {
        const next = { ...prev };
        for (const provider of PROVIDERS) {
          const row = data.find((r) => r.provider === provider.key);
          if (row) next[provider.key] = row.trigger_stage_name;
        }
        return next;
      });
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
        `${label} connected. Cookie reminders will send when a deal hits your trigger stage.`,
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

  async function saveStage(
    event: FormEvent,
    provider: (typeof PROVIDERS)[number],
    row: IntegrationRow,
  ) {
    event.preventDefault();
    const draft = stageDrafts[provider.key].trim();
    if (!draft) return;
    setSaving(provider.key);
    setError(null);
    try {
      await apiFetch(`/integrations/${row.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trigger_stage_name: draft }),
        errorMessage: "Unable to update trigger stage.",
      });
      setMessage("Trigger stage saved.");
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to update trigger stage.");
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
        description="Connect Salesforce or HubSpot so Demo Completed deals trigger an immediate cookie-order reminder."
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
                When a {provider.objectLabel} moves to your trigger stage (default{" "}
                <strong>Demo Completed</strong>), Close&nbsp;&amp;&nbsp;Keep emails you a link to
                order cookies with the prospect prefilled — and reminds you to write a personal gift
                note.
              </p>

              {loading ? (
                <p className="mt-4 text-sm text-stone-500">Loading…</p>
              ) : row ? (
                <div className="mt-5 space-y-4">
                  <dl className="grid gap-2 text-sm text-stone-700 sm:grid-cols-2">
                    <div>
                      <dt className="text-stone-500">Status</dt>
                      <dd className="font-medium text-espresso">
                        {row.enabled ? "Connected" : "Disabled"}
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
                        {row.external_org_id || row.instance_url || "—"}
                      </dd>
                    </div>
                  </dl>

                  <form
                    onSubmit={(e) => void saveStage(e, provider, row)}
                    className="flex flex-col gap-2 sm:flex-row sm:items-end"
                  >
                    <label className="block flex-1 text-sm">
                      <span className="font-medium text-espresso">Trigger stage name</span>
                      <input
                        className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2"
                        value={stageDrafts[provider.key]}
                        onChange={(e) =>
                          setStageDrafts((prev) => ({
                            ...prev,
                            [provider.key]: e.target.value,
                          }))
                        }
                        placeholder="Demo Completed"
                      />
                    </label>
                    <button
                      type="submit"
                      disabled={saving === provider.key || !stageDrafts[provider.key].trim()}
                      className="rounded-full bg-wood px-4 py-2 text-sm font-medium text-white hover:bg-wood-dark disabled:opacity-50"
                    >
                      {saving === provider.key ? "Saving…" : "Save stage"}
                    </button>
                  </form>

                  <div className="flex flex-wrap gap-2 pt-1">
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
      </div>
    </>
  );
}
