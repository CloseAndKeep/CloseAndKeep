import { cookiePacks } from "@/lib/gift-catalog";
import { GIFT_NOTE_MAX_LENGTH } from "@/lib/gift-notes";
import type { ShippingAddressValue } from "@/components/orders/shipping-address-fields";
import { EMPTY_SHIPPING_ADDRESS } from "@/components/orders/shipping-address-fields";

export type AddressMode = "known" | "request";

export type OrderPrefill = {
  name: string;
  email: string;
  giftId: string;
  note: string;
  addressMode: AddressMode;
  address: ShippingAddressValue;
  /** True when name + email + note are set and shipping mode is usable → jump to Review. */
  readyForReview: boolean;
};

function firstParam(params: URLSearchParams, key: string): string {
  return params.get(key)?.trim() ?? "";
}

function resolveGiftId(params: URLSearchParams): string {
  const giftId = firstParam(params, "gift_id");
  if (giftId && cookiePacks.some((p) => p.id === giftId)) {
    return giftId;
  }
  const pack = firstParam(params, "pack");
  if (pack === "12" || pack === "cookies-12") {
    return "cookies-12";
  }
  if (pack === "4" || pack === "cookies-4" || !pack) {
    return cookiePacks[0]?.id ?? "cookies-4";
  }
  // Unknown pack → default 4-pack
  return cookiePacks[0]?.id ?? "cookies-4";
}

function truthy(value: string): boolean {
  const v = value.toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

/**
 * Parse `/orders/new` query params for AI Helper (and dashboard) prefills.
 */
export function parseOrderPrefill(params: URLSearchParams): OrderPrefill {
  const name = firstParam(params, "name");
  const email = firstParam(params, "email");
  const noteRaw = params.get("note")?.trim() ?? "";
  const note = noteRaw.slice(0, GIFT_NOTE_MAX_LENGTH);
  const giftId = resolveGiftId(params);

  const street = firstParam(params, "street") || firstParam(params, "shipping_street");
  const street2 = firstParam(params, "street2") || firstParam(params, "shipping_street2");
  const city = firstParam(params, "city") || firstParam(params, "shipping_city");
  const state = firstParam(params, "state") || firstParam(params, "shipping_state");
  const zip =
    firstParam(params, "zip") ||
    firstParam(params, "postal_code") ||
    firstParam(params, "shipping_postal_code");
  const company =
    firstParam(params, "company") || firstParam(params, "shipping_company");

  const hasFullAddress = Boolean(street && city && state && zip);
  const askParam = firstParam(params, "ask_address");
  let addressMode: AddressMode;
  if (hasFullAddress && !truthy(askParam)) {
    addressMode = "known";
  } else if (truthy(askParam) || (name && email && !hasFullAddress)) {
    addressMode = "request";
  } else if (hasFullAddress) {
    addressMode = "known";
  } else {
    addressMode = "request";
  }

  const address: ShippingAddressValue = hasFullAddress
    ? {
        company,
        street,
        street2,
        city,
        state,
        postalCode: zip,
      }
    : { ...EMPTY_SHIPPING_ADDRESS };

  const shippingOk =
    addressMode === "request" ||
    Boolean(address.street && address.city && address.state && address.postalCode);

  const readyForReview = Boolean(name && email && note && giftId && shippingOk);

  return {
    name,
    email,
    giftId,
    note,
    addressMode,
    address,
    readyForReview,
  };
}
