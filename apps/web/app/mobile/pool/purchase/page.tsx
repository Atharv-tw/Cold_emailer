import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import PurchasePanel from "@/components/PurchasePanel";
import { api } from "@/lib/api";
import type { Billing } from "@/lib/types";

export default async function PurchasePage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const billing = await api<Billing>("/v1/billing");
  if (billing.is_paid) redirect("/pool");

  return (
    <main>
      <h1>Get the contact pool</h1>
      <p>
        <Link href="/pool">← Back</Link>
      </p>
      <PurchasePanel billing={billing} />
    </main>
  );
}
