import type { Metadata } from "next";
import Link from "next/link";
import { contactEmail } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact CloseAndKeep about orders, partnerships, or your account.",
  alternates: {
    canonical: "/contact",
  },
  openGraph: {
    url: "/contact",
    title: "Contact",
    description: "Contact CloseAndKeep about orders, partnerships, or your account.",
  },
};

export default function ContactPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl tracking-tight text-espresso">Contact</h1>
      <p className="mt-4 max-w-2xl text-lg text-stone-600">
        We’d love to hear from you. Reach out anytime and we’ll get back as soon as we can.
      </p>

      <div className="mt-10 space-y-8 text-sm leading-relaxed text-stone-700">
        <section>
          <h2 className="font-display text-xl text-espresso">Email</h2>
          <p className="mt-2">
            <a
              href={`mailto:${contactEmail}`}
              className="font-medium text-wood-dark hover:underline"
            >
              {contactEmail}
            </a>
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">Help with an order</h2>
          <p className="mt-2">
            For shipping status, address changes, or payment questions, see{" "}
            <Link href="/support" className="font-medium text-wood-dark hover:underline">
              Support
            </Link>{" "}
            or email us with your order details.
          </p>
        </section>
      </div>

      <p className="mt-10 text-sm text-stone-500">
        <Link href="/" className="text-wood-dark hover:underline">
          ← Back home
        </Link>
      </p>
    </div>
  );
}
