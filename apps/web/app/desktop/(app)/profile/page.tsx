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
          <h1>Profile</h1>
          <p>
            This is what your emails get written from. The more specific it is, the less the mail
            reads like a template.
          </p>
        </div>
      </div>

      <ProfileForm profile={profile} disclosure={disclosure} user={user} />
    </>
  );
}
