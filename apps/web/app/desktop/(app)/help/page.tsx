import { requireAuth } from "@/lib/auth-guard";

function Step({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="dz-card">
      <h2 style={{ marginBottom: "0.75rem" }}>{title}</h2>
      <div className="flex flex-col gap-2 text-sm text-fg">{children}</div>
    </div>
  );
}

export default async function HelpPage() {
  await requireAuth();

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Help</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            How to actually find someone&rsquo;s email address before you write to them.
          </p>
        </div>
      </div>

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
    </>
  );
}
