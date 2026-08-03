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
    name: "Cold outreach",
    short_name: "Outreach",
    description: "Write, send and track personal cold email.",
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#1a5fd0",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
