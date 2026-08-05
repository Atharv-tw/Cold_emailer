import { redirect } from "next/navigation";

import { auth } from "@/auth";
import ImportWizard from "@/components/ImportWizard";

export default async function ImportPage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Import Contacts</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            Upload a CSV or Excel export to add people to your outreach list.
          </p>
        </div>
      </div>

      <div className="dz-card">
        <div style={{ paddingBottom: "1.5rem", borderBottom: "1px solid var(--line)", marginBottom: "1.5rem" }}>
          <p style={{ color: "var(--fg)", marginBottom: "0.5rem" }}>
            Every row is checked before anything is saved — duplicates, addresses you have already stopped contacting, 
            and rows missing required details are flagged before import.
          </p>
          <p className="muted" style={{ fontSize: "12px" }}>
            Importing adds people to your list as drafts. Nothing is written or sent until you do it yourself, one email at a time.
          </p>
        </div>
        
        <ImportWizard />
      </div>
    </>
  );
}
