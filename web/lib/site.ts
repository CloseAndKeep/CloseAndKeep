/** Canonical public site origin for SEO (sitemap, Open Graph, absolute URLs). */
export function getSiteUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_SITE_URL?.trim().replace(/\/$/, "");
  if (fromEnv) {
    return fromEnv;
  }
  if (process.env.VERCEL_PROJECT_PRODUCTION_URL) {
    return `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL.replace(/\/$/, "")}`;
  }
  return "https://closeandkeep.com";
}

export const siteName = "CloseAndKeep";

export const siteDescription =
  "Send thoughtful follow-up gifts to prospects and customers. Pay once per order — no subscription required.";
