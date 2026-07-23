import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Terms for using CloseAndKeep, payments, and fulfillment.",
  alternates: {
    canonical: "/terms",
  },
};

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <h1 className="font-display text-4xl tracking-tight text-espresso">Terms of Service</h1>
      <p className="mt-4 text-sm text-stone-500">Last updated: [Insert Date]</p>
      <p className="mt-4 rounded-xl border border-amber-200/80 bg-amber-50/70 px-4 py-3 text-sm text-stone-700">
        Note: This is a draft prepared for CloseAndKeep&rsquo;s review and is not a substitute for
        advice from a licensed attorney. Please have counsel review before publishing, especially the
        payment, liability, and dispute-resolution sections, and fill in all bracketed placeholders.
      </p>

      <div className="mt-8 space-y-8 text-sm leading-relaxed text-stone-700">
        <p>
          Welcome to CloseAndKeep. These Terms of Service (&ldquo;Terms&rdquo;) govern your access to
          and use of the CloseAndKeep website, application, and gifting services (collectively, the
          &ldquo;Service&rdquo;), operated by CloseAndKeep (&ldquo;CloseAndKeep,&rdquo;
          &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;). By creating an account or using
          the Service, you agree to these Terms. If you do not agree, do not use the Service.
        </p>

        <section>
          <h2 className="font-display text-xl text-espresso">1. Eligibility and Accounts</h2>
          <p className="mt-2">
            1.1 The Service is intended for business use by sales, customer success, and similar
            professional teams. You must be at least 18 years old and able to form a binding contract
            to use the Service.
          </p>
          <p className="mt-2">
            1.2 You are responsible for maintaining the confidentiality of your account credentials
            and for all activity that occurs under your account. Notify us immediately at [support
            email] if you suspect unauthorized use.
          </p>
          <p className="mt-2">
            1.3 You agree to provide accurate, current information when creating an account and when
            placing orders, including accurate recipient shipping information.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">2. Acceptable Use</h2>
          <p className="mt-2">You agree not to use the Service to:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>
              Send gifts to any recipient without a legitimate business relationship or reasonable
              belief that the recipient will welcome the gift;
            </li>
            <li>
              Send gifts to recipients who are prohibited by law, employer policy, or government
              ethics rules from accepting gifts (for example, certain government employees);
            </li>
            <li>
              Include harassing, threatening, discriminatory, or unlawful content in gift notes or
              messages;
            </li>
            <li>
              Attempt to defraud CloseAndKeep, our fulfillment partners, or any third party,
              including through fraudulent payment methods;
            </li>
            <li>
              Reverse-engineer, resell, or use the Service to build a competing product; or
            </li>
            <li>Violate any applicable law or third party&rsquo;s rights.</li>
          </ul>
          <p className="mt-2">We may suspend or terminate accounts that violate this section.</p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">3. Orders, Pricing, and Payment</h2>
          <p className="mt-2">
            <span className="font-medium text-espresso">3.1 Pricing.</span> CloseAndKeep charges a
            per-order fee at the time an order is placed. There is no subscription fee; you only pay
            for gifts you send.
          </p>
          <p className="mt-2">
            <span className="font-medium text-espresso">3.2 Payment processing.</span> All payments
            are processed by Stripe. By placing an order, you agree to Stripe&rsquo;s terms of service
            applicable to payment processing. CloseAndKeep does not store your full payment card
            details.
          </p>
          <p className="mt-2">
            <span className="font-medium text-espresso">3.3 Taxes.</span> Prices do not include
            applicable sales, use, or similar taxes unless stated otherwise. You are responsible for
            any such taxes.
          </p>
          <p className="mt-2">
            <span className="font-medium text-espresso">3.4 Order errors.</span> You are responsible
            for the accuracy of recipient names, addresses, and gift notes at the time of ordering.
            CloseAndKeep is not responsible for gifts misdirected due to inaccurate information you
            provided.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">4. Cancellations and Refunds</h2>
          <p className="mt-2">
            4.1 You may cancel an order for a full refund any time before it enters fulfillment
            (i.e., before the gift has been prepared for shipment). Once an order has entered
            fulfillment, it generally cannot be cancelled because our gifts, including baked goods,
            are prepared to order.
          </p>
          <p className="mt-2">
            4.2 If a gift arrives damaged, spoiled, or materially different from what was ordered,
            contact us at [support email] within [X] days of delivery for a replacement or refund at
            our discretion.
          </p>
          <p className="mt-2">
            4.3 We do not offer refunds for gifts that were delivered as ordered but were declined,
            unwanted, or unopened by the recipient.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">5. Shipping and Fulfillment</h2>
          <p className="mt-2">
            5.1 CloseAndKeep works with third-party bakeries, gift vendors, and shipping carriers to
            fulfill orders. Delivery timelines are estimates only and are not guaranteed.
          </p>
          <p className="mt-2">
            5.2 Some gifts (such as baked goods) are perishable and time-sensitive. You are
            responsible for confirming that a recipient&rsquo;s address can accept a shipment within
            the expected delivery window.
          </p>
          <p className="mt-2">
            5.3 CloseAndKeep is not liable for delays, losses, or damage caused by shipping carriers,
            weather, incorrect address information, or events outside our reasonable control.
          </p>
          <p className="mt-2">
            5.4 CloseAndKeep will make reasonable efforts to disclose common allergens in gift
            offerings, but you are responsible for confirming a gift is appropriate for a given
            recipient&rsquo;s dietary needs before ordering.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">6. Third-Party Recipient Information</h2>
          <p className="mt-2">
            When you place an order, you provide us with personal information about your gift
            recipient (such as name and shipping address) on their behalf. You represent that you
            have a lawful basis and reasonable business justification for providing this information
            and that doing so does not violate any agreement or duty you owe to the recipient. See
            our{" "}
            <Link href="/privacy" className="text-wood-dark hover:underline">
              Privacy Policy
            </Link>{" "}
            for how recipient information is handled.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">7. Intellectual Property</h2>
          <p className="mt-2">
            7.1 CloseAndKeep and its licensors own all right, title, and interest in the Service,
            including its software, design, and trademarks. These Terms do not grant you any rights
            to our intellectual property except the limited right to use the Service as permitted
            here.
          </p>
          <p className="mt-2">
            7.2 You retain ownership of the content you submit (such as gift notes and recipient
            records). You grant CloseAndKeep a limited license to use that content solely to provide
            and improve the Service.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">8. Disclaimers</h2>
          <p className="mt-2">
            THE SERVICE AND ALL GIFTS ARE PROVIDED &ldquo;AS IS&rdquo; AND &ldquo;AS
            AVAILABLE.&rdquo; TO THE MAXIMUM EXTENT PERMITTED BY LAW, CLOSEANDKEEP DISCLAIMS ALL
            WARRANTIES, EXPRESS OR IMPLIED, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
            PARTICULAR PURPOSE, AND NON-INFRINGEMENT, AND DOES NOT WARRANT THAT THE SERVICE WILL BE
            UNINTERRUPTED, ERROR-FREE, OR THAT ANY GIFT WILL ARRIVE ON A PARTICULAR DATE.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">9. Limitation of Liability</h2>
          <p className="mt-2">
            TO THE MAXIMUM EXTENT PERMITTED BY LAW, CLOSEANDKEEP AND ITS OFFICERS, EMPLOYEES, AND
            PARTNERS WILL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR
            PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, DATA, OR GOODWILL, ARISING FROM YOUR USE OF THE
            SERVICE. OUR TOTAL LIABILITY FOR ANY CLAIM ARISING OUT OF OR RELATING TO THESE TERMS OR
            THE SERVICE WILL NOT EXCEED THE AMOUNT YOU PAID TO CLOSEANDKEEP FOR THE ORDER GIVING RISE
            TO THE CLAIM IN THE MONTHS BEFORE THE CLAIM AROSE.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">10. Indemnification</h2>
          <p className="mt-2">
            You agree to indemnify and hold harmless CloseAndKeep from any claims, damages, or
            expenses (including reasonable attorneys&rsquo; fees) arising from your violation of these
            Terms, your misuse of the Service, or the recipient information you provide.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">11. Term and Termination</h2>
          <p className="mt-2">
            11.1 These Terms remain in effect while you use the Service. You may stop using the
            Service and close your account at any time.
          </p>
          <p className="mt-2">
            11.2 We may suspend or terminate your access to the Service, with or without notice, if
            you violate these Terms, engage in fraudulent activity, or for any other reason at our
            discretion, including discontinuation of the Service.
          </p>
          <p className="mt-2">
            11.3 Sections that by their nature should survive termination (including Sections 7–10
            and 12) will survive.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">12. Governing Law and Disputes</h2>
          <p className="mt-2">
            12.1 These Terms are governed by the laws of the State of Colorado, without regard to
            conflict-of-laws principles.
          </p>
          <p className="mt-2">
            12.2 Any dispute arising from these Terms or the Service will be resolved in the state or
            federal courts located in Colorado, and you consent to personal jurisdiction there.
            [Consider adding an arbitration clause and/or class-action waiver with counsel&rsquo;s
            input if desired.]
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">13. Changes to These Terms</h2>
          <p className="mt-2">
            We may update these Terms from time to time. If we make material changes, we will update
            the &ldquo;Last updated&rdquo; date and, where appropriate, notify you by email or through
            the Service. Continued use of the Service after changes take effect constitutes acceptance
            of the updated Terms.
          </p>
        </section>

        <section>
          <h2 className="font-display text-xl text-espresso">14. Contact Us</h2>
          <p className="mt-2">Questions about these Terms can be sent to:</p>
          <p className="mt-2">
            CloseAndKeep
            <br />
            [Business address]
            <br />
            [support email]
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
