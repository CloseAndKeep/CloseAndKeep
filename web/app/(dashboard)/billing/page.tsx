"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { API_BASE_URL } from "@/lib/api";

export default function BillingPage() {
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<"checkout" | "portal" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [billing, setBilling] = useState({
    email: "",
    subscription_status: "inactive",
    subscription_plan: "free",
    has_payment_method: false,
  });

  useEffect(() => {
    async function loadBilling() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${API_BASE_URL}/billing/me`, {
          credentials: "include",
        });
        if (!response.ok) {
          const data = (await response.json().catch(() => null)) as { detail?: string } | null;
          throw new Error(data?.detail ?? "Unable to load billing info.");
        }
        const data = (await response.json()) as typeof billing;
        setBilling(data);
      } catch (loadError) {
        const message =
          loadError instanceof Error ? loadError.message : "Unable to load billing info.";
        setError(message);
      } finally {
        setLoading(false);
      }
    }
    void loadBilling();
  }, []);

  async function startCheckout() {
    setActionLoading("checkout");
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/billing/checkout`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(data?.detail ?? "Unable to start checkout.");
      }
      const data = (await response.json()) as { checkout_url: string };
      window.location.href = data.checkout_url;
    } catch (actionError) {
      const message =
        actionError instanceof Error ? actionError.message : "Unable to start checkout.";
      setError(message);
      setActionLoading(null);
    }
  }

  async function openPortal() {
    setActionLoading("portal");
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/billing/portal`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(data?.detail ?? "Unable to open billing portal.");
      }
      const data = (await response.json()) as { portal_url: string };
      window.location.href = data.portal_url;
    } catch (actionError) {
      const message =
        actionError instanceof Error ? actionError.message : "Unable to open billing portal.";
      setError(message);
      setActionLoading(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Billing"
        description="Manage your subscription and payment method with Stripe."
      />

      <div className="rounded-2xl border border-stone-200/90 bg-white/90 p-8 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <h2 className="font-display text-2xl text-espresso">Current plan</h2>
            <p className="mt-2 text-stone-600">
              Logged in as{" "}
              <span className="font-medium text-espresso">{loading ? "Loading..." : billing.email}</span>
            </p>
          </div>
          <span className="rounded-full bg-wood/15 px-4 py-2 text-sm font-medium text-wood-dark">
            {loading ? "..." : billing.subscription_plan}
          </span>
        </div>
        <dl className="mt-8 grid gap-4 border-t border-stone-100 pt-8 sm:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              Subscription status
            </dt>
            <dd className="mt-1 text-lg text-espresso">
              {loading ? "Loading..." : billing.subscription_status}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              Payment method
            </dt>
            <dd className="mt-1 text-stone-600">
              {loading
                ? "Loading..."
                : billing.has_payment_method
                  ? "Connected via Stripe"
                  : "No payment method on file"}
            </dd>
          </div>
        </dl>
        {error ? (
          <p className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </p>
        ) : null}
        <div className="mt-8 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={startCheckout}
            disabled={loading || actionLoading !== null}
            className="rounded-full bg-wood px-6 py-3 text-sm font-medium text-white hover:bg-wood-dark disabled:opacity-60"
          >
            {actionLoading === "checkout" ? "Redirecting..." : "Start subscription"}
          </button>
          <button
            type="button"
            onClick={openPortal}
            disabled={loading || actionLoading !== null || !billing.has_payment_method}
            className="rounded-full border border-stone-300 bg-white px-6 py-3 text-sm font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-60"
          >
            {actionLoading === "portal" ? "Opening..." : "Manage subscription"}
          </button>
        </div>
      </div>
    </>
  );
}
