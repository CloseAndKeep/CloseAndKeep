import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How CloseAndKeep collects, uses, and protects your data.",
  alternates: {
    canonical: "/privacy",
  },
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl tracking-tight text-espresso">Privacy Policy</h1>
      <p className="mt-4 text-sm text-stone-500">Last updated: [Insert Date]</p>

      <div className="mt-8 space-y-8 text-sm leading-relaxed text-stone-700">
        <p>
          CloseAndKeep (&ldquo;CloseAndKeep,&rdquo; &ldquo;we,&rdquo; &ldquo;us,&rdquo; or
          &ldquo;our&rdquo;) respects your privacy and the privacy of the people you send gifts to.
          This Privacy Policy explains what information we collect, how we use it, and the choices
          available to you. It applies to our website, application, and gifting services (the
          &ldquo;Service&rdquo;).
        </p>
        <p>
          Because of how CloseAndKeep works, we collect information about two different groups of
          people: (1) our customers, who create accounts and place orders, and (2) gift recipients,
          whose information is provided to us by our customers. Both are covered below.
        </p>

        <section>
          <h2 className="font-display text-xl text-espresso">1. Information We Collect</h2>

          <h3 className="mt-4 font-medium text-espresso">
            1.1 Information from Account Holders (Customers)
          </h3>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>
              <span className="font-medium text-espresso">Account information:</span> name, work
              email, company name, and password (or SSO credentials).
            </li>
            <li>
              <span className="font-medium text-espresso">Order information:</span> gift selections,
              order history, notes/messages you write to recipients, and internal tracking status
              (e.g., won/lost/open).
            </li>
            <li>
              <span className="font-medium text-espresso">Payment information:</span> processed
              directly by Stripe. CloseAndKeep does not receive or store full card numbers; we retain
              limited metadata such as transaction ID, amount, and last four digits for order
              records.
            </li>
            <li>
              <span className="font-medium text-espresso">Usage data:</span> log data, device/browser
              information, and analytics about how you interact with the Service.
            </li>
          </ul>

          <h3 className="mt-4 font-medium text-espresso">
            1.2 Information About Gift Recipients (Third Parties)
          </h3>
          <p className="mt-2">
            When you place an order, you provide us with information about your intended recipient,
            which may include:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Name</li>
            <li>Shipping address</li>
            <li>Company/title (if provided)</li>
            <li>Any personal details included in your gift note</li>
          </ul>
          <p className="mt-2">
            Recipients do not create accounts and typically do not provide this information to us
            directly — it comes from our customers. We use it solely to fulfill and ship the gift and
            to support the customer relationship, as described below.
          </p>

          <h3 className="mt-4 font-medium text-espresso">1.3 Cookies and Similar Technologies</h3>
          <p className="mt-2">
            We use cookies and similar technologies on our website to keep you logged in, remember
            preferences, and understand aggregate usage through analytics tools (e.g., [Google
            Analytics or similar]). You can control cookies through your browser settings.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">2. How We Use Information</h2>
          <p className="mt-2">We use the information above to:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Create and maintain customer accounts;</li>
            <li>Process orders and payments;</li>
            <li>
              Prepare, package, and ship gifts to recipients through our bakery/vendor and shipping
              partners;
            </li>
            <li>
              Send order confirmations, shipment tracking, and follow-up reminders to customers;
            </li>
            <li>Provide customer support;</li>
            <li>
              Monitor, maintain, and improve the Service, including fraud prevention and security;
            </li>
            <li>
              Communicate service updates, and, where you&rsquo;ve opted in, product news; and
            </li>
            <li>Comply with legal obligations.</li>
          </ul>
          <p className="mt-2">
            We do not use gift recipient information for our own marketing purposes, and we do not
            sell recipient information.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">3. How We Share Information</h2>
          <p className="mt-2">We share information only as needed to operate the Service:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>
              <span className="font-medium text-espresso">Service providers:</span> Stripe (payment
              processing), our fulfillment partners and bakeries (to prepare and pack gifts), and
              shipping carriers (to deliver gifts) receive the minimum information necessary — for
              example, a carrier receives the recipient&rsquo;s name and address, not payment
              details.
            </li>
            <li>
              <span className="font-medium text-espresso">Analytics and infrastructure providers:</span>{" "}
              hosting, analytics, and customer support tool providers who process data on our behalf
              under confidentiality obligations.
            </li>
            <li>
              <span className="font-medium text-espresso">Legal and safety reasons:</span> we may
              disclose information if required by law, subpoena, or legal process, or to protect the
              rights, property, or safety of CloseAndKeep, our customers, or others.
            </li>
            <li>
              <span className="font-medium text-espresso">Business transfers:</span> if CloseAndKeep
              is involved in a merger, acquisition, or sale of assets, information may be transferred
              as part of that transaction, subject to this Policy or a successor policy.
            </li>
          </ul>
          <p className="mt-2">
            We do not sell personal information to third parties for their own marketing purposes.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">4. Data Retention</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>
              Account data is retained for as long as your account is active, and for a reasonable
              period afterward to comply with legal, tax, and accounting obligations.
            </li>
            <li>
              Recipient data (name and shipping address) is retained only as long as reasonably
              necessary to fulfill the order, support delivery issues or refund requests, and
              maintain order history for the customer, after which it is deleted or anonymized on a
              schedule of [X months/years] unless a customer or recipient requests earlier deletion.
            </li>
            <li>
              Payment metadata is retained per Stripe&rsquo;s and our own recordkeeping requirements
              (typically tied to tax and accounting retention rules).
            </li>
          </ul>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">5. Your Rights and Choices</h2>

          <h3 className="mt-4 font-medium text-espresso">5.1 Customers (Account Holders)</h3>
          <p className="mt-2">
            You can access, correct, or update your account information at any time by logging into
            your account or contacting us at [privacy email]. You may request deletion of your
            account, subject to our legitimate need to retain certain records (e.g., for tax
            purposes).
          </p>

          <h3 className="mt-4 font-medium text-espresso">5.2 Gift Recipients</h3>
          <p className="mt-2">
            If you received a gift through CloseAndKeep and would like to know what information we
            hold about you, or would like it corrected or deleted, you can contact us at [privacy
            email]. We will honor deletion requests once any pending shipment or support matter tied
            to that data is resolved.
          </p>

          <h3 className="mt-4 font-medium text-espresso">
            5.3 State and International Privacy Rights
          </h3>
          <p className="mt-2">
            Depending on where you live, you may have additional rights under laws such as the
            Colorado Privacy Act, the California Consumer Privacy Act (CCPA/CPRA), or the EU/UK
            General Data Protection Regulation (GDPR), including rights to access, correct, delete, or
            port your personal information, and to opt out of certain processing. To exercise these
            rights, contact us at [privacy email]. We will not discriminate against you for
            exercising these rights.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">6. Security</h2>
          <p className="mt-2">
            We use reasonable administrative, technical, and physical safeguards designed to protect
            information, including SSL/TLS encryption in transit and access controls on our systems.
            No method of transmission or storage is completely secure, and we cannot guarantee
            absolute security.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">7. Children&rsquo;s Privacy</h2>
          <p className="mt-2">
            The Service is intended for business use by adults and is not directed to children under
            16. We do not knowingly collect personal information from children. If you believe a
            child has provided us information, contact us at [privacy email] and we will delete it.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">8. International Data Transfers</h2>
          <p className="mt-2">
            If you access the Service from outside the United States, your information may be
            transferred to and processed in the United States or other countries where our service
            providers operate, which may have different data protection laws than your country.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">9. Third-Party Links</h2>
          <p className="mt-2">
            Our Service may contain links to third-party websites (for example, Stripe&rsquo;s
            checkout pages). This Privacy Policy does not apply to those third-party sites, and we
            encourage you to review their privacy policies.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">10. Changes to This Policy</h2>
          <p className="mt-2">
            We may update this Privacy Policy from time to time. If we make material changes, we will
            update the &ldquo;Last updated&rdquo; date above and, where appropriate, notify customers
            by email or through the Service.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">11. Contact Us</h2>
          <p className="mt-2">
            If you have questions about this Privacy Policy or want to exercise your privacy rights,
            contact us at:
          </p>
          <p className="mt-2">
            CloseAndKeep
            <br />
            [Business address]
            <br />
            [privacy email]
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
