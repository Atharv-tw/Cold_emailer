"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

/**
 * The "this is going out" panel, and the only thing on the page that knows the
 * send happens somewhere else.
 *
 * Two problems it exists to solve, both of which made a working send look
 * broken:
 *
 * 1. A due time can be *now*. `schedule_step` returns the current instant when
 *    the slot it picked has already passed and the window is open
 *    (scheduling.py:145), which means "as soon as possible" - but rendered as a
 *    clock time it reads as a promise, and the worker's tick only runs every
 *    two minutes. So for up to two minutes the page showed "Queued for 4:19 PM"
 *    at 4:20. Nothing was wrong; the sentence was.
 *
 * 2. The worker sends out of band. The server component was rendered before
 *    that happened and never hears about it, so the panel sat there saying
 *    "Queued" after the email had gone. `cache: "no-store"` makes a *reload*
 *    accurate; it does nothing for a page already on screen.
 *
 * The refresh is deliberately invisible. `router.refresh()` inside a transition
 * re-fetches the server tree and swaps it in without unmounting anything - no
 * fallback, no scroll reset, no cleared textarea - and this component renders
 * no pending state at all, because a spinner every fifteen seconds would look
 * like the page was struggling. The only visible change is the moment the
 * panel's own text changes, which is the thing worth seeing.
 */

/** Slow enough to be nothing, quick enough to catch a two-minute tick. */
const POLL_MS = 15_000;

/** Give up after ~10 minutes. See `exhausted` below for why this is not forever. */
const MAX_POLLS = 40;

/** Within this of the due time, start watching for the send. */
const SOON_MS = 2 * 60 * 1000;

function when(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function QueuedNotice({ queuedFor }: { queuedFor: string }) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  // Null until mounted, so the server renders the plain "Queued for ..." and
  // hydration has nothing to disagree with. Reading the clock during a server
  // render would make the first paint depend on when it happened.
  const [nowMs, setNowMs] = useState<number | null>(null);
  const [exhausted, setExhausted] = useState(false);

  const due = new Date(queuedFor).getTime();
  const watching = nowMs !== null && due - nowMs <= SOON_MS;
  const overdue = nowMs !== null && due <= nowMs;

  // A new due time is a new wait: re-arm everything the reschedule invalidated.
  useEffect(() => {
    setNowMs(Date.now());
    setExhausted(false);
  }, [queuedFor]);

  useEffect(() => {
    if (exhausted) return;

    // Not close yet: just keep the clock roughly honest so the panel notices
    // when it becomes close. No network, no refresh.
    if (!watching) {
      const id = setInterval(() => setNowMs(Date.now()), 30_000);
      return () => clearInterval(id);
    }

    let polls = 0;
    const id = setInterval(() => {
      setNowMs(Date.now());

      // A background tab does not need to know. It will refresh on focus, and
      // this keeps a forgotten tab from polling all afternoon.
      if (typeof document !== "undefined" && document.hidden) return;

      polls += 1;
      if (polls > MAX_POLLS) {
        setExhausted(true);
        return;
      }
      startTransition(() => router.refresh());
    }, POLL_MS);
    return () => clearInterval(id);
  }, [watching, exhausted, queuedFor, router]);

  // Once it sends, the parent re-renders with queued_for null and this whole
  // component unmounts, which is what clears the interval.

  if (exhausted) {
    return (
      <div className="note">
        <strong>Still queued.</strong>
        <p className="muted">
          This was due at {when(queuedFor)} and has not gone yet — most likely
          your sending window closed, or the daily cap is reached, in which case
          it goes out at the start of the next window. Reload to check.
        </p>
      </div>
    );
  }

  if (overdue) {
    return (
      <div className="note">
        <strong>Sending now.</strong>
        <p className="muted">
          Its time has come round, and sends are checked every couple of
          minutes, so this goes out shortly. You do not need to stay on this
          page — it updates itself.
        </p>
      </div>
    );
  }

  return (
    <div className="note">
      <strong>Queued for {when(queuedFor)}.</strong>
      <p className="muted">
        Edit the text above and save, and that is what goes out — the time only
        changes if you reschedule.
      </p>
    </div>
  );
}
