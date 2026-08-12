import ImportWizard from "@/components/ImportWizard";
import { requireAuth } from "@/lib/auth-guard";

/**
 * Desktop opens the import wizard in a modal from the people screen. On a
 * phone a modal holding a five-column preview table is worse than a page, so
 * this stays a route - and it is the one the people screen's Import button
 * links to.
 */
export default async function ImportPage() {
  await requireAuth();

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Import a list</h1>
          <p>
            Upload a CSV or Excel export. Every row is checked before anything is saved —
            duplicates, addresses you have already stopped contacting, and rows still missing the
            one detail an email needs are shown so you can see them before you import.
          </p>
        </div>
      </div>

      <p className="text-sm text-muted">
        Importing adds people to your list as drafts. Nothing is written or sent until you do it
        yourself, one email at a time.
      </p>

      <ImportWizard />
    </>
  );
}
