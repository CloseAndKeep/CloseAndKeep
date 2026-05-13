"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;

    async function checkAuth() {
      try {
        const response = await fetch(`${getApiBaseUrl()}/auth/me`, {
          credentials: "include",
        });

        if (!response.ok) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
          return;
        }

        if (active) {
          setReady(true);
        }
      } catch {
        router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      }
    }

    void checkAuth();

    return () => {
      active = false;
    };
  }, [pathname, router]);

  if (!ready) {
    return (
      <div className="rounded-2xl border border-stone-200 bg-white/80 p-6 text-sm text-stone-600">
        Checking your session...
      </div>
    );
  }

  return <>{children}</>;
}
