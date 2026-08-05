import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import PwaSetup from "@/components/PwaSetup";
import { api } from "@/lib/api";
import type { Dashboard } from "@/lib/types";

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const user = session.apiUser;
  const [data, pushKey] = await Promise.all([
    api<Dashboard>("/v1/dashboard"),
    api<{ key: string }>("/v1/push/key").catch(() => ({ key: "" })),
  ]);

  const totalContacts = data.targets.length;
  const inFlight = data.counts.active || 0;
  const replied = data.counts.replied || 0;
  const completed = data.counts.completed || 0;
  const totalProcessed = inFlight + replied + completed;
  const completionRate = totalContacts > 0 ? Math.round((totalProcessed / totalContacts) * 100) : 0;

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Dashboard</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>Plan, prioritize, and track your outreach with ease.</p>
        </div>
        <div className="header-actions">
          <Link href="/import">
            <button className="secondary" style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}>
              Import Data
            </button>
          </Link>
          <Link href="/targets/new">
            <button className="primary" style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}>
              + Add Contact
            </button>
          </Link>
        </div>
      </div>

      {(!user.connected || user.missing_scopes.length > 0) && (
        <div className="dz-card" style={{ background: "var(--warning-light)", color: "var(--warning)", border: "1px solid #fde68a", padding: "1rem" }}>
          <strong>Action Required:</strong> Google is not properly connected or missing scopes. Check your settings.
        </div>
      )}

      {/* Top Stats Row */}
      <div className="stats-grid">
        <div className="dz-card" style={{ background: "var(--accent)", color: "white" }}>
          <div className="stat-title">
            <span>Total Contacts</span>
            <span className="stat-icon" style={{ borderColor: "rgba(255,255,255,0.4)" }}>↗</span>
          </div>
          <div className="stat-value">{totalContacts}</div>
          <div className="stat-trend" style={{ color: "rgba(255,255,255,0.8)" }}>
            <span style={{ background: "rgba(255,255,255,0.2)", padding: "2px 6px", borderRadius: "4px" }}>Active</span> Available in CRM
          </div>
        </div>

        <div className="dz-card">
          <div className="stat-title">
            <span style={{ color: "var(--muted)" }}>Completed</span>
            <span className="stat-icon" style={{ borderColor: "var(--line)", color: "var(--fg)" }}>↗</span>
          </div>
          <div className="stat-value">{completed}</div>
          <div className="stat-trend">
            <span style={{ color: "var(--accent)", background: "var(--accent-light)", padding: "2px 6px", borderRadius: "4px" }}>●</span> Targets reached
          </div>
        </div>

        <div className="dz-card">
          <div className="stat-title">
            <span style={{ color: "var(--muted)" }}>In Flight</span>
            <span className="stat-icon" style={{ borderColor: "var(--line)", color: "var(--fg)" }}>↗</span>
          </div>
          <div className="stat-value">{inFlight}</div>
          <div className="stat-trend">
            <span style={{ color: "var(--accent)", background: "var(--accent-light)", padding: "2px 6px", borderRadius: "4px" }}>●</span> Currently sending
          </div>
        </div>

        <div className="dz-card">
          <div className="stat-title">
            <span style={{ color: "var(--muted)" }}>Replied</span>
            <span className="stat-icon" style={{ borderColor: "var(--line)", color: "var(--fg)" }}>↗</span>
          </div>
          <div className="stat-value">{replied}</div>
          <div className="stat-trend">
            <span style={{ color: "var(--accent)", background: "var(--accent-light)", padding: "2px 6px", borderRadius: "4px" }}>●</span> Total replies
          </div>
        </div>
      </div>

      {/* Middle Row */}
      <div className="dashboard-grid">
        {/* Project Analytics */}
        <div className="dz-card">
          <h2 style={{ marginBottom: "1.5rem" }}>Pipeline Analytics</h2>
          <div className="bar-chart-container">
            <div className="bar striped" style={{ height: "60%" }}></div>
            <div className="bar solid-light" style={{ height: "80%" }}></div>
            <div className="bar solid" style={{ height: "95%", position: "relative" }}>
               <div style={{ position: "absolute", top: "-25px", left: "50%", transform: "translateX(-50%)", background: "var(--surface)", fontSize: "10px", padding: "2px 6px", borderRadius: "10px", boxShadow: "0 2px 4px rgba(0,0,0,0.1)", fontWeight: "600", color: "var(--accent)" }}>{completionRate}%</div>
            </div>
            <div className="bar solid" style={{ height: "70%" }}></div>
            <div className="bar striped" style={{ height: "45%" }}></div>
            <div className="bar striped" style={{ height: "55%" }}></div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: "1rem", padding: "0 1rem", color: "var(--muted)", fontSize: "12px", fontWeight: "600" }}>
            <span>S</span><span>M</span><span>T</span><span>W</span><span>T</span><span>F</span><span>S</span>
          </div>
        </div>

        {/* Reminders / Due Today */}
        <div className="dz-card">
          <h2 style={{ marginBottom: "0.5rem" }}>Due Today</h2>
          {data.due.length === 0 ? (
            <div style={{ margin: "auto", textAlign: "center", color: "var(--muted)" }}>
              <span style={{ fontSize: "32px", display: "block", marginBottom: "0.5rem" }}>✅</span>
              Nothing due
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem" }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "18px", fontWeight: "600", color: "var(--fg)", marginBottom: "0.25rem" }}>
                  {data.due[0].name || data.due[0].email}
                </div>
                <div style={{ fontSize: "12px", color: "var(--muted)", marginBottom: "1rem" }}>
                  Due at {when(data.due[0].due_at)}
                </div>
                <Link href={`/targets/${data.due[0].target_id}`}>
                  <button className="primary" style={{ width: "100%", borderRadius: "2rem", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}>
                    <span>✉️</span> Write Draft
                  </button>
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Project List / Buckets */}
        <div className="dz-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
            <h2>Filters</h2>
            <Link href="/targets">
              <button className="secondary" style={{ padding: "0.2rem 0.5rem", fontSize: "11px", borderRadius: "2rem" }}>+ All</button>
            </Link>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <Link href="/targets?status=draft" className="list-item" style={{ padding: "0" }}>
              <div style={{ color: "var(--accent)", fontSize: "18px", paddingRight: "0.5rem" }}>%</div>
              <div className="list-content">
                <div className="list-title">Drafts Needed</div>
                <div className="list-desc">{data.counts.draft || 0} waiting</div>
              </div>
            </Link>
            <Link href="/targets?status=paused" className="list-item" style={{ padding: "0" }}>
              <div style={{ color: "var(--warning)", fontSize: "18px", paddingRight: "0.5rem" }}>⏸</div>
              <div className="list-content">
                <div className="list-title">Paused</div>
                <div className="list-desc">{data.counts.paused || 0} paused</div>
              </div>
            </Link>
            <Link href="/targets?status=bounced" className="list-item" style={{ padding: "0" }}>
              <div style={{ color: "var(--danger)", fontSize: "18px", paddingRight: "0.5rem" }}>✕</div>
              <div className="list-content">
                <div className="list-title">Bounced</div>
                <div className="list-desc">{data.counts.bounced || 0} failed</div>
              </div>
            </Link>
          </div>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="dashboard-grid">
        {/* Recent Activity */}
        <div className="dz-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
            <h2>Recent Activity</h2>
            <span className="badge badge-completed">Live</span>
          </div>
          
          <div style={{ display: "flex", flexDirection: "column" }}>
            {data.recent.length === 0 ? (
               <p className="muted">Nothing has happened yet.</p>
            ) : (
              data.recent.slice(0, 4).map((entry, idx) => (
                <div key={idx} className="list-item">
                  <div className="list-icon" style={{ background: "var(--line)" }}>👤</div>
                  <div className="list-content">
                    <div className="list-title">{entry.type}</div>
                    <div className="list-desc">{entry.detail || "System update"}</div>
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>{when(entry.at)}</div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Project Progress (Donut Chart representation) */}
        <div className="dz-card" style={{ alignItems: "center", justifyContent: "center" }}>
          <h2 style={{ width: "100%", textAlign: "left", marginBottom: "1rem" }}>Outreach Progress</h2>
          <div className="donut-container" style={{ borderRadius: "50%", background: `conic-gradient(var(--accent) ${completionRate}%, var(--line) 0)` }}>
            {/* Inner white circle for donut effect */}
            <div style={{ position: "absolute", inset: "15px", background: "var(--surface)", borderRadius: "50%" }}></div>
            <div className="donut-text">
              <h4>{completionRate}%</h4>
              <span>Contacted</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: "1rem", marginTop: "1.5rem", fontSize: "12px", fontWeight: "500", color: "var(--fg)" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}><span style={{ color: "var(--accent)" }}>●</span> Reached</span>
            <span style={{ display: "flex", alignItems: "center", gap: "0.25rem", color: "var(--muted)" }}><span>●</span> Pending</span>
          </div>
        </div>

        {/* Campaign Status (Time Tracker style) */}
        <div className="dz-card dz-card-dark" style={{ justifyContent: "space-between" }}>
          <div>
            <h2 style={{ fontSize: "16px", color: "rgba(255,255,255,0.8)", marginBottom: "1rem" }}>Campaign Status</h2>
            <div style={{ fontSize: "36px", fontWeight: "700", marginBottom: "1rem", letterSpacing: "0.05em" }}>
              {inFlight > 0 ? "ACTIVE" : "IDLE"}
            </div>
          </div>
          <div style={{ display: "flex", gap: "1rem" }}>
            <button style={{ width: "40px", height: "40px", borderRadius: "50%", background: "white", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "16px" }}>⏸</button>
            <button style={{ width: "40px", height: "40px", borderRadius: "50%", background: "var(--danger)", color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "16px", border: "2px solid rgba(255,255,255,0.2)" }}>■</button>
          </div>
        </div>
      </div>
      
      <PwaSetup vapidKey={pushKey.key} />
    </>
  );
}
