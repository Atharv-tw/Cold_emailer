import Icon, { type IconName } from "@/components/Icon";
import LocalTime from "@/components/LocalTime";
import type { TimelineEntry } from "@/lib/types";

function iconFor(type: string): IconName {
  if (type.includes("sent")) return "send";
  if (type.includes("cancel") || type.includes("fail")) return "x";
  if (type.includes("queue")) return "clock";
  if (type.includes("created")) return "sparkle";
  return "info";
}

/**
 * Event details arrive with timestamps embedded in the sentence. They are
 * written by the API in UTC, so they have to be split back out and handed to
 * `LocalTime` - rendering the raw string would show a time nobody is in.
 */
function EventDetailText({ text }: { text: string }) {
  if (!text) return null;
  const parts = text.split(/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:\d{2}|Z))/);
  return (
    <div className="list-desc">
      {parts.map((part, i) =>
        part.match(/^\d{4}-\d{2}-\d{2}T/) ? <LocalTime key={i} iso={part} /> : <span key={i}>{part}</span>,
      )}
    </div>
  );
}

/** What has happened to one target, oldest first. Shared by both trees. */
export default function TimelineList({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) return <p className="muted">Nothing has happened yet.</p>;

  return (
    <div className="flex flex-col">
      {entries.map((entry, index) => (
        <div key={index} className="dz-list-item">
          <div className="list-icon" style={{ background: "var(--line)", color: "var(--fg)" }}>
            <Icon name={iconFor(entry.type)} size={16} />
          </div>
          <div className="list-content min-w-0">
            <div className="list-title">{entry.type}</div>
            {entry.detail && <EventDetailText text={entry.detail} />}
          </div>
          <div className="shrink-0" style={{ fontSize: "11px", color: "var(--muted)" }}>
            <LocalTime iso={entry.at} />
          </div>
        </div>
      ))}
    </div>
  );
}
