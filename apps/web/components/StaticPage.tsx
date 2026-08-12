import Link from "next/link";

import { supportEmail } from "@/lib/site";

/**
 * Chrome for standalone legal/info pages (privacy, terms) - the same visual
 * language as the landing page, but without the marketing sections, so it
 * works whether someone lands here from Google's consent screen or the
 * in-app footer.
 */
export default function StaticPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <main className="flex min-h-screen flex-col bg-bg">
      <header
        className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 backdrop-blur sm:px-16"
        style={{ background: "rgba(234, 236, 223, 0.85)", borderBottom: "1px solid var(--line)" }}
      >
        <Link href="/" className="flex items-center gap-2.5">
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[14px] font-bold"
            style={{ background: "var(--lime)", color: "var(--ink)", fontFamily: "var(--font-display)" }}
          >
            O
          </span>
          <span
            className="text-[17px] font-bold text-fg"
            style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}
          >
            Outreach
          </span>
        </Link>
        <Link href="/" className="text-sm font-medium text-muted transition-colors hover:text-fg">
          ← Back home
        </Link>
      </header>

      <article className="mx-auto w-full max-w-3xl flex-1 px-6 py-14 sm:px-8">
        <h1>{title}</h1>
        <p className="mt-2 text-sm text-muted">Last updated {updated}</p>
        <div className="mt-10 flex flex-col gap-7 text-[15px] leading-relaxed">{children}</div>
      </article>

      <footer className="flex flex-col items-center gap-3 px-8 py-10 text-center text-xs text-muted">
        <span>Outreach — write, send and track personal cold email.</span>
        <nav className="flex items-center gap-5">
          <Link href="/privacy" className="hover:text-fg">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-fg">
            Terms
          </Link>
          <a href={`mailto:${supportEmail}`} className="hover:text-fg">
            Contact us
          </a>
        </nav>
      </footer>
    </main>
  );
}
