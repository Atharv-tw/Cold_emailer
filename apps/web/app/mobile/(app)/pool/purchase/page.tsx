import { redirect } from "next/navigation";

import PurchasePanel from "@/components/PurchasePanel";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Billing } from "@/lib/types";

export default async function PurchasePage() {
  await requireAuth();

  const billing = await api<Billing>("/v1/billing");
  if (billing.is_paid) redirect("/pool");

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Get the contact pool</h1>
        </div>
      </div>

      <PurchasePanel billing={billing} />
    </>
  );
}
