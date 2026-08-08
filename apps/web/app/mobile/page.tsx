import { redirect } from "next/navigation";

import { auth, signIn } from "@/auth";

export default async function Home() {
  const session = await auth();
  if (session?.apiUser) redirect("/dashboard");

  return (
    <main>
      <h1>Cold outreach</h1>
      <p>
        Sign in with Google, add your resume, and add the people you want to
        reach. The email gets written for you; nothing sends until you press
        send.
      </p>

      <form
        action={async () => {
          "use server";
          await signIn("google", { redirectTo: "/dashboard" });
        }}
      >
        <button type="submit" className="primary">
          Continue with Google
        </button>
      </form>

      <div className="note">
        <strong>You will see an &ldquo;unverified app&rdquo; warning.</strong>{" "}
        That is expected while the Google consent screen is in testing mode, and
        it is not a sign that something is wrong. It also means access is capped
        at 100 accounts for now.
      </div>

      <div className="note">
        Getting <strong>&ldquo;Access blocked&rdquo;</strong> or{" "}
        <code>Error 403: access_denied</code> instead? That account has not been
        added as a tester yet, which is a separate list from the warning above.
        Ask for an invite rather than retrying — nothing you do on this screen
        will change it.
      </div>

      <div className="note">
        Reading your inbox is what stops the tool emailing someone who already
        replied. It only ever looks at threads it started.
      </div>
    </main>
  );
}
