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

export type Gift = {
  id: string;
  name: string;
  description: string;
  priceHint: string;
  accent: string;
};

export const gifts: Gift[] = [
  {
    id: "g1",
    name: "Artisan chocolate box",
    description: "Small-batch dark chocolate; includes a handwritten-style card slot.",
    priceHint: "Included in plan",
    accent: "from-amber-700/20 to-orange-200/40",
  },
  {
    id: "g2",
    name: "Roaster’s coffee kit",
    description: "Whole bean + brew guide — great after a long demo.",
    priceHint: "Included in plan",
    accent: "from-stone-600/25 to-amber-100/50",
  },
  {
    id: "g3",
    name: "Cookie assortment",
    description: "Shareable tin; neutral allergens note on request.",
    priceHint: "Included in plan",
    accent: "from-rose-300/30 to-amber-50/50",
  },
];

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
    giftId: "g1",
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

export function giftById(id: string) {
  return gifts.find((g) => g.id === id);
}

export function ordersForProspect(prospectId: string) {
  return orders.filter((o) => o.prospectId === prospectId);
}
