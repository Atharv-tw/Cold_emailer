"use server";

import { api } from "@/lib/api";
import { attempt, refuse, type Result } from "@/lib/result";

export async function reportIssue(message: string): Promise<Result<void>> {
  const text = message.trim();
  if (!text) {
    return refuse("empty_report", "Say a bit about what went wrong.");
  }
  return attempt(() =>
    api<void>("/v1/support/report", { method: "POST", body: JSON.stringify({ message: text }) }),
  );
}
