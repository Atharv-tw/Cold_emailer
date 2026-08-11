"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import {
  cancelScheduledSend,
  generateDraft,
  saveDraft,
  scheduleSend,
  sendNow,
} from "@/app/desktop/(app)/dashboard/actions";
import QueuedNotice from "@/components/QueuedNotice";
import { useGeminiKey } from "@/lib/useGeminiKey";
import type { Draft, EmailTemplate, Target } from "@/lib/types";

/** Send times carry seconds so they do not look automated; nobody needs to see that. */
function when(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

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
  queuedFor = null,
}: {
  target: Target;
  initial: Draft | null;
  templates: EmailTemplate[];
  /** When this draft is due to go out, or null if it is not queued. */
  queuedFor?: string | null;
}) {
  const router = useRouter();
  const [subject, setSubject] = useState(initial?.subject ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  // What is actually stored, so Discard has something to go back to. Moves
  // forward on every save and on every generation, because at that point the
  // stored copy is the new baseline.
  const [saved, setSaved] = useState({
    subject: initial?.subject ?? "",
    body: initial?.body ?? "",
  });
  const [warnings, setWarnings] = useState<string[]>(initial?.warnings ?? []);
  const [instruction, setInstruction] = useState("");
  const [templateKey, setTemplateKey] = useState(templates[0]?.key ?? "specific_hook");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const { key: geminiKey, hasKey: hasGeminiKey } = useGeminiKey();

  const step = (initial?.step ?? target.touches_sent + 1) || 1;
  const isFollowUp = step > 1;
  const unsaved = subject !== saved.subject || body !== saved.body;

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
          className="secondary"
          disabled={pending || !hasGeminiKey}
          title={hasGeminiKey ? undefined : "Add your Gemini API key in Settings first"}
          onClick={() =>
            run(async () => {
              setStatus("Writing…");
              const draft = await generateDraft(target.id, instruction, templateKey, geminiKey);
              setSubject(draft.subject);
              setBody(draft.body);
              setSaved({ subject: draft.subject, body: draft.body });
              setWarnings(draft.warnings);
              setStatus("Written. Read it before you send it.");
            })
          }
        >
          {initial ? "Write it again" : "Write it for me"}
        </button>
        {!hasGeminiKey && (
          <p className="muted" style={{ fontSize: "12px", marginTop: "0.25rem" }}>
            Add your Gemini API key in Settings to write drafts automatically.
          </p>
        )}
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

      {queuedFor && <QueuedNotice queuedFor={queuedFor} />}

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
              setSaved({ subject, body });
              setWarnings(draft.warnings);
              setStatus(
                queuedFor
                  ? "Saved. This is what goes out at the queued time."
                  : "Saved as a draft. Nothing has been sent.",
              );
            })
          }
        >
          {queuedFor ? "Save edit" : "Save draft"}
        </button>

        {/* Only offered when it would do something. A Discard that is always
            there invites the question of what it discards when nothing has
            changed - and the honest answer would be "nothing". */}
        {unsaved && (
          <button
            type="button"
            className="quiet"
            disabled={pending}
            onClick={() => {
              setSubject(saved.subject);
              setBody(saved.body);
              setStatus("Reverted to the last saved version.");
              setError("");
            }}
          >
            Discard changes
          </button>
        )}

        {/* Sending in the window is the recommended path - it respects the
            sending hours, the per-user gap and the daily cap. It gets the
            accent; sending now bypasses all three, so it stays calm. */}
        <button
          type="button"
          className="accent"
          disabled={pending || !body.trim()}
          onClick={() =>
            run(async () => {
              await saveDraft(target.id, subject, body);
              const result = await scheduleSend(target.id);
              // Same honesty as the panel below: a due time in the past or the
              // immediate present means "next tick", not that exact minute.
              const at = result.scheduled_for;
              setStatus(
                !at
                  ? "Queued."
                  : new Date(at).getTime() <= Date.now()
                    ? "Queued — going out in the next couple of minutes."
                    : `Queued for ${when(at)}.`,
              );
              router.refresh();
            })
          }
        >
          {queuedFor ? "Pick a new time" : "Send in my next window"}
        </button>

        {queuedFor && (
          <button
            type="button"
            className="quiet"
            disabled={pending}
            onClick={() =>
              run(async () => {
                await cancelScheduledSend(target.id);
                setStatus("Taken out of the queue. The draft is still here.");
                router.refresh();
              })
            }
          >
            Cancel send
          </button>
        )}

        <button
          type="button"
          className="secondary"
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
      </section>
    </div>
  );
}
