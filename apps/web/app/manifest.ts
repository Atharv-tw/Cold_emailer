import type { MetadataRoute } from "next";

/**
 * The whole of the "app".
 *
 * There is no separate mobile build and no store listing. This file plus a
 * service worker is what turns the site into something Chrome offers to
 * install on a laptop and iOS will add to a home screen. Installing is an
 * upgrade for people who want it, not a requirement for anyone.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Outreach",
    short_name: "Outreach",
    description: "Write, send and track personal cold email.",
    start_url: "/dashboard",
    display: "standalone",
    // Both of these were left over from an earlier palette: the splash flashed
    // white before the cream background painted, and the theme colour was a
    // dark green that appears nowhere in globals.css. They now match --bg and
    // the themeColor in layout.tsx, which have to agree or the browser chrome
    // changes colour as the page loads.
    background_color: "#eaecdf",
    theme_color: "#eaecdf",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // A separate file rather than the "any" icon reused: Android crops
      // maskable icons to a circle 80% of the width, which would have taken a
      // bite out of the O in the full-bleed version.
      {
        src: "/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
