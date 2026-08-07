import ProfileForm from "@/components/ProfileForm";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Disclosure, Profile, SessionUser } from "@/lib/types";

export default async function ProfilePage() {
  const session = await requireAuth();

  const [profile, disclosure, user] = await Promise.all([
    api<Profile>("/v1/profile"),
    api<Disclosure>("/v1/resumes/disclosure"),
    api<SessionUser>("/v1/auth/me").catch(() => session.apiUser),
  ]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Settings</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            This is what your emails get written from. The more specific it is, the less the mail
            reads like a template.
          </p>
        </div>
      </div>

      <div className="dz-card">
        <ProfileForm profile={profile} disclosure={disclosure} user={user} />
      </div>
    </>
  );
}
