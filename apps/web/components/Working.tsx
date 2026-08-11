"use client";

import { useEffect, useState } from "react";

/**
 * "Writing…" — something to look at while a model takes its time.
 *
 * Both the calls this covers are slow enough that a button which merely goes
 * grey reads as a button that did nothing, and the second click is how you
 * get two drafts. So the indicator says what is happening in words, animates
 * so it is visibly alive, and - when the wait runs long - rotates through
 * what is actually going on rather than repeating itself.
 *
 * `role="status"` rather than a spinner alone: a screen reader announces the
 * label instead of leaving the user with silence.
 */
export default function Working({
  label,
  hints = [],
  /** How long each hint holds before the next one, in ms. */
  every = 4000,
  tone = "light",
}: {
  label: string;
  hints?: string[];
  every?: number;
  /** The dark cards need their own colours; the defaults vanish on black. */
  tone?: "light" | "dark";
}) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (hints.length < 2) return;
    const timer = setInterval(
      () => setIndex((current) => (current + 1) % hints.length),
      every,
    );
    return () => clearInterval(timer);
  }, [hints.length, every]);

  return (
    <p
      className={tone === "dark" ? "working working-on-dark" : "working"}
      role="status"
      aria-live="polite"
    >
      <span className="working-dots" aria-hidden="true">
        <span className="working-dot" />
        <span className="working-dot" />
        <span className="working-dot" />
      </span>
      <span>
        {label}
        {hints.length > 0 && <span className="working-hint"> — {hints[index]}</span>}
      </span>
    </p>
  );
}
