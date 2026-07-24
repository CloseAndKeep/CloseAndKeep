import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Redeem a gift",
  description: "Enter your Close & Keep redeem code to view your gift and share a delivery address.",
  robots: {
    index: true,
    follow: true,
  },
};

export default function RedeemLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
