import Link from "next/link";

export default function ForgotPasswordPage() {
  return (
    <main className="flex min-h-[100dvh] items-center justify-center px-5">
      <div className="w-full max-w-sm rounded-2xl border border-line bg-surface p-6 text-center shadow-sm">
        <div
          className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-full text-[20px] font-bold"
          style={{ background: "var(--lime)", color: "var(--ink)", fontFamily: "var(--font-display)" }}
        >
          O
        </div>
        <h1 className="mb-2 text-fg">There&rsquo;s no password to reset</h1>
        <p className="mb-6 text-sm text-muted">
          This app doesn&rsquo;t use passwords at all — sign in with Google instead, and you&rsquo;re
          back in.
        </p>
        <Link href="/login">
          <button className="accent w-full" style={{ borderRadius: "0.875rem", padding: "0.85rem" }}>
            Sign in with Google
          </button>
        </Link>
      </div>
    </main>
  );
}
