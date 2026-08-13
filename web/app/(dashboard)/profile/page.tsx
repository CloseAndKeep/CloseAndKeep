"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Camera, UserRound } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch, fetchErrorMessage } from "@/lib/api";

type MeResponse = {
  user_id: number;
  email: string;
  name: string | null;
  company: string | null;
  role: string;
  is_guest: boolean;
  has_avatar: boolean;
  billing_mode?: "per_order" | "monthly";
  auto_order_enabled?: boolean;
  auto_order_gift_id?: string | null;
  has_payment_method?: boolean;
  crm_connected?: boolean;
  has_api_key?: boolean;
  monthly_balance_cents?: number;
  monthly_order_count?: number;
  max_spending_cents?: number | null;
};

function initialsFor(name: string | null, email: string): string {
  const trimmed = (name || "").trim();
  if (trimmed) {
    const parts = trimmed.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0]![0]!}${parts[1]![0]!}`.toUpperCase();
    }
    return trimmed.slice(0, 2).toUpperCase();
  }
  return (email || "?").slice(0, 2).toUpperCase();
}

export default function ProfilePage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordLoading, setPasswordLoading] = useState(false);

  const [billingError, setBillingError] = useState<string | null>(null);
  const [billingSuccess, setBillingSuccess] = useState<string | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [spendingLimitInput, setSpendingLimitInput] = useState("");

  useEffect(() => {
    return () => {
      if (avatarUrl) URL.revokeObjectURL(avatarUrl);
    };
  }, [avatarUrl]);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<MeResponse>("/auth/me", {
          errorMessage: "Unable to load your profile.",
        });
        if (!active) return;
        setMe(data);
        setSpendingLimitInput(
          data.max_spending_cents != null
            ? (data.max_spending_cents / 100).toFixed(2)
            : "",
        );

        if (data.has_avatar) {
          const blob = await apiFetch<Blob>("/auth/me/avatar", {
            responseType: "blob",
            errorMessage: "Unable to load your profile photo.",
          });
          if (!active) return;
          setAvatarUrl(URL.createObjectURL(blob));
        } else {
          setAvatarUrl(null);
        }
      } catch (loadError) {
        if (!active) return;
        setError(
          loadError instanceof Error ? loadError.message : "Unable to load your profile.",
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, []);

  async function refreshAvatar(hasAvatar: boolean) {
    if (!hasAvatar) {
      setAvatarUrl(null);
      return;
    }
    const blob = await apiFetch<Blob>("/auth/me/avatar", {
      responseType: "blob",
      errorMessage: "Unable to load your profile photo.",
    });
    setAvatarUrl(URL.createObjectURL(blob));
  }

  async function handleUpload(file: File | null) {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const updated = await apiFetch<MeResponse>("/auth/me/avatar", {
        method: "POST",
        body,
        errorMessage: "Unable to upload profile photo.",
      });
      setMe(updated);
      await refreshAvatar(updated.has_avatar);
      if (fileRef.current) fileRef.current.value = "";
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to upload profile photo.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function handleRemove() {
    setUploading(true);
    setError(null);
    try {
      const updated = await apiFetch<MeResponse>("/auth/me/avatar", {
        method: "DELETE",
        errorMessage: "Unable to remove profile photo.",
      });
      setMe(updated);
      await refreshAvatar(false);
    } catch (removeError) {
      setError(
        removeError instanceof Error
          ? removeError.message
          : "Unable to remove profile photo.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function patchBilling(body: Record<string, unknown>) {
    setBillingLoading(true);
    setBillingError(null);
    setBillingSuccess(null);
    try {
      const updated = await apiFetch<MeResponse>("/auth/me/billing", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        errorMessage: "Unable to update billing preferences.",
      });
      setMe(updated);
      setSpendingLimitInput(
        updated.max_spending_cents != null
          ? (updated.max_spending_cents / 100).toFixed(2)
          : "",
      );
      setBillingSuccess("Billing preferences saved.");
    } catch (err) {
      setBillingError(fetchErrorMessage(err, "Unable to update billing preferences."));
    } finally {
      setBillingLoading(false);
    }
  }

  async function saveSpendingLimit() {
    const trimmed = spendingLimitInput.trim();
    if (!trimmed) {
      void patchBilling({ max_spending_cents: null });
      return;
    }
    const dollars = Number(trimmed);
    if (!Number.isFinite(dollars) || dollars < 1) {
      setBillingError("Enter a max spending limit of at least $1.00, or clear the field to remove it.");
      return;
    }
    const cents = Math.round(dollars * 100);
    void patchBilling({ max_spending_cents: cents });
  }

  async function startCardSetup() {
    setBillingLoading(true);
    setBillingError(null);
    setBillingSuccess(null);
    try {
      const data = await apiFetch<{ setup_url: string }>(
        "/auth/me/billing/setup-payment-method",
        {
          method: "POST",
          errorMessage: "Unable to start card setup.",
        },
      );
      window.location.href = data.setup_url;
    } catch (err) {
      setBillingError(fetchErrorMessage(err, "Unable to start card setup."));
      setBillingLoading(false);
    }
  }

  async function payBalanceNow() {
    setBillingLoading(true);
    setBillingError(null);
    setBillingSuccess(null);
    try {
      const result = await apiFetch<{
        status: string;
        charged_cents?: number;
        order_count?: number;
      }>("/auth/me/billing/pay-balance", {
        method: "POST",
        errorMessage: "Unable to charge your balance.",
      });
      const refreshed = await apiFetch<MeResponse>("/auth/me", {
        errorMessage: "Unable to refresh profile.",
      });
      setMe(refreshed);
      if (result.status === "paid") {
        const dollars = ((result.charged_cents ?? 0) / 100).toFixed(2);
        setBillingSuccess(
          `Charged $${dollars} for ${result.order_count ?? 0} order(s). A receipt was emailed.`,
        );
      } else {
        setBillingSuccess("No open balance to charge.");
      }
    } catch (err) {
      setBillingError(fetchErrorMessage(err, "Unable to charge your balance."));
    } finally {
      setBillingLoading(false);
    }
  }

  async function onChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (newPassword.length < 12) {
      setPasswordError("Password must be at least 12 characters.");
      return;
    }
    if (!/[A-Za-z]/.test(newPassword) || !/\d/.test(newPassword)) {
      setPasswordError("Password must include at least one letter and one number.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.");
      return;
    }
    if (currentPassword === newPassword) {
      setPasswordError("New password must be different from the current password.");
      return;
    }

    setPasswordLoading(true);
    try {
      await apiFetch("/auth/me/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
        errorMessage: "Unable to update password.",
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordSuccess("Password updated.");
    } catch (submitError) {
      setPasswordError(fetchErrorMessage(submitError, "Unable to update password."));
    } finally {
      setPasswordLoading(false);
    }
  }

  const displayName = me?.name?.trim() || "Your profile";
  const initials = me ? initialsFor(me.name, me.email) : "?";

  return (
    <>
      <PageHeader
        title="Profile"
        description="Your account details and profile photo."
      />

      {error ? (
        <p className="mb-6 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      <div className="rounded-2xl border border-stone-200/90 bg-white/90 p-8 shadow-sm">
        {loading || !me ? (
          <p className="text-sm text-stone-500">Loading profile…</p>
        ) : (
          <div className="flex flex-col gap-8 sm:flex-row sm:items-start">
            <div className="flex flex-col items-center gap-3 sm:items-start">
              <div className="relative h-28 w-28 overflow-hidden rounded-full border border-stone-200 bg-stone-100">
                {avatarUrl ? (
                  // Blob URLs are not supported by next/image.
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={avatarUrl}
                    alt={`${displayName} profile photo`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-wood-dark">
                    <UserRound className="h-8 w-8 opacity-70" strokeWidth={1.5} />
                    <span className="text-sm font-semibold tracking-wide">{initials}</span>
                  </div>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  void handleUpload(file);
                }}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => fileRef.current?.click()}
                  className="inline-flex items-center gap-1.5 rounded-full bg-wood px-4 py-2 text-sm font-medium text-white hover:bg-wood-dark disabled:opacity-60"
                >
                  <Camera className="h-4 w-4" strokeWidth={1.75} />
                  {uploading ? "Saving…" : avatarUrl ? "Change photo" : "Upload photo"}
                </button>
                {me.has_avatar ? (
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={() => void handleRemove()}
                    className="rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100 disabled:opacity-60"
                  >
                    Remove
                  </button>
                ) : null}
              </div>
              <p className="max-w-[16rem] text-center text-xs text-stone-500 sm:text-left">
                JPEG, PNG, or WebP up to 2&nbsp;MB.
              </p>
            </div>

            <div className="min-w-0 flex-1 space-y-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                  Name
                </p>
                <p className="mt-1 font-display text-2xl text-espresso">
                  {me.name?.trim() || ""}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                  Email
                </p>
                <p className="mt-1 break-all text-base text-espresso">{me.email}</p>
              </div>
              {me.company?.trim() ? (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                    Company
                  </p>
                  <p className="mt-1 text-base text-espresso">{me.company.trim()}</p>
                </div>
              ) : null}
            </div>
          </div>
        )}
      </div>

      {!loading && me && !me.is_guest && (me.crm_connected || me.has_api_key) ? (
        <div className="mt-6 rounded-2xl border border-stone-200/90 bg-white/90 p-8 shadow-sm">
          <h2 className="font-display text-xl text-espresso">
            {me.crm_connected ? "Monthly billing & auto-order" : "Monthly billing"}
          </h2>
          <p className="mt-1 text-sm text-stone-600">
            {me.crm_connected
              ? "Available because Salesforce or HubSpot is connected."
              : "Available because you have an API key. Custom CRM orders can be billed monthly."}
          </p>

          <div className="mt-6 space-y-6">
            <div>
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-stone-300 text-wood focus:ring-wood"
                  checked={me.billing_mode === "monthly"}
                  disabled={billingLoading}
                  onChange={(event) => {
                    if (event.target.checked) {
                      if (
                        !window.confirm(
                          "You will be billed automatically at the end of each month for all open cookie orders. A receipt will be emailed after each charge. Continue?",
                        )
                      ) {
                        return;
                      }
                      if (!me.has_payment_method) {
                        setBillingError(
                          "Add a card before enabling monthly billing.",
                        );
                        return;
                      }
                      void patchBilling({ billing_mode: "monthly" });
                    } else {
                      void patchBilling({ billing_mode: "per_order" });
                    }
                  }}
                />
                <span>
                  <span className="block text-sm font-medium text-espresso">
                    Pay monthly
                  </span>
                  <span className="mt-1 block text-sm text-stone-600">
                    Accrue cookie orders during the month and charge your saved
                    card at month end (or anytime with Pay now). Orders can still
                    ship before the monthly charge.
                  </span>
                </span>
              </label>

              <p className="mt-3 rounded-xl border border-amber-200/80 bg-amber-50/80 px-3 py-2 text-sm text-stone-700">
                Your saved card is billed automatically at month end for the
                running balance. A receipt email is sent after each successful
                charge. Card details are stored securely by Stripe — not on
                CloseAndKeep servers. Fulfillment can proceed while payment is
                still owed for the month.
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={billingLoading}
                  onClick={() => void startCardSetup()}
                  className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-100 disabled:opacity-60"
                >
                  {me.has_payment_method ? "Update card" : "Add card"}
                </button>
                <span className="text-sm text-stone-500">
                  {me.has_payment_method
                    ? "Card on file"
                    : "No card saved yet"}
                </span>
              </div>
            </div>

            {(me.billing_mode === "monthly" ||
              (me.monthly_order_count ?? 0) > 0) ? (
              <div className="rounded-xl border border-stone-200 bg-stone-50/80 px-4 py-3">
                <p className="text-sm text-stone-700">
                  Open balance:{" "}
                  <span className="font-semibold text-espresso">
                    ${((me.monthly_balance_cents ?? 0) / 100).toFixed(2)}
                  </span>{" "}
                  across {me.monthly_order_count ?? 0} order
                  {(me.monthly_order_count ?? 0) === 1 ? "" : "s"}
                  {me.max_spending_cents != null ? (
                    <>
                      {" "}
                      · Limit:{" "}
                      <span className="font-semibold text-espresso">
                        ${(me.max_spending_cents / 100).toFixed(2)}
                      </span>
                    </>
                  ) : null}
                </p>
                <button
                  type="button"
                  disabled={
                    billingLoading || (me.monthly_order_count ?? 0) === 0
                  }
                  onClick={() => void payBalanceNow()}
                  className="mt-3 rounded-xl bg-wood px-4 py-2 text-sm font-semibold text-white hover:bg-wood-dark disabled:opacity-60"
                >
                  Pay now
                </button>
              </div>
            ) : null}

            <div>
              <p className="text-sm font-medium text-espresso">Max spending limit</p>
              <p className="mt-1 text-sm text-stone-600">
                Cap your open monthly balance. When the limit is reached, new
                monthly-billed orders are blocked and you get an email to pay or
                raise the limit. Leave blank for no limit.
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-stone-500">
                    $
                  </span>
                  <input
                    type="number"
                    min="1"
                    step="0.01"
                    inputMode="decimal"
                    placeholder="No limit"
                    disabled={billingLoading}
                    className="w-40 rounded-xl border border-stone-300 bg-white py-2 pl-7 pr-3 text-sm text-espresso outline-none focus:border-wood disabled:opacity-60"
                    value={spendingLimitInput}
                    onChange={(event) => setSpendingLimitInput(event.target.value)}
                  />
                </div>
                <button
                  type="button"
                  disabled={billingLoading}
                  onClick={() => void saveSpendingLimit()}
                  className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-100 disabled:opacity-60"
                >
                  Save limit
                </button>
              </div>
            </div>

            {me.crm_connected ? (
            <div>
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-stone-300 text-wood focus:ring-wood"
                  checked={Boolean(me.auto_order_enabled)}
                  disabled={billingLoading}
                  onChange={(event) => {
                    if (event.target.checked) {
                      const giftId =
                        me.auto_order_gift_id === "cookies-12"
                          ? "cookies-12"
                          : "cookies-4";
                      void patchBilling({
                        auto_order_gift_id: giftId,
                        auto_order_enabled: true,
                      });
                    } else {
                      void patchBilling({ auto_order_enabled: false });
                    }
                  }}
                />
                <span>
                  <span className="block text-sm font-medium text-espresso">
                    Auto-order on CRM stage
                  </span>
                  <span className="mt-1 block text-sm text-stone-600">
                    When a deal hits your trigger stage, create a cookie order
                    using Cookie Note and street / city / state / ZIP from the CRM.
                    If those address fields are blank, we email the recipient for
                    shipping; otherwise the order is ready to pay.
                  </span>
                </span>
              </label>

              <fieldset className="mt-3 ml-7 space-y-2" disabled={billingLoading}>
                <legend className="sr-only">Auto-order pack size</legend>
                {(
                  [
                    ["cookies-4", "4 cookies"],
                    ["cookies-12", "12 cookies"],
                  ] as const
                ).map(([id, label]) => (
                  <label key={id} className="flex items-center gap-2 text-sm text-stone-700">
                    <input
                      type="radio"
                      name="auto_order_gift_id"
                      checked={(me.auto_order_gift_id || "cookies-4") === id}
                      onChange={() => {
                        void patchBilling({
                          auto_order_gift_id: id,
                          ...(me.auto_order_enabled
                            ? {}
                            : { auto_order_enabled: false }),
                        });
                      }}
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
            </div>
            ) : null}

            {billingError ? (
              <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {billingError}
              </p>
            ) : null}
            {billingSuccess ? (
              <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                {billingSuccess}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {!loading && me && !me.is_guest ? (
        <div className="mt-6 rounded-2xl border border-stone-200/90 bg-white/90 p-8 shadow-sm">
          <h2 className="font-display text-xl text-espresso">Change password</h2>
          <p className="mt-1 text-sm text-stone-600">
            Use at least 12 characters with one letter and one number.
          </p>

          <form className="mt-6 max-w-md space-y-4" onSubmit={onChangePassword}>
            <div>
              <label
                className="mb-1 block text-sm font-medium text-stone-700"
                htmlFor="currentPassword"
              >
                Current password
              </label>
              <input
                id="currentPassword"
                type="password"
                autoComplete="current-password"
                className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                required
              />
            </div>

            <div>
              <label
                className="mb-1 block text-sm font-medium text-stone-700"
                htmlFor="newPassword"
              >
                New password
              </label>
              <input
                id="newPassword"
                type="password"
                autoComplete="new-password"
                className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                required
                minLength={12}
              />
            </div>

            <div>
              <label
                className="mb-1 block text-sm font-medium text-stone-700"
                htmlFor="confirmNewPassword"
              >
                Confirm new password
              </label>
              <input
                id="confirmNewPassword"
                type="password"
                autoComplete="new-password"
                className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
                minLength={12}
              />
            </div>

            {passwordError ? (
              <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {passwordError}
              </p>
            ) : null}

            {passwordSuccess ? (
              <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                {passwordSuccess}
              </p>
            ) : null}

            <button
              type="submit"
              className="rounded-xl bg-wood px-4 py-2 text-sm font-semibold text-white transition hover:bg-wood-dark disabled:opacity-70"
              disabled={passwordLoading}
            >
              {passwordLoading ? "Updating…" : "Update password"}
            </button>
          </form>
        </div>
      ) : null}
    </>
  );
}
