"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

type ConnectionRow = {
  id: number;
  client_id: string;
  client_label: string;
  scopes: string;
  created_at: string;
  last_used_at: string | null;
  access_expires_at: string;
};

function formatWhen(value: string | null) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function AiConnectionsPage() {
  const [rows, setRows] = useState<ConnectionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setRows(
        await apiFetch<ConnectionRow[]>("/mcp/connections", {
          errorMessage: "Unable to load AI connections.",
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load AI connections.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function disconnect(id: number) {
    if (!window.confirm("Disconnect this AI? It will need to Connect again to place orders.")) {
      return;
    }
    try {
      await apiFetch(`/mcp/connections/${id}`, {
        method: "DELETE",
        errorMessage: "Unable to disconnect.",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to disconnect.");
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="AI connections"
        description="Apps that can place CloseAndKeep gift orders for your account via MCP Connect."
      />

      <p className="text-sm text-stone-600">
        Set up Claude, ChatGPT, or Cursor on{" "}
        <Link href="/developers/ai" className="font-medium text-wood-dark underline">
          Use with AI
        </Link>
        . Prefer Connect over API keys.
      </p>

      {error ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-stone-500">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-stone-600">No AI connections yet.</p>
      ) : (
        <ul className="divide-y divide-stone-200 border-t border-stone-200">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
              <div>
                <p className="font-medium text-espresso">{row.client_label}</p>
                <p className="mt-1 text-xs text-stone-500">
                  Connected {formatWhen(row.created_at)}
                  {row.last_used_at ? ` · Last used ${formatWhen(row.last_used_at)}` : ""}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void disconnect(row.id)}
                className="rounded-full border border-stone-300 px-4 py-1.5 text-sm font-medium text-espresso hover:border-wood"
              >
                Disconnect
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
