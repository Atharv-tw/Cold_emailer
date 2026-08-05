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
    <section>
      <h2>{title}</h2>
      {withContact.length === 0 ? (
        <p className="muted">Nobody contacted yet.</p>
      ) : (
        <div className="table-scroll">
          <table className="preview">
            <thead>
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
                  <td>{label(row.value)}</td>
                  <td className="muted">{row.contacted}</td>
                  <td className="muted">{row.replied}</td>
                  <td>{pct(row.contacted ? row.replied / row.contacted : 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default async function AnalyticsPage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const data = await api<Analytics>("/v1/analytics");
  const t = data.totals;

  return (
    <main>
      <h1>Analytics</h1>
      <p>
        <Link href="/dashboard">← Dashboard</Link>
      </p>

      <section>
        <h2>Overall</h2>
        <div className="buckets">
          <div className="bucket">
            <span className="bucket-count">{pct(t.reply_rate)}</span>
            <span className="bucket-label">Reply rate</span>
          </div>
          <div className="bucket">
            <span className="bucket-count">{pct(t.bounce_rate)}</span>
            <span className="bucket-label">Bounce rate</span>
          </div>
          <div className="bucket">
            <span className="bucket-count">{pct(t.opt_out_rate)}</span>
            <span className="bucket-label">Opt-out rate</span>
          </div>
          <div className="bucket">
            <span className="bucket-count">{data.active_sequences}</span>
            <span className="bucket-label">Active</span>
          </div>
          <div className="bucket">
            <span className="bucket-count">{data.follow_ups_due}</span>
            <span className="bucket-label">Follow-ups due</span>
          </div>
          <div className="bucket">
            <span className="bucket-count">{data.stale}</span>
            <span className="bucket-label">Stale</span>
          </div>
        </div>
        <p className="muted">
          {t.sent} sent · {t.contacted} people contacted · {t.replied} replied ·{" "}
          {t.bounced} bounced · {t.opted_out} opted out. Rates are against people
          contacted, not messages sent.
        </p>
      </section>

      <Facet title="Target type" rows={data.by_target_type} />
      <Facet title="Company type" rows={data.by_company_type} />
      <Facet title="Intent" rows={data.by_intent} />
    </main>
  );
}
