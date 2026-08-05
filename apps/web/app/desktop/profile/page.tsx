import { redirect } from "next/navigation";

import { auth } from "@/auth";
import ProfileForm from "@/components/ProfileForm";
import { api } from "@/lib/api";
import type { Disclosure, Profile } from "@/lib/types";

export default async function ProfilePage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const [profile, disclosure] = await Promise.all([
    api<Profile>("/v1/profile"),
    api<Disclosure>("/v1/resumes/disclosure"),
  ]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Your Profile & Settings</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            This is what your emails get written from. The more specific it is, the less the mail reads like a template.
          </p>
        </div>
      </div>

      <div className="dz-card">
        <ProfileForm profile={profile} disclosure={disclosure} />
      </div>
    </>
  );
}
