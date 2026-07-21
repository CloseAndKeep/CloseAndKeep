"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Package,
  CalendarClock,
  CreditCard,
  ShieldCheck,
  KeyRound,
  Plug,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { BrandLogo } from "@/components/brand-logo";
import { SiteFooter } from "@/components/layout/site-footer";

const baseNav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/prospects", label: "Prospects", icon: Users },
  { href: "/orders", label: "Orders", icon: Package },
  { href: "/follow-ups", label: "Follow-ups", icon: CalendarClock },
  { href: "/integrations", label: "Integrations", icon: Plug },
  { href: "/billing", label: "Payments", icon: CreditCard },
  { href: "/api-keys", label: "API keys", icon: KeyRound },
];

const adminNavItem = { href: "/admin", label: "Admin", icon: ShieldCheck };

type MeResponse = {
  role?: string;
  is_guest?: boolean;
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);
  const [isGuest, setIsGuest] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadRole() {
      try {
        const data = await apiFetch<MeResponse>("/auth/me");
        if (!active) return;
        setIsAdmin(data.role === "admin");
        setIsGuest(data.role === "guest" || data.is_guest === true);
      } catch {
        // Non-admins and unauthenticated users simply don't see the admin link.
      }
    }
    void loadRole();
    return () => {
      active = false;
    };
  }, []);

  const nav = [
    ...baseNav.filter(
      (item) =>
        !(isGuest && item.href === "/follow-ups") &&
        !(isGuest && item.href === "/api-keys") &&
        !(isGuest && item.href === "/integrations"),
    ),
    ...(isAdmin ? [adminNavItem] : []),
  ];

  async function handleLogout() {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } finally {
      router.replace("/login");
    }
  }

  return (
    <div className="min-h-screen bg-cream text-espresso md:flex">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-56 flex-col border-r border-stone-200/90 bg-white/70 backdrop-blur-md md:flex">
        <div className="flex h-16 items-center border-b border-stone-200/80 px-4">
          <BrandLogo priority />
        </div>
        <nav className="flex-1 space-y-0.5 p-3">
          {nav.map(({ href, label, icon: Icon }) => {
            const active =
              pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-wood/15 text-wood-dark"
                    : "text-stone-600 hover:bg-stone-100/80 hover:text-espresso"
                )}
              >
                <Icon className="h-5 w-5 shrink-0 opacity-90" strokeWidth={1.75} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-stone-200/80 p-4 text-xs text-stone-500 leading-relaxed">
          <p className="font-medium text-stone-600">
            {isGuest ? "Guest session" : "Session mode"}
          </p>
          <p className="mt-1">
            {isGuest
              ? "Orders you place are kept for shipping. This session won't come back, and follow-ups are unavailable."
              : "Dashboard routes require an active API session."}
          </p>
          <button
            type="button"
            className="mt-3 inline-flex rounded-lg border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 hover:bg-stone-100"
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Mobile nav */}
      <div className="md:hidden sticky top-0 z-40 border-b border-stone-200/90 bg-white/95 backdrop-blur">
        <div className="flex h-12 items-center px-3">
          <BrandLogo variant="mark" className="mr-3 shrink-0" />
          <div className="flex gap-1 overflow-x-auto pb-1 text-xs font-medium whitespace-nowrap">
            {nav.map(({ href, label }) => {
              const active =
                pathname === href ||
                (href !== "/dashboard" && pathname.startsWith(href));
              return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "rounded-full px-2.5 py-1",
                  active ? "bg-wood/20 text-wood-dark" : "text-stone-600"
                )}
              >
                {label}
              </Link>
            );
            })}
          </div>
        </div>
      </div>

      <div className="flex min-h-screen flex-1 flex-col md:pl-56">
        <div className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">{children}</div>
        <SiteFooter />
      </div>
    </div>
  );
}
