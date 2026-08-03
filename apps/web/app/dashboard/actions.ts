"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import type { Draft, SendResult, Target } from "@/lib/types";

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

export async function generateDraft(id: string, instruction: string): Promise<Draft> {
  return api<Draft>(`/v1/targets/${id}/draft`, {
    method: "POST",
    body: JSON.stringify({ instruction }),
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
