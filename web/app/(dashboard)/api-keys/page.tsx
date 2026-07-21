"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/ui/page-header";
import { getApiBaseUrl } from "@/lib/api";

type ApiKeyRow = {
  id: number;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

type CreatedKey = ApiKeyRow & { api_key: string };

function formatWhen(value: string | null) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [freshKey, setFreshKey] = useState<CreatedKey | null>(null);
  const [copied, setCopied] = useState(false);

  async function loadKeys() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/api-keys`, {
        credentials: "include",
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(
          typeof data?.detail === "string" ? data.detail : "Unable to load API keys.",
        );
      }
      setKeys((await response.json()) as ApiKeyRow[]);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load API keys.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadKeys();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    setCopied(false);
    try {
      const response = await fetch(`${getApiBaseUrl()}/api-keys`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(
          typeof data?.detail === "string" ? data.detail : "Unable to create API key.",
        );
      }
      const created = (await response.json()) as CreatedKey;
      setFreshKey(created);
      setName("");
      await loadKeys();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unable to create API key.");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id: number) {
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/api-keys/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Unable to revoke API key.");
      }
      if (freshKey?.id === id) setFreshKey(null);
      await loadKeys();
    } catch (revokeError) {
      setError(revokeError instanceof Error ? revokeError.message : "Unable to revoke API key.");
    }
  }

  async function copyFreshKey() {
    if (!freshKey) return;
    try {
      await navigator.clipboard.writeText(freshKey.api_key);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const active = keys.filter((k) => !k.revoked_at);
  const revoked = keys.filter((k) => k.revoked_at);

  return (
    <>
      <PageHeader
        title="API keys"
        description="Create keys so agents or scripts can open gift orders. Payment still happens on Stripe Checkout — card data never hits CloseAndKeep."
      />

      <p className="mb-8 text-sm text-stone-600">
        Request examples:{" "}
        <Link href="/developers" className="font-medium text-wood-dark hover:underline">
          API docs
        </Link>
        .
      </p>

      {error ? (
        <p className="mb-6 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      {freshKey ? (
        <div className="mb-8 rounded-2xl border border-amber-200 bg-amber-50/80 p-6">
          <h2 className="font-display text-lg text-espresso">Copy your key now</h2>
          <p className="mt-2 text-sm text-stone-600">
            This is the only time the full secret is shown. Store it like a password.
          </p>
          <code className="mt-4 block break-all rounded-xl bg-white px-3 py-3 text-sm text-espresso">
            {freshKey.api_key}
          </code>
          <button
            type="button"
            onClick={() => void copyFreshKey()}
            className="mt-4 inline-flex rounded-full bg-wood px-4 py-2 text-sm font-medium text-white hover:bg-wood-dark"
          >
            {copied ? "Copied" : "Copy key"}
          </button>
        </div>
      ) : null}

      <form
        onSubmit={(e) => void handleCreate(e)}
        className="rounded-2xl border border-stone-200/90 bg-white/90 p-6 shadow-sm"
      >
        <h2 className="font-display text-xl text-espresso">Create an API key</h2>
        <label className="mt-4 block text-sm font-medium text-stone-700">
          Label
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. CRM agent"
            maxLength={120}
            className="mt-1.5 w-full rounded-xl border border-stone-200 bg-cream/50 px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
          />
        </label>
        <button
          type="submit"
          disabled={creating || !name.trim()}
          className="mt-4 inline-flex rounded-full bg-wood px-5 py-2.5 text-sm font-medium text-white hover:bg-wood-dark disabled:opacity-50"
        >
          {creating ? "Creating…" : "Create key"}
        </button>
      </form>

      <section className="mt-10">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
          Active keys ({active.length})
        </h3>
        {loading ? (
          <p className="mt-3 text-sm text-stone-500">Loading…</p>
        ) : active.length === 0 ? (
          <p className="mt-3 text-sm text-stone-500">No active keys yet.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {active.map((key) => (
              <li
                key={key.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-stone-200/90 bg-white/90 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-espresso">{key.name}</p>
                  <p className="mt-0.5 font-mono text-xs text-stone-500">
                    {key.key_prefix}… · created {formatWhen(key.created_at)}
                    {key.last_used_at ? ` · last used ${formatWhen(key.last_used_at)}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleRevoke(key.id)}
                  className="rounded-lg border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 hover:bg-stone-100"
                >
                  Revoke
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {revoked.length > 0 ? (
        <section className="mt-10">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
            Revoked ({revoked.length})
          </h3>
          <ul className="mt-4 space-y-2 text-sm text-stone-500">
            {revoked.map((key) => (
              <li key={key.id}>
                {key.name} · {key.key_prefix}… · revoked {formatWhen(key.revoked_at)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
