import type { Metadata } from "next";
import { SiteFooter } from "@/components/layout/site-footer";

export const metadata: Metadata = {
  title: "Sign up",
  description:
    "Create a CloseAndKeep account to send follow-up gifts to prospects and customers.",
  alternates: {
    canonical: "/signup",
  },
  openGraph: {
    url: "/signup",
    title: "Sign up",
    description:
      "Create a CloseAndKeep account to send follow-up gifts to prospects and customers.",
  },
};

export default function SignupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-cream">
      <div className="flex-1">{children}</div>
      <SiteFooter />
    </div>
  );
}
