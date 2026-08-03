import { redirect } from "next/navigation";

import { auth, signOut } from "@/auth";

export default async function Dashboard() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const user = session.apiUser;

  return (
    <main>
      <h1>Signed in as {user.email}</h1>
      <p>
        {user.connected
          ? "Google account connected."
          : "Google account is not connected - sending is disabled until it is."}
      </p>

      {user.missing_scopes.length > 0 && (
        <div className="note">
          <strong>Some permissions were not granted.</strong> Without{" "}
          <code>gmail.readonly</code> the app can send but cannot see replies,
          which is the one state it must not run in. Sign in again and leave
          every box ticked.
        </div>
      )}

      {!user.profile_complete && (
        <div className="note">
          Your profile is empty, so there is nothing to write an email from.
          Upload a resume or fill the form in by hand before adding targets.
        </div>
      )}

      <form
        action={async () => {
          "use server";
          await signOut({ redirectTo: "/" });
        }}
      >
        <button type="submit">Sign out</button>
      </form>
    </main>
  );
}
