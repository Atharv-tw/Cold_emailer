import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { api } from "@/lib/api";
import type { Ops } from "@/lib/types";

function when(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : "never";
}

export default async function OpsPage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const data = await api<Ops>("/v1/ops");

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>System Health</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            Monitor the background worker, API connections, and failed sends.
          </p>
        </div>
      </div>

      {(!data.worker_running || !data.connected) && (
        <div className="dz-card" style={{ background: "var(--danger-light)", color: "var(--danger)", border: "1px solid #fecaca", padding: "1rem" }}>
          {!data.worker_running && <div style={{ marginBottom: "0.5rem" }}><strong>The background worker looks stopped.</strong> Nothing will send and replies will not be noticed.</div>}
          {!data.connected && <div><strong>Google is disconnected.</strong> {data.disconnected_reason || "Sign in again to reconnect."}</div>}
        </div>
      )}

      <div className="dashboard-grid">
        <div className="dz-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
            <h2 style={{ fontSize: "18px" }}>Background Worker</h2>
            <span className={`badge ${data.worker_running ? 'badge-completed' : 'badge-danger'}`}>
              {data.worker_running ? "Running" : "Stopped"}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {data.jobs.length === 0 ? (
              <p className="muted" style={{ padding: "1rem 0" }}>No job has run yet.</p>
            ) : (
              data.jobs.slice(0, 5).map((job, idx) => (
                <div key={idx} className="list-item">
                  <div className="list-icon" style={{ background: "var(--line)", fontSize: "14px" }}>⚙️</div>
                  <div className="list-content">
                    <div className="list-title">{job.job}</div>
                    <div className="list-desc">{job.detail || "Executed successfully"}</div>
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>{when(job.at)}</div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="dz-card">
          <h2 style={{ fontSize: "18px", marginBottom: "1.5rem" }}>Google Integration</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ padding: "1rem", background: "var(--bg)", borderRadius: "var(--radius-md)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                <strong style={{ fontSize: "13px" }}>Reply Watch</strong>
                <span className={`badge ${data.watch_healthy ? 'badge-completed' : 'badge-danger'}`}>
                  {data.watch_healthy ? "Active" : "Inactive"}
                </span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--muted)" }}>
                Last renewed: {when(data.watch_last_renewed)}<br/>
                Expires: {when(data.watch_expires_at)}
              </div>
            </div>
            
            <div style={{ padding: "1rem", background: "var(--bg)", borderRadius: "var(--radius-md)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                <strong style={{ fontSize: "13px" }}>Inbox Sync</strong>
              </div>
              <div style={{ fontSize: "12px", color: "var(--muted)" }}>
                Last read: {when(data.reconcile_last_read)}<br/>
                Follow-ups due: {data.follow_ups_due}
              </div>
            </div>
          </div>
        </div>

        <div className="dz-card" style={{ gridColumn: "1 / -1" }}>
          <h2 style={{ fontSize: "18px", marginBottom: "1.5rem" }}>Failed Sends</h2>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {data.failed_sends.length === 0 ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--muted)" }}>
                <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>🎉</div>
                <p>No failed sends. Every email has gone through successfully.</p>
              </div>
            ) : (
              <div className="table-scroll">
                <table className="preview">
                  <thead style={{ background: "#fcfcfc" }}>
                    <tr>
                      <th>Target</th>
                      <th>Error</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.failed_sends.map((failure, index) => (
                      <tr key={`${failure.target_id}-${index}`}>
                        <td>
                          <Link href={`/targets/${failure.target_id}`} style={{ fontWeight: "600", color: "var(--fg)" }}>
                            {failure.email || "a target"}
                          </Link>
                        </td>
                        <td><span className="badge badge-danger">{failure.error || "failed"}</span></td>
                        <td className="muted">{when(failure.at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
