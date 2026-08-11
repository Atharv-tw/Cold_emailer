"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { attempt, type Result } from "@/lib/result";
import type { Draft, SendResult, Target } from "@/lib/types";

/** As on desktop: refusals come back as values, not throws. See `lib/result.ts`. */

export async function savePushSubscription(subscription: {
  endpoint: string;
  keys: Record<string, string>;
}): Promise<void> {
  await api<unknown>("/v1/push/subscriptions", {
    method: "POST",
    body: JSON.stringify(subscription),
  }).catch(() => {});
}

export async function createTarget(payload: unknown): Promise<Result<Target>> {
  const result = await attempt(() =>
    api<Target>("/v1/targets", { method: "POST", body: JSON.stringify(payload) }),
  );
  if (result.ok) revalidatePath("/targets");
  return result;
}

export async function deleteTarget(id: string): Promise<Result<void>> {
  const result = await attempt(() => api<void>(`/v1/targets/${id}`, { method: "DELETE" }));
  if (result.ok) revalidatePath("/targets");
  return result;
}

export async function stopTarget(id: string, suppress: boolean): Promise<Result<Target>> {
  const result = await attempt(() =>
    api<Target>(`/v1/targets/${id}/stop?suppress=${suppress ? "true" : "false"}`, {
      method: "POST",
    }),
  );
  if (result.ok) {
    revalidatePath("/targets");
    revalidatePath("/dashboard");
  }
  return result;
}

export async function generateDraft(
  id: string,
  instruction: string,
  templateKey: string,
): Promise<Result<Draft>> {
  return attempt(() =>
    api<Draft>(`/v1/targets/${id}/draft`, {
      method: "POST",
      body: JSON.stringify({ instruction, template_key: templateKey }),
    }),
  );
}

export async function saveDraft(
  id: string,
  subject: string,
  body: string,
): Promise<Result<Draft>> {
  return attempt(() =>
    api<Draft>(`/v1/targets/${id}/draft`, {
      method: "PUT",
      body: JSON.stringify({ subject, body }),
    }),
  );
}

export async function sendNow(id: string): Promise<Result<SendResult>> {
  const result = await attempt(() =>
    api<SendResult>(`/v1/targets/${id}/send`, { method: "POST" }),
  );
  if (result.ok) {
    revalidatePath("/dashboard");
    revalidatePath(`/targets/${id}`);
  }
  return result;
}

export async function scheduleSend(id: string): Promise<Result<SendResult>> {
  const result = await attempt(() =>
    api<SendResult>(`/v1/targets/${id}/schedule`, { method: "POST" }),
  );
  if (result.ok) {
    revalidatePath("/dashboard");
    revalidatePath(`/targets/${id}`);
  }
  return result;
}
