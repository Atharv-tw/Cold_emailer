import ProfileForm from "@/components/ProfileForm";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Disclosure, Profile, SessionUser } from "@/lib/types";

export default async function ProfilePage() {
  const session = await requireAuth();

  // The disclosure is served by the API rather than written here, so the
  // wording cannot drift from what the upload endpoint actually does.
  const [profile, disclosure, user] = await Promise.all([
    api<Profile>("/v1/profile"),
    api<Disclosure>("/v1/resumes/disclosure"),
    api<SessionUser>("/v1/auth/me").catch(() => session.apiUser!),
  ]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Your profile</h1>
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
