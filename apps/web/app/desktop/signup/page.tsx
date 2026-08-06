import Link from "next/link";

export default function SignupPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6">
      <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-8 text-center shadow-sm">
        <div className="mb-6 flex items-center justify-center gap-2 text-xl font-bold text-accent">
          <span className="text-2xl">◎</span> Outreach
        </div>
        <h1 className="mb-2 text-fg">There&rsquo;s nothing to sign up for</h1>
        <p className="mb-6 text-sm text-muted">
          Accounts are created automatically the first time you sign in with Google — there&rsquo;s
          no separate form to fill out.
        </p>
        <Link href="/login">
          <button className="primary" style={{ borderRadius: "0.75rem", padding: "0.75rem 1.5rem" }}>
            Continue with Google
          </button>
        </Link>
      </div>
    </main>
  );
}
