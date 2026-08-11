import { redirect } from "next/navigation";
import { auth, signIn } from "@/auth";

export default async function Home() {
  const session = await auth();
  if (session?.apiUser) redirect("/mobile/dashboard");

  return (
    <main className="min-h-[100dvh] flex flex-col items-center justify-center bg-[var(--ink)] p-6 text-white text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full text-[28px] font-bold mb-6" style={{ background: "var(--lime)", color: "var(--ink)", fontFamily: "var(--font-display)" }}>
        O
      </div>
      
      <h1 className="text-3xl font-bold mb-4" style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}>Cold outreach</h1>
      
      <p className="text-white/70 mb-10 max-w-sm text-[15px] leading-relaxed">
        Sign in with Google, add your resume, and add the people you want to
        reach. The email gets written for you; nothing sends until you press send.
      </p>

      <form
        className="w-full max-w-sm mb-12"
        action={async () => {
          "use server";
          await signIn("google", { redirectTo: "/mobile/dashboard" });
        }}
      >
        <button type="submit" className="w-full py-[14px] rounded-xl text-[var(--ink)] font-bold text-[16px] transition-colors active:opacity-80" style={{ background: "var(--lime)" }}>
          Continue with Google
        </button>
      </form>

      <div className="flex flex-col gap-4 max-w-sm text-left w-full">
        <div className="bg-white/5 border border-white/10 rounded-2xl p-4 text-[13px] text-white/80 leading-relaxed">
          <strong className="text-white block mb-1 font-semibold text-[14px]">Unverified app warning</strong>
          That is expected while the Google consent screen is in testing mode, and it is not a sign that something is wrong. Access is capped at 100 accounts for now.
        </div>

        <div className="bg-white/5 border border-white/10 rounded-2xl p-4 text-[13px] text-white/80 leading-relaxed">
          <strong className="text-white block mb-1 font-semibold text-[14px]">Access blocked?</strong>
          That account has not been added as a tester yet. Ask for an invite rather than retrying — nothing you do on this screen will change it.
        </div>

        <div className="bg-white/5 border border-white/10 rounded-2xl p-4 text-[13px] text-white/80 leading-relaxed">
          <strong className="text-white block mb-1 font-semibold text-[14px]">Inbox reading</strong>
          Reading your inbox is what stops the tool emailing someone who already replied. It only ever looks at threads it started.
        </div>
      </div>
    </main>
  );
}
