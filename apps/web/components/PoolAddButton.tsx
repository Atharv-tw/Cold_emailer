"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { ErrorModal, InlineError } from "@/components/ActionError";
import { addFromPool } from "@/lib/pool-actions";
import type { ActionError } from "@/lib/result";

/**
 * Adds one pool contact to the user's list, then goes to the new target.
 *
 * The redirect is the point rather than a convenience: a pool contact arrives
 * with no hook, and the hook is what makes the email worth sending. Landing
 * the user on the target page is what turns "added 40 people" into "wrote to
 * one person for a reason".
 *
 * Failures are shown in place. The API refuses an add for several ordinary
 * reasons - already on the list, suppressed, the address has since bounced -
 * and each of those is something the user should read, not a toast that
 * disappears. An incomplete profile is the exception: nothing on this page
 * fixes it, so `ErrorModal` sends them to the profile instead.
 */
export default function PoolAddButton({ contactId }: { contactId: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<ActionError | null>(null);

  function add() {
    setError(null);
    startTransition(async () => {
      const result = await addFromPool(contactId);
      if (result.ok) router.push(`/targets/${result.data.id}`);
      else setError(result.error);
    });
  }

  return (
    <>
      <div className="mt-auto flex flex-col gap-1.5">
        <button
          type="button"
          className="primary w-full"
          style={{ borderRadius: "2rem", padding: "0.45rem 1rem", fontWeight: 600 }}
          onClick={add}
          disabled={pending}
        >
          {pending ? "Adding…" : "Add to my list"}
        </button>
        <InlineError error={error} className="text-xs text-danger" />
      </div>

      <ErrorModal error={error} onClose={() => setError(null)} />
    </>
  );
}
