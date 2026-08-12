import DraftEditor from "@/components/DraftEditor";
import ReplyCard from "@/components/ReplyCard";
import ThreadPanel from "@/components/ThreadPanel";
import TimelineList from "@/components/TimelineList";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Draft, EmailTemplate, Reply, Target, TargetDetail } from "@/lib/types";

const VERIFICATION_TONE: Record<string, string> = {
  deliverable: "badge-completed",
  risky: "badge-pending",
  undeliverable: "badge-danger",
  unknown: "badge-pending",
};

/**
 * One target, in the order that matters on a phone: what they said, then what
 * to say back, then the record.
 *
 * Desktop puts compose and the thread side by side. Stacked, that ordering
 * would bury the draft under a thread that grows with every touch, so the
 * thread and history move below it.
 *
 * This page previously rendered `<fieldset>`/`<pre>` markup of its own instead
 * of `ThreadPanel`, and did not pass `queued_for` to the editor - so on mobile
 * a queued send showed no notice and offered no way to cancel it.
 */
export default async function TargetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAuth();

  const { id } = await params;
  const [target, detail, draft, templates, reply] = await Promise.all([
    api<Target>(`/v1/targets/${id}`),
    api<TargetDetail>(`/v1/targets/${id}/timeline`),
    // No draft yet is the normal state for a new target, not an error.
    api<Draft>(`/v1/targets/${id}/draft`).catch(() => null),
    api<EmailTemplate[]>("/v1/templates"),
    // Absent for every target nobody answered, which is most of them. This
    // request is also what marks the reply read.
    api<Reply>(`/v1/targets/${id}/reply`).catch(() => null),
  ]);

  const verification = target.verification ?? {};
  const tone = VERIFICATION_TONE[verification.status ?? "unknown"] ?? "badge-pending";

  return (
    <>
      <div className="page-header">
        <div className="min-w-0">
          <h1 className="break-words">{target.name || target.email}</h1>
          <p className="break-words">
            {target.email}
            {target.company && ` · ${target.company}`}
            {target.role && ` · ${target.role}`}
          </p>
        </div>
      </div>

      {/* Above everything, including the compose box. Once someone has
          answered, what they said is the only thing on this page worth reading
          first - and the sequence is over, so the draft below it is no longer
          actionable anyway. */}
      {reply && <ReplyCard reply={reply} />}

      {/* "Not configured" is a fact about the deployment, not about this
          address. Warning on every target for a feature that was never
          switched on trains people to ignore the banner that matters. */}
      {verification.status &&
        verification.status !== "deliverable" &&
        verification.reason !== "verification_not_configured" && (
          <div
            className="dz-card"
            style={{ background: "var(--warning-light)", border: "1px solid #fde68a", padding: "1rem" }}
          >
            <p className={tone}>{verification.detail}</p>
            {verification.did_you_mean && (
              <p className="muted" style={{ marginTop: "0.5rem", fontSize: "12px" }}>
                Suggested correction: <strong>{verification.did_you_mean}</strong>. The address
                cannot be edited — delete this and add them again.
              </p>
            )}
          </div>
        )}

      {target.hook && (
        <div className="dz-card" style={{ padding: "1rem", background: "var(--accent-light)" }}>
          <strong style={{ color: "var(--accent)" }}>Why them:</strong>{" "}
          <span style={{ color: "var(--fg)" }}>{target.hook}</span>
        </div>
      )}

      <div id="compose" className="dz-card">
        <h2 style={{ marginBottom: "1rem" }}>Compose</h2>
        <DraftEditor
          target={target}
          initial={draft}
          templates={templates}
          queuedFor={detail.queued_for}
        />
      </div>

      <div className="dz-card">
        <h2 style={{ marginBottom: "1rem" }}>Thread</h2>
        <ThreadPanel messages={detail.messages} />
      </div>

      <div className="dz-card">
        <h2 style={{ marginBottom: "1rem" }}>History</h2>
        <TimelineList entries={detail.timeline} />
      </div>
    </>
  );
}
