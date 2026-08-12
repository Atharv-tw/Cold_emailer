import Link from "next/link";
import { redirect } from "next/navigation";

import { auth, signIn } from "@/auth";

/**
 * The mobile sign-in screen.
 *
 * Same three caveats the desktop card carries - the unverified-app warning,
 * the tester-list 403, and why the app reads your inbox - but as separate
 * cards rather than a paragraph stack. On a phone the desktop treatment is
 * one unbroken wall of small text that gets scrolled past; each of these is
 * something somebody actually hits, and they have to be findable when they do.
 */
export default async function LoginPage() {
  const session = await auth();
  if (session?.apiUser) redirect("/dashboard");

  return (
    <main className="flex min-h-[100dvh] flex-col items-center justify-center px-5 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div
            className="mb-5 flex h-14 w-14 items-center justify-center rounded-full text-[24px] font-bold"
            style={{ background: "var(--lime)", color: "var(--ink)", fontFamily: "var(--font-display)" }}
          >
            O
          </div>
          <h1 className="mb-2 text-fg">Sign in</h1>
          <p className="text-[15px] leading-relaxed text-muted">
            There&rsquo;s no separate account to create — signing in with Google sets one up
            automatically the first time.
          </p>
        </div>

        <form
          action={async () => {
            "use server";
            await signIn("google", { redirectTo: "/dashboard" });
          }}
        >
          <button
            type="submit"
            className="accent w-full"
            style={{ borderRadius: "0.875rem", padding: "0.9rem", fontSize: "16px" }}
          >
            Continue with Google
          </button>
        </form>

        <div className="mt-8 flex flex-col gap-3">
          <div className="dz-card gap-1 p-4">
            <strong className="text-[14px] font-semibold text-fg">Unverified app warning</strong>
            <p className="text-[13px] leading-relaxed">
              That&rsquo;s expected while the Google consent screen is in testing mode, and it
              isn&rsquo;t a sign something is wrong. Access is capped at 100 accounts for now.
            </p>
          </div>

          <div className="dz-card gap-1 p-4">
            <strong className="text-[14px] font-semibold text-fg">Access blocked?</strong>
            <p className="text-[13px] leading-relaxed">
              Getting <code>Error 403: access_denied</code> means that account hasn&rsquo;t been
              added as a tester yet. Ask for an invite rather than retrying — nothing on this
              screen will change it.
            </p>
          </div>

          <div className="dz-card gap-1 p-4">
            <strong className="text-[14px] font-semibold text-fg">Inbox reading</strong>
            <p className="text-[13px] leading-relaxed">
              Reading your inbox is what stops the tool emailing someone who already replied. It
              only ever looks at threads it started.
            </p>
          </div>
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
