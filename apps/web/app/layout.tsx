import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cold outreach",
  description: "Write, send and track personal cold email.",
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
