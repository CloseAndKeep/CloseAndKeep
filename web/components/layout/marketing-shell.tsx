import Link from "next/link";
import { BrandLogo } from "@/components/brand-logo";
import { SiteFooter } from "@/components/layout/site-footer";

const headerLinks = [
  { href: "/pricing", label: "Pricing" },
  { href: "/support", label: "Support" },
] as const;

export function MarketingShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-cream flex flex-col">
      <header className="border-b border-stone-200/80 bg-cream/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4 sm:px-6">
          <BrandLogo priority />
          <nav className="flex items-center gap-1 sm:gap-2" aria-label="Marketing">
            {headerLinks.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="rounded-full px-2.5 py-1.5 text-sm font-medium text-stone-600 transition hover:bg-stone-100/80 hover:text-espresso sm:px-3"
              >
                {label}
              </Link>
            ))}
            <Link
              href="/login"
              className="rounded-full px-2.5 py-1.5 text-sm font-medium text-stone-600 transition hover:bg-stone-100/80 hover:text-espresso sm:px-3"
            >
              Log in
            </Link>
            <Link
              href="/signup"
              className="ml-1 inline-flex items-center rounded-full bg-wood px-3.5 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-wood-dark sm:px-4"
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  );
}
