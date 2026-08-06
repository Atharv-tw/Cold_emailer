import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import TargetForm from "@/components/TargetForm";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";

export default async function NewTargetPage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const profile = await api<Profile>("/v1/profile");

  if (!profile.completeness.complete) {
    return (
      <>
        <div className="page-header">
          <div>
            <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Action Required</h1>
            <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
              Complete your profile before adding contacts.
            </p>
          </div>
        </div>
        
        <div className="dz-card" style={{ background: "var(--warning-light)", border: "1px solid #fde68a" }}>
          <h2 style={{ fontSize: "18px", color: "var(--warning)", marginBottom: "1rem" }}>Profile Incomplete</h2>
          <p style={{ marginBottom: "1rem" }}>
            An email written from an empty profile has nothing specific to say,
            which is exactly the mail that gets deleted. Still needed:
          </p>
          <ul style={{ marginLeft: "1.5rem", marginBottom: "1.5rem" }}>
            {profile.completeness.prompts.map((prompt) => (
              <li key={prompt} style={{ marginBottom: "0.25rem" }}>{prompt}</li>
            ))}
          </ul>
          <Link href="/profile">
            <button className="primary">Go to your profile</button>
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Add Contact</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            Answer these questions and the email will be drafted automatically.
          </p>
        </div>
        <div className="header-actions">
          <Link href="/targets">
            <button className="secondary" style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}>
              ← Cancel
            </button>
          </Link>
        </div>
      </div>

      <div className="dz-card">
        <TargetForm />
      </div>
    </>
  );
}
