import { supportEmail } from "@/lib/site";

/** The actual policy text, shared by the desktop and mobile /privacy pages
 *  so the two routes can never quietly drift apart. */
export default function PrivacyPolicyContent() {
  return (
    <>
      <section className="flex flex-col gap-3">
        <p className="text-fg">
          Outreach is a small, personally-run tool for writing, sending and tracking your own cold
          email through your own Gmail account. This page explains what it collects, why, and how
          to make it stop.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>What we collect</h2>
        <p className="text-fg">
          <strong>Your Google account.</strong> Signing in with Google gives us your name, email
          address and profile picture, and asks for a few Gmail permissions:
        </p>
        <ul className="ml-5 flex list-disc flex-col gap-2 text-fg">
          <li>
            <strong>Send email</strong> — so the app can send a draft on your behalf. Nothing is
            ever sent automatically; every email is reviewed and dispatched by you, one at a time.
          </li>
          <li>
            <strong>Read email</strong> — used only to notice replies on threads this app started,
            so it never emails someone who has already written back. It does not read the rest of
            your inbox.
          </li>
          <li>
            <strong>Calendar (optional)</strong> — if you turn on reminders, upcoming events are
            mirrored in so the app can nudge you about follow-ups. You can leave this off entirely.
          </li>
        </ul>
        <p className="text-fg">
          <strong>What you add yourself.</strong> Your outreach targets and contact lists, any
          resume or profile details you upload (used to help draft emails, and deletable at any
          time from Settings), and message templates you write.
        </p>
        <p className="text-fg">
          <strong>Your AI key.</strong> If you use AI drafting, you paste in your own Gemini API
          key. It is kept only in your browser for that session and is never sent to or stored on
          our server — there is no server-side key.
        </p>
        <p className="text-fg">
          <strong>Payment proof.</strong> If you buy access to the shared contact pool, the UPI
          reference and screenshot you upload are stored so a human can verify the payment. Nothing
          else about a purchase is collected — there is no card or bank data involved.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>What we don&apos;t do</h2>
        <ul className="ml-5 flex list-disc flex-col gap-2 text-fg">
          <li>We don&apos;t sell or rent your data to anyone.</li>
          <li>We don&apos;t send email without you pressing send.</li>
          <li>We don&apos;t use your Gmail access for anything but sending and reply-detection.</li>
          <li>We don&apos;t share your Gemini key — it never leaves your browser.</li>
        </ul>
      </section>

      <section className="flex flex-col gap-3">
        <h2>Where it&apos;s stored</h2>
        <p className="text-fg">
          Your Google refresh token is encrypted at rest and only decrypted server-side, per
          request, to make an API call on your behalf. Resumes and payment screenshots are stored
          in object storage used only for this app. Resume data is deleted immediately when you
          use the &quot;Delete my resume and parsed data&quot; control in Settings.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>Third parties involved</h2>
        <p className="text-fg">
          Google (sign-in, Gmail, Calendar), Google&apos;s Gemini API (only if you supply a key),
          QuickEmailVerification (checks whether an address you&apos;re about to email looks real,
          before you send to it), and Cloudflare R2 (file storage). Each only sees what it needs to
          do its one job.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>Deleting your data</h2>
        <p className="text-fg">
          You can delete your uploaded resume and everything extracted from it at any time from
          Settings. To remove your account and everything else tied to it, email{" "}
          <a href={`mailto:${supportEmail}`} className="font-medium text-fg underline">
            {supportEmail}
          </a>{" "}
          and it will be handled directly.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>Changes</h2>
        <p className="text-fg">
          If this policy changes in a way that matters, the &quot;last updated&quot; date at the
          top of this page will move. There is no mailing list announcing revisions.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2>Questions</h2>
        <p className="text-fg">
          Reach out any time at{" "}
          <a href={`mailto:${supportEmail}`} className="font-medium text-fg underline">
            {supportEmail}
          </a>
          , or use &quot;Report an issue&quot; in the app footer or in Settings.
        </p>
      </section>
    </>
  );
}
