import { redirect } from "next/navigation";

import { auth } from "@/auth";
import ProfileForm from "@/components/ProfileForm";
import { api } from "@/lib/api";
import type { Disclosure, Profile } from "@/lib/types";

export default async function ProfilePage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  // The disclosure is served by the API rather than written here, so the
  // wording cannot drift from what the upload endpoint actually does.
  const [profile, disclosure] = await Promise.all([
    api<Profile>("/v1/profile"),
    api<Disclosure>("/v1/resumes/disclosure"),
  ]);

  return (
    <main>
      <h1>Your profile</h1>
      <p>
        This is what your emails get written from. The more specific it is, the
        less the mail reads like a template.
      </p>
      <ProfileForm profile={profile} disclosure={disclosure} />
    </main>
  );
}
