"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { followUps, prospects } from "@/lib/mock-data";
import { getApiBaseUrl } from "@/lib/api";

export default function FollowUpsPage() {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    let active = true;
    async function gateGuests() {
      try {
        const response = await fetch(`${getApiBaseUrl()}/auth/me`, {
          credentials: "include",
        });
        if (!response.ok) {
          router.replace("/login?next=/follow-ups");
          return;
        }
        const data = (await response.json()) as { role?: string; is_guest?: boolean };
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
        description="Reminders tied to prospects — email delivery will connect to your provider later."
      />

      <ul className="space-y-4">
        {followUps.map((f) => {
          const prospect = prospects.find((x) => x.id === f.prospectId);
          return (
            <li
              key={f.id}
              className="rounded-2xl border border-stone-200/90 bg-white/90 p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-display text-lg text-espresso">{prospect?.name}</p>
                  <p className="text-sm text-stone-500">{prospect?.company}</p>
                </div>
                <time className="rounded-full bg-cream px-3 py-1 text-sm font-medium text-wood-dark">
                  {f.dueDate}
                </time>
              </div>
              <p className="mt-3 text-stone-700">{f.note}</p>
              <Link
                href={`/prospects/${f.prospectId}`}
                className="mt-3 inline-block text-sm font-medium text-wood-dark hover:underline"
              >
                Open prospect →
              </Link>
            </li>
          );
        })}
      </ul>
    </>
  );
}
