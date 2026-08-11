"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { attempt, type Result } from "@/lib/result";
import type { Target } from "@/lib/types";

/**
 * Take a person out of the shared pool and onto this user's own list.
 *
 * Lives in `lib` rather than beside a page because both the desktop and mobile
 * trees render the pool, and middleware rewrites one URL to either of them.
 * Putting it under `app/desktop` would have the mobile page importing across
 * the split for no reason.
 *
 * The API copies the contact's details onto a new target and leaves `hook`
 * empty on purpose, so the caller is sent straight to the target page to write
 * it. The pool row itself does not change - it stays available to everyone
 * else, minus this user, who is filtered out of the listing from now on.
 */
export async function addFromPool(contactId: string): Promise<Result<Target>> {
  const result = await attempt(() =>
    api<Target>(`/v1/pool/${contactId}/add`, { method: "POST" }),
  );
  if (result.ok) {
    // The listing hides anyone already on the list, and both the dashboard and
    // the people page gained a row.
    revalidatePath("/pool");
    revalidatePath("/targets");
    revalidatePath("/dashboard");
  }
  return result;
}
