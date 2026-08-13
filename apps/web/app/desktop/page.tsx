import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import Icon from "@/components/Icon";
import LandingAccordion from "@/components/LandingAccordion";
import { supportEmail } from "@/lib/site";

/* ---------- sub-components (server, no state) ---------- */

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[14px] font-bold"
        style={{
          background: "var(--lime)",
          color: "var(--ink)",
          fontFamily: "var(--font-display)",
        }}
      >
        O
      </span>
      <span
        className="text-[17px] font-bold text-fg"
        style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}
      >
        Outreach
      </span>
    </div>
  );
}

function StepCard({
  number,
  title,
  body,
  tone,
}: {
  number: string;
  title: string;
  body: string;
  tone: string;
}) {
  return (
    <div className="landing-step">
      <div className="landing-step-num" style={{ background: tone }}>
        {number}
      </div>
      <h3 className="text-fg">{title}</h3>
      <p className="text-sm text-muted">{body}</p>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  body,
  iconBg,
  iconFg,
  variant,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  iconBg: string;
  iconFg: string;
  variant?: "hero" | "lime" | "default";
}) {
  const cls = [
    "landing-feature",
    variant === "hero" ? "landing-feature-hero" : "",
    variant === "lime" ? "landing-feature-lime" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={cls}>
      <div
        className="landing-feature-icon"
        style={{ background: iconBg, color: iconFg }}
      >
        {icon}
      </div>
      <h3 className="text-fg">{title}</h3>
      <p className="text-sm text-muted">{body}</p>
    </div>
  );
}

/* ---------- data ---------- */

const FAQ_ITEMS = [
  {
    q: "Will it send emails without me?",
    a: "No. Generating a draft never sends anything — you always review and press send yourself, one email at a time.",
  },
  {
    q: 'I saw an "unverified app" warning from Google — is that normal?',
    a: "Yes. The Google consent screen is still in testing mode, so you'll see that warning. It's expected, and access is capped at 100 accounts for now.",
  },
  {
    q: "Do I need to pay for an AI key?",
    a: "No — Google's Gemini API has a free tier that's enough for regular use. You paste your own key into Settings; it's never stored on the server.",
  },
  {
    q: "Why does it need to read my inbox?",
    a: "Purely to notice replies, so the tool never emails someone who already wrote back. It only ever looks at threads it started.",
  },
];

/* ---------- page ---------- */

