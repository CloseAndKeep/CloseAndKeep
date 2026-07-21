"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { PackageCheck, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { BrandLogo } from "@/components/brand-logo";
import { SiteFooter } from "@/components/layout/site-footer";

const nav = [
  { href: "/admin", label: "Order queue", icon: PackageCheck },
  { href: "/dashboard", label: "Back to app", icon: ArrowLeft },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

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
        <div className="flex h-16 items-center gap-2 border-b border-stone-200/80 px-4">
          <BrandLogo href="/admin" variant="mark" priority />
          <Link href="/admin" className="font-display text-lg tracking-tight">
            Admin
          </Link>
        </div>
        <nav className="flex-1 space-y-0.5 p-3">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = href === "/admin" ? pathname.startsWith("/admin") : pathname === href;
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
          <p className="font-medium text-stone-600">Admin mode</p>
          <p className="mt-1">Fulfill paid orders and add tracking.</p>
          <button
            type="button"
            className="mt-3 inline-flex rounded-lg border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 hover:bg-stone-100"
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </aside>

      <div className="md:hidden sticky top-0 z-40 border-b border-stone-200/90 bg-white/95 backdrop-blur">
        <div className="flex h-12 items-center px-3">
          <Link href="/admin" className="font-display text-lg shrink-0 mr-3">
            Admin
          </Link>
          <div className="flex gap-1 overflow-x-auto pb-1 text-xs font-medium whitespace-nowrap">
            {nav.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="rounded-full px-2.5 py-1 text-stone-600"
              >
                {label}
              </Link>
            ))}
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
