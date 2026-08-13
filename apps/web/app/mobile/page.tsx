import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import Icon from "@/components/Icon";
import LandingAccordion from "@/components/LandingAccordion";
import { supportEmail } from "@/lib/site";

/**
 * The mobile marketing landing.
 *
 * This route used to be a sign-in splash, which meant a phone had no landing
 * page at all and `/login` did not exist - anyone arriving from a shared link
 * got the sign-in form with none of the explanation around it. The splash's
 * content now lives at `/login`, where the desktop tree already put it, and
 * this is the page that has to answer "what is this" for somebody who has
 * never seen it.
 *
 * Copy is shared with the desktop landing verbatim. Layout is not: one column
 * throughout, the section paddings roughly halved, and the desktop hero's
 * 700px glow dropped rather than scaled - a blur that wide on a 375px screen
 * is a flat wash over the headline instead of a highlight behind it.
 */

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

const STEPS: { number: string; title: string; body: string; tone: string }[] = [
  {
    number: "1",
    title: "Add your resume",
    body: "Upload it once. It's read into a headline, bio, projects and experience you can edit.",
    tone: "var(--ink)",
  },
  {
    number: "2",
    title: "Add people to reach",
    body: "One at a time, or import a whole list — a founder, a hiring manager, a professor.",
    tone: "var(--orange)",
  },
  {
    number: "3",
    title: "Get a real draft",
    body: "Not a template — a real email naming a specific project and why it's relevant to them.",
    tone: "var(--purple)",
  },
  {
    number: "4",
    title: "Review and send",
    body: "Nothing goes out until you say so. Replies and bounces are tracked automatically.",
    tone: "var(--lime-dark)",
  },
];

const FEATURES: {
  icon: React.ReactNode;
  title: string;
  body: string;
  iconBg: string;
  iconFg: string;
}[] = [
  {
    icon: <Icon name="sparkle" size={20} />,
    title: "Drafted from your work",
    body: "Emails are written from your resume and projects, not a generic template — every draft names something real you built.",
    iconBg: "var(--lime-tint)",
    iconFg: "var(--accent)",
  },
  {
    icon: <Icon name="user" size={20} />,
    title: "You stay in control",
    body: "Generating a draft never sends it. Review, edit, then press send yourself, every time.",
    iconBg: "var(--lime-tint)",
    iconFg: "var(--accent)",
  },
  {
    icon: <Icon name="mail" size={20} />,
    title: "Tracks what happens",
    body: "Replies, bounces and follow-ups are tracked automatically, so nobody slips through.",
    iconBg: "var(--orange-light)",
    iconFg: "var(--orange)",
  },
  {
    icon: <Icon name="check" size={20} />,
    title: "Checks addresses first",
    body: "Every address is verified before you send — no guessing whether a made-up address will bounce.",
    iconBg: "var(--accent-light)",
    iconFg: "var(--accent)",
  },
  {
    icon: <Icon name="users" size={20} />,
    title: "One list, filtered your way",
    body: "Filter contacts by company type, role, or what you're asking for, so you always know who's next.",
    iconBg: "var(--purple-light)",
    iconFg: "var(--purple)",
  },
];

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
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
    </div>
  );
}

function SectionHeading({ eyebrow, title, body }: { eyebrow: string; title: string; body?: string }) {
  return (
    <div className="mb-8 text-center">
      <span
        className="mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold"
        style={{ background: "var(--lime-tint)", color: "var(--accent)" }}
      >
        {eyebrow}
      </span>
      <h2
        className="text-2xl font-bold text-fg"
        style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.03em", lineHeight: 1.2 }}
      >
        {title}
      </h2>
      {body && <p className="mt-3 text-sm text-muted">{body}</p>}
    </div>
  );
}

