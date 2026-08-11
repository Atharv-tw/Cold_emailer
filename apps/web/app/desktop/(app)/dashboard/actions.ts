"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { attempt, refuse, type Result } from "@/lib/result";
import type { Draft, ScheduledOut, SendResult, Target } from "@/lib/types";

/**
 * Every action here returns a `Result` rather than throwing.
 *
 * The API's refusals are written for the user - "alex@example.com is already
 * on your list", "your profile is not complete enough" - and a thrown error
 * never reaches them: Next.js replaces it with a digest in production. See
 * `lib/result.ts`.
 */

export async function getScheduled(): Promise<Result<ScheduledOut>> {
  return attempt(() => api<ScheduledOut>("/v1/dashboard/scheduled"));
}

export async function savePushSubscription(subscription: {
  endpoint: string;
  keys: Record<string, string>;
}): Promise<void> {
  // Nothing reads the outcome: this is registered in the background and a
  // failure has nothing for the user to do about it.
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

/**
 * Everything optional, and never the address: changing that would carry the
 * verification result, the touch count and the Gmail thread over to a
 * different person. The API refuses it too.
 */
export async function updateTarget(id: string, payload: unknown): Promise<Result<Target>> {
  const result = await attempt(() =>
    api<Target>(`/v1/targets/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  );
  if (result.ok) {
    revalidatePath("/targets");
    revalidatePath(`/targets/${id}`);
  }
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
  geminiKey: string,
): Promise<Result<Draft>> {
  if (!geminiKey.trim()) {
    return refuse("gemini_key_missing", "Add your Gemini API key in Settings to use AI features.");
  }
  return attempt(() =>
    api<Draft>(`/v1/targets/${id}/draft`, {
      method: "POST",
      body: JSON.stringify({ instruction, template_key: templateKey }),
      headers: { "X-Gemini-Api-Key": geminiKey.trim() },
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

/** Take a queued email back out of the queue. The draft itself is untouched. */
export async function cancelScheduledSend(id: string): Promise<Result<void>> {
  const result = await attempt(() =>
    api<void>(`/v1/targets/${id}/schedule`, { method: "DELETE" }),
  );
  if (result.ok) {
    revalidatePath("/dashboard");
    revalidatePath(`/targets/${id}`);
  }
  return result;
}
