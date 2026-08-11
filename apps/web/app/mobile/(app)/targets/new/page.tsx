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

  // The API refuses to create a target from a thin profile. Saying so here
  // beats letting someone fill in a long form and then rejecting it.
  if (!profile.completeness.complete) {
    return (
      <main>
        <h1>Fill in your profile first</h1>
        <p>
          An email written from an empty profile has nothing specific to say,
          which is exactly the mail that gets deleted. Still needed:
        </p>
        <ul>
          {profile.completeness.prompts.map((prompt) => (
            <li key={prompt}>{prompt}</li>
          ))}
        </ul>
        <p>
          <Link href="/profile">Go to your profile</Link>
        </p>
      </main>
    );
  }

  return (
    <main>
      <h1>Add someone</h1>
      <p>
        Answer these about them and the email gets written from your profile.
        You read it and send it yourself.
      </p>
      <TargetForm />
    </main>
  );
}
