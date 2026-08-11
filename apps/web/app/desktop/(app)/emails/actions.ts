"use server";

import { api } from "@/lib/api";
import { attempt, type Result } from "@/lib/result";
import type { Target } from "@/lib/types";

export async function searchTargets(q: string): Promise<Result<Target[]>> {
  if (!q.trim()) return { ok: true, data: [] };
  return attempt(() => api<Target[]>(`/v1/targets?q=${encodeURIComponent(q.trim())}`));
}
