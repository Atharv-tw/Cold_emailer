"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import type { ParsedResume, Profile } from "@/lib/types";

/**
 * Server actions for the profile screen.
 *
 * The upload goes through the server rather than straight from the browser to
 * the API, for the same reason the API session token never reaches the client:
 * there is no credential in the browser to authenticate it with.
 */

export async function uploadResume(form: FormData): Promise<ParsedResume> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    throw new Error("Choose a PDF or .docx first.");
  }

  const forwarded = new FormData();
  forwarded.append("file", file);
  forwarded.append("keep_original", String(form.get("keep_original") === "on"));

  // Content-Type is left unset so fetch writes the multipart boundary itself.
  return api<ParsedResume>("/v1/resumes", {
    method: "POST",
    body: forwarded,
    headers: {},
  });
}

export async function saveProfile(payload: unknown): Promise<Profile> {
  const profile = await api<Profile>("/v1/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  revalidatePath("/profile");
  return profile;
}

export async function saveProjects(payload: unknown): Promise<Profile> {
  const profile = await api<Profile>("/v1/profile/projects", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  revalidatePath("/profile");
  return profile;
}

export async function saveExperience(payload: unknown): Promise<Profile> {
  const profile = await api<Profile>("/v1/profile/experience", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  revalidatePath("/profile");
  return profile;
}

export async function deleteMyData(): Promise<void> {
  await api<void>("/v1/profile/data", { method: "DELETE" });
  revalidatePath("/profile");
}
