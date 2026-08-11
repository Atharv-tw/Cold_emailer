import type { Metadata, Viewport } from "next";

import { siteUrl } from "@/lib/site";
import "./globals.css";

const DESCRIPTION = "Write, send and track personal cold email.";

export const metadata: Metadata = {
  // Without this every relative image path below stays relative, and a
  // relative og:image is the single most common reason a link preview comes
  // out blank.
  metadataBase: new URL(siteUrl),
  title: {
    default: "Cold outreach - write, send and track personal cold email",
    // Child pages set a bare title ("Targets") and get the brand appended, so
    // no page has to remember to repeat it.
    template: "%s · Cold outreach",
  },
  description: DESCRIPTION,
  applicationName: "Outreach",
  // The landing page is served from / by a middleware rewrite, not from
  // /desktop, so that is what should be treated as canonical.
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "Cold outreach",
    title: "Cold outreach - write, send and track personal cold email",
    description: DESCRIPTION,
    locale: "en_GB",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Outreach" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Cold outreach - write, send and track personal cold email",
    description: DESCRIPTION,
    images: ["/og.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  // Lets iOS treat it as an app once it is on the home screen, which is also
  // the only way web push works there.
  appleWebApp: { capable: true, title: "Outreach", statusBarStyle: "default" },
  // Every icon is declared here and lives in public/, rather than some of them
  // relying on Next's app/icon.* file convention. The two mechanisms do not
  // combine: defining this key at all switches the file convention off, so a
  // convention-based icon.svg goes silently unlinked while the PNGs listed
  // here keep working - which looks like the SVG simply being ignored.
  //
  // SVG first so browsers that understand it get the crisp one; the PNGs stay
  // for crawlers and older Android builds that will not take an SVG favicon.
  icons: {
    icon: [
      { url: "/icon.svg", type: "image/svg+xml" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#eaecdf",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
