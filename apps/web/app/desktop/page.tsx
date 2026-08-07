import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";

function Feature({
  icon,
  title,
  body,
  tint,
}: {
  icon: string;
  title: string;
  body: string;
  tint: "accent" | "lime" | "orange" | "purple";
}) {
  const tones: Record<typeof tint, { bg: string; fg: string }> = {
    accent: { bg: "var(--accent-light)", fg: "var(--accent)" },
    lime: { bg: "#f2fbd9", fg: "var(--lime-dark)" },
    orange: { bg: "var(--orange-light)", fg: "var(--orange)" },
    purple: { bg: "var(--purple-light)", fg: "var(--purple)" },
  };
  const tone = tones[tint];

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5 text-left">
      <div
        className="flex h-10 w-10 items-center justify-center rounded-full text-lg"
        style={{ background: tone.bg, color: tone.fg }}
      >
        {icon}
      </div>
      <h3 className="text-fg">{title}</h3>
      <p className="text-sm text-muted">{body}</p>
    </div>
  );
}

function Step({ number, title, body, tone }: { number: string; title: string; body: string; tone: string }) {
  return (
    <div className="flex flex-1 flex-col gap-3 text-left">
      <div
        className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold text-white"
        style={{ background: tone }}
      >
        {number}
      </div>
      <h3 className="text-fg">{title}</h3>
      <p className="text-sm text-muted">{body}</p>
    </div>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <div className="border-b border-line py-5 last:border-none">
      <h3 className="mb-1.5 text-fg">{q}</h3>
      <p className="text-sm text-muted">{a}</p>
    </div>
  );
}

