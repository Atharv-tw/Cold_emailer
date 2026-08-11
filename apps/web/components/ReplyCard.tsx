"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import type { Reply } from "@/lib/types";

/**
 * What the person actually wrote, on the target whose sequence they ended.
 *
 * The body is stored whole rather than trimmed, because the classifier had
 * already fetched and parsed it and throwing it away was the only reason the
 * product could say "they replied" without saying what they said. Trimming
 * belongs here, at display time, where it can be undone by clicking.
 *
 * The Gmail link is the escape hatch for everything this card deliberately
 * does not do: attachments, images, formatting, and replying itself. Rendering
 * any of that would mean becoming a mail client, and the user already has one.
 */

// Where a reply stops being new text and starts being a copy of what we sent.
// Gmail writes "On <date>, <name> <address> wrote:"; Outlook writes a block of
// "From:/Sent:/To:" headers; everything else falls back to the `>` convention.
// Missing the marker costs nothing worse than showing the quote inline.
const QUOTE_MARKERS = [
  /^On .+ wrote:\s*$/m,
  /^-{2,}\s*Original Message\s*-{2,}\s*$/im,
  /^_{5,}\s*$/m,
  /^From:.*$/m,
  /^>.*$/m,
];

export function split(body: string): { text: string; quoted: string } {
  let cut = -1;
  for (const marker of QUOTE_MARKERS) {
    const found = body.search(marker);
    // The earliest marker wins: a reply that quotes twice should collapse from
    // the first quote, not the last.
    if (found !== -1 && (cut === -1 || found < cut)) cut = found;
  }
  if (cut === -1) return { text: body, quoted: "" };
  return { text: body.slice(0, cut).trimEnd(), quoted: body.slice(cut) };
}

export default function ReplyCard({ reply }: { reply: Reply }) {
  const [showQuoted, setShowQuoted] = useState(false);
  const { text, quoted } = split(reply.body ?? "");

  return (
    <div
      className="dz-card"
      style={{ padding: "1.5rem", border: "1px solid var(--accent)" }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1rem",
          marginBottom: "1rem",
        }}
      >
        <h2 style={{ margin: 0 }}>They replied</h2>
        {reply.gmail_thread_url && (
          <a
            href={reply.gmail_thread_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", fontSize: "13px" }}
          >
            Open in Gmail
            <Icon name="send" size={14} />
          </a>
        )}
      </div>

      <p className="muted" style={{ fontSize: "13px", margin: "0 0 1rem" }}>
        {reply.from_email}
        {reply.subject && ` · ${reply.subject}`}
      </p>

      <pre
        style={{
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          fontFamily: "inherit",
          fontSize: "14px",
          color: "var(--fg)",
          margin: 0,
        }}
      >
        {text || "(they sent an empty message)"}
      </pre>

      {quoted && (
        <>
          <button
            type="button"
            className="secondary"
            onClick={() => setShowQuoted((open) => !open)}
            style={{ marginTop: "1rem", fontSize: "12px", padding: "0.3rem 0.75rem" }}
          >
            {showQuoted ? "Hide quoted text" : "Show quoted text"}
          </button>
          {showQuoted && (
            <pre
              style={{
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                fontFamily: "inherit",
                fontSize: "13px",
                color: "var(--muted)",
                marginTop: "0.75rem",
                paddingLeft: "0.75rem",
                borderLeft: "2px solid var(--line)",
              }}
            >
              {quoted}
            </pre>
          )}
        </>
      )}
    </div>
  );
}
