import Link from "next/link";

import NewEmailButton from "@/components/NewEmailButton";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { MessageOut } from "@/lib/types";

function when(iso: string | null): string {
  if (!iso) return "not sent";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusOf(message: MessageOut): {
  label: string;
  tone: string;
  accent: string;
  iconBg: string;
  iconColor: string;
} {
  if (message.is_undeliverable) {
    return { label: "Undeliverable", tone: "badge-danger", accent: "var(--danger)", iconBg: "var(--danger-light)", iconColor: "var(--danger)" };
  }
  if (message.status === "failed") {
    return { label: "Failed", tone: "badge-danger", accent: "var(--danger)", iconBg: "var(--danger-light)", iconColor: "var(--danger)" };
  }
  if (message.is_reply) {
    return { label: "Replied", tone: "badge-completed", accent: "var(--accent)", iconBg: "var(--accent-light)", iconColor: "var(--accent)" };
  }
  if (message.status === "sent") {
    return { label: "Sent", tone: "badge-pending", accent: "var(--orange)", iconBg: "var(--orange-light)", iconColor: "var(--orange)" };
  }
  return { label: message.status, tone: "badge-pending", accent: "var(--line)", iconBg: "var(--cream)", iconColor: "var(--muted)" };
}

export default async function EmailsPage() {
  await requireAuth();
  const messages = await api<MessageOut[]>("/v1/messages");

  return (
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Sent Emails</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
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
        <div className="dz-card mx-auto w-full max-w-4xl gap-2">
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
                <div className="text-right text-xs text-muted">{when(message.sent_at)}</div>
              </Link>
            );
          })}
        </div>
      )}
    </>
  );
}
