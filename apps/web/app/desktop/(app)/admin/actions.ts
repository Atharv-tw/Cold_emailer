"use server";

import { revalidatePath } from "next/cache";

import { api, ApiError } from "@/lib/api";
import type { AdminPayment, AdminUserRow } from "@/lib/types";

type Result<T> = { ok: true; data: T } | { ok: false; error: string };

async function attempt<T>(run: () => Promise<T>): Promise<Result<T>> {
  try {
    return { ok: true, data: await run() };
  } catch (error) {
    // A 403 here means the account lost the operator role between rendering
    // the page and clicking - worth showing rather than swallowing.
    if (error instanceof ApiError) return { ok: false, error: error.message };
    throw error;
  }
}

export async function reviewPayment(
  paymentId: string,
  approve: boolean,
  note: string,
): Promise<Result<AdminPayment>> {
  const result = await attempt(() =>
    api<AdminPayment>(`/v1/admin/payments/${paymentId}/${approve ? "approve" : "reject"}`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  );
  if (result.ok) revalidatePath("/admin");
  return result;
}

export async function setUserPlan(
  userId: string,
  isPaid: boolean,
): Promise<Result<AdminUserRow>> {
  // Only `is_paid` crosses this boundary. The API's body model declares that
  // field and nothing else, so `is_admin` is not settable from here or from
  // anywhere else a request can reach.
  const result = await attempt(() =>
    api<AdminUserRow>(`/v1/admin/users/${userId}/plan`, {
      method: "POST",
      body: JSON.stringify({ is_paid: isPaid }),
    }),
  );
  if (result.ok) revalidatePath("/admin");
  return result;
}
