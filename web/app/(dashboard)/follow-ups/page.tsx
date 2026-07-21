"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

/**
 * Follow-up reminders are not backed by the API yet. This page is an honest
 * placeholder — no mock prospects or dates.
 */
export default function FollowUpsPage() {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    let active = true;
    async function gateGuests() {
      try {
        const data = await apiFetch<{ role?: string; is_guest?: boolean }>("/auth/me", {
          errorMessage: "Not authenticated.",
        });
        if (data.role === "guest" || data.is_guest) {
          router.replace("/dashboard");
          return;
        }
        if (active) setAllowed(true);
      } catch {
        router.replace("/login?next=/follow-ups");
      }
    }
    void gateGuests();
    return () => {
      active = false;
    };
  }, [router]);

  if (!allowed) {
    return (
      <div className="rounded-2xl border border-stone-200 bg-white/80 p-6 text-sm text-stone-600">
        Checking your session...
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title="Follow-ups"
        description="Prospect reminders will live here once email delivery is connected."
      />

      <div className="rounded-2xl border border-dashed border-stone-300 bg-white/70 px-6 py-12 text-center">
        <p className="font-display text-xl text-espresso">Coming soon</p>
        <p className="mx-auto mt-2 max-w-md text-sm text-stone-600">
          We are not showing placeholder reminders. When this ships, you will be able
          to schedule follow-ups tied to real prospects from your account.
        </p>
      </div>
    </>
  );
}
