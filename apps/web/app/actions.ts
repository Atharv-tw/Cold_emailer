"use server";

import { signOut } from "@/auth";
import { api } from "@/lib/api";

/**
 * Shared by both chromes. It lived under `desktop/(app)/` until the mobile
 * shell grew a logout button too - a server action does not need to sit in a
 * route directory, and importing a `desktop/` path from `MobileChrome` would
 * have read as a mistake.
 *
 * The old logout button posted straight to Auth.js's `/api/auth/signout`
 * route, which requires a CSRF token the raw form never sent - so it silently
 * no-opped. Calling `signOut()` as a server action bypasses that route
 * entirely. The backend call is defense-in-depth: nothing reached it before.
 */
export async function logout() {
  await api<void>("/v1/auth/logout", { method: "POST" }).catch(() => {});
  await signOut({ redirectTo: "/" });
}
