"use client";

import Link from "next/link";

import Modal from "@/components/Modal";
import type { ActionError } from "@/lib/result";

/**
 * How a refused action is shown.
 *
 * Most refusals are one sentence the user reads and acts on, so the default is
 * a line of red text next to the control they pressed. Two of them are not:
 *
 *   profile_incomplete   nothing on this screen fixes it - the fix is on
 *                        another page, so it gets a modal with the link.
 *   pool_access_required the pool is a paid tier and the answer is a page,
 *                        not a sentence.
 *
 * These branch on `error.code`, not on the wording. The sentence is written
 * for a person and gets rewritten; the code is the contract. `code` is "" for
 * anything the API did not name, which lands on the default.
 */

/** Codes that deserve a modal with somewhere to go rather than inline text. */
const DESTINATIONS: Record<string, { title: string; href: string; cta: string }> = {
  profile_incomplete: {
    title: "Complete your profile",
    href: "/profile",
    cta: "Go to profile",
  },
  pool_access_required: {
    title: "The pool is a paid feature",
    href: "/pool/purchase",
    cta: "See the plan",
  },
  gemini_key_missing: {
    title: "Add your Gemini key",
    href: "/settings",
    cta: "Open settings",
  },
};

export function needsItsOwnPage(error: ActionError | null): boolean {
  return error != null && error.code in DESTINATIONS;
}

/** The red line under a control. Renders nothing when there is no error. */
export function InlineError({
  error,
  className = "error",
}: {
  error: ActionError | null;
  className?: string;
}) {
  if (!error || needsItsOwnPage(error)) return null;
  return (
    <p role="alert" className={className}>
      {error.message || "Something went wrong. Try again."}
    </p>
  );
}

/**
 * The modal for the codes above. Renders nothing for anything else, so a
 * caller can pass whatever it got and let the two components sort it out.
 */
export function ErrorModal({
  error,
  onClose,
}: {
  error: ActionError | null;
  onClose: () => void;
}) {
  const destination = error ? DESTINATIONS[error.code] : undefined;
  if (!error || !destination) return null;

  return (
    <Modal open onClose={onClose} title={destination.title}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-secondary">{error.message}</p>
        <div className="flex justify-end pt-2">
          <Link href={destination.href} className="button primary" onClick={onClose}>
            {destination.cta}
          </Link>
        </div>
      </div>
    </Modal>
  );
}
