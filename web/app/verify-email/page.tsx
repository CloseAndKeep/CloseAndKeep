"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch, fetchErrorMessage } from "@/lib/api";
import { BrandLogo } from "@/components/brand-logo";

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<main className="bg-cream px-4 py-16" />}>
      <VerifyEmailContent />
    </Suspense>
  );
}

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<"pending" | "ok" | "error">(
    token ? "pending" : "error",
  );

  useEffect(() => {
    if (!token) {
      setError("This verification link is missing a token.");
      setStatus("error");
      return;
    }

    let active = true;

    async function verify() {
      try {
        await apiFetch("/auth/verify-email", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
          errorMessage: "Could not verify email.",
        });
        if (!active) return;
        setStatus("ok");
        router.replace("/dashboard");
      } catch (verifyError) {
        if (!active) return;
        setError(fetchErrorMessage(verifyError, "Could not verify email."));
        setStatus("error");
      }
    }

    void verify();
    return () => {
      active = false;
    };
  }, [router, token]);

  return (
    <main className="bg-cream px-4 py-16">
      <div className="mx-auto w-full max-w-md rounded-2xl border border-stone-200 bg-white/90 p-8 shadow-sm">
        <div className="mb-6 flex justify-center">
          <BrandLogo priority />
        </div>
        <h1 className="font-display text-3xl text-espresso">Verify email</h1>

        {status === "pending" ? (
          <p className="mt-2 text-sm text-stone-600">Confirming your email address…</p>
        ) : null}

        {status === "ok" ? (
          <p className="mt-2 text-sm text-stone-600">Email verified. Redirecting…</p>
        ) : null}

        {status === "error" ? (
          <>
            <p className="mt-2 text-sm text-stone-600">
              {error || "This verification link is invalid or has expired."}
            </p>
            <div className="mt-6 flex flex-col gap-3">
              <Link
                href="/check-email"
                className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-transparent bg-wood px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-wood-dark"
              >
                Resend verification email
              </Link>
              <p className="text-sm text-stone-600">
                Or{" "}
                <Link className="font-medium text-wood-dark hover:underline" href="/login">
                  sign in
                </Link>
                .
              </p>
            </div>
          </>
        ) : null}
      </div>
    </main>
  );
}
