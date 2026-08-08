"use client";

import { useState } from "react";

import type { ThreadMessage } from "@/lib/types";

/**
 * The conversation so far, one tile per touch.
 *
 * Only one is open at a time: a thread of three touches shown in full is a
 * wall of text you scroll past, and the point of the panel is to answer "what
 * have I already said to this person" at a glance.
 *
 * The draft opens by default because it is the one you are working on. It is
 * deliberately not editable here - it is the same message row the composer is
 * already editing, and two editors over one row have no answer for which wins.
 * So this tile previews it and sends you to the composer instead.
 */

function when(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function label(message: ThreadMessage): string {
  if (message.queued_for) return `queued · ${when(message.queued_for)}`;
  if (message.sent_at) return `sent · ${when(message.sent_at)}`;
  return message.status;
}

export default function ThreadPanel({ messages }: { messages: ThreadMessage[] }) {
  const draft = messages.find((message) => message.status === "draft");
  const [open, setOpen] = useState<number | null>(
    draft?.step ?? messages[messages.length - 1]?.step ?? null,
  );

  function jumpToComposer() {
    const composer = document.getElementById("compose");
    composer?.scrollIntoView({ behavior: "smooth", block: "start" });
    composer?.querySelector("textarea")?.focus();
  }

  if (messages.length === 0) {
    return <p className="muted">Nothing written yet.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {messages.map((message) => {
        const expanded = open === message.step;
        const isDraft = message.status === "draft";

        return (
          <div
            key={message.step}
            style={{
              border: "1px solid var(--line)",
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
            }}
          >
            <button
              type="button"
              className="quiet w-full"
              aria-expanded={expanded}
              onClick={() => setOpen(expanded ? null : message.step)}
              style={{ display: "block", textAlign: "left", padding: "0.75rem 1rem" }}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="badge badge-completed">Touch {message.step}</span>
                <span style={{ fontSize: "12px", color: "var(--muted)" }}>{label(message)}</span>
              </span>
              <span
                className="mt-1 block truncate font-semibold text-fg"
                style={{ fontSize: "14px" }}
              >
                {message.subject || "(no subject — replies in the thread)"}
              </span>
            </button>

            {expanded && (
              <div style={{ padding: "0 1rem 1rem" }}>
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    fontFamily: "inherit",
                    fontSize: "13px",
                    color: "var(--muted)",
                    margin: 0,
                  }}
                >
                  {message.body}
                </pre>

                {message.error && (
                  <p style={{ color: "var(--danger)", marginTop: "0.5rem", fontSize: "12px" }}>
                    {message.error}
                  </p>
                )}

                {isDraft && (
                  <button
                    type="button"
                    className="secondary small"
                    style={{ marginTop: "0.75rem" }}
                    onClick={jumpToComposer}
                  >
                    Edit in composer
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
