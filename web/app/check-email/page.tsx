"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiFetch, fetchErrorMessage } from "@/lib/api";
import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";

export default function CheckEmailPage() {
  return (
    <Suspense fallback={<main className="bg-cream px-4 py-16" />}>
      <CheckEmailContent />
    </Suspense>
  );
}

function CheckEmailContent() {
  const searchParams = useSearchParams();
  const initialEmail = searchParams.get("email")?.trim() ?? "";
  const [email, setEmail] = useState(initialEmail);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onResend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (!email.trim()) {
      setError("Enter the email you used to sign up.");
      return;
    }
    setLoading(true);
    try {
      const result = await apiFetch<{ message: string }>("/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
        errorMessage: "Could not resend verification email.",
      });
      setMessage(result.message || "If an account needs verification, we sent an email.");
    } catch (resendError) {
      setError(fetchErrorMessage(resendError, "Could not resend verification email."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="bg-cream px-4 py-16">
      <div className="mx-auto w-full max-w-md rounded-2xl border border-stone-200 bg-white/90 p-8 shadow-sm">
        <div className="mb-6 flex justify-center">
          <BrandLogo priority />
        </div>
        <h1 className="font-display text-3xl text-espresso">Check your email</h1>
        <p className="mt-2 text-sm text-stone-600">
          We sent a verification link
          {initialEmail ? (
            <>
              {" "}
              to <span className="font-medium text-stone-800">{initialEmail}</span>
            </>
          ) : null}
          . Confirm your email to access your dashboard.
        </p>

        <form className="mt-6 space-y-4" onSubmit={onResend}>
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className="field-input"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>

          {error ? (
            <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </p>
          ) : null}
          {message ? (
            <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              {message}
            </p>
          ) : null}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Sending..." : "Resend verification email"}
          </Button>
        </form>

        <p className="mt-4 text-sm text-stone-600">
          Already verified?{" "}
          <Link className="font-medium text-wood-dark hover:underline" href="/login">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
