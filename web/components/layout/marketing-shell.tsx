import Link from "next/link";
import { BrandLogo } from "@/components/brand-logo";

export function MarketingShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-cream flex flex-col">
      <header className="border-b border-stone-200/80 bg-cream/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6">
          <BrandLogo priority />
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-stone-200/80 py-8 text-center text-sm text-stone-500">
        <p>CloseAndKeep — gifting follow-up for customer teams.</p>
        <nav className="mt-3 flex items-center justify-center gap-4">
          <Link href="/pricing" className="hover:text-espresso transition-colors">
            Pricing
          </Link>
          <Link href="/privacy" className="hover:text-espresso transition-colors">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-espresso transition-colors">
            Terms
          </Link>
        </nav>
      </footer>
    </div>
  );
}
