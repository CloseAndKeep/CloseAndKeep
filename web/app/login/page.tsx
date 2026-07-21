"use client";

import { Suspense } from "react";
import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch, fetchErrorMessage } from "@/lib/api";
import { BrandLogo } from "@/components/brand-logo";
import { safeInternalPath } from "@/lib/utils";

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="bg-cream px-4 py-16" />}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);
  const nextPath = safeInternalPath(searchParams.get("next"));

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiFetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        errorMessage: "Login failed. Check your credentials.",
      });
      router.replace(nextPath);
    } catch (submitError) {
      setError(fetchErrorMessage(submitError, "Login failed."));
    } finally {
      setLoading(false);
    }
  }

  async function continueAsGuest() {
    setError(null);
    setGuestLoading(true);
    try {
      await apiFetch("/auth/guest", {
        method: "POST",
        errorMessage: "Could not start a guest session.",
      });
      // Guests cannot use follow-ups; send them to the dashboard instead.
      const guestNext = nextPath === "/follow-ups" || nextPath.startsWith("/follow-ups/")
        ? "/dashboard"
        : nextPath;
      router.replace(guestNext);
    } catch (guestError) {
      setError(fetchErrorMessage(guestError, "Could not start a guest session."));
    } finally {
      setGuestLoading(false);
    }
  }

  const busy = loading || guestLoading;

  return (
    <main className="bg-cream px-4 py-16">
      <div className="mx-auto w-full max-w-md rounded-2xl border border-stone-200 bg-white/90 p-8 shadow-sm">
        <div className="mb-6 flex justify-center">
          <BrandLogo priority />
        </div>
        <h1 className="font-display text-3xl text-espresso">Login</h1>
        <p className="mt-2 text-sm text-stone-600">
          Sign in to access your CloseAndKeep dashboard.
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>

          {error ? (
            <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            className="w-full rounded-xl bg-wood px-3 py-2 text-sm font-semibold text-white transition hover:bg-wood-dark disabled:opacity-70"
            disabled={busy}
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div className="mt-5">
          <div className="relative flex items-center gap-3">
            <div className="h-px flex-1 bg-stone-200" />
            <span className="text-xs uppercase tracking-wide text-stone-400">or</span>
            <div className="h-px flex-1 bg-stone-200" />
          </div>
          <button
            type="button"
            className="mt-4 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 transition hover:bg-stone-50 disabled:opacity-70"
            disabled={busy}
            onClick={() => void continueAsGuest()}
          >
            {guestLoading ? "Starting guest session..." : "Continue as guest"}
          </button>
          <p className="mt-2 text-xs text-stone-500">
            Guest mode does not restore your session later, hides follow-ups, and keeps orders only for shipping.
          </p>
        </div>

        <p className="mt-4 text-sm text-stone-600">
          Need an account?{" "}
          <Link className="font-medium text-wood-dark hover:underline" href="/signup">
            Create one
          </Link>
          {" · "}
          Need the marketing site?{" "}
          <Link className="font-medium text-wood-dark hover:underline" href="/">
            Go home
          </Link>
        </p>
      </div>
    </main>
  );
}
