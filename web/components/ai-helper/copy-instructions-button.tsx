"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

type Props = {
  text: string;
  className?: string;
};

export function CopyInstructionsButton({ text, className }: Props) {
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
    <Button type="button" variant="primary" className={className} onClick={() => void onCopy()}>
      {copied ? "Copied — paste into Claude" : "Copy instructions"}
    </Button>
  );
}
