import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cold outreach",
  description: "Write, send and track personal cold email.",
  // Lets iOS treat it as an app once it is on the home screen, which is also
  // the only way web push works there.
  appleWebApp: { capable: true, title: "Outreach", statusBarStyle: "default" },
  // iOS does not read the manifest's icons when adding to the home screen. It
  // looks for an apple-touch-icon, and without one it uses a screenshot of the
  // page - so the app lands on the home screen as a blurry picture of whatever
  // was on screen at the time.
  icons: {
    icon: "/icon-192.png",
    apple: "/icon-192.png",
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
