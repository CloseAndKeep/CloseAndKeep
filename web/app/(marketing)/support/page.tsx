import type { Metadata } from "next";
import Link from "next/link";
import { contactEmail } from "@/lib/site";

export const metadata: Metadata = {
  title: "Support",
  description: "Get help with CloseAndKeep orders, shipping, and your account.",
  alternates: {
    canonical: "/support",
  },
  openGraph: {
    url: "/support",
    title: "Support",
    description: "Get help with CloseAndKeep orders, shipping, and your account.",
  },
};

export default function SupportPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl tracking-tight text-espresso">Support</h1>
      <p className="mt-4 max-w-2xl text-lg text-stone-600">
        Questions about an order, shipping, or your account? We’re here to help.
      </p>

      <div className="mt-10 space-y-8 text-sm leading-relaxed text-stone-700">
        <section>
          <h2 className="font-display text-xl text-espresso">Email us</h2>
          <p className="mt-2">
            Reach us at{" "}
            <a
              href={`mailto:${contactEmail}`}
              className="font-medium text-wood-dark hover:underline"
            >
              {contactEmail}
            </a>
            . Include your order details when you can so we can help faster.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">Orders and shipping</h2>
          <p className="mt-2">
            After you pay, we fulfill cookie gift orders manually. If a recipient needs to
            provide an address, they’ll get an email with a secure link. For status updates
            or changes before a gift ships, email support with the order info from your
            account.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">Payments</h2>
          <p className="mt-2">
            Payments are processed securely by Stripe. You pay once per gift order—there is
            no subscription. For billing questions or refunds on orders that have not
            shipped, contact us at the address above.
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
