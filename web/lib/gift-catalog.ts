/** Canonical cookie-pack catalog (labels only; live prices come from the API). */

export type CookiePack = {
  id: string;
  cookieCount: number;
};

export const cookiePacks: CookiePack[] = [
  { id: "cookies-4", cookieCount: 4 },
  { id: "cookies-12", cookieCount: 12 },
];

export function cookieCountLabel(cookieCount: number): string {
  return cookieCount === 1 ? "1 cookie" : `${cookieCount} cookies`;
}

/** Human label for a gift id (cookie count only; price comes from the API). */
export function labelForGiftId(giftId: string): string {
  const pack = cookiePacks.find((p) => p.id === giftId);
  if (pack) {
    return cookieCountLabel(pack.cookieCount);
  }
  return giftId;
}
