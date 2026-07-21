"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { cookiePacks, labelForGiftId } from "@/lib/mock-data";
import { formatGiftPrice, useGiftPrices } from "@/lib/gifts";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";

const steps = ["Prospect & cookies", "Shipping & note", "Review"];

type Prospect = {
  id: number;
  name: string;
  title: string;
  company: string;
  email: string;
  deal_status: "open" | "won" | "lost";
};

type AddressMode = "known" | "request";

export function GiftOrderWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [prospectId, setProspectId] = useState("");
  const [giftId, setGiftId] = useState(cookiePacks[0]?.id ?? "");
  const [recipientName, setRecipientName] = useState("");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [addressMode, setAddressMode] = useState<AddressMode>("known");
  const [address, setAddress] = useState("");
  const [note, setNote] = useState("");
  const [isGuest, setIsGuest] = useState(false);
  const [loadingProspects, setLoadingProspects] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const { byId: priceById } = useGiftPrices();

  useEffect(() => {
    async function loadProspects() {
      setLoadingProspects(true);
      setError(null);
      try {
        const [prospectsResponse, meResponse] = await Promise.all([
          fetch(`${getApiBaseUrl()}/prospects`, { credentials: "include" }),
          fetch(`${getApiBaseUrl()}/auth/me`, { credentials: "include" }),
        ]);
        if (!prospectsResponse.ok) {
          throw new Error("Unable to load prospects.");
        }
        const data = (await prospectsResponse.json()) as Prospect[];
        setProspects(data);
        if (data.length > 0) {
          setProspectId(String(data[0].id));
        }
        if (meResponse.ok) {
          const me = (await meResponse.json()) as { role?: string; is_guest?: boolean };
          const guest = me.role === "guest" || me.is_guest === true;
          setIsGuest(guest);
          if (guest) {
            setAddressMode("known");
          }
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
  const selectedPack = useMemo(() => cookiePacks.find((p) => p.id === giftId), [giftId]);
  const selectedPriceLabel = formatGiftPrice(priceById.get(giftId));
  const requestAddress = !isGuest && addressMode === "request";

  const canNext =
    step === 0
      ? Boolean(prospectId && giftId)
      : step === 1
        ? Boolean(
            recipientName.trim() &&
              note.trim() &&
              (requestAddress
                ? recipientEmail.trim().includes("@")
                : address.trim()),
          )
        : true;

  function next() {
    if (step < steps.length - 1 && canNext) setStep((s) => s + 1);
  }

  function back() {
    if (step > 0) setStep((s) => s - 1);
  }

  async function submitOrder() {
    if (!selectedProspect || !selectedPack) {
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const body: Record<string, unknown> = {
        prospect_id: selectedProspect.id,
        gift_id: selectedPack.id,
        recipient_name: recipientName.trim(),
        note: note.trim(),
      };
      if (requestAddress) {
        body.request_recipient_address = true;
        body.recipient_email = recipientEmail.trim();
      } else {
        body.shipping_address = address.trim();
      }

      const response = await fetch(`${getApiBaseUrl()}/gift-orders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(
          typeof data?.detail === "string" ? data.detail : "Unable to submit order.",
        );
      }
      const data = (await response.json()) as { id: number; checkout_url?: string | null };
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      router.push(`/orders/${data.id}`);
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
                Order will be tied to this prospect. Follow-ups and outcomes stay on the prospect record.
              </p>
            </div>

            <div>
              <span className="block text-sm font-medium text-espresso" id="cookie-amount-label">
                Number of cookies
              </span>
              <div
                className="mt-2 flex flex-wrap gap-2"
                role="radiogroup"
                aria-labelledby="cookie-amount-label"
              >
                {cookiePacks.map((pack) => {
                  const selected = giftId === pack.id;
                  const packPrice = formatGiftPrice(priceById.get(pack.id));
                  return (
                    <button
                      key={pack.id}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      onClick={() => setGiftId(pack.id)}
                      className={`min-w-[5.5rem] flex-1 rounded-xl border px-3 py-3 text-left text-sm transition sm:min-w-0 sm:flex-none ${
                        selected
                          ? "border-wood bg-wood/10 font-medium text-wood-dark ring-2 ring-wood/30"
                          : "border-stone-200 bg-white text-espresso hover:border-stone-300"
                      }`}
                    >
                      <span className="block">{pack.cookieCount === 1 ? "1 cookie" : `${pack.cookieCount} cookies`}</span>
                      <span className="mt-0.5 block text-xs font-normal text-stone-600">
                        {packPrice ?? "Price at checkout"}
                      </span>
                    </button>
                  );
                })}
              </div>
              <p className="mt-2 text-xs text-stone-500">
                {requestAddress
                  ? "You authorize payment at checkout. We charge only after the recipient submits their address."
                  : "You pay once at Stripe checkout when you submit."}
              </p>
              {selectedPack ? (
                <p className="mt-2 text-sm font-medium text-espresso">
                  Order total: {selectedPriceLabel ?? "shown at checkout"}
                </p>
              ) : null}
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

            {!isGuest ? (
              <fieldset>
                <legend className="block text-sm font-medium text-espresso">Shipping address</legend>
                <div className="mt-2 space-y-2">
                  <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-stone-200 px-4 py-3 text-sm has-[:checked]:border-wood has-[:checked]:bg-wood/5">
                    <input
                      type="radio"
                      name="address-mode"
                      className="mt-1"
                      checked={addressMode === "known"}
                      onChange={() => setAddressMode("known")}
                    />
                    <span>
                      <span className="font-medium text-espresso">I know the address</span>
                      <span className="mt-0.5 block text-xs text-stone-500">
                        Enter the full shipping address now and pay at checkout.
                      </span>
                    </span>
                  </label>
                  <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-stone-200 px-4 py-3 text-sm has-[:checked]:border-wood has-[:checked]:bg-wood/5">
                    <input
                      type="radio"
                      name="address-mode"
                      className="mt-1"
                      checked={addressMode === "request"}
                      onChange={() => setAddressMode("request")}
                    />
                    <span>
                      <span className="font-medium text-espresso">Email recipient for address</span>
                      <span className="mt-0.5 block text-xs text-stone-500">
                        Authorize payment now. We email them a link for shipping, and charge only after they reply.
                      </span>
                    </span>
                  </label>
                </div>
              </fieldset>
            ) : null}

            {requestAddress ? (
              <div>
                <label className="block text-sm font-medium text-espresso">Recipient email</label>
                <input
                  type="email"
                  className="mt-2 w-full rounded-xl border border-stone-200 px-4 py-3 text-sm"
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                  placeholder={selectedProspect?.email ?? "recipient@company.com"}
                />
                <p className="mt-1 text-xs text-stone-500">
                  They will get a secure link to enter their shipping address.
                </p>
              </div>
            ) : (
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
            )}

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
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 text-sm">
            <div className="rounded-xl bg-cream/80 p-4">
              <p className="text-xs font-semibold uppercase text-stone-500">Prospect</p>
              <p className="mt-1 font-medium text-espresso">{selectedProspect?.name}</p>
              <p className="text-stone-600">{selectedProspect?.company}</p>
            </div>
            <div className="rounded-xl bg-cream/80 p-4">
              <p className="text-xs font-semibold uppercase text-stone-500">Cookies</p>
              <p className="mt-1 font-medium text-espresso">{labelForGiftId(giftId)}</p>
              {selectedPack ? (
                <p className="mt-2 text-stone-600">
                  Total: {selectedPriceLabel ?? "shown at checkout"}
                </p>
              ) : null}
            </div>
            <div className="rounded-xl bg-cream/80 p-4">
              <p className="text-xs font-semibold uppercase text-stone-500">Ship to</p>
              <p className="mt-1 font-medium text-espresso">{recipientName}</p>
              {requestAddress ? (
                <>
                  <p className="text-stone-600">{recipientEmail}</p>
                  <p className="mt-2 text-xs text-stone-500">
                    Address will be collected from the recipient by email.
                  </p>
                </>
              ) : (
                <p className="text-stone-600 whitespace-pre-line">{address}</p>
              )}
            </div>
            <div className="rounded-xl bg-cream/80 p-4">
              <p className="text-xs font-semibold uppercase text-stone-500">Note</p>
              <p className="text-stone-700 whitespace-pre-line">{note}</p>
            </div>
            <p className="text-stone-500">
              {requestAddress
                ? "Submitting opens Stripe to authorize payment. After that, we email the recipient for their address — you are charged only when they submit it."
                : "Submitting saves your order and opens Stripe to pay once. Fulfillment starts after payment."}
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
              {submitting
                ? "Redirecting to payment..."
                : requestAddress
                  ? "Authorize & request address"
                  : "Pay & submit order"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
