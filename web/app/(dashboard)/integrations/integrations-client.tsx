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
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [stageDraft, setStageDraft] = useState("Demo Completed");
  const [saving, setSaving] = useState(false);

  const salesforce = rows.find((row) => row.provider === "salesforce") ?? null;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<IntegrationRow[]>("/integrations", {
        errorMessage: "Unable to load integrations.",
      });
      setRows(data);
      const sf = data.find((row) => row.provider === "salesforce");
      if (sf) setStageDraft(sf.trigger_stage_name);
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
    if (connected === "salesforce") {
      setMessage(
        "Salesforce connected. Cookie reminders will send when a deal hits your trigger stage.",
      );
      void load();
    } else if (oauthError) {
      setError(`Salesforce connection failed: ${oauthError}`);
    }
  }, [searchParams, load]);

  async function connectSalesforce() {
    setConnecting(true);
    setError(null);
    setMessage(null);
    try {
      const data = await apiFetch<{ authorize_url: string }>("/integrations/salesforce/connect", {
        errorMessage: "Unable to start Salesforce connection.",
      });
      window.location.href = data.authorize_url;
    } catch (connectError) {
      setError(
        connectError instanceof Error
          ? connectError.message
          : "Unable to start Salesforce connection.",
      );
      setConnecting(false);
    }
  }

  async function disconnect() {
    if (!salesforce) return;
    setError(null);
    try {
      await apiFetch(`/integrations/${salesforce.id}`, {
        method: "DELETE",
        errorMessage: "Unable to disconnect Salesforce.",
      });
      setMessage("Salesforce disconnected.");
      await load();
    } catch (disconnectError) {
      setError(
        disconnectError instanceof Error
          ? disconnectError.message
          : "Unable to disconnect Salesforce.",
      );
    }
  }

  async function saveStage(event: FormEvent) {
    event.preventDefault();
    if (!salesforce) return;
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/integrations/${salesforce.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trigger_stage_name: stageDraft.trim() }),
        errorMessage: "Unable to update trigger stage.",
      });
      setMessage("Trigger stage saved.");
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to update trigger stage.");
    } finally {
      setSaving(false);
    }
  }

  async function syncNow() {
    setSyncing(true);
    setError(null);
    try {
      const data = await apiFetch<{ count: number }>("/integrations/salesforce/sync", {
        method: "POST",
        errorMessage: "Salesforce sync failed.",
      });
      setMessage(
        `Sync finished (${data.count} opportunity update${data.count === 1 ? "" : "s"}).`,
      );
      await load();
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : "Salesforce sync failed.");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Integrations"
        description="Connect Salesforce so Demo Completed deals trigger an immediate cookie-order reminder."
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

      <section className="max-w-2xl rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-espresso">Salesforce</h2>
        <p className="mt-1 text-sm text-stone-600">
          When an opportunity moves to your trigger stage (default <strong>Demo Completed</strong>),
          Close&nbsp;&amp;&nbsp;Keep emails you a link to order cookies with the prospect prefilled —
          and reminds you to write a personal gift note.
        </p>

        {loading ? (
          <p className="mt-4 text-sm text-stone-500">Loading…</p>
        ) : salesforce ? (
          <div className="mt-5 space-y-4">
            <dl className="grid gap-2 text-sm text-stone-700 sm:grid-cols-2">
              <div>
                <dt className="text-stone-500">Status</dt>
                <dd className="font-medium text-espresso">
                  {salesforce.enabled ? "Connected" : "Disabled"}
                </dd>
              </div>
              <div>
                <dt className="text-stone-500">Last poll</dt>
                <dd>{formatWhen(salesforce.last_polled_at)}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-stone-500">Org</dt>
                <dd className="truncate">
                  {salesforce.external_org_id || salesforce.instance_url || "—"}
                </dd>
              </div>
            </dl>

            <form onSubmit={saveStage} className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <label className="block flex-1 text-sm">
                <span className="font-medium text-espresso">Trigger stage name</span>
                <input
                  className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2"
                  value={stageDraft}
                  onChange={(e) => setStageDraft(e.target.value)}
                  placeholder="Demo Completed"
                />
              </label>
              <button
                type="submit"
                disabled={saving || !stageDraft.trim()}
                className="rounded-full bg-wood px-4 py-2 text-sm font-medium text-white hover:bg-wood-dark disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save stage"}
              </button>
            </form>

            <div className="flex flex-wrap gap-2 pt-1">
              <button
                type="button"
                onClick={() => void syncNow()}
                disabled={syncing}
                className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-espresso hover:bg-stone-50 disabled:opacity-50"
              >
                {syncing ? "Syncing…" : "Sync now"}
              </button>
              <button
                type="button"
                onClick={() => void disconnect()}
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
              onClick={() => void connectSalesforce()}
              disabled={connecting}
              className="rounded-full bg-wood px-5 py-2.5 text-sm font-medium text-white hover:bg-wood-dark disabled:opacity-50"
            >
              {connecting ? "Redirecting…" : "Connect Salesforce"}
            </button>
          </div>
        )}
      </section>
    </>
  );
}
