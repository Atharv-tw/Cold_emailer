"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import type { AvatarOut, ParsedResume, Profile } from "@/lib/types";

/**
 * Server actions for the profile screen.
 *
 * The upload goes through the server rather than straight from the browser to
 * the API, for the same reason the API session token never reaches the client:
 * there is no credential in the browser to authenticate it with.
 */

export async function uploadResume(form: FormData, geminiKey: string): Promise<ParsedResume> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    throw new Error("Choose a PDF or .docx first.");
  }
  if (!geminiKey.trim()) {
    throw new Error("Add your Gemini API key in Settings to use AI features.");
  }

  const forwarded = new FormData();
  forwarded.append("file", file);
  forwarded.append("keep_original", String(form.get("keep_original") === "on"));

  // `api` leaves Content-Type off a FormData body so fetch can write the
  // multipart boundary itself. Passing `headers: {}` here does not achieve
  // that - spreading an empty object removes nothing.
  return api<ParsedResume>("/v1/resumes", {
    method: "POST",
    body: forwarded,
    headers: { "X-Gemini-Api-Key": geminiKey.trim() },
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

export async function uploadAvatar(form: FormData): Promise<AvatarOut> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    throw new Error("Choose an image first.");
  }
  const forwarded = new FormData();
  forwarded.append("file", file);
  const result = await api<AvatarOut>("/v1/profile/avatar", { method: "POST", body: forwarded });
  // "layout" (not the default "page") also revalidates (app)/layout.tsx,
  // which is where the topbar reads the avatar from - otherwise only the
  // profile page itself would pick up the change.
  revalidatePath("/profile", "layout");
  return result;
}

export async function removeAvatar(): Promise<void> {
  await api<void>("/v1/profile/avatar", { method: "DELETE" });
  revalidatePath("/profile", "layout");
}
