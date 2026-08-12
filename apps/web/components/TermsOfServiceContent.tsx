import { supportEmail } from "@/lib/site";

/** The actual terms text, shared by the desktop and mobile /terms pages so
 *  the two routes can never quietly drift apart. */
export default function TermsOfServiceContent() {
  return (
    <>
      <section className="flex flex-col gap-3">
        <p className="text-fg">
          Outreach is a small, personally-run tool for writing, sending and tracking your own cold
          email. By creating an account you agree to the terms below. If something here doesn&apos;t
          sit right, write in before you rely on the app — see &quot;Contact&quot; below.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>What this is</h2>
        <p className="text-fg">
          A tool that helps you draft and send email one recipient at a time, through your own
          Gmail account, with your own AI key. It is not a bulk-mail or marketing platform, and
          sending limits exist specifically to keep it that way — they are not something to route
          around.
        </p>
        <p className="text-fg">
          The Google consent screen for this app may still show an &quot;unverified app&quot;
          warning while it is in testing, with access capped at a limited number of accounts. That
          is expected and not a sign anything is wrong.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>Your account</h2>
        <p className="text-fg">
          You sign in with Google and are responsible for what happens under your account,
          including anything sent from it. Keep your Google account secure — anyone who can sign
          into it can send email through this app as you.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>Acceptable use</h2>
        <ul className="ml-5 flex list-disc flex-col gap-2 text-fg">
          <li>No spam, unsolicited bulk mail, or anything that would get a real inbox flagged.</li>
          <li>No harassment, deception, or content that&apos;s illegal where you or the recipient are.</li>
          <li>No trying to bypass sending caps, verification checks, or the recipient guard.</li>
          <li>
            If you use the shared contact pool, its contacts are for your own outreach only — not
            for resale, scraping, or bulk export elsewhere.
          </li>
        </ul>
        <p className="text-fg">
          We can suspend or close an account that puts other users&apos; deliverability, the shared
          contact pool, or anyone&apos;s inbox at risk.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>AI-drafted content</h2>
        <p className="text-fg">
          Draft generation uses your own Gemini API key and is billed to that key, not to us. AI
          drafts can be wrong, oddly worded, or inappropriate for a given recipient — nothing is
          sent until you review and press send, and you&apos;re responsible for what you actually
          send.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>The contact pool and payments</h2>
        <p className="text-fg">
          Pool access is bought by hand: you pay via UPI and upload proof, and a person reviews and
          approves the claim — there is no payment gateway processing your card or bank details
          through this app. Because approval is manual, it isn&apos;t instant. Questions about a
          pending or rejected claim go to{" "}
          <a href={`mailto:${supportEmail}`} className="font-medium text-fg underline">
            {supportEmail}
          </a>
          .
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>No warranty</h2>
        <p className="text-fg">
          This is provided as-is, without guarantees of uptime, deliverability, or that a given
          email will land anywhere in particular. To the extent the law allows, we&apos;re not
          liable for lost opportunities, missed replies, or damages arising from using or being
          unable to use the app.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>Changes</h2>
        <p className="text-fg">
          These terms can change as the app changes. The &quot;last updated&quot; date above moves
          when they do. Continuing to use the app after a change means you accept the new terms.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>Contact</h2>
        <p className="text-fg">
          Questions about these terms:{" "}
          <a href={`mailto:${supportEmail}`} className="font-medium text-fg underline">
            {supportEmail}
          </a>
          , or use &quot;Report an issue&quot; in the app footer or in Settings.
        </p>
      </section>
    </>
  );
}
