"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import { safeInternalPath } from "@/lib/utils";

type MeResponse = {
  email?: string;
  role?: string;
  is_guest?: boolean;
  email_verified?: boolean;
};

type ConsentResponse = {
  redirect_url: string;
};

function hostLabel(clientId: string | null, clientName: string | null) {
  const hay = `${clientName || ""} ${clientId || ""}`.toLowerCase();
  if (hay.includes("claude") || hay.includes("anthropic")) return "Claude";
  if (hay.includes("openai") || hay.includes("chatgpt")) return "ChatGPT";
  if (hay.includes("cursor")) return "Cursor";
  if (clientName) return clientName;
  if (clientId?.startsWith("https://")) return clientId;
  return "your AI";
}

function AuthorizeInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const oauth = useMemo(() => {
    return {
      client_id: searchParams.get("client_id"),
      redirect_uri: searchParams.get("redirect_uri"),
      scope: searchParams.get("scope"),
      state: searchParams.get("state"),
      code_challenge: searchParams.get("code_challenge"),
      code_challenge_method: searchParams.get("code_challenge_method") || "S256",
      resource: searchParams.get("resource"),
      client_name: searchParams.get("client_name"),
      response_type: searchParams.get("response_type"),
    };
  }, [searchParams]);

  const nextPath = useMemo(() => {
    const qs = searchParams.toString();
    return safeInternalPath(`/oauth/mcp/authorize${qs ? `?${qs}` : ""}`);
  }, [searchParams]);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<MeResponse>("/auth/me");
        if (!active) return;
        setMe(data);
      } catch (err) {
        if (!active) return;
        if (err instanceof ApiError && err.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
          return;
        }
        setError(err instanceof Error ? err.message : "Unable to load your account.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [nextPath, router]);

  const label = hostLabel(oauth.client_id, oauth.client_name);
  const isGuest = me?.role === "guest" || me?.is_guest === true;
  const missing =
    !oauth.client_id ||
    !oauth.redirect_uri ||
    !oauth.code_challenge ||
    oauth.response_type !== "code";

  async function allow() {
    if (!oauth.client_id || !oauth.redirect_uri || !oauth.code_challenge) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await apiFetch<ConsentResponse>("/oauth/mcp/consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: oauth.client_id,
          redirect_uri: oauth.redirect_uri,
          scope: oauth.scope,
          state: oauth.state,
          code_challenge: oauth.code_challenge,
          code_challenge_method: oauth.code_challenge_method,
          resource: oauth.resource,
          client_name: oauth.client_name,
        }),
        errorMessage: "Unable to complete Connect.",
      });
      window.location.href = result.redirect_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to complete Connect.");
      setSubmitting(false);
    }
  }

  function deny() {
    if (!oauth.redirect_uri) {
      router.push("/developers/ai");
      return;
    }
    const url = new URL(oauth.redirect_uri);
    url.searchParams.set("error", "access_denied");
    if (oauth.state) url.searchParams.set("state", oauth.state);
    window.location.href = url.toString();
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-lg flex-col justify-center px-4 py-16 sm:px-6">
      <p className="text-sm text-stone-500">
        <Link href="/" className="font-medium text-wood-dark hover:underline">
          CloseAndKeep
        </Link>
        <span className="mx-2">/</span>
        Connect AI
      </p>
      <h1 className="mt-3 font-display text-3xl tracking-tight text-espresso">
        Connect {label}
      </h1>
      <p className="mt-3 text-stone-600">
        Allow {label} to place CloseAndKeep cookie gift orders for your account. You still pay on
        Stripe — the AI never sees your card.
      </p>

      {loading ? (
        <p className="mt-8 text-sm text-stone-500">Checking your session…</p>
      ) : missing ? (
        <p className="mt-8 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          This Connect link is missing required OAuth parameters. Open Connect from Claude,
          ChatGPT, or Cursor again.
        </p>
      ) : isGuest ? (
        <div className="mt-8 space-y-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-950">
          <p>Guest accounts cannot connect an AI. Create a full account and verify your email.</p>
          <Link href="/signup" className="font-medium text-wood-dark underline">
            Sign up
          </Link>
        </div>
      ) : (
        <>
          <ul className="mt-8 space-y-2 text-sm text-stone-700">
            <li>Place cookie gift orders (after you confirm a draft)</li>
            <li>See your prospects and gift status</li>
            <li>Signed in as {me?.email}</li>
          </ul>
          {error ? (
            <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              {error}
            </p>
          ) : null}
          <div className="mt-8 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void allow()}
              disabled={submitting}
              className="inline-flex items-center rounded-full bg-wood px-5 py-2.5 text-sm font-medium text-white transition hover:bg-wood-dark disabled:opacity-60"
            >
              {submitting ? "Connecting…" : "Allow"}
            </button>
            <button
              type="button"
              onClick={deny}
              disabled={submitting}
              className="inline-flex items-center rounded-full border border-stone-300 bg-white px-5 py-2.5 text-sm font-medium text-espresso transition hover:border-wood"
            >
              Deny
            </button>
          </div>
          <p className="mt-4 text-xs text-stone-500">
            You can disconnect anytime from{" "}
            <Link href="/ai-connections" className="underline">
              AI connections
            </Link>
            .
          </p>
        </>
      )}
    </div>
  );
}

export default function McpAuthorizePage() {
  return (
    <Suspense fallback={<div className="p-16 text-center text-stone-500">Loading…</div>}>
      <AuthorizeInner />
    </Suspense>
  );
}
