import { Suspense } from "react";
import { RedeemClient } from "./redeem-client";

export default function RedeemPage() {
  return (
    <Suspense fallback={<p className="mx-auto max-w-lg px-4 py-12 text-sm text-stone-500">Loading…</p>}>
      <RedeemClient />
    </Suspense>
  );
}