export default async function Home() {
  const session = await auth();
  if (session?.apiUser) redirect("/dashboard");

  return (
    <main className="flex min-h-screen flex-col bg-bg">
      {/* ─── Header ─── */}
      <header
        className="sticky top-0 z-10 flex items-center justify-between px-8 py-4 backdrop-blur sm:px-16"
        style={{
          background: "rgba(234, 236, 223, 0.85)",
          borderBottom: "1px solid var(--line)",
        }}
      >
        <Logo />
        <nav className="hidden items-center gap-8 text-sm font-medium text-muted sm:flex">
          <a href="#how-it-works" className="transition-colors hover:text-fg">
            How it works
          </a>
          <a href="#features" className="transition-colors hover:text-fg">
            Features
          </a>
          <a href="#faq" className="transition-colors hover:text-fg">
            FAQ
          </a>
        </nav>
        <Link href="/login">
          <button className="primary" style={{ borderRadius: "999px" }}>
            Sign in
          </button>
        </Link>
      </header>

      {/* ─── Hero ─── */}
      <section
        className="relative mx-auto flex w-full max-w-5xl flex-col items-center gap-8 overflow-hidden px-6 py-16 text-center sm:py-20"
      >
        {/* Subtle gradient glow — centred behind headline */}
        <div
          className="pointer-events-none absolute left-1/2 top-1/3 -translate-x-1/2 -translate-y-1/2"
          style={{
            width: "700px",
            height: "500px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(198, 239, 78, 0.18) 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />

        {/* Badge */}
        <span
          className="relative z-[1] rounded-full px-4 py-1.5 text-xs font-semibold"
          style={{ background: "var(--lime)", color: "var(--accent)" }}
        >
          Built for students &amp; early-career job hunters
        </span>

        {/* Headline */}
        <h1
          className="relative z-[1] max-w-3xl text-5xl font-bold text-fg sm:text-6xl"
          style={{
            fontFamily: "var(--font-display)",
            letterSpacing: "-0.04em",
            lineHeight: 1.08,
          }}
        >
          Cold outreach that
          <br />
          sounds like{" "}
          <span
            style={{
              background: "linear-gradient(135deg, var(--accent), var(--lime-dark))",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            you
          </span>
          .
        </h1>

        {/* Sub copy */}
        <p className="relative z-[1] max-w-xl text-lg text-muted" style={{ lineHeight: 1.7 }}>
          Outreach is an email client that connects to your Google account to send
          emails on your behalf and check your inbox for replies. Every email is
          drafted from what you actually built — nothing sends until you press send.
        </p>

        {/* CTAs */}
        <div className="relative z-[1] flex flex-wrap items-center justify-center gap-4">
          <Link href="/login">
            <button
              className="accent"
              style={{
                borderRadius: "2rem",
                padding: "0.85rem 2.25rem",
                fontSize: "16px",
                fontWeight: 700,
              }}
            >
              Get started with Google
            </button>
          </Link>
          <a href="#how-it-works">
            <button
              className="secondary"
              style={{
                borderRadius: "2rem",
                padding: "0.85rem 2.25rem",
                fontSize: "16px",
              }}
            >
              See how it works ↓
            </button>
          </a>
        </div>

        {/* Trust badges */}
        <div className="relative z-[1] mt-2 flex flex-wrap items-center justify-center gap-3">
          <span className="landing-trust">
            <Icon name="check" size={14} strokeWidth={2.5} /> Free — bring your
            own Gemini key
          </span>
          <span className="landing-trust">
            <Icon name="check" size={14} strokeWidth={2.5} /> Nothing sends
            automatically
          </span>
          <span className="landing-trust">
            <Icon name="check" size={14} strokeWidth={2.5} /> Verifies addresses
            first
          </span>
        </div>
      </section>

      {/* ─── How it works ─── */}
      <section
        id="how-it-works"
        className="border-t border-line bg-surface px-6 py-24 sm:px-16"
      >
        <div className="mx-auto max-w-5xl">
          <div className="mb-12 text-center">
            <span
              className="mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold"
              style={{ background: "var(--lime-tint)", color: "var(--accent)" }}
            >
              Simple setup
            </span>
            <h2
              className="text-3xl font-bold text-fg"
              style={{
                fontFamily: "var(--font-display)",
                letterSpacing: "-0.03em",
              }}
            >
              Four steps. You always press send.
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-muted">
              No sequences to configure, no drip campaigns. Just a straight line from your
              resume to a real, personal email.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <StepCard
              number="1"
              title="Add your resume"
              body="Upload it once. It's read into a headline, bio, projects and experience you can edit."
              tone="var(--ink)"
            />
            <StepCard
              number="2"
              title="Add people to reach"
              body="One at a time, or import a whole list — a founder, a hiring manager, a professor."
              tone="var(--orange)"
            />
            <StepCard
              number="3"
              title="Get a real draft"
              body="Not a template — a real email naming a specific project and why it's relevant to them."
              tone="var(--purple)"
            />
            <StepCard
              number="4"
              title="Review and send"
              body="Nothing goes out until you say so. Replies and bounces are tracked automatically."
              tone="var(--lime-dark)"
            />
          </div>
        </div>
      </section>

      {/* ─── Features ─── */}
      <section id="features" className="px-6 py-24 sm:px-16">
        <div className="mx-auto max-w-5xl">
          <div className="mb-12 text-center">
            <span
              className="mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold"
              style={{ background: "var(--lime-tint)", color: "var(--accent)" }}
            >
              Features
            </span>
            <h2
              className="text-3xl font-bold text-fg"
              style={{
                fontFamily: "var(--font-display)",
                letterSpacing: "-0.03em",
              }}
            >
              Everything cold outreach actually needs
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-muted">
              No CRM to configure, no sequences to design. Just the parts that
              matter.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {/* Hero card — spans 2 cols */}
            <FeatureCard
              variant="hero"
              icon={<Icon name="sparkle" size={22} />}
              title="Drafted from your work"
              body="Emails are written from your resume and projects, not a generic template — every draft names something real you built."
              iconBg="rgba(198, 239, 78, 0.2)"
              iconFg="var(--lime)"
            />

            <FeatureCard
              icon={<Icon name="user" size={20} />}
              title="You stay in control"
              body="Generating a draft never sends it. Review, edit, then press send yourself, every time."
              iconBg="var(--lime-tint)"
              iconFg="var(--accent)"
            />

            <FeatureCard
              icon={<Icon name="mail" size={20} />}
              title="Tracks what happens"
              body="Replies, bounces and follow-ups are tracked automatically, so nobody slips through."
              iconBg="var(--orange-light)"
              iconFg="var(--orange)"
            />

            {/* Lime card */}
            <FeatureCard
              variant="lime"
              icon={<Icon name="check" size={20} />}
              title="Checks addresses first"
              body="Every address is verified before you send — no guessing whether a made-up address will bounce."
              iconBg="rgba(10, 10, 10, 0.1)"
              iconFg="var(--ink)"
            />

            <FeatureCard
              icon={<Icon name="users" size={20} />}
              title="One list, filtered your way"
              body="Filter contacts by company type, role, or what you're asking for, so you always know who's next."
              iconBg="var(--purple-light)"
              iconFg="var(--purple)"
            />


          </div>
        </div>
      </section>

      {/* ─── FAQ ─── */}
      <section
        id="faq"
        className="border-t border-line bg-surface px-6 py-24 sm:px-16"
      >
        <div className="mx-auto max-w-2xl">
          <div className="mb-10 text-center">
            <span
              className="mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold"
              style={{ background: "var(--lime-tint)", color: "var(--accent)" }}
            >
              FAQ
            </span>
            <h2
              className="text-3xl font-bold text-fg"
              style={{
                fontFamily: "var(--font-display)",
                letterSpacing: "-0.03em",
              }}
            >
              Questions people actually ask
            </h2>
          </div>
          <LandingAccordion items={FAQ_ITEMS} />
        </div>
      </section>

      {/* ─── CTA ─── */}
      <section className="landing-cta px-6 py-28 sm:px-16">
        {/* Decorative dots */}
        <div className="landing-dots">
          <div className="landing-dot" style={{ top: "15%", left: "10%" }} />
          <div className="landing-dot" style={{ top: "70%", left: "20%" }} />
          <div className="landing-dot" style={{ top: "25%", right: "15%" }} />
          <div className="landing-dot" style={{ bottom: "20%", right: "10%" }} />
          <div className="landing-dot" style={{ top: "50%", left: "50%" }} />
        </div>

        <div className="relative z-[1] mx-auto flex max-w-2xl flex-col items-center gap-6 text-center">
          <h2
            className="text-4xl font-bold text-white"
            style={{
              fontFamily: "var(--font-display)",
              letterSpacing: "-0.035em",
              lineHeight: 1.15,
            }}
          >
            Stop sending the same
            <br />
            email to everyone.
          </h2>
          <p className="max-w-md text-white/65">
            Sign in with Google and have your first real draft ready in a couple
            of minutes.
          </p>
          <Link href="/login">
            <button
              className="accent"
              style={{
                borderRadius: "2rem",
                padding: "0.85rem 2.5rem",
                fontSize: "16px",
                fontWeight: 700,
              }}
            >
              Get started with Google
            </button>
          </Link>
        </div>
      </section>

      {/* ─── Footer ───
          One row, not two. The upper row used to be the header again - same
          logo, same three section anchors, same Sign in - which made the
          bottom of the page read as somewhere new to start rather than as the
          end. What is left is the part that exists only down here: the legal
          and contact links, beside the line about who this is for. */}
      <footer
        className="flex w-full flex-col items-center gap-4 px-8 py-10 text-center sm:flex-row sm:justify-between sm:gap-6 sm:px-16 sm:text-left"
        style={{ borderTop: "1px solid var(--line)" }}
      >
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:gap-4">
          <Logo />
          <span className="text-xs text-muted">
            Built for people doing their own outreach.
          </span>
        </div>
        <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-muted">
          <Link href="/privacy" className="hover:text-fg">
            Privacy policy
          </Link>
          <Link href="/terms" className="hover:text-fg">
            Terms of service
          </Link>
          <a href={`mailto:${supportEmail}`} className="hover:text-fg">
            Contact us
          </a>
          <a
            href={`mailto:${supportEmail}?subject=${encodeURIComponent("Issue report — Outreach")}`}
            className="hover:text-fg"
          >
            Report an issue
          </a>
        </nav>
      </footer>
    </main>
  );
}
