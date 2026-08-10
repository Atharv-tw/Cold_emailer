import Link from "next/link";
import { redirect } from "next/navigation";

import PurchasePanel from "@/components/PurchasePanel";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Billing } from "@/lib/types";

export default async function PurchasePage() {
  await requireAuth();

  const billing = await api<Billing>("/v1/billing");
  // Somebody who already paid has no business on a payment page - most likely
  // they followed a stale link or a bookmark.
  if (billing.is_paid) redirect("/pool");

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Get the contact pool</h1>
          <p>Pay by UPI, send the screenshot, and we approve it by hand</p>
        </div>
        <div className="header-actions">
          <Link href="/pool">
            <button style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}>
              Back
            </button>
          </Link>
        </div>
      </div>

      <div className="max-w-2xl">
        <PurchasePanel billing={billing} />
      </div>
    </>
  );
}
