/** Placeholder data — replace with API calls later */

export const mockAccount = {
  name: "Alex Rivera",
  email: "alex@example.com",
  plan: "Individual" as const,
  weeklyOrdersUsed: 1,
  weeklyOrderLimit: 1,
};

export type DealStatus = "open" | "won" | "lost";

export type Prospect = {
  id: string;
  name: string;
  title: string;
  company: string;
  email: string;
  /** Rough pipeline signal for the dashboard — no separate “pitch” record in the UI */
  dealStatus: DealStatus;
};

export const prospects: Prospect[] = [
  {
    id: "p1",
    name: "Jordan Lee",
    title: "VP Operations",
    company: "Northwind Labs",
    email: "jordan@northwind.example",
    dealStatus: "open",
  },
  {
    id: "p2",
    name: "Sam Patel",
    title: "Director of IT",
    company: "Contoso Health",
    email: "sam.patel@contoso.example",
    dealStatus: "won",
  },
  {
    id: "p3",
    name: "Taylor Morgan",
    title: "Head of Sales",
    company: "Fabrikam SaaS",
    email: "t.morgan@fabrikam.example",
    dealStatus: "lost",
  },
];

export type CookiePack = {
  id: string;
  cookieCount: number;
};

export const cookiePacks: CookiePack[] = [
  { id: "cookies-1", cookieCount: 1 },
  { id: "cookies-2", cookieCount: 2 },
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

export type OrderStatus =
  | "queued"
  | "ordered"
  | "shipped"
  | "delivered";

export type GiftOrder = {
  id: string;
  prospectId: string;
  giftId: string;
  recipientName: string;
  status: OrderStatus;
  requestedAt: string;
};

export const orders: GiftOrder[] = [
  {
    id: "o1",
    prospectId: "p1",
    giftId: "cookies-4",
    recipientName: "Jordan Lee",
    status: "queued",
    requestedAt: "2026-04-29",
  },
];

export type FollowUp = {
  id: string;
  prospectId: string;
  dueDate: string;
  note: string;
};

export const followUps: FollowUp[] = [
  {
    id: "f1",
    prospectId: "p1",
    dueDate: "2026-05-05",
    note: "Check if gift arrived; share ROI doc.",
  },
  {
    id: "f2",
    prospectId: "p2",
    dueDate: "2026-05-08",
    note: "Onboarding check-in.",
  },
];

export function prospectById(id: string) {
  return prospects.find((p) => p.id === id);
}

export function ordersForProspect(prospectId: string) {
  return orders.filter((o) => o.prospectId === prospectId);
}
