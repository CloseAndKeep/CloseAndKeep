"use client";

import { useState } from "react";

export function CopyTextButton({
  text,
  label = "Copy",
}: {
  text: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      onClick={() => void onCopy()}
      className="inline-flex items-center rounded-full bg-wood px-5 py-2.5 text-sm font-medium text-white transition hover:bg-wood-dark"
    >
      {copied ? "Copied" : label}
    </button>
  );
}
