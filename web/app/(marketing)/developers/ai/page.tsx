import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Use with AI",
  description:
    "Install the CloseAndKeep orders skill in Cursor, Claude, or ChatGPT Actions. Cards stay on Stripe.",
  alternates: {
    canonical: "/developers/ai",
  },
  openGraph: {
    url: "/developers/ai",
    title: "CloseAndKeep — use with your AI",
    description:
      "Portable skill + API key so your preferred agent can place cookie gifts after you confirm.",
  },
};

export default function DevelopersAiPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <p className="text-sm text-stone-500">
        <Link href="/developers" className="font-medium text-wood-dark hover:underline">
          API
        </Link>
        <span className="mx-2">/</span>
        Use with AI
      </p>
      <h1 className="mt-3 font-display text-4xl tracking-tight text-espresso">Use with your AI</h1>
      <p className="mt-4 max-w-2xl text-lg text-stone-600">
        Install the CloseAndKeep orders skill, store a dedicated API key as a secret, and ask your
        agent to send cookies after a demo. You confirm the details; Stripe Checkout (or monthly
        billing) handles payment. Card numbers never enter the chat.
      </p>

      <p className="mt-8">
        <a
          href="/skills/closeandkeep-orders.zip"
          download="closeandkeep-orders.zip"
          className="inline-flex items-center rounded-full bg-wood px-5 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-wood-dark"
        >
          Download closeandkeep-orders.zip
        </a>
      </p>
      <p className="mt-3 text-sm text-stone-500">
        Direct link:{" "}
        <a
          href="https://www.closeandkeep.com/skills/closeandkeep-orders.zip"
          className="break-all font-medium text-wood-dark hover:underline"
        >
          closeandkeep.com/skills/closeandkeep-orders.zip
        </a>
      </p>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Privacy</h2>
        <p>
          Recipient name, email, address, and gift note are sent to the AI provider you choose
          (Cursor, Anthropic, OpenAI, etc.). Prefer per-order Checkout while experimenting. Revoke
          a leaked key under{" "}
          <Link href="/api-keys" className="font-medium text-wood-dark hover:underline">
            API keys
          </Link>
          .
        </p>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Setup</h2>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            Create a verified account (not guest) and a dedicated key labeled for this host (e.g.{" "}
            <code className="text-xs">Cursor AI</code>).
          </li>
          <li>
            Download the skill zip:{" "}
            <a
              href="/skills/closeandkeep-orders.zip"
              download="closeandkeep-orders.zip"
              className="font-medium text-wood-dark hover:underline"
            >
              closeandkeep-orders.zip
            </a>
            . Unzip it, then drop the <code className="text-xs">closeandkeep-orders</code> folder
            into your Cursor (or Claude) skills directory.
          </li>
          <li>Store the key as secret <code className="text-xs">CLOSEANDKEEP_API_KEY</code> only.</li>
          <li>
            Smoke test: “Send a test 4-pack to me at my email with note ‘AI skill test’” — the agent
            must confirm before calling the API.
          </li>
        </ol>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Host matrix</h2>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong className="font-medium text-espresso">Cursor</strong> — drop the folder under
            project/user skills; set the secret.
          </li>
          <li>
            <strong className="font-medium text-espresso">Claude</strong> — skill or project
            instructions + secret.
          </li>
          <li>
            <strong className="font-medium text-espresso">ChatGPT</strong> — use Actions with{" "}
            <code className="text-xs">openapi-orders.yaml</code> inside the zip; never bake a key into
            a shared GPT.
          </li>
          <li>
            <strong className="font-medium text-espresso">Prompt-only</strong> — paste the skill for
            guidance; you run curl or the dashboard yourself.
          </li>
        </ul>
      </section>

      <section className="mt-12 space-y-3 text-sm leading-relaxed text-stone-700">
        <h2 className="font-display text-2xl text-espresso">Also see</h2>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <Link href="/developers" className="font-medium text-wood-dark hover:underline">
              HTTP API examples
            </Link>
          </li>
          <li>
            <Link href="/api-keys" className="font-medium text-wood-dark hover:underline">
              API keys
            </Link>{" "}
            (create / revoke)
          </li>
          <li>
            Custom CRM <strong className="font-medium">Send cookies</strong> button walkthrough lives
            in the repo at <code className="text-xs">docs/custom-crm-setup.md</code>
          </li>
        </ul>
      </section>
    </div>
  );
}
