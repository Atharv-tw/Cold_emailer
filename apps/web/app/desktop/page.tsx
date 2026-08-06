import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 text-left">
      <h3 className="mb-1 text-fg">{title}</h3>
      <p className="text-sm text-muted">{body}</p>
    </div>
  );
}

export default async function Home() {
  const session = await auth();
  if (session?.apiUser) redirect("/dashboard");

  return (
    <main className="flex min-h-screen flex-col bg-bg">
      <header className="flex items-center justify-between px-8 py-6 sm:px-16">
        <div className="flex items-center gap-2 text-xl font-bold text-accent">
          <span className="text-2xl">◎</span> Outreach
        </div>
        <Link href="/login">
          <button className="secondary">Sign in</button>
        </Link>
      </header>

      <section className="mx-auto flex max-w-2xl flex-1 flex-col items-center justify-center gap-6 px-6 py-16 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-fg sm:text-5xl">
          Cold outreach that sounds like <span className="text-accent">you</span>.
        </h1>
        <p className="text-lg text-muted">
          Sign in with Google, add your resume, and add the people you want to reach. The email
          gets written for you from what you actually did — nothing sends until you press send.
        </p>
        <Link href="/login">
          <button
            className="primary"
            style={{ borderRadius: "2rem", padding: "0.75rem 2rem", fontSize: "16px" }}
          >
            Get started
          </button>
        </Link>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Feature
            title="Drafted for you"
            body="Emails are written from your resume and projects, not a template."
          />
          <Feature
            title="You stay in control"
            body="Nothing sends automatically. Review, edit, then press send."
          />
          <Feature
            title="Tracks what happens"
            body="Replies, bounces and follow-ups are tracked so nobody slips through."
          />
        </div>
      </section>

      <footer className="px-8 py-6 text-center text-xs text-muted">
        Built for people doing their own outreach.
      </footer>
    </main>
  );
}
