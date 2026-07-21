import Link from "next/link";
import { Facebook, Linkedin } from "lucide-react";

const footerLinks = [
  { href: "/", label: "Home" },
  { href: "/pricing", label: "Pricing" },
  { href: "/developers", label: "API" },
  { href: "/support", label: "Support" },
  { href: "/contact", label: "Contact" },
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

export function SiteFooter() {
  return (
    <footer className="border-t border-stone-200/80 bg-cream py-8 text-center text-sm text-stone-500">
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
        className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2"
        aria-label="Social media"
      >
        {socialLinks.map(({ href, label, icon: Icon }) => (
          <a
            key={label}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-stone-500 transition-colors hover:text-espresso"
          >
            <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden />
            <span>{label}</span>
          </a>
        ))}
      </nav>
    </footer>
  );
}
