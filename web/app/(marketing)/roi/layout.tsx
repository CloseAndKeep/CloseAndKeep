import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ROI Calculator",
  description:
    "Estimate incremental revenue and ROI from sending cookie gifts after demos and to existing customers.",
  alternates: {
    canonical: "/roi",
  },
  openGraph: {
    url: "/roi",
    title: "ROI Calculator",
    description:
      "Estimate incremental revenue and ROI from sending cookie gifts after demos and to existing customers.",
  },
};

export default function RoiLayout({ children }: { children: React.ReactNode }) {
  return children;
}
