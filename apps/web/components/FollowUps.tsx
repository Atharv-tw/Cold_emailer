import Link from "next/link";

import Icon from "@/components/Icon";
import LocalTime from "@/components/LocalTime";
import type { ScheduledItem } from "@/lib/types";

/**
 * Every follow-up that is coming, most urgent first.
 *
 * The distinction this container exists to draw: a schedule row is a slot, and
 * a slot with no draft in it sends nothing. The worker looks for a draft at
 * that step, finds none, and skips - so a follow-up nobody wrote quietly never
 * happens, and until this list existed there was nowhere that said so.
 *
 * Three bands, ranked by the API so the modal and this agree:
 *
 *   0  parked - it was due, it was never written, the worker has stopped
 *      scanning it. Red, and the only one that asks for something.
 *   1  unwritten and due within a day. Not late yet; will be.
 *   2  everything else, which is the normal case and stays quiet.
 */

const WHEN: Intl.DateTimeFormatOptions = {
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
};

export default function FollowUps({
  items,
  className = "",
}: {
  items: ScheduledItem[];
  /** Grid placement from the caller; the card styling stays here. */
  className?: string;
}) {
  if (items.length === 0) {
    return (
      <div className={`dz-card ${className}`.trim()}>
        <h2 style={{ marginBottom: "0.75rem" }}>Follow-ups</h2>
        <p className="muted">
          Nothing scheduled. A follow-up is queued automatically each time an
          email sends.
        </p>
      </div>
    );
  }

  const needsWriting = items.filter((item) => item.needs_draft).length;

  return (
    <div className={`dz-card ${className}`.trim()}>
      <div className="mb-3 flex items-center justify-between">
        <h2>Follow-ups</h2>
        {needsWriting > 0 && (
          <span className="text-xs font-semibold text-danger">
            {needsWriting} need{needsWriting === 1 ? "s" : ""} writing
          </span>
        )}
      </div>

      <div className="flex flex-col">
        {items.map((item) => (
          <Link
            key={`${item.target_id}-${item.step}`}
            href={`/targets/${item.target_id}`}
            className="dz-list-item"
          >
            <div
              className="list-icon"
              style={item.needs_draft ? { color: "var(--danger)" } : undefined}
            >
              <Icon name={item.needs_draft ? "x" : "clock"} size={16} />
            </div>

            <div className="list-content">
              <div className="list-title">{item.name || item.email}</div>
              <div className="list-desc">
                {item.company || "—"} · touch {item.step}
              </div>
            </div>

            {/* The right-hand column is the whole point: what this row needs,
                not merely when it is. A time next to an empty draft is the
                promise that was being broken. */}
            {item.needs_draft ? (
              <div className="text-right">
                <div className="text-xs font-semibold text-danger">Draft it now</div>
                <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                  was due <LocalTime iso={item.due_at} options={WHEN} />
                </div>
              </div>
            ) : (
              <div className="text-right">
                <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                  <LocalTime iso={item.due_at} options={WHEN} />
                </div>
                {!item.drafted && (
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>not written yet</div>
                )}
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
