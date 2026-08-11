import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import ImportWizard from "@/components/ImportWizard";

export default async function ImportPage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  return (
    <main>
      <h1>Import a list</h1>
      <p>
        Upload a CSV or Excel export. Every row is checked before anything is
        saved — duplicates, addresses you have already stopped contacting, and
        rows still missing the one detail an email needs are shown so you can
        see them before you import.
      </p>
      <p className="muted">
        Importing adds people to your list as drafts. Nothing is written or sent
        until you do it yourself, one email at a time.
      </p>

      <ImportWizard />

      <p>
        <Link href="/dashboard">← Back to the dashboard</Link>
      </p>
    </main>
  );
}
