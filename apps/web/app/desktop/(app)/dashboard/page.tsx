import Link from "next/link";

import FollowUps from "@/components/FollowUps";
import Icon from "@/components/Icon";
import LocalTime from "@/components/LocalTime";
import PwaSetup from "@/components/PwaSetup";
import ScheduledStat from "@/components/ScheduledStat";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Dashboard, ScheduledOut, SentByDay } from "@/lib/types";

// A clock time has to be formatted in the browser - see LocalTime.
const WHEN: Intl.DateTimeFormatOptions = {
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
};

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
  const [data, pushKey, followUps] = await Promise.all([
    api<Dashboard>("/v1/dashboard"),
    api<{ key: string }>("/v1/push/key").catch(() => ({ key: "" })),
    // Already ranked by urgency server-side. A failure here must not take the
    // dashboard down with it - the rest of this page is still worth showing.
    api<ScheduledOut>("/v1/dashboard/scheduled").catch(() => ({ items: [] })),
  ]);

  const totalContacts = data.targets.length;
  const replied = data.counts.replied || 0;
  const unreadReplies = data.counts.unread_replies || 0;
  const scheduled = data.counts.scheduled || 0;
  const reachedCount = data.targets.filter((t) => t.touches_sent > 0).length;
  const reachedPercent = totalContacts > 0 ? Math.round((reachedCount / totalContacts) * 100) : 0;
  const sentThisPeriod = data.sent_by_day.reduce((sum, d) => sum + d.count, 0);
  const { linePath, areaPath } = sparkline(data.sent_by_day);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Where your outreach actually stands.</p>
        </div>
        <div className="header-actions">
          <Link href="/targets/new">
            <button className="accent flex items-center gap-1.5">
              <Icon name="plus" size={17} strokeWidth={2.2} />
              Add contact
            </button>
          </Link>
        </div>
      </div>

      {/* Row 1: replies / sent trend / total contacts */}
      <div className="grid grid-cols-4 gap-5">
        <div className="dz-card dz-card-lime">
          <div className="stat-title">
            <span className="font-semibold">Total replies</span>
            <span className="stat-icon">
              <Icon name="mail" size={15} />
            </span>
          </div>
          <div className="stat-value">{replied}</div>
          <div className="stat-trend" style={{ color: "rgba(10,10,10,0.65)" }}>
            {unreadReplies > 0
              ? `${unreadReplies} you haven't read`
              : "People who wrote back"}
          </div>
        </div>

        <div className="dz-card col-span-2">
          <div className="stat-title">
            <span className="eyebrow">Sent · last 30 days</span>
            <span
              className="text-fg"
              style={{ fontFamily: "var(--font-display)", fontSize: "20px", fontWeight: 700, letterSpacing: "-0.03em" }}
            >
              {sentThisPeriod}
            </span>
          </div>
          <svg viewBox="0 0 320 72" className="mt-auto h-16 w-full" preserveAspectRatio="none">
            <path d={areaPath} fill="var(--lime)" fillOpacity="0.45" stroke="none" />
            <path d={linePath} fill="none" stroke="var(--ink)" strokeWidth="2" strokeLinejoin="round" />
          </svg>
        </div>

        <div className="dz-card dz-card-dark items-center justify-center text-center">
          <div
            className="donut-container"
            style={{
              borderRadius: "50%",
              background: `conic-gradient(var(--lime) ${reachedPercent}%, rgba(255,255,255,0.14) 0)`,
            }}
          >
            <div style={{ position: "absolute", inset: "15px", background: "var(--ink)", borderRadius: "50%" }} />
            <div className="donut-text">
              <h4 style={{ color: "var(--lime)" }}>{totalContacts}</h4>
              <span style={{ color: "rgba(255,255,255,0.7)" }}>Contacts</span>
            </div>
          </div>
          <p className="mt-2 text-xs" style={{ color: "rgba(255,255,255,0.7)" }}>
            {reachedPercent}% reached at least once
          </p>
        </div>
      </div>

      {/* Row 2: follow-ups / scheduled. This slot used to hold "Recently
          contacted", which was a record of work already done - pleasant, but
          it asked nothing. What goes here now is the list that does: a
          follow-up nobody writes never sends. */}
      <div className="grid grid-cols-4 gap-5">
        <FollowUps items={followUps.items} className="col-span-3" />
        <ScheduledStat count={scheduled} />
      </div>

      {/* Row 3: reply tracker */}
      <div className="dz-card">
        <h2 style={{ marginBottom: "0.75rem" }}>Reply tracker</h2>
        {data.replies.length === 0 ? (
          <p className="muted">No replies yet.</p>
        ) : (
          <div className="flex flex-col">
            {data.replies.map((reply) => (
              <Link key={`${reply.target_id}-${reply.at}`} href={`/targets/${reply.target_id}`} className="dz-list-item">
                <div className="list-icon">
                  <Icon name="mail" size={16} />
                </div>
                <div className="list-content">
                  <div className="list-title">
                    {reply.name || "Someone"}
                    {/* A dot rather than bold text: the row is a link, and
                        weight changes shift the layout as they are read. */}
                    {reply.unread && (
                      <span
                        aria-label="unread"
                        title="You have not opened this reply yet"
                        style={{
                          display: "inline-block",
                          width: "7px",
                          height: "7px",
                          borderRadius: "50%",
                          background: "var(--accent)",
                          marginLeft: "0.5rem",
                          verticalAlign: "middle",
                        }}
                      />
                    )}
                  </div>
                  <div className="list-desc">{reply.company || "—"}</div>
                </div>
                <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                  <LocalTime iso={reply.at} options={WHEN} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      <PwaSetup vapidKey={pushKey.key} />
    </>
  );
}
