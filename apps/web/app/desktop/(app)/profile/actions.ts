"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { attempt, refuse, type Result } from "@/lib/result";
import type { AvatarOut, ParsedResume, Profile } from "@/lib/types";

/**
 * Server actions for the profile screen.
 *
 * The upload goes through the server rather than straight from the browser to
 * the API, for the same reason the API session token never reaches the client:
 * there is no credential in the browser to authenticate it with.
 *
 * Each one returns a `Result` rather than throwing, so the API's sentence -
 * "That image is too large (max 5MB)" - is what the user reads instead of a
 * production digest. See `lib/result.ts`.
 */

export async function uploadResume(
  form: FormData,
  geminiKey: string,
): Promise<Result<ParsedResume>> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return refuse("no_file", "Choose a PDF or .docx first.");
  }
  if (!geminiKey.trim()) {
    return refuse("gemini_key_missing", "Add your Gemini API key in Settings to use AI features.");
  }

  const forwarded = new FormData();
  forwarded.append("file", file);
  forwarded.append("keep_original", String(form.get("keep_original") === "on"));

  // `api` leaves Content-Type off a FormData body so fetch can write the
  // multipart boundary itself. Passing `headers: {}` here does not achieve
  // that - spreading an empty object removes nothing.
  return attempt(() =>
    api<ParsedResume>("/v1/resumes", {
      method: "POST",
      body: forwarded,
      headers: { "X-Gemini-Api-Key": geminiKey.trim() },
    }),
  );
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

export async function uploadAvatar(form: FormData): Promise<Result<AvatarOut>> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return refuse("no_file", "Choose an image first.");
  }
  const forwarded = new FormData();
  forwarded.append("file", file);
  const result = await attempt(() =>
    api<AvatarOut>("/v1/profile/avatar", { method: "POST", body: forwarded }),
  );
  // "layout" (not the default "page") also revalidates (app)/layout.tsx,
  // which is where the topbar reads the avatar from - otherwise only the
  // profile page itself would pick up the change.
  if (result.ok) revalidatePath("/profile", "layout");
  return result;
}

export async function removeAvatar(): Promise<Result<void>> {
  const result = await attempt(() => api<void>("/v1/profile/avatar", { method: "DELETE" }));
  if (result.ok) revalidatePath("/profile", "layout");
  return result;
}
