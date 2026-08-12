import type { MessageOut } from "@/lib/types";

export type MessageTone = {
  label: string;
  tone: string;
  accent: string;
  iconBg: string;
  iconColor: string;
};

/**
 * How a sent message reads in a list: its label, its badge class and the three
 * colours the row is tinted with.
 *
 * Shared by both trees. The two email screens lay the row out differently - a
 * four-column grid on desktop, a stacked card on a phone - but "what does this
 * message's state look like" is one answer, and a second copy of this table
 * would be where the two silently stopped agreeing.
 */
export function statusOf(message: MessageOut): MessageTone {
  if (message.is_undeliverable) {
    return {
      label: "Undeliverable",
      tone: "badge-danger",
      accent: "var(--danger)",
      iconBg: "var(--danger-light)",
      iconColor: "var(--danger)",
    };
  }
  if (message.status === "failed") {
    return {
      label: "Failed",
      tone: "badge-danger",
      accent: "var(--danger)",
      iconBg: "var(--danger-light)",
      iconColor: "var(--danger)",
    };
  }
  if (message.is_reply) {
    return {
      label: "Replied",
      tone: "badge-completed",
      accent: "var(--accent)",
      iconBg: "var(--accent-light)",
      iconColor: "var(--accent)",
    };
  }
  if (message.status === "sent") {
    return {
      label: "Sent",
      tone: "badge-pending",
      accent: "var(--orange)",
      iconBg: "var(--orange-light)",
      iconColor: "var(--orange)",
    };
  }
  return {
    label: message.status,
    tone: "badge-pending",
    accent: "var(--line)",
    iconBg: "var(--cream)",
    iconColor: "var(--muted)",
  };
}
