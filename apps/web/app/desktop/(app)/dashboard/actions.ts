"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import type { Draft, ScheduledOut, SendResult, Target } from "@/lib/types";

export async function getScheduled(): Promise<ScheduledOut> {
  return api<ScheduledOut>("/v1/dashboard/scheduled");
}

export async function savePushSubscription(subscription: {
  endpoint: string;
  keys: Record<string, string>;
}): Promise<void> {
  await api<unknown>("/v1/push/subscriptions", {
    method: "POST",
    body: JSON.stringify(subscription),
  });
}

export async function createTarget(payload: unknown): Promise<Target> {
  const target = await api<Target>("/v1/targets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  revalidatePath("/targets");
  return target;
}

/**
 * Everything optional, and never the address: changing that would carry the
 * verification result, the touch count and the Gmail thread over to a
 * different person. The API refuses it too.
 */
export async function updateTarget(id: string, payload: unknown): Promise<Target> {
  const target = await api<Target>(`/v1/targets/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  revalidatePath("/targets");
  revalidatePath(`/targets/${id}`);
  return target;
}

export async function deleteTarget(id: string): Promise<void> {
  await api<void>(`/v1/targets/${id}`, { method: "DELETE" });
  revalidatePath("/targets");
}

export async function stopTarget(id: string, suppress: boolean): Promise<Target> {
  const target = await api<Target>(
    `/v1/targets/${id}/stop?suppress=${suppress ? "true" : "false"}`,
    { method: "POST" },
  );
  revalidatePath("/targets");
  revalidatePath("/dashboard");
  return target;
}

export async function generateDraft(
  id: string,
  instruction: string,
  templateKey: string,
  geminiKey: string,
): Promise<Draft> {
  if (!geminiKey.trim()) {
    throw new Error("Add your Gemini API key in Settings to use AI features.");
  }
  return api<Draft>(`/v1/targets/${id}/draft`, {
    method: "POST",
    body: JSON.stringify({ instruction, template_key: templateKey }),
    headers: { "X-Gemini-Api-Key": geminiKey.trim() },
  });
}

export async function saveDraft(id: string, subject: string, body: string): Promise<Draft> {
  return api<Draft>(`/v1/targets/${id}/draft`, {
    method: "PUT",
    body: JSON.stringify({ subject, body }),
  });
}

export async function sendNow(id: string): Promise<SendResult> {
  const result = await api<SendResult>(`/v1/targets/${id}/send`, { method: "POST" });
  revalidatePath("/dashboard");
  revalidatePath(`/targets/${id}`);
  return result;
}

export async function scheduleSend(id: string): Promise<SendResult> {
  const result = await api<SendResult>(`/v1/targets/${id}/schedule`, { method: "POST" });
  revalidatePath("/dashboard");
  revalidatePath(`/targets/${id}`);
  return result;
}

/** Take a queued email back out of the queue. The draft itself is untouched. */
export async function cancelScheduledSend(id: string): Promise<void> {
  await api<void>(`/v1/targets/${id}/schedule`, { method: "DELETE" });
  revalidatePath("/dashboard");
  revalidatePath(`/targets/${id}`);
}
