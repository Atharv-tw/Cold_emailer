import Link from "next/link";

import PwaSetup from "@/components/PwaSetup";
import ScheduledStat from "@/components/ScheduledStat";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Dashboard, SentByDay } from "@/lib/types";

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function relative(iso: string | null): string {
  if (!iso) return "never";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

function sparkline(days: SentByDay[], width = 320, height = 72) {
  const values = days.map((d) => d.count);
  const max = Math.max(1, ...values);
  const stepX = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((v, i) => {
    const x = i * stepX;
    const y = height - (v / max) * (height - 10) - 5;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const linePath = `M${points.join(" L")}`;
  const areaPath = `${linePath} L${width},${height} L0,${height} Z`;
  return { linePath, areaPath };
}

export default async function DashboardPage() {
  await requireAuth();
  const [data, pushKey] = await Promise.all([
    api<Dashboard>("/v1/dashboard"),
    api<{ key: string }>("/v1/push/key").catch(() => ({ key: "" })),
  ]);

  const totalContacts = data.targets.length;
  const replied = data.counts.replied || 0;
  const scheduled = data.counts.scheduled || 0;
  const reachedCount = data.targets.filter((t) => t.touches_sent > 0).length;
  const reachedPercent = totalContacts > 0 ? Math.round((reachedCount / totalContacts) * 100) : 0;
  const sentThisPeriod = data.sent_by_day.reduce((sum, d) => sum + d.count, 0);
  const { linePath, areaPath } = sparkline(data.sent_by_day);

  const recentlyContacted = data.targets
    .filter((t) => t.last_touch_at)
    .sort((a, b) => (b.last_touch_at ?? "").localeCompare(a.last_touch_at ?? ""))
    .slice(0, 6);

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Dashboard</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            Where your outreach actually stands.
          </p>
        </div>
        <div className="header-actions">
          <Link href="/targets/new">
            <button
              className="primary"
              style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}
            >
              + Add Contact
            </button>
          </Link>
        </div>
      </div>

      {/* Row 1: replies / sent trend / total contacts */}
      <div className="grid grid-cols-4 gap-5">
        <div className="dz-card bg-[#f97316] text-white">
          <div className="stat-title">
            <span>Total Replies</span>
            <span className="stat-icon" style={{ borderColor: "rgba(255,255,255,0.5)" }}>
              ✉
            </span>
          </div>
          <div className="stat-value">{replied}</div>
          <div className="stat-trend" style={{ color: "rgba(255,255,255,0.85)" }}>
            People who wrote back
          </div>
        </div>

        <div className="dz-card col-span-2">
          <div className="stat-title">
            <span className="text-muted">Sent, last 30 days</span>
            <span className="text-fg font-semibold">{sentThisPeriod}</span>
          </div>
          <svg viewBox="0 0 320 72" className="mt-auto h-16 w-full" preserveAspectRatio="none">
            <path d={areaPath} fill="var(--accent-light)" stroke="none" />
            <path d={linePath} fill="none" stroke="var(--accent)" strokeWidth="2" />
          </svg>
        </div>

        <div className="dz-card dz-card-dark items-center justify-center text-center">
          <div
            className="donut-container"
            style={{
              borderRadius: "50%",
              background: `conic-gradient(white ${reachedPercent}%, rgba(255,255,255,0.25) 0)`,
            }}
          >
            <div style={{ position: "absolute", inset: "15px", background: "var(--accent)", borderRadius: "50%" }} />
            <div className="donut-text">
              <h4 style={{ color: "white" }}>{totalContacts}</h4>
              <span style={{ color: "rgba(255,255,255,0.85)" }}>Contacts</span>
            </div>
          </div>
          <p className="mt-3 text-xs" style={{ color: "rgba(255,255,255,0.85)" }}>
            {reachedPercent}% reached at least once
          </p>
        </div>
      </div>

      {/* Row 2: recently contacted / scheduled */}
      <div className="grid grid-cols-4 gap-5">
        <div className="dz-card col-span-3">
          <div className="mb-4 flex items-center justify-between">
            <h2>Recently Contacted</h2>
            <Link href="/targets" className="text-xs font-medium text-accent">
              View all
            </Link>
          </div>
          {recentlyContacted.length === 0 ? (
            <p className="muted">Nobody yet — send your first email to see it here.</p>
          ) : (
            <div className="flex flex-col">
              {recentlyContacted.map((target) => (
                <Link key={target.id} href={`/targets/${target.id}`} className="list-item">
                  <div className="list-icon" style={{ background: "var(--accent-light)", color: "var(--accent)" }}>
                    {(target.name || target.email).charAt(0).toUpperCase()}
                  </div>
                  <div className="list-content">
                    <div className="list-title">{target.name || target.email}</div>
                    <div className="list-desc">{target.company || "—"}</div>
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                    {relative(target.last_touch_at)}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <ScheduledStat count={scheduled} />
      </div>

      {/* Row 3: reply tracker */}
      <div className="dz-card">
        <h2 style={{ marginBottom: "1rem" }}>Reply Tracker</h2>
        {data.replies.length === 0 ? (
          <p className="muted">No replies yet.</p>
        ) : (
          <div className="flex flex-col">
            {data.replies.map((reply) => (
              <Link key={`${reply.target_id}-${reply.at}`} href={`/targets/${reply.target_id}`} className="list-item">
                <div className="list-icon" style={{ background: "var(--accent-light)", color: "var(--accent)" }}>
                  ✉
                </div>
                <div className="list-content">
                  <div className="list-title">{reply.name || "Someone"}</div>
                  <div className="list-desc">{reply.company || "—"}</div>
                </div>
                <div style={{ fontSize: "11px", color: "var(--muted)" }}>{when(reply.at)}</div>
              </Link>
            ))}
          </div>
        )}
      </div>

      <PwaSetup vapidKey={pushKey.key} />
    </>
  );
}
