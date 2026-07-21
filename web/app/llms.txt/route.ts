import { getSiteUrl, siteDescription, siteName } from "@/lib/site";

export const dynamic = "force-static";

export function GET() {
  const siteUrl = getSiteUrl();

  const body = `# ${siteName}

> ${siteDescription}

${siteName} helps sales and customer teams send thoughtful cookie follow-up gifts. Log who you are following up with, choose a cookie pack, add a personal note, and pay once per order via Stripe. Fulfillment starts after payment succeeds. Track outcomes as won, lost, or open.

## Pages

- [Home](${siteUrl}/): Product overview and how it works
- [Pricing](${siteUrl}/pricing): Per-order cookie pack pricing (no subscription required)
- [API](${siteUrl}/developers): Create gift orders via API key; humans pay on Stripe Checkout
- [Sign up](${siteUrl}/signup): Create an account
- [Support](${siteUrl}/support): Help with orders, shipping, and accounts
- [Privacy](${siteUrl}/privacy): Privacy policy
- [Terms](${siteUrl}/terms): Terms of use

## Optional

- [Sitemap](${siteUrl}/sitemap.xml): Machine-readable list of public pages
`;

  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}
