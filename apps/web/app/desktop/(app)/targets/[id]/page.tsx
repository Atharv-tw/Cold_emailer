import Link from "next/link";

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
    api<Draft>(`/v1/targets/${id}/draft`).catch(() => null),
    api<EmailTemplate[]>("/v1/templates"),
    // 404 on every target nobody answered, which is most of them. Opening this
    // page is also what marks the reply read - there is no state where someone
    // has the reply on screen and has not seen it.
    api<Reply>(`/v1/targets/${id}/reply`).catch(() => null),
  ]);

  const verification = target.verification ?? {};
  const tone = VERIFICATION_TONE[verification.status ?? "unknown"] ?? "badge-pending";

  return (
    <>
      <div className="page-header">
        <div>
          <h1>{target.name || target.email}</h1>
          <p>
            {target.email}
            {target.company && ` · ${target.company}`}
            {target.role && ` · ${target.role}`}
          </p>
        </div>
        <div className="header-actions">
          <Link href="/dashboard">
            <button className="secondary" style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}>
              ← Back
            </button>
          </Link>
        </div>
      </div>

      <div className="dashboard-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Above everything, including the compose box. Once someone has
              answered, what they said is the only thing on this page worth
              reading first - and the sequence is over, so the draft below it
              is no longer actionable anyway. */}
          {reply && <ReplyCard reply={reply} />}

          {/* "Not configured" is a fact about the deployment, not about this
              address. Warning on every target for a feature that was never
              switched on trains people to ignore the banner that matters. */}
          {verification.status &&
            verification.status !== "deliverable" &&
            verification.reason !== "verification_not_configured" && (
            <div className="dz-card" style={{ background: "var(--warning-light)", border: "1px solid #fde68a", padding: "1rem" }}>
              <p className={tone}>{verification.detail}</p>
              {verification.did_you_mean && (
                <p className="muted" style={{ marginTop: "0.5rem", fontSize: "12px" }}>
                  Suggested correction: <strong>{verification.did_you_mean}</strong>. The address cannot be edited — delete this and add them again.
                </p>
              )}
            </div>
          )}

          {target.hook && (
            <div className="dz-card" style={{ padding: "1rem", background: "var(--accent-light)" }}>
              <strong style={{ color: "var(--accent)" }}>Why them:</strong> <span style={{ color: "var(--fg)" }}>{target.hook}</span>
            </div>
          )}

          <div id="compose" className="dz-card" style={{ padding: "1.5rem" }}>
            <h2 style={{ marginBottom: "1.5rem" }}>Compose</h2>
            <DraftEditor
              target={target}
              initial={draft}
              templates={templates}
              queuedFor={detail.queued_for}
            />
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div className="dz-card">
            <h2 style={{ marginBottom: "1.5rem" }}>Thread</h2>
            <ThreadPanel messages={detail.messages} />
          </div>

          <div className="dz-card">
            <h2 style={{ marginBottom: "1.5rem" }}>History</h2>
            <TimelineList entries={detail.timeline} />
          </div>
        </div>
      </div>
    </>
  );
}
