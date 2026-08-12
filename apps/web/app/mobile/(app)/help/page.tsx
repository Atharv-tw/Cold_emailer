import HelpContent from "@/components/HelpContent";
import { requireAuth } from "@/lib/auth-guard";

export default async function HelpPage() {
  await requireAuth();

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Help</h1>
          <p>
            How to actually find someone&rsquo;s email address before you write to them — and what
            happens to a resume you upload.
          </p>
        </div>
      </div>

      <HelpContent />
    </>
  );
}
