"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
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
  UserCircle,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { BrandLogo } from "@/components/brand-logo";

const primaryNav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/prospects", label: "Prospects", icon: Users },
  { href: "/orders", label: "Orders", icon: Package },
] as const;

const secondaryNav = [
  { href: "/follow-ups", label: "Follow-ups", badge: "Soon", icon: CalendarClock },
  { href: "/integrations", label: "Integrations", icon: Plug },
  { href: "/billing", label: "Payments", icon: CreditCard },
  { href: "/api-keys", label: "API keys", icon: KeyRound },
  { href: "/profile", label: "Profile", icon: UserCircle },
] as const;

const adminNavItem = { href: "/admin", label: "Admin", icon: ShieldCheck };

type MeResponse = {
  role?: string;
  is_guest?: boolean;
};

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  badge?: string;
};

function isActivePath(pathname: string, href: string) {
  return pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);
  const [isGuest, setIsGuest] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    function onPointerDown(event: PointerEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  const moreNav: NavItem[] = [
    ...secondaryNav.filter(
      (item) =>
        !(isGuest && item.href === "/follow-ups") &&
        !(isGuest && item.href === "/api-keys") &&
        !(isGuest && item.href === "/integrations"),
    ),
    ...(isAdmin ? [adminNavItem] : []),
  ];

  const sidebarNav: NavItem[] = [...primaryNav, ...moreNav];

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
          <BrandLogo href="/dashboard" priority />
        </div>
        <nav className="flex-1 space-y-0.5 p-3">
          {sidebarNav.map(({ href, label, icon: Icon, badge }) => {
            const active = isActivePath(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-wood/15 text-wood-dark"
                    : "text-stone-600 hover:bg-stone-100/80 hover:text-espresso",
                )}
              >
                <Icon className="h-5 w-5 shrink-0 opacity-90" strokeWidth={1.75} />
                <span className="flex-1">{label}</span>
                {badge ? (
                  <span className="rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">
                    {badge}
                  </span>
                ) : null}
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
          {isGuest ? (
            <Link
              href="/signup"
              className="mt-3 inline-flex text-xs font-medium text-wood-dark hover:underline"
            >
              Create a full account →
            </Link>
          ) : null}
          <button
            type="button"
            className="mt-3 inline-flex rounded-lg border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 hover:bg-stone-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wood/40"
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Mobile nav */}
      <div className="md:hidden sticky top-0 z-40 border-b border-stone-200/90 bg-white/95 backdrop-blur">
        <div className="flex h-12 items-center gap-2 px-3">
          <BrandLogo variant="mark" href="/dashboard" className="shrink-0" />
          <nav className="flex flex-1 gap-1 overflow-x-auto text-xs font-medium whitespace-nowrap" aria-label="Primary">
            {primaryNav.map(({ href, label }) => {
              const active = isActivePath(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "rounded-full px-2.5 py-1",
                    active ? "bg-wood/20 text-wood-dark" : "text-stone-600",
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
          <div className="relative shrink-0" ref={menuRef}>
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-stone-600 hover:bg-stone-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wood/40"
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
            {menuOpen ? (
              <div
                role="menu"
                className="absolute right-0 mt-2 w-52 rounded-xl border border-stone-200 bg-white py-1 shadow-lg"
              >
                {moreNav.map(({ href, label, badge }) => (
                  <Link
                    key={href}
                    href={href}
                    role="menuitem"
                    className={cn(
                      "flex items-center justify-between px-3 py-2.5 text-sm",
                      isActivePath(pathname, href)
                        ? "bg-wood/10 font-medium text-wood-dark"
                        : "text-stone-700 hover:bg-stone-50",
                    )}
                  >
                    <span>{label}</span>
                    {badge ? (
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-stone-400">
                        {badge}
                      </span>
                    ) : null}
                  </Link>
                ))}
                <div className="my-1 border-t border-stone-100" />
                {isGuest ? (
                  <Link
                    href="/signup"
                    role="menuitem"
                    className="block px-3 py-2.5 text-sm font-medium text-wood-dark hover:bg-stone-50"
                  >
                    Create account
                  </Link>
                ) : null}
                <button
                  type="button"
                  role="menuitem"
                  className="w-full px-3 py-2.5 text-left text-sm text-stone-700 hover:bg-stone-50"
                  onClick={handleLogout}
                >
                  Logout
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="flex min-h-screen flex-1 flex-col md:pl-56">
        <div className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">{children}</div>
      </div>
    </div>
  );
}