export default async function Home() {
  const session = await auth();
  if (session?.apiUser) redirect("/dashboard");

  return (
    <main className="flex min-h-[100dvh] flex-col bg-bg">
      <header
        className="sticky top-0 z-10 flex items-center justify-between px-5 py-3 backdrop-blur"
        style={{ background: "rgba(234, 236, 223, 0.85)", borderBottom: "1px solid var(--line)" }}
      >
        <Logo />
        <Link href="/login">
          <button className="primary" style={{ borderRadius: "999px", padding: "0.45rem 1.1rem" }}>
            Sign in
          </button>
        </Link>
      </header>

      {/* ─── Hero ─── */}
      <section className="flex flex-col items-center gap-6 overflow-hidden px-5 py-12 text-center">
        <span
          className="rounded-full px-4 py-1.5 text-xs font-semibold"
          style={{ background: "var(--lime)", color: "var(--accent)" }}
        >
          Built for students &amp; early-career job hunters
        </span>

        <h1
          className="text-[34px] font-bold text-fg"
          style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.04em", lineHeight: 1.1 }}
        >
          Cold outreach that sounds like{" "}
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

        <p className="text-[15px] text-muted" style={{ lineHeight: 1.65 }}>
          Outreach is an email client that connects to your Google account to send emails
          on your behalf and check your inbox for replies. Every email is drafted from what
          you actually built. Nothing sends until you press send.
        </p>

        <div className="flex w-full flex-col gap-3">
          <Link href="/login" className="w-full">
            <button
              className="accent w-full"
              style={{ borderRadius: "2rem", padding: "0.85rem", fontSize: "16px", fontWeight: 700 }}
            >
              Get started with Google
            </button>
          </Link>
          <a href="#how-it-works" className="w-full">
            <button className="secondary w-full" style={{ borderRadius: "2rem", padding: "0.85rem", fontSize: "16px" }}>
              See how it works ↓
            </button>
          </a>
        </div>

        <div className="mt-1 flex flex-col items-center gap-2">
          <span className="landing-trust">
            <Icon name="check" size={14} strokeWidth={2.5} /> Free — bring your own Gemini key
          </span>
          <span className="landing-trust">
            <Icon name="check" size={14} strokeWidth={2.5} /> Nothing sends automatically
          </span>
          <span className="landing-trust">
            <Icon name="check" size={14} strokeWidth={2.5} /> Verifies addresses first
          </span>
        </div>
      </section>

      {/* ─── How it works ─── */}
      <section id="how-it-works" className="scroll-mt-16 border-t border-line bg-surface px-5 py-14">
        <SectionHeading
          eyebrow="Simple setup"
          title="Four steps. You always press send."
          body="No sequences to configure, no drip campaigns. Just a straight line from your resume to a real, personal email."
        />
        <div className="flex flex-col gap-4">
          {STEPS.map((step) => (
            <div key={step.number} className="landing-step">
              <div className="landing-step-num" style={{ background: step.tone }}>
                {step.number}
              </div>
              <h3 className="text-fg">{step.title}</h3>
              <p className="text-sm text-muted">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Features ─── */}
      <section id="features" className="scroll-mt-16 px-5 py-14">
        <SectionHeading
          eyebrow="Features"
          title="Everything cold outreach actually needs"
          body="No CRM to configure, no sequences to design. Just the parts that matter."
        />
        <div className="flex flex-col gap-4">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="landing-feature">
              <div
                className="landing-feature-icon"
                style={{ background: feature.iconBg, color: feature.iconFg }}
              >
                {feature.icon}
              </div>
              <h3 className="text-fg">{feature.title}</h3>
              <p className="text-sm text-muted">{feature.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── FAQ ─── */}
      <section id="faq" className="scroll-mt-16 border-t border-line bg-surface px-5 py-14">
        <SectionHeading eyebrow="FAQ" title="Questions people actually ask" />
        <LandingAccordion items={FAQ_ITEMS} />
      </section>

      {/* ─── CTA ─── */}
      <section className="landing-cta px-5 py-16">
        <div className="landing-dots">
          <div className="landing-dot" style={{ top: "15%", left: "10%" }} />
          <div className="landing-dot" style={{ top: "70%", left: "20%" }} />
          <div className="landing-dot" style={{ top: "25%", right: "15%" }} />
          <div className="landing-dot" style={{ bottom: "20%", right: "10%" }} />
        </div>

        <div className="relative z-[1] flex flex-col items-center gap-5 text-center">
          <h2
            className="text-[28px] font-bold text-white"
            style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.035em", lineHeight: 1.2 }}
          >
            Stop sending the same email to everyone.
          </h2>
          <p className="text-sm text-white/65">
            Sign in with Google and have your first real draft ready in a couple of minutes.
          </p>
          <Link href="/login" className="w-full">
            <button
              className="accent w-full"
              style={{ borderRadius: "2rem", padding: "0.85rem", fontSize: "16px", fontWeight: 700 }}
            >
              Get started with Google
            </button>
          </Link>
        </div>
      </section>

      {/* ─── Footer ───
          One block, matching desktop. The section anchors went with it: they
          pointed back up a page the reader has just scrolled through, and the
          sections they name are the thing directly above. */}
      <footer
        className="flex flex-col items-center gap-4 px-5 py-10 text-center"
        style={{ borderTop: "1px solid var(--line)" }}
      >
        <Logo />
        <nav className="flex w-full flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted">
          <Link href="/privacy">Privacy policy</Link>
          <Link href="/terms">Terms of service</Link>
          <a href={`mailto:${supportEmail}`}>Contact us</a>
          <a href={`mailto:${supportEmail}?subject=${encodeURIComponent("Issue report — Outreach")}`}>
            Report an issue
          </a>
        </nav>
        <span className="text-xs text-muted">Built for people doing their own outreach.</span>
      </footer>
    </main>
  );
}
