import Link from "next/link";
import { redirect } from "next/navigation";

import { auth, signIn } from "@/auth";

export default async function LoginPage() {
  const session = await auth();
  if (session?.apiUser) redirect("/dashboard");

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6">
      <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-8 shadow-sm">
        <Link href="/" className="mb-6 flex items-center gap-2 text-xl font-bold text-accent">
          <span className="text-2xl">◎</span> Outreach
        </Link>

        <h1 className="mb-1 text-fg">Sign in</h1>
        <p className="mb-6 text-sm text-muted">
          There&rsquo;s no separate account to create — signing in with Google sets one up
          automatically the first time.
        </p>

        <form
          action={async () => {
            "use server";
            await signIn("google", { redirectTo: "/dashboard" });
          }}
        >
          <button
            type="submit"
            className="primary"
            style={{ width: "100%", borderRadius: "0.75rem", padding: "0.75rem" }}
          >
            Continue with Google
          </button>
        </form>

        <div className="mt-6 flex flex-col gap-3 text-xs text-muted">
          <p>
            <strong className="text-fg">You may see an &ldquo;unverified app&rdquo; warning.</strong>{" "}
            That&rsquo;s expected while the Google consent screen is in testing mode — it isn&rsquo;t
            a sign something is wrong. Access is capped at 100 accounts for now.
          </p>
          <p>
            Getting <strong className="text-fg">&ldquo;Access blocked&rdquo;</strong> or{" "}
            <code>Error 403: access_denied</code> instead? That account hasn&rsquo;t been added as
            a tester yet. Ask for an invite rather than retrying.
          </p>
          <p>
            Reading your inbox is what stops the tool emailing someone who already replied — it
            only ever looks at threads it started.
          </p>
        </div>

        <p className="mt-6 text-center text-xs text-muted">
          <Link href="/signup" className="underline">
            New here?
          </Link>
          {" · "}
          <Link href="/forgot-password" className="underline">
            Can&rsquo;t sign in?
          </Link>
        </p>
      </div>
    </main>
  );
}
