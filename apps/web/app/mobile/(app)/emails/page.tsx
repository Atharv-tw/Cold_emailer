import Link from "next/link";

import LocalTime from "@/components/LocalTime";
import NewEmailButton from "@/components/NewEmailButton";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import { statusOf } from "@/lib/message-status";
import type { MessageOut } from "@/lib/types";

// Clock times are formatted in the browser - see LocalTime. Formatting them
// here would use the server's timezone, which is UTC.
const WHEN: Intl.DateTimeFormatOptions = {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
};

export default async function EmailsPage() {
  await requireAuth();
  const messages = await api<MessageOut[]>("/v1/messages");

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Sent Emails</h1>
          <p>
            {messages.length} email{messages.length === 1 ? "" : "s"} across everyone you&rsquo;ve
            contacted
          </p>
        </div>
        <div className="header-actions">
          <NewEmailButton />
        </div>
      </div>

      {messages.length === 0 ? (
        <div className="dz-card items-center py-12 text-center text-muted">
          <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>✉️</div>
          <h3>Nothing sent yet</h3>
          <p>Emails you send will show up here.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {messages.map((message) => {
            const tone = statusOf(message);
            return (
              // Desktop puts icon, subject, badge and time on one
              // `grid-cols-[auto_minmax(0,1fr)_auto_96px]` row. That row needs
              // ~500px before the subject starts truncating to nothing, so
              // here it becomes two: what the email is, then what happened to
              // it.
              <Link
                key={message.id}
                href={`/targets/${message.target_id}`}
                className={`flex flex-col gap-2 rounded-xl border-l-4 bg-surface p-3 ring-1 ring-line ${
                  message.is_undeliverable ? "opacity-60" : ""
                }`}
                style={{ borderColor: tone.accent }}
              >
                <div className="flex items-start gap-3">
                  <div className="list-icon shrink-0" style={{ background: tone.iconBg, color: tone.iconColor }}>
                    {(message.target_name || message.target_email).charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-fg">
                      {message.subject || "(no subject)"}
                    </div>
                    <div className="truncate text-xs text-muted">
                      {message.target_name || message.target_email}
                      {message.target_company ? ` · ${message.target_company}` : ""}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2 border-t border-line pt-2">
                  <span className={`badge ${tone.tone}`}>{tone.label}</span>
                  <span className="text-xs text-muted">
                    {message.sent_at ? <LocalTime iso={message.sent_at} options={WHEN} /> : "not sent"}
                  </span>
                </div>

                {message.error && (
                  <p className="text-xs text-danger">{message.error}</p>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </>
  );
}
