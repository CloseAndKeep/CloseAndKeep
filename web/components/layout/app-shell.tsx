"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Package,
  CalendarClock,
  CreditCard,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getApiBaseUrl } from "@/lib/api";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/prospects", label: "Prospects", icon: Users },
  { href: "/orders", label: "Orders", icon: Package },
  { href: "/follow-ups", label: "Follow-ups", icon: CalendarClock },
  { href: "/billing", label: "Billing", icon: CreditCard },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    try {
      await fetch(`${getApiBaseUrl()}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      router.replace("/login");
    }
  }

  return (
    <div className="min-h-screen bg-cream text-espresso">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-56 flex-col border-r border-stone-200/90 bg-white/70 backdrop-blur-md md:flex">
        <div className="flex h-16 items-center gap-2 border-b border-stone-200/80 px-5">
          <Sparkles className="h-6 w-6 text-wood" aria-hidden />
          <Link href="/" className="font-display text-lg tracking-tight">
            Close<span className="text-wood-dark">&</span>Keep
          </Link>
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
          <p className="font-medium text-stone-600">Session mode</p>
          <p className="mt-1">Dashboard routes require an active API session.</p>
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
          <Link href="/" className="font-display text-lg shrink-0 mr-3">
            Close<span className="text-wood-dark">&</span>Keep
          </Link>
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

      <div className="md:pl-56">
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">{children}</div>
      </div>
    </div>
  );
}
