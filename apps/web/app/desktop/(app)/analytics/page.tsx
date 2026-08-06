import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { api } from "@/lib/api";
import type { Analytics, AnalyticsFacetRow } from "@/lib/types";

function pct(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

function label(value: string): string {
  return value === "unset" ? "unset" : value.replace(/_/g, " ");
}

function Facet({ title, rows }: { title: string; rows: AnalyticsFacetRow[] }) {
  const withContact = rows.filter((row) => row.contacted > 0);
  return (
    <div className="dz-card" style={{ padding: "0", overflow: "hidden" }}>
      <div style={{ padding: "1.5rem", borderBottom: "1px solid var(--line)" }}>
        <h2 style={{ fontSize: "18px" }}>{title}</h2>
      </div>
      {withContact.length === 0 ? (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--muted)" }}>
          Nobody contacted yet.
        </div>
      ) : (
        <div className="table-scroll">
          <table className="preview">
            <thead style={{ background: "#fcfcfc" }}>
              <tr>
                <th>{title}</th>
                <th>Contacted</th>
                <th>Replied</th>
                <th>Reply rate</th>
              </tr>
            </thead>
            <tbody>
              {withContact.map((row) => (
                <tr key={row.value}>
                  <td style={{ fontWeight: "500", color: "var(--fg)" }}>{label(row.value)}</td>
                  <td className="muted">{row.contacted}</td>
                  <td className="muted">{row.replied}</td>
                  <td>
                    <span className="badge badge-completed">
                      {pct(row.contacted ? row.replied / row.contacted : 0)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default async function AnalyticsPage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const data = await api<Analytics>("/v1/analytics");
  const t = data.totals;

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Analytics</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            {t.sent} sent · {t.contacted} people contacted · {t.replied} replied
          </p>
        </div>
      </div>

      <div className="stats-grid" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
        <div className="dz-card" style={{ alignItems: "center", textAlign: "center", padding: "1rem" }}>
          <div className="stat-title" style={{ justifyContent: "center", marginBottom: "0.5rem" }}><span className="muted">Reply Rate</span></div>
          <div className="stat-value" style={{ fontSize: "24px" }}>{pct(t.reply_rate)}</div>
        </div>
        <div className="dz-card" style={{ alignItems: "center", textAlign: "center", padding: "1rem" }}>
          <div className="stat-title" style={{ justifyContent: "center", marginBottom: "0.5rem" }}><span className="muted">Bounce Rate</span></div>
          <div className="stat-value" style={{ fontSize: "24px" }}>{pct(t.bounce_rate)}</div>
        </div>
        <div className="dz-card" style={{ alignItems: "center", textAlign: "center", padding: "1rem" }}>
          <div className="stat-title" style={{ justifyContent: "center", marginBottom: "0.5rem" }}><span className="muted">Opt-out Rate</span></div>
          <div className="stat-value" style={{ fontSize: "24px" }}>{pct(t.opt_out_rate)}</div>
        </div>
        <div className="dz-card" style={{ alignItems: "center", textAlign: "center", padding: "1rem", background: "var(--accent-light)", color: "var(--accent)" }}>
          <div className="stat-title" style={{ justifyContent: "center", marginBottom: "0.5rem", color: "var(--accent)" }}>Active</div>
          <div className="stat-value" style={{ fontSize: "24px" }}>{data.active_sequences}</div>
        </div>
        <div className="dz-card" style={{ alignItems: "center", textAlign: "center", padding: "1rem" }}>
          <div className="stat-title" style={{ justifyContent: "center", marginBottom: "0.5rem" }}><span className="muted">Follow-ups</span></div>
          <div className="stat-value" style={{ fontSize: "24px" }}>{data.follow_ups_due}</div>
        </div>
        <div className="dz-card" style={{ alignItems: "center", textAlign: "center", padding: "1rem" }}>
          <div className="stat-title" style={{ justifyContent: "center", marginBottom: "0.5rem" }}><span className="muted">Stale</span></div>
          <div className="stat-value" style={{ fontSize: "24px" }}>{data.stale}</div>
        </div>
      </div>

      <div className="dashboard-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <Facet title="Target type" rows={data.by_target_type} />
        <Facet title="Company type" rows={data.by_company_type} />
        <Facet title="Intent" rows={data.by_intent} />
      </div>
    </>
  );
}
