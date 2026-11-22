import type { Metadata } from "next";
import Link from "next/link";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CopyInstructionsButton } from "@/components/ai-helper/copy-instructions-button";
import { CopyTextButton } from "@/components/ai-helper/copy-text-button";

export const metadata: Metadata = {
  title: "Use with AI",
  description:
    "Connect Claude, ChatGPT, or Cursor to place CloseAndKeep cookie gifts — or paste AI Helper instructions for a prefill link.",
  alternates: {
    canonical: "/developers/ai",
  },
  openGraph: {
    url: "/developers/ai",
    title: "CloseAndKeep — Use with AI",
    description:
      "MCP Connect for Claude, ChatGPT, and Cursor. AI Helper stays available with no Connect step.",
  },
};

const EXAMPLE_LINK =
  "https://www.closeandkeep.com/send?name=Alyssa%20Ozer&email=alyssa.ozer%40continuserve.com&pack=4&ask_address=1&note=Thanks%20for%20the%20demo%20%E2%80%94%20enjoy%20these%20cookies%21";

// Public MCP URL must be reachable by Claude/ChatGPT/Cursor clouds.
// Production API is the Render service (api.closeandkeep.com is not DNS'd yet).
const MCP_URL =
  process.env.NEXT_PUBLIC_MCP_URL?.replace(/\/$/, "") ||
  "https://closeandkeep-api.onrender.com/mcp";

const CURSOR_DEEPLINK = (() => {
  const config = Buffer.from(
    JSON.stringify({
      url: MCP_URL,
    }),
  ).toString("base64");
  return `cursor://anysphere.cursor-deeplink/mcp/install?name=CloseAndKeep&config=${config}`;
})();

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
        Use with AI
      </p>
      <h1 className="mt-3 font-display text-4xl tracking-tight text-espresso">Use with AI</h1>
      <p className="mt-4 max-w-2xl text-lg text-stone-600">
        Connect Claude, ChatGPT, or Cursor once, then place cookie gifts from chat. You still pay on
        Stripe. Prefer the no-Connect{" "}
        <a href="#ai-helper" className="font-medium text-wood-dark underline">
          AI Helper
        </a>{" "}
        if your team will not install anything.
      </p>

      <section className="mt-12 space-y-4">
        <h2 className="font-display text-2xl text-espresso">Connect your AI</h2>
        <p className="text-sm text-stone-600">
          MCP URL (same for every host). You need a verified CloseAndKeep account (not guest).
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <code className="rounded-md bg-cream/80 px-3 py-2 text-xs text-espresso">{MCP_URL}</code>
          <CopyTextButton text={MCP_URL} label="Copy MCP URL" />
          <Link
            href="/ai-connections"
            className="text-sm font-medium text-wood-dark hover:underline"
          >
            Manage connections
          </Link>
        </div>

        <div className="mt-8 space-y-8">
          <div>
            <h3 className="font-display text-xl text-espresso">Claude</h3>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-stone-700">
              <li>Copy the MCP URL above.</li>
              <li>Claude → Settings → Connectors → Add custom connector.</li>
              <li>Paste the URL → Connect → log in to CloseAndKeep → Allow.</li>
            </ol>
            <p className="mt-2 text-sm text-stone-600">
              Native directory listing (search for CloseAndKeep inside Claude, no URL paste) is in
              progress. Custom Connect works today; directory requires Anthropic review after we
              submit listing materials.
            </p>
          </div>
          <div>
            <h3 className="font-display text-xl text-espresso">ChatGPT</h3>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-stone-700">
              <li>Copy the MCP URL above.</li>
              <li>Open ChatGPT settings for custom MCP / connectors (labels vary).</li>
              <li>Paste the URL → Connect → log in to CloseAndKeep → Allow.</li>
            </ol>
          </div>
          <div>
            <h3 className="font-display text-xl text-espresso">Cursor</h3>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-stone-700">
              <li>
                <a
                  href={CURSOR_DEEPLINK}
                  className="font-medium text-wood-dark underline"
                >
                  Add to Cursor
                </a>{" "}
                (installs the MCP URL only — no secret in the link).
              </li>
              <li>Or paste the MCP URL into Cursor MCP settings.</li>
              <li>Connect → log in to CloseAndKeep → Allow.</li>
            </ol>
          </div>
        </div>

        <p className="text-sm text-stone-600">
          After Connect, say something like “Send 4 cookies to Dana at dana@acme.com — thanks for
          the demo.” The AI drafts the gift, you confirm, then you get a Stripe pay link.
        </p>
      </section>

      <section id="ai-helper" className="mt-16 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">AI Helper (no Connect)</h2>
        <p>
          Paste instructions once into a shared Claude Project or ChatGPT GPT. The AI returns a
          prefill <code className="text-xs">/send?…</code> link — it does not place the order.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <CopyInstructionsButton text={instructionsText} />
          <a
            href="/ai-helper-order-cookies/INSTRUCTIONS.txt"
            download="ai-helper-order-cookies-INSTRUCTIONS.txt"
            className="inline-flex items-center rounded-full border border-stone-300 bg-white px-5 py-2.5 text-sm font-medium text-espresso transition hover:border-wood hover:text-wood-dark"
          >
            Download .txt
          </a>
        </div>
        <p className="rounded-xl bg-cream/80 px-4 py-3 text-xs break-all text-stone-600">
          Example link shape: {EXAMPLE_LINK}
        </p>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Privacy</h2>
        <p>
          Recipient name, email, address, and gift note go to the AI host you connect (and to
          CloseAndKeep when an order is created). Cards stay with Stripe. Prefer per-order Checkout
          while using AI.
        </p>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Advanced: API skill</h2>
        <p>
          Power users / CRM scripts can still use a <code className="text-xs">cak_</code> API key
          and the skill zip. Most sellers should use Connect or AI Helper.
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
    </div>
  );
}
