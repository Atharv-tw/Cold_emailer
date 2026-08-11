"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { attempt, refuse, type Result } from "@/lib/result";
import type { ParsedResume, Profile } from "@/lib/types";

/**
 * Server actions for the profile screen.
 *
 * The upload goes through the server rather than straight from the browser to
 * the API, for the same reason the API session token never reaches the client:
 * there is no credential in the browser to authenticate it with.
 */

export async function uploadResume(form: FormData): Promise<Result<ParsedResume>> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return refuse("no_file", "Choose a PDF or .docx first.");
  }

  const forwarded = new FormData();
  forwarded.append("file", file);
  forwarded.append("keep_original", String(form.get("keep_original") === "on"));

  // `api` leaves Content-Type off a FormData body so fetch can write the
  // multipart boundary itself. Passing `headers: {}` here does not achieve
  // that - spreading an empty object removes nothing.
  return attempt(() => api<ParsedResume>("/v1/resumes", { method: "POST", body: forwarded }));
}

export async function saveProfile(payload: unknown): Promise<Result<Profile>> {
  const result = await attempt(() =>
    api<Profile>("/v1/profile", { method: "PUT", body: JSON.stringify(payload) }),
  );
  if (result.ok) revalidatePath("/profile");
  return result;
}

export async function saveProjects(payload: unknown): Promise<Result<Profile>> {
  const result = await attempt(() =>
    api<Profile>("/v1/profile/projects", { method: "PUT", body: JSON.stringify(payload) }),
  );
  if (result.ok) revalidatePath("/profile");
  return result;
}

export async function saveExperience(payload: unknown): Promise<Result<Profile>> {
  const result = await attempt(() =>
    api<Profile>("/v1/profile/experience", { method: "PUT", body: JSON.stringify(payload) }),
  );
  if (result.ok) revalidatePath("/profile");
  return result;
}

export async function deleteMyData(): Promise<Result<void>> {
  const result = await attempt(() => api<void>("/v1/profile/data", { method: "DELETE" }));
  if (result.ok) revalidatePath("/profile");
  return result;
}
