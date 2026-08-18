"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { attempt, type Result } from "@/lib/result";

export async function createTrackedThread(payload: unknown): Promise<Result<any>> {
  const result = await attempt(() =>
    api<any>("/v1/trackers/threads", { method: "POST", body: JSON.stringify(payload) }),
  );
  if (result.ok) revalidatePath("/trackers");
  return result;
}

export async function deleteTrackedThread(id: string): Promise<Result<void>> {
  const result = await attempt(() => api<void>(`/v1/trackers/threads/${id}`, { method: "DELETE" }));
  if (result.ok) revalidatePath("/trackers");
  return result;
}

export async function createTrackedSender(payload: unknown): Promise<Result<any>> {
  const result = await attempt(() =>
    api<any>("/v1/trackers/senders", { method: "POST", body: JSON.stringify(payload) }),
  );
  if (result.ok) revalidatePath("/trackers");
  return result;
}

export async function deleteTrackedSender(id: string): Promise<Result<void>> {
  const result = await attempt(() => api<void>(`/v1/trackers/senders/${id}`, { method: "DELETE" }));
  if (result.ok) revalidatePath("/trackers");
  return result;
}
