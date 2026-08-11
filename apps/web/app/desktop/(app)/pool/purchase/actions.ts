"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { attempt, type Result } from "@/lib/result";
import type { PaymentRequestOut } from "@/lib/types";

/**
 * File a payment claim.
 *
 * The upload goes through the server rather than straight from the browser to
 * object storage: the browser has no credential for the bucket, and giving it
 * one - even a scoped upload URL - would let anyone with an account write
 * objects. The API is where the size cap, the magic-byte sniff and the
 * one-open-claim rule are applied, and none of those are worth having if the
 * client can skip them.
 */
export async function submitPaymentProof(formData: FormData): Promise<Result<void>> {
  // The API's message is written for the person reading it - "that image is
  // larger than 5 MB", "you already have a claim waiting" - so `attempt`
  // passes it through rather than replacing it with something vaguer.
  const result = await attempt(async () => {
    await api<PaymentRequestOut>("/v1/billing/request", { method: "POST", body: formData });
  });
  if (result.ok) {
    revalidatePath("/pool");
    revalidatePath("/pool/purchase");
  }
  return result;
}
