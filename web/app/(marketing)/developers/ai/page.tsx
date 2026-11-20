import type { Metadata } from "next";
import Link from "next/link";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CopyInstructionsButton } from "@/components/ai-helper/copy-instructions-button";

export const metadata: Metadata = {
  title: "AI Helper: Order Cookies",
  description:
    "Paste chat instructions so Claude or ChatGPT hands your team a ready-to-pay CloseAndKeep link. No API key.",
  alternates: {
    canonical: "/developers/ai",
  },
  openGraph: {
    url: "/developers/ai",
    title: "CloseAndKeep — AI Helper: Order Cookies",
    description:
      "Company setup once: paste AI Helper instructions. Sellers chat, click the link, confirm, and pay on Stripe.",
  },
};

const EXAMPLE_LINK =
  "https://www.closeandkeep.com/send?name=Alyssa%20Ozer&email=alyssa.ozer%40continuserve.com&pack=4&ask_address=1&note=Thanks%20for%20the%20demo%20%E2%80%94%20enjoy%20these%20cookies%21";

function loadInstructionsText(): string {
  return readFileSync(
    join(process.cwd(), "public/ai-helper-order-cookies/INSTRUCTIONS.txt"),
    "utf8",
  );
}

export default function DevelopersAiPage() {
  const instructionsText = loadInstructionsText();

  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <p className="text-sm text-stone-500">
        <Link href="/developers" className="font-medium text-wood-dark hover:underline">
          API
        </Link>
        <span className="mx-2">/</span>
        AI Helper
      </p>
      <h1 className="mt-3 font-display text-4xl tracking-tight text-espresso">
        AI Helper: Order Cookies
      </h1>
      <p className="mt-4 max-w-2xl text-lg text-stone-600">
        Give your team&apos;s Claude or ChatGPT a short set of instructions. When a seller asks to
        send cookies, the AI replies with a CloseAndKeep link — already filled. They click, confirm,
        and pay on Stripe. No API key, no app install, no network allowlist.
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <CopyInstructionsButton text={instructionsText} />
        <a
          href="/ai-helper-order-cookies/INSTRUCTIONS.txt"
          download="ai-helper-order-cookies-INSTRUCTIONS.txt"
          className="inline-flex items-center rounded-full border border-stone-300 bg-white px-5 py-2.5 text-sm font-medium text-espresso transition hover:border-wood hover:text-wood-dark"
        >
          Download .txt
        </a>
        <Link
          href="/developers"
          className="text-sm font-medium text-wood-dark hover:underline"
        >
          API docs
        </Link>
      </div>
      <p className="mt-3 text-sm text-stone-500">
        File:{" "}
        <a
          href="https://www.closeandkeep.com/ai-helper-order-cookies/INSTRUCTIONS.txt"
          className="break-all font-medium text-wood-dark hover:underline"
        >
          ai-helper-order-cookies/INSTRUCTIONS.txt
        </a>
      </p>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">How it works</h2>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            Seller: “Send 4 cookies to Alyssa Ozer at alyssa@… — thanks for the demo. I don’t have her
            address.”
          </li>
          <li>AI confirms, then returns one prefill link (no order is placed yet).</li>
          <li>Seller opens the link → Review is filled → Pay on Stripe.</li>
        </ol>
        <p className="rounded-xl bg-cream/80 px-4 py-3 text-xs break-all text-stone-600">
          Example link shape: {EXAMPLE_LINK}
        </p>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Company setup (once)</h2>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            Click <strong className="font-medium">Copy instructions</strong> (or download the{" "}
            <a
              href="/ai-helper-order-cookies/INSTRUCTIONS.txt"
              download="ai-helper-order-cookies-INSTRUCTIONS.txt"
              className="font-medium text-wood-dark hover:underline"
            >
              .txt
            </a>
            ).
          </li>
          <li>
            Paste into your shared <strong className="font-medium">Claude Project</strong>{" "}
            instructions, a ChatGPT custom GPT, or the equivalent for your host.
          </li>
          <li>
            Sellers only need a CloseAndKeep account (not guest). They chat, click the link, and pay.
          </li>
        </ol>
        <p>
          Smoke test: ask the AI to send a test 4-pack to you at your email with note “AI Helper
          test”. It must confirm, then give a{" "}
          <code className="text-xs">closeandkeep.com/send?…</code> link — not place an order itself.
        </p>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Privacy</h2>
        <p>
          Recipient name, email, address, and gift note are sent to the AI provider you choose
          (Anthropic, OpenAI, etc.) when you type them in chat. Prefer per-order Checkout while
          trying this out.
        </p>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Advanced: API skill</h2>
        <p>
          Agents that should call <code className="text-xs">api.closeandkeep.com</code> directly
          (Cursor secrets, custom CRM buttons) still use the API key skill — that path needs a{" "}
          <code className="text-xs">cak_</code> key and host setup. Most sales teams should use AI
          Helper instead.
        </p>
        <p>
          <a
            href="/skills/closeandkeep-orders.zip"
            download="closeandkeep-orders.zip"
            className="font-medium text-wood-dark hover:underline"
          >
            Download closeandkeep-orders.zip
          </a>
          {" · "}
          <Link href="/api-keys" className="font-medium text-wood-dark hover:underline">
            API keys
          </Link>
          {" · "}
          <Link href="/developers" className="font-medium text-wood-dark hover:underline">
            HTTP examples
          </Link>
        </p>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Also see</h2>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Custom CRM <strong className="font-medium">Send cookies</strong> button walkthrough:{" "}
            <code className="text-xs">docs/custom-crm-setup.md</code>
          </li>
          <li>
            Plan and naming: <code className="text-xs">docs/ai-helper-order-cookies.md</code>
          </li>
        </ul>
      </section>
    </div>
  );
}
