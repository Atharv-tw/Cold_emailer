"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { attempt, type Result } from "@/lib/result";
import type { ImportCommitResult, ImportPreview } from "@/lib/types";

/**
 * The two import steps forward the uploaded file to the API.
 *
 * The file rides through as multipart FormData, which `api` detects and lets
 * fetch frame itself. Both steps send the file: the API re-reads and
 * re-validates it on commit rather than trusting rows the browser sends back,
 * so nothing edited in between can slip a suppressed or duplicate address in.
 */

export async function previewImport(formData: FormData): Promise<Result<ImportPreview>> {
  return attempt(() =>
    api<ImportPreview>("/v1/import/preview", { method: "POST", body: formData }),
  );
}

export async function commitImport(formData: FormData): Promise<Result<ImportCommitResult>> {
  const result = await attempt(() =>
    api<ImportCommitResult>("/v1/import/commit", { method: "POST", body: formData }),
  );
  if (result.ok) {
    // New targets land on the dashboard and its counts.
    revalidatePath("/dashboard");
    revalidatePath("/targets");
  }
  return result;
}
