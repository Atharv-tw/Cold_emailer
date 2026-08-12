import Link from "next/link";

import NewEmailButton from "@/components/NewEmailButton";
import LocalTime from "@/components/LocalTime";
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
            {messages.length} email{messages.length === 1 ? "" : "s"} across everyone you&rsquo;ve contacted
          </p>
        </div>
        <div className="header-actions">
          <NewEmailButton />
        </div>
      </div>

      {messages.length === 0 ? (
        <div className="dz-card items-center py-16 text-center text-muted">
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>✉️</div>
          <h3>Nothing sent yet</h3>
          <p>Emails you send will show up here.</p>
        </div>
      ) : (
        <div className="dz-card w-full gap-2">
          {messages.map((message) => {
            const tone = statusOf(message);
            return (
              <Link
                key={message.id}
                href={`/targets/${message.target_id}`}
                className={`grid grid-cols-[auto_minmax(0,1fr)_auto_96px] items-center gap-4 rounded-xl border-l-4 px-3 py-3 transition-colors hover:bg-bg ${
                  message.is_undeliverable ? "opacity-60" : ""
                }`}
                style={{ borderColor: tone.accent }}
              >
                <div className="list-icon" style={{ background: tone.iconBg, color: tone.iconColor }}>
                  {(message.target_name || message.target_email).charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-fg">
                    {message.subject || "(no subject)"}
                  </div>
                  <div className="truncate text-xs text-muted">
                    {message.target_name || message.target_email} · {message.target_company || "—"}
                    {message.error && ` · ${message.error}`}
                  </div>
                </div>
                <span className={`badge ${tone.tone}`}>{tone.label}</span>
                <div className="text-right text-xs text-muted">
                  {message.sent_at ? <LocalTime iso={message.sent_at} options={WHEN} /> : "not sent"}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </>
  );
}
