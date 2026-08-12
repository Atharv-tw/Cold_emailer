function Step({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="dz-card">
      <h2 style={{ marginBottom: "0.75rem" }}>{title}</h2>
      <div className="flex flex-col gap-2 text-sm text-fg">{children}</div>
    </div>
  );
}

/**
 * The body of the help screen, shared by both trees.
 *
 * It is several hundred words of guidance that has to say the same thing on a
 * phone as on a laptop, and a second copy under `app/mobile/` would be edited
 * once and then be wrong somewhere. The cards stack at any width, so there is
 * nothing layout-specific to fork - only the page headers differ, and those
 * stay in the two `page.tsx` files.
 */
export default function HelpContent() {
  return (
    <>
      <h2 className="mt-2">Finding an address</h2>

      <Step title="1. Start with the company's email pattern">
        <p>
          Most companies use one consistent pattern for every employee — usually{" "}
          <code>first.last@company.com</code>, <code>first@company.com</code>, or{" "}
          <code>firstlast@company.com</code>. If you already know one person&rsquo;s email at the
          company (from a team page, a GitHub commit, a press release), you&rsquo;ve found the
          pattern for everyone else there too.
        </p>
        <p className="muted">
          Sites like a company&rsquo;s own &ldquo;Team&rdquo; or &ldquo;About&rdquo; page, and public
          GitHub org members, are good places to spot a real example.
        </p>
      </Step>

      <Step title="2. Get the name and role right from LinkedIn">
        <p>
          Search LinkedIn for the company and the kind of role you&rsquo;re after (founder, hiring
          manager, the engineer on the team you want to join). LinkedIn gives you the exact spelling
          of their name — which matters, since a guessed pattern only works if the name is correct —
          and often their &ldquo;About&rdquo; section gives you a specific detail worth mentioning in
          your email.
        </p>
      </Step>

      <Step title="3. Combine the two into a guess">
        <p>
          Take the name from LinkedIn and apply the pattern you found in step 1. If you can&rsquo;t
          find a confirmed example anywhere, try the most common patterns in order:{" "}
          <code>first.last@</code>, <code>first@</code>, <code>flast@</code>,{" "}
          <code>firstl@</code> (first name plus first letter of last name).
        </p>
      </Step>

      <Step title="4. Verify before you send">
        <p>
          Never send on a guess alone. Add them as a contact here and this app checks the address
          for you automatically — it catches typos, invalid domains, and addresses that don&rsquo;t
          actually exist, before anything goes out. If a guess comes back as undeliverable, try the
          next most common pattern rather than sending anyway.
        </p>
      </Step>

      <Step title="5. Write down why you're reaching out">
        <p>
          The single biggest thing that gets a cold email opened isn&rsquo;t the subject line —
          it&rsquo;s having one real, specific reason for writing to that exact person. Their post
          about a technical problem, a project they shipped, a specific line in their bio. That&rsquo;s
          what the &ldquo;What made you pick this person?&rdquo; field is for when you add someone —
          fill it in with something real and the draft will actually sound like you read their page,
          not like a template.
        </p>
      </Step>

      {/*
        The long-form version of the resume disclosure. The profile screen shows
        one line and an info button; anything that needs a paragraph to explain
        lives here, where it can be read by someone who wants it rather than
        skimmed past by everyone who doesn't.
      */}
      <h2 className="mt-4 scroll-mt-6" id="resume">
        Uploading a resume
      </h2>

      <Step title="What happens to the file">
        <p>
          The text of your resume is sent to Google Gemini to be read, using{" "}
          <strong>your own API key</strong> — the one you set from the top bar. What it extracts —
          headline, bio, links, education, projects and roles — is written into the profile form for
          you to check. It is <strong>not</strong> saved to your profile until you press Save, so
          anything the model got wrong is yours to fix first.
        </p>
        <p>
          The file itself is deleted as soon as it has been read, unless you tick{" "}
          <em>keep the original</em>. Everything stored is encrypted at rest.
        </p>
      </Step>

      <Step title="Deleting it later">
        <p>
          <strong>Delete my resume and parsed data</strong> in Settings removes all of it, files
          included. You don&rsquo;t have to keep a resume on file to keep using the app — every field
          the upload fills in can be typed by hand, and the result is identical.
        </p>
      </Step>

      <Step title="If nothing comes back">
        <p>
          Scanned or image-only PDFs can&rsquo;t be read — there is no text in them to extract, only a
          picture of text. If yours came from a scanner or a photo, either export a text PDF from the
          original document or fill the profile in by hand.
        </p>
        <p className="muted">
          A <code>.docx</code> works just as well as a PDF, and is more reliable if your PDF was
          produced by a design tool.
        </p>
      </Step>
    </>
  );
}
