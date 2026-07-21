import Link from "next/link";

const footerLinks = [
  { href: "/", label: "Home" },
  { href: "/pricing", label: "Pricing" },
  { href: "/developers", label: "API" },
  { href: "/support", label: "Support" },
  { href: "/contact", label: "Contact" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
] as const;

function FacebookIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
    >
      <path d="M14 13.5h2.5l1-4H14v-2c0-1.03 0-2 2-2h1.5V2.14C17.174 2.097 15.943 2 14.643 2 11.928 2 10 3.657 10 6.7v2.8H7v4h3V22h4z" />
    </svg>
  );
}

function LinkedInIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
    >
      <path d="M6.94 5a2 2 0 1 1-4-.002 2 2 0 0 1 4 .002zM7 8.48H3V21h4zm6.32 0H9.34V21h3.94v-6.57c0-3.66 4.77-4 4.77 0V21H22v-7.93c0-6.17-7.06-5.94-8.72-2.91z" />
    </svg>
  );
}

const socialLinks = [
  {
    href: "https://www.facebook.com/profile.php?id=61592292207936",
    label: "Facebook",
    icon: FacebookIcon,
  },
  {
    href: "https://www.linkedin.com/company/closeandkeep/about/",
    label: "LinkedIn",
    icon: LinkedInIcon,
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
            <Icon className="h-4 w-4" />
            <span>{label}</span>
          </a>
        ))}
      </nav>
    </footer>
  );
}
