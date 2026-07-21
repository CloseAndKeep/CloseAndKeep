import type { Metadata } from "next";
import { DM_Sans, Fraunces } from "next/font/google";
import { getSiteUrl, siteDescription, siteName } from "@/lib/site";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const siteUrl = getSiteUrl();

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: `${siteName} — Simple gifting follow-up for customer teams`,
    template: `%s — ${siteName}`,
  },
  description: siteDescription,
  applicationName: siteName,
  keywords: [
    "sales follow-up gifts",
    "customer gifting",
    "post-demo gifts",
    "cookie gifts for sales",
    "CloseAndKeep",
  ],
  authors: [{ name: siteName }],
  creator: siteName,
  openGraph: {
    type: "website",
    locale: "en_US",
    url: siteUrl,
    siteName,
    title: `${siteName} — Simple gifting follow-up for customer teams`,
    description: siteDescription,
    images: [
      {
        url: "/brand/mark-512.png",
        width: 512,
        height: 512,
        alt: siteName,
      },
    ],
  },
  twitter: {
    card: "summary",
    title: `${siteName} — Simple gifting follow-up for customer teams`,
    description: siteDescription,
    images: ["/brand/mark-512.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
  alternates: {
    canonical: "/",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${dmSans.variable} ${fraunces.variable} min-h-screen font-sans antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