export default async function Home() {
  const session = await auth();
  if (session?.apiUser) redirect("/dashboard");

  return (
    <main className="flex min-h-screen flex-col bg-bg">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-bg/90 px-8 py-5 backdrop-blur sm:px-16">
        <div className="flex items-center gap-2 text-xl font-bold text-accent">
          <span className="text-2xl">◎</span> Outreach
        </div>
        <nav className="hidden items-center gap-8 text-sm font-medium text-muted sm:flex">
          <a href="#how-it-works" className="hover:text-fg">
            How it works
          </a>
          <a href="#features" className="hover:text-fg">
            Features
          </a>
          <a href="#faq" className="hover:text-fg">
            FAQ
          </a>
        </nav>
        <Link href="/login">
          <button className="secondary">Sign in</button>
        </Link>
      </header>

      {/* Hero */}
      <section className="mx-auto flex max-w-3xl flex-col items-center gap-6 px-6 py-20 text-center">
        <span
          className="rounded-full px-3 py-1 text-xs font-semibold"
          style={{ background: "#f2fbd9", color: "var(--lime-dark)" }}
        >
          Built for students and early-career job hunters
        </span>
        <h1 className="text-4xl font-bold tracking-tight text-fg sm:text-5xl">
          Cold outreach that sounds like <span className="text-accent">you</span>, not a template.
        </h1>
        <p className="max-w-xl text-lg text-muted">
          Sign in with Google, add your resume, and add the people you want to reach. Every email is
          drafted from what you actually built — nothing sends until you press send.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link href="/login">
            <button
              className="primary"
              style={{ borderRadius: "2rem", padding: "0.75rem 2rem", fontSize: "16px" }}
            >
              Get started with Google
            </button>
          </Link>
          <a href="#how-it-works">
            <button
              className="secondary"
              style={{ borderRadius: "2rem", padding: "0.75rem 2rem", fontSize: "16px" }}
            >
              See how it works
            </button>
          </a>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm text-muted">
          <span>✓ Free to use, bring your own Gemini key</span>
          <span>✓ Nothing sends automatically</span>
          <span>✓ Verifies addresses before you send</span>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="border-t border-line bg-surface px-6 py-20 sm:px-16">
        <div className="mx-auto max-w-4xl">
          <h2 className="mb-2 text-2xl font-bold text-fg">How it works</h2>
          <p className="mb-10 text-muted">Four steps, and you're always the one who presses send.</p>
          <div className="grid grid-cols-1 gap-8 sm:grid-cols-4">
            <Step
              number="1"
              title="Add your resume"
              body="Upload it once. It's read into a headline, bio, projects and experience you can edit."
              tone="var(--accent)"
            />
            <Step
              number="2"
              title="Add the people you want to reach"
              body="One at a time, or import a whole list — a founder, a hiring manager, a professor."
              tone="var(--orange)"
            />
            <Step
              number="3"
              title="Get a draft, written from your work"
              body="Not a template — a real email naming a specific project and why it's relevant to them."
              tone="var(--purple)"
            />
            <Step
              number="4"
              title="Review, edit, and press send"
              body="Nothing goes out until you say so. Replies and bounces are tracked automatically."
              tone="var(--lime-dark)"
            />
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="px-6 py-20 sm:px-16">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-2 text-2xl font-bold text-fg">Everything cold outreach actually needs</h2>
          <p className="mb-10 text-muted">No CRM to configure, no sequences to design. Just the parts that matter.</p>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <Feature
              icon="✍️"
              tint="accent"
              title="Drafted for you"
              body="Emails are written from your resume and projects, not a generic template — every draft names something real."
            />
            <Feature
              icon="🖐️"
              tint="lime"
              title="You stay in control"
              body="Generating a draft never sends it. Review, edit, then press send yourself, every time."
            />
            <Feature
              icon="📬"
              tint="orange"
              title="Tracks what happens"
              body="Replies, bounces and follow-ups are tracked automatically, so nobody you've reached out to slips through."
            />
            <Feature
              icon="✅"
              tint="purple"
              title="Checks addresses first"
              body="Every address is verified before you send — no guessing whether a made-up address will bounce."
            />
            <Feature
              icon="🗂️"
              tint="accent"
              title="One list, filtered your way"
              body="Filter contacts by company type, role, or what you're asking for, so you always know who's next."
            />
            <Feature
              icon="🔑"
              tint="lime"
              title="Your own AI key"
              body="Bring your own free Gemini key. It's never stored on our servers — just kept in your browser tab."
            />
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="border-t border-line bg-surface px-6 py-20 sm:px-16">
        <div className="mx-auto max-w-2xl">
          <h2 className="mb-8 text-2xl font-bold text-fg">Questions people actually ask</h2>
          <Faq
            q="Will it send emails without me?"
            a="No. Generating a draft never sends anything — you always review and press send yourself, one email at a time."
          />
          <Faq
            q="I saw an “unverified app” warning from Google — is that normal?"
            a="Yes. The Google consent screen is still in testing mode, so you'll see that warning. It's expected, and access is capped at 100 accounts for now."
          />
          <Faq
            q="Do I need to pay for an AI key?"
            a="No — Google's Gemini API has a free tier that's enough for regular use. You paste your own key into Settings; it's never stored on the server."
          />
          <Faq
            q="Why does it need to read my inbox?"
            a="Purely to notice replies, so the tool never emails someone who already wrote back. It only ever looks at threads it started."
          />
        </div>
      </section>

      {/* Closing CTA */}
      <section className="px-6 py-20 sm:px-16" style={{ background: "var(--ink)" }}>
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-5 text-center">
          <h2 className="text-3xl font-bold text-white">Stop sending the same email to everyone.</h2>
          <p className="text-white/70">
            Sign in with Google and have your first real draft ready in a couple of minutes.
          </p>
          <Link href="/login">
            <button
              style={{
                borderRadius: "2rem",
                padding: "0.75rem 2rem",
                fontSize: "16px",
                background: "var(--lime)",
                color: "var(--ink)",
                fontWeight: 700,
              }}
            >
              Get started with Google
            </button>
          </Link>
        </div>
      </section>

      <footer className="flex flex-col items-center gap-3 px-8 py-8 text-center text-xs text-muted sm:flex-row sm:justify-between sm:px-16">
        <div className="flex items-center gap-2 font-semibold text-fg">
          <span className="text-accent">◎</span> Outreach
        </div>
        <span>Built for people doing their own outreach.</span>
        <Link href="/login" className="underline">
          Sign in
        </Link>
      </footer>
    </main>
  );
}
