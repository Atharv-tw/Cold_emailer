import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cold outreach",
  description: "Write, send and track personal cold email.",
  // Lets iOS treat it as an app once it is on the home screen, which is also
  // the only way web push works there.
  appleWebApp: { capable: true, title: "Outreach", statusBarStyle: "default" },
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
