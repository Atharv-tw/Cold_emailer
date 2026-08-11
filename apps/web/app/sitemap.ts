import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/site";

/**
 * Short on purpose.
 *
 * A sitemap is a list of pages worth ranking, not an inventory of routes. The
 * landing page is the only one that qualifies: everything else is either
 * behind the login or a form (login, signup, password reset) that helps nobody
 * arriving from a search. Those stay crawlable - they are linked from the
 * landing page and harmless - they are just not advertised here.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: siteUrl,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 1,
    },
  ];
}
