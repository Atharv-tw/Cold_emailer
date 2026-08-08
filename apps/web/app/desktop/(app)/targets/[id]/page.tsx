import Link from "next/link";

import DraftEditor from "@/components/DraftEditor";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Draft, EmailTemplate, Target, TargetDetail } from "@/lib/types";

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
  const [target, detail, draft, templates] = await Promise.all([
    api<Target>(`/v1/targets/${id}`),
    api<TargetDetail>(`/v1/targets/${id}/timeline`),
    api<Draft>(`/v1/targets/${id}/draft`).catch(() => null),
    api<EmailTemplate[]>("/v1/templates"),
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
          {verification.status && verification.status !== "deliverable" && (
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

          <div className="dz-card" style={{ padding: "1.5rem" }}>
            <h2 style={{ marginBottom: "1.5rem" }}>Compose</h2>
            <DraftEditor target={target} initial={draft} templates={templates} />
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div className="dz-card">
            <h2 style={{ marginBottom: "1.5rem" }}>Thread</h2>
            {detail.messages.length === 0 ? (
              <p className="muted">Nothing sent yet.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {detail.messages.map((message) => (
                  <div key={message.step} style={{ border: "1px solid var(--line)", borderRadius: "var(--radius-md)", padding: "1rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <span className="badge badge-completed">Touch {message.step}</span>
                      <span style={{ fontSize: "12px", color: "var(--muted)" }}>
                        {message.status} {message.sent_at && `· ${new Date(message.sent_at).toLocaleString()}`}
                      </span>
                    </div>
                    <strong style={{ display: "block", marginBottom: "0.5rem", fontSize: "14px" }}>{message.subject}</strong>
                    <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "13px", color: "var(--muted)", margin: 0 }}>
                      {message.body}
                    </pre>
                    {message.error && <p style={{ color: "var(--danger)", marginTop: "0.5rem", fontSize: "12px" }}>{message.error}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="dz-card">
            <h2 style={{ marginBottom: "1.5rem" }}>History</h2>
            <div style={{ display: "flex", flexDirection: "column" }}>
              {detail.timeline.map((entry, index) => (
                <div key={index} className="list-item">
                  <div className="list-icon" style={{ background: "var(--line)", fontSize: "12px" }}>⏳</div>
                  <div className="list-content">
                    <div className="list-title">{entry.type}</div>
                    {entry.detail && <div className="list-desc">{entry.detail}</div>}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>{new Date(entry.at).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
