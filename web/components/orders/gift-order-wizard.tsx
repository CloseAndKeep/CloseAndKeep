"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { gifts } from "@/lib/mock-data";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";

const steps = ["Prospect", "Gift", "Shipping & note", "Review"];

type Prospect = {
  id: number;
  name: string;
  title: string;
  company: string;
  email: string;
  deal_status: "open" | "won" | "lost";
};

export function GiftOrderWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [prospectId, setProspectId] = useState("");
  const [giftId, setGiftId] = useState(gifts[0]?.id ?? "");
  const [recipientName, setRecipientName] = useState("");
  const [address, setAddress] = useState("");
  const [note, setNote] = useState("");
  const [loadingProspects, setLoadingProspects] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    async function loadProspects() {
      setLoadingProspects(true);
      setError(null);
      try {
        const response = await fetch(`${getApiBaseUrl()}/prospects`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Unable to load prospects.");
        }
        const data = (await response.json()) as Prospect[];
        setProspects(data);
        if (data.length > 0) {
          setProspectId(String(data[0].id));
        }
      } catch (loadError) {
        const message =
          loadError instanceof Error ? loadError.message : "Unable to load prospects.";
        setError(message);
      } finally {
        setLoadingProspects(false);
      }
    }
    void loadProspects();
  }, []);

  const selectedProspect = useMemo(
    () => prospects.find((p) => String(p.id) === prospectId),
    [prospectId, prospects],
  );
  const selectedGift = gifts.find((g) => g.id === giftId);

  const canNext =
    step === 0
      ? Boolean(prospectId)
      : step === 1
        ? Boolean(giftId)
        : step === 2
          ? recipientName.trim() && address.trim() && note.trim()
          : true;

  function next() {
    if (step < steps.length - 1 && canNext) setStep((s) => s + 1);
  }

  function back() {
    if (step > 0) setStep((s) => s - 1);
  }

  async function submitOrder() {
    if (!selectedProspect || !selectedGift) {
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/gift-orders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          prospect_id: selectedProspect.id,
          gift_id: selectedGift.id,
          recipient_name: recipientName.trim(),
          shipping_address: address.trim(),
          note: note.trim(),
        }),
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(data?.detail ?? "Unable to submit order.");
      }
      setSuccessMessage("Order submitted successfully.");
      router.push("/prospects");
      router.refresh();
    } catch (submitError) {
      const message =
        submitError instanceof Error ? submitError.message : "Unable to submit order.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-2xl border border-stone-200/90 bg-white/90 shadow-sm">
      <div className="border-b border-stone-100 px-6 py-4">
        <ol className="flex flex-wrap gap-2 text-xs font-medium sm:gap-4">
          {steps.map((label, i) => (
            <li
              key={label}
              className={
                i === step
                  ? "rounded-full bg-wood/20 px-3 py-1 text-wood-dark"
                  : i < step
                    ? "rounded-full px-3 py-1 text-stone-500"
                    : "rounded-full px-3 py-1 text-stone-400"
              }
            >
              {i + 1}. {label}
            </li>
          ))}
        </ol>
      </div>

      <div className="p-6 sm:p-8">
        {error ? (
          <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        {successMessage ? (
          <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {successMessage}
          </div>
        ) : null}

        {step === 0 && (
          <div className="space-y-6 max-w-lg">
            <div>
              <label className="block text-sm font-medium text-espresso">Prospect</label>
              <select
                className="mt-2 w-full rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm"
                value={prospectId}
                onChange={(e) => setProspectId(e.target.value)}
                disabled={loadingProspects || prospects.length === 0}
              >
                {prospects.length === 0 ? (
                  <option value="">
                    {loadingProspects ? "Loading prospects..." : "No prospects available"}
                  </option>
                ) : null}
                {prospects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — {p.company}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-stone-500">
                Gift will be tied to this prospect. Follow-ups and outcomes stay on the prospect record.
              </p>
            </div>
            {prospects.length === 0 && !loadingProspects ? (
              <p className="text-sm text-stone-600">
                Add a prospect first in{" "}
                <Link href="/prospects" className="font-medium text-wood-dark hover:underline">
                  Prospects
                </Link>
                .
              </p>
            ) : null}
          </div>
        )}

        {step === 1 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {gifts.map((g) => (
              <button
                key={g.id}
                type="button"
                onClick={() => setGiftId(g.id)}
                className={`rounded-2xl border p-4 text-left transition ${
                  giftId === g.id
                    ? "border-wood bg-wood/10 ring-2 ring-wood/30"
                    : "border-stone-200 hover:border-stone-300"
                }`}
              >
                <div className={`h-20 rounded-xl bg-gradient-to-br ${g.accent} mb-3`} />
                <p className="font-medium text-espresso">{g.name}</p>
                <p className="mt-1 text-xs text-stone-600">{g.description}</p>
              </button>
            ))}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 max-w-xl">
            <div>
              <label className="block text-sm font-medium text-espresso">
                Recipient name (for delivery)
              </label>
              <input
                className="mt-2 w-full rounded-xl border border-stone-200 px-4 py-3 text-sm"
                value={recipientName}
                onChange={(e) => setRecipientName(e.target.value)}
                placeholder={selectedProspect?.name ?? "Full name"}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-espresso">
                Full shipping address
              </label>
              <textarea
                className="mt-2 w-full rounded-xl border border-stone-200 px-4 py-3 text-sm min-h-[100px]"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Street, city, state, ZIP / postal code"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-espresso">
                Note on the gift (card or enclosure)
              </label>
              <textarea
                className="mt-2 w-full rounded-xl border border-stone-200 px-4 py-3 text-sm min-h-[88px]"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Short personal message — required before fulfillment."
              />
              <p className="mt-1 text-xs text-stone-500">
                Fulfillment uses this text verbatim (placeholder — API will enforce required).
              </p>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4 text-sm">
            <div className="rounded-xl bg-cream/80 p-4">
              <p className="text-xs font-semibold uppercase text-stone-500">Prospect</p>
              <p className="mt-1 font-medium text-espresso">{selectedProspect?.name}</p>
              <p className="text-stone-600">{selectedProspect?.company}</p>
            </div>
            <div className="rounded-xl bg-cream/80 p-4">
              <p className="text-xs font-semibold uppercase text-stone-500">Gift</p>
              <p className="mt-1 font-medium text-espresso">{selectedGift?.name}</p>
            </div>
            <div className="rounded-xl bg-cream/80 p-4">
              <p className="text-xs font-semibold uppercase text-stone-500">Ship to</p>
              <p className="mt-1 font-medium text-espresso">{recipientName}</p>
              <p className="text-stone-600 whitespace-pre-line">{address}</p>
            </div>
            <div className="rounded-xl bg-cream/80 p-4">
              <p className="text-xs font-semibold uppercase text-stone-500">Note</p>
              <p className="text-stone-700 whitespace-pre-line">{note}</p>
            </div>
            <p className="text-stone-500">
              Submitting creates a queued gift order tied to this prospect.
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-stone-100 px-6 py-4">
        <Link href="/dashboard" className="text-sm text-stone-600 hover:text-espresso">
          Cancel
        </Link>
        <div className="flex gap-2">
          {step > 0 ? (
            <Button type="button" variant="secondary" onClick={back}>
              <ChevronLeft className="h-4 w-4" />
              Back
            </Button>
          ) : null}
          {step < steps.length - 1 ? (
            <Button type="button" disabled={!canNext} onClick={next}>
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          ) : (
            <Button type="button" variant="primary" disabled={!canNext || submitting} onClick={submitOrder}>
              {submitting ? "Submitting..." : "Submit order"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
