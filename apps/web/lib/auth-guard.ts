import type { Session } from "next-auth";
import { redirect } from "next/navigation";

import { auth } from "@/auth";

export type AuthedSession = Session & { apiUser: NonNullable<Session["apiUser"]> };

/**
 * The auth check every protected page needs, in one place instead of copied
 * into each one. `redirect()` never returns, so by the time this returns,
 * `apiUser` really is present - the cast just tells callers what the runtime
 * check already guarantees.
 */
export async function requireAuth(): Promise<AuthedSession> {
  const session = await auth();
  if (!session?.apiUser) {
    redirect("/login");
  }
  return session as AuthedSession;
}
