"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";

export type CheckSetupReport = {
  provider: string;
  ok: boolean;
  missing_fields: string[];
  unknown_stage: boolean;
  trigger_stage_name: string;
  messages: string[];
};

type ProviderKey = "salesforce" | "hubspot";

export function CheckSetup({
  provider,
  label,
}: {
  provider: ProviderKey;
  label: string;
}) {
  const [checking, setChecking] = useState(false);
  const [report, setReport] = useState<CheckSetupReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runCheck() {
    setChecking(true);
    setError(null);
    try {
      const data = await apiFetch<CheckSetupReport>(`/integrations/${provider}/check-setup`, {
        method: "POST",
        errorMessage: `Unable to check ${label} setup.`,
      });
      setReport(data);
    } catch (checkError) {
      setReport(null);
      setError(
        checkError instanceof Error ? checkError.message : `Unable to check ${label} setup.`,
      );
    } finally {
      setChecking(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => void runCheck()}
        disabled={checking}
        className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-espresso hover:bg-stone-50 disabled:opacity-50"
      >
        {checking ? "Checking…" : "Check setup"}
      </button>
      {error ? <p className="basis-full text-sm text-rose-700">{error}</p> : null}
      {report ? (
        <div
          className={
            report.ok
              ? "basis-full rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
              : "basis-full rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
          }
        >
          <p className="font-medium text-espresso">
            {report.ok ? "Setup looks good" : "Setup needs attention"}
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {report.messages.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}
