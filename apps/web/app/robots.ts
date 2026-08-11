import type { MetadataRoute } from "next";

import { PRIVATE_PATHS, siteUrl } from "@/lib/site";

/**
 * Almost all of this site is one person's private outreach pipeline.
 *
 * The landing page is the only thing worth indexing; everything else is a
 * signed-in view of who someone is emailing and whether they replied. Those
 * pages redirect when logged out, so a crawler would not get content from
 * them anyway - the point of listing them is to keep the URLs themselves out
 * of search results, since a path like /targets/<id> is a fact about the user
 * even when the body behind it is a login screen.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // No trailing slashes: "/dashboard" is a prefix match covering both the
      // page itself and everything under it, whereas "/dashboard/" would leave
      // the bare page crawlable.
      disallow: ["/api/", ...PRIVATE_PATHS],
    },
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
