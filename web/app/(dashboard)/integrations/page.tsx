import { Suspense } from "react";
import { IntegrationsClient } from "./integrations-client";

export default function IntegrationsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-stone-500">Loading integrations…</p>}>
      <IntegrationsClient />
    </Suspense>
  );
}
