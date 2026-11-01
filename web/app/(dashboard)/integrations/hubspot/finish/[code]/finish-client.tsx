"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { ApiError, apiFetch } from "@/lib/api";

export function FinishHubSpotInstall({ code }: { code: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const installCode = code.trim();
    if (!installCode) {
      setError("This HubSpot install link is missing a code. Install CloseAndKeep from HubSpot again.");
      return;
    }

    async function claim() {
      try {
        await apiFetch("/integrations/hubspot/claim", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code: installCode }),
          errorMessage: "Unable to link this HubSpot portal.",
        });
        if (active) {
          router.replace("/integrations?connected=hubspot");
        }
      } catch (claimError) {
        if (!active) return;
        if (claimError instanceof ApiError && claimError.status === 403) {
          setError(
            "Create a CloseAndKeep account, then open this page again to link the HubSpot portal.",
          );
          return;
        }
        setError(
          claimError instanceof Error
            ? claimError.message
            : "Unable to link this HubSpot portal.",
        );
      }
    }

    void claim();
    return () => {
      active = false;
    };
  }, [code, router]);

  const loginNext = `/login?next=${encodeURIComponent(`/integrations/hubspot/finish/${code}`)}`;

  return (
    <>
      <PageHeader
        title="Link HubSpot"
        description="Attaching this HubSpot portal to your CloseAndKeep account."
      />
      {error ? (
        <div className="max-w-xl rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <p>{error}</p>
          <p className="mt-3 flex flex-wrap gap-3">
            <Link className="font-medium text-wood-dark hover:underline" href={loginNext}>
              Sign in
            </Link>
            <Link className="font-medium text-wood-dark hover:underline" href="/signup">
              Create an account
            </Link>
            <Link className="font-medium text-wood-dark hover:underline" href="/integrations">
              Back to Integrations
            </Link>
          </p>
        </div>
      ) : (
        <p className="text-sm text-stone-600">Linking your HubSpot portal…</p>
      )}
    </>
  );
}
