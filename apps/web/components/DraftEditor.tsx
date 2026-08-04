"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { generateDraft, saveDraft, scheduleSend, sendNow } from "@/app/dashboard/actions";
import type { Draft, EmailTemplate, Target } from "@/lib/types";

/**
 * Write, check, send.
 *
 * The generate button never sends and the send button never generates. Lint
 * warnings show inline and block nothing: a user who wants three links in
 * their email is allowed three links in their email, they just get told.
 */

export default function DraftEditor({
  target,
  initial,
  templates,
}: {
  target: Target;
  initial: Draft | null;
  templates: EmailTemplate[];
}) {
  const router = useRouter();
  const [subject, setSubject] = useState(initial?.subject ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  const [warnings, setWarnings] = useState<string[]>(initial?.warnings ?? []);
  const [instruction, setInstruction] = useState("");
  const [templateKey, setTemplateKey] = useState(templates[0]?.key ?? "specific_hook");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  const step = (initial?.step ?? target.touches_sent + 1) || 1;
  const isFollowUp = step > 1;

  function run(work: () => Promise<void>) {
    setError("");
    startTransition(async () => {
      try {
        await work();
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Something went wrong.");
      }
    });
  }

  if (!target.can_send) {
    return (
      <div className="note">
        <strong>Nothing further will be sent to this person.</strong>
        <p className="muted">{target.blocked_reason}</p>
      </div>
    );
  }

  return (
    <div className="stack">
      <section>
        <h2>
          {isFollowUp ? `Follow-up ${step - 1}` : "First email"}{" "}
          <span className="muted">
            ({target.touches_remaining} of 3 remaining)
          </span>
        </h2>
        {isFollowUp && (
          <p className="muted">
            This replies inside the existing thread. It should be shorter than
            the first one and should not repeat the pitch.
          </p>
        )}
      </section>

      <section>
        <label>
          Template
          <select value={templateKey} onChange={(event) => setTemplateKey(event.target.value)}>
            {templates.map((template) => (
              <option key={template.key} value={template.key}>
                {template.name}
              </option>
            ))}
          </select>
        </label>
        <p className="muted">
          {templates.find((template) => template.key === templateKey)?.description}
        </p>

        <label>
          Steer the writing (optional)
          <input
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            placeholder="mention the latency work; warmer; shorter"
          />
        </label>
        <button
          type="button"
          className="quiet"
          disabled={pending}
          onClick={() =>
            run(async () => {
              setStatus("Writing…");
              const draft = await generateDraft(target.id, instruction, templateKey);
              setSubject(draft.subject);
              setBody(draft.body);
              setWarnings(draft.warnings);
              setStatus("Written. Read it before you send it.");
            })
          }
        >
          {initial ? "Write it again" : "Write it for me"}
        </button>
      </section>

      <section>
        {!isFollowUp && (
          <label>
            Subject
            <input value={subject} onChange={(event) => setSubject(event.target.value)} />
          </label>
        )}
        <label>
          Body
          <textarea rows={14} value={body} onChange={(event) => setBody(event.target.value)} />
        </label>
        <p className="muted">{body.length} characters — under 900 reads better.</p>
      </section>

      {warnings.length > 0 && (
        <div className="note">
          <strong>Worth a look before sending:</strong>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
          <p className="muted">These are suggestions. Send it anyway if you disagree.</p>
        </div>
      )}

      {status && <p className="ok">{status}</p>}
      {error && <p className="error">{error}</p>}

      <section>
        <button
          type="button"
          className="quiet"
          disabled={pending || !body.trim()}
          onClick={() =>
            run(async () => {
              const draft = await saveDraft(target.id, subject, body);
              setWarnings(draft.warnings);
              setStatus("Saved as a draft. Nothing has been sent.");
            })
          }
        >
          Save draft
        </button>

        <button
          type="button"
          disabled={pending || !body.trim()}
          onClick={() =>
            run(async () => {
              await saveDraft(target.id, subject, body);
              if (!confirm(`Send this to ${target.email} now?`)) return;
              await sendNow(target.id);
              setStatus("Sent.");
              router.refresh();
            })
          }
        >
          Send now
        </button>

        <button
          type="button"
          className="quiet"
          disabled={pending || !body.trim()}
          onClick={() =>
            run(async () => {
              await saveDraft(target.id, subject, body);
              const result = await scheduleSend(target.id);
              setStatus(
                result.scheduled_for
                  ? `Queued for ${new Date(result.scheduled_for).toLocaleString()}.`
                  : "Queued.",
              );
              router.refresh();
            })
          }
        >
          Send in my next window
        </button>
      </section>
    </div>
  );
}
