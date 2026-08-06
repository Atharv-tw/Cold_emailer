import Link from "next/link";

import { auth } from "@/auth";

export default async function DesktopNotFound() {
  const session = await auth();
  const signedIn = Boolean(session?.apiUser);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg px-6 text-center">
      <div className="flex items-center gap-2 text-xl font-bold text-accent">
        <span className="text-2xl">◎</span> Outreach
      </div>
      <h1 className="text-6xl font-bold text-fg">404</h1>
      <p className="text-muted">That page doesn&rsquo;t exist.</p>
      <Link href={signedIn ? "/dashboard" : "/"}>
        <button className="primary" style={{ borderRadius: "0.75rem", padding: "0.75rem 1.5rem" }}>
          {signedIn ? "Back to dashboard" : "Back home"}
        </button>
      </Link>
    </main>
  );
}
