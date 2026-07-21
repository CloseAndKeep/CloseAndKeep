"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<"checking" | "ok" | "denied">("checking");

  useEffect(() => {
    let active = true;

    async function checkAdmin() {
      try {
        const data = await apiFetch<{ role?: string }>("/auth/me", {
          errorMessage: "Not authenticated.",
        });
        if (!active) return;

        if (data.role === "admin") {
          setState("ok");
        } else {
          setState("denied");
        }
      } catch {
        router.replace("/login?next=/admin");
      }
    }

    void checkAdmin();

    return () => {
      active = false;
    };
  }, [router]);

  if (state === "checking") {
    return (
      <div className="rounded-2xl border border-stone-200 bg-white/80 p-6 text-sm text-stone-600">
        Checking admin access...
      </div>
    );
  }

  if (state === "denied") {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
        You need an admin account to view this area.
      </div>
    );
  }

  return <>{children}</>;
}
