"use client";

import { useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api";

/** Live gift/price info from the API (`GET /gifts`), sourced from Stripe. */
export type GiftPrice = {
  gift_id: string;
  cookie_count: number;
  /** Amount in the smallest currency unit (e.g. cents), or null if unavailable. */
  unit_amount: number | null;
  currency: string | null;
};

export async function fetchGiftPrices(): Promise<GiftPrice[]> {
  const response = await fetch(`${getApiBaseUrl()}/gifts`, { credentials: "include" });
  if (!response.ok) {
    throw new Error("Unable to load gift prices.");
  }
  return (await response.json()) as GiftPrice[];
}

/** Format a live price, or return null when the amount is not available. */
export function formatGiftPrice(price?: GiftPrice | null): string | null {
  if (!price || price.unit_amount == null) {
    return null;
  }
  const currency = (price.currency ?? "usd").toUpperCase();
  const amount = price.unit_amount / 100;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
  } catch {
    return `$${amount.toFixed(2)}`;
  }
}

/** Client hook that loads the live gift catalog with Stripe prices. */
export function useGiftPrices(): {
  prices: GiftPrice[];
  byId: Map<string, GiftPrice>;
  loading: boolean;
} {
  const [prices, setPrices] = useState<GiftPrice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchGiftPrices()
      .then((data) => {
        if (active) setPrices(data);
      })
      .catch(() => {
        if (active) setPrices([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const byId = new Map(prices.map((price) => [price.gift_id, price]));
  return { prices, byId, loading };
}
