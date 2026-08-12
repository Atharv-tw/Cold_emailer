import Link from "next/link";

import TargetForm from "@/components/TargetForm";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Profile } from "@/lib/types";

export default async function NewTargetPage() {
  await requireAuth();

  const profile = await api<Profile>("/v1/profile");

  // The API refuses to create a target from a thin profile. Saying so here
  // beats letting someone fill in a long form and then rejecting it.
  if (!profile.completeness.complete) {
    return (
      <>
        <div className="page-header">
          <div>
            <h1>Fill in your profile first</h1>
            <p>
              An email written from an empty profile has nothing specific to say, which is exactly
              the mail that gets deleted.
            </p>
          </div>
        </div>

        <div className="dz-card gap-3">
          <h2>Still needed</h2>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm text-fg">
            {profile.completeness.prompts.map((prompt) => (
              <li key={prompt}>{prompt}</li>
            ))}
          </ul>
          <Link href="/profile">
            <button className="accent w-full">Go to your profile</button>
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Add someone</h1>
          <p>
            Answer these about them and the email gets written from your profile. You read it and
            send it yourself.
          </p>
        </div>
      </div>

      <TargetForm />
    </>
  );
}
