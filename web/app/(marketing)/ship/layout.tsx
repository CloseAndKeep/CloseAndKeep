import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Shipping address",
  robots: {
    index: false,
    follow: false,
  },
};

export default function ShipLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
