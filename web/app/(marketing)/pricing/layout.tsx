import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Pay once per gift order at checkout. No subscription — choose a cookie pack and send when you need to.",
  alternates: {
    canonical: "/pricing",
  },
  openGraph: {
    url: "/pricing",
    title: "Pricing",
    description:
      "Pay once per gift order at checkout. No subscription — choose a cookie pack and send when you need to.",
  },
};

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
