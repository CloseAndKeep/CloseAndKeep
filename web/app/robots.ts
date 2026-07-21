import type { MetadataRoute } from "next";
import { getSiteUrl } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = getSiteUrl();

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/dashboard",
          "/orders",
          "/prospects",
          "/follow-ups",
          "/billing",
          "/gifts",
          "/admin",
          "/login",
          "/ship/",
        ],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
