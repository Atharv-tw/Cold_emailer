"use server";

import { api } from "@/lib/api";
import type { Target } from "@/lib/types";

export async function searchTargets(q: string): Promise<Target[]> {
  if (!q.trim()) return [];
  return api<Target[]>(`/v1/targets?q=${encodeURIComponent(q.trim())}`);
}
