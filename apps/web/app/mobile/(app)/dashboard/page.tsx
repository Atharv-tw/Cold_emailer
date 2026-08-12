import Link from "next/link";

import FollowUps from "@/components/FollowUps";
import Icon from "@/components/Icon";
import LocalTime from "@/components/LocalTime";
import PwaSetup from "@/components/PwaSetup";
import ScheduledStat from "@/components/ScheduledStat";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Dashboard, ScheduledOut } from "@/lib/types";

// A clock time has to be formatted in the browser - see LocalTime.
const WHEN: Intl.DateTimeFormatOptions = {
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
};

function Stat({
  label,
  value,
  trend,
  variant = "",
  icon,
}: {
  label: string;
  value: number | string;
  trend: string;
  variant?: string;
  icon: "mail" | "users" | "send";
}) {
  return (
    <div className={`dz-card ${variant}`}>
      <div className="stat-title">
        <span className="font-semibold">{label}</span>
        <span className="stat-icon">
          <Icon name={icon} size={14} />
        </span>
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-trend muted">{trend}</div>
    </div>
  );
}

/**
 * The mobile dashboard.
 *
 * This replaces a bare-HTML page left over from before the redesign - it had
 * no styling at all and leaned on `.buckets`/`.bucket-count`, classes that
 * were never defined in `globals.css`, so it rendered as a stack of unstyled
 * divs.
 *
 * It reads the same three endpoints as desktop and shows the same things in
 * the same order, in one column. What is deliberately dropped: the sparkline
 * and the reach donut. `.donut-container` is a fixed 140px and the sparkline
 * is drawn on a 320-wide viewBox - both survive the squeeze, but neither is
 * legible enough at this width to earn the vertical space, and the number
 * underneath each of them says the same thing.
 */
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

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Where your outreach actually stands.</p>
        </div>
        <div className="header-actions">
          <Link href="/targets/new" className="w-full">
            <button className="accent flex w-full items-center justify-center gap-1.5">
              <Icon name="plus" size={17} strokeWidth={2.2} />
              Add contact
            </button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat
          label="Replies"
          value={replied}
          variant="dz-card-lime"
          icon="mail"
          trend={unreadReplies > 0 ? `${unreadReplies} unread` : "People who wrote back"}
        />
        <Stat
          label="Contacts"
          value={totalContacts}
          icon="users"
          trend={`${reachedPercent}% reached once`}
        />
        <Stat label="Sent" value={sentThisPeriod} icon="send" trend="Last 30 days" />
        <ScheduledStat count={scheduled} />
      </div>

      <FollowUps items={followUps.items} />

      <div className="dz-card">
        <h2 style={{ marginBottom: "0.75rem" }}>Reply tracker</h2>
        {data.replies.length === 0 ? (
          <p className="muted">No replies yet.</p>
        ) : (
          <div className="flex flex-col">
            {data.replies.map((reply) => (
              <Link
                key={`${reply.target_id}-${reply.at}`}
                href={`/targets/${reply.target_id}`}
                className="dz-list-item"
              >
                <div className="list-icon">
                  <Icon name="mail" size={16} />
                </div>
                <div className="list-content min-w-0">
                  <div className="list-title truncate">
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
                  <div className="list-desc truncate">{reply.company || "—"}</div>
                </div>
                <div className="shrink-0" style={{ fontSize: "11px", color: "var(--muted)" }}>
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
