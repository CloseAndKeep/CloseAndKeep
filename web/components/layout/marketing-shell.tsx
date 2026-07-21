import Link from "next/link";
import { Facebook, Linkedin } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";

const footerLinks = [
  { href: "/", label: "Home" },
  { href: "/pricing", label: "Pricing" },
  { href: "/support", label: "Support" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
] as const;

const socialLinks = [
  {
    href: "https://www.facebook.com/profile.php?id=61592292207936",
    label: "Facebook",
    icon: Facebook,
  },
  {
    href: "https://www.linkedin.com/company/closeandkeep/about/",
    label: "LinkedIn",
    icon: Linkedin,
  },
] as const;

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
        <nav className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
          {footerLinks.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="hover:text-espresso transition-colors"
            >
              {label}
            </Link>
          ))}
        </nav>
        <nav
          className="mt-4 flex items-center justify-center gap-3"
          aria-label="Social media"
        >
          {socialLinks.map(({ href, label, icon: Icon }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full p-2 text-stone-500 transition-colors hover:bg-stone-200/60 hover:text-espresso"
              aria-label={label}
            >
              <Icon className="h-5 w-5" strokeWidth={1.75} />
            </a>
          ))}
        </nav>
      </footer>
    </div>
  );
}
