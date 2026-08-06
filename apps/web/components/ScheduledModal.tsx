"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";

import { getScheduled } from "@/app/desktop/(app)/dashboard/actions";
import Modal from "@/components/Modal";
import type { ScheduledItem } from "@/lib/types";

function dateKey(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

function timeOf(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function groupByDate(items: ScheduledItem[]): [string, ScheduledItem[]][] {
  const groups = new Map<string, ScheduledItem[]>();
  for (const item of [...items].sort((a, b) => a.due_at.localeCompare(b.due_at))) {
    const key = dateKey(item.due_at);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  return [...groups.entries()];
}

export default function ScheduledModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [items, setItems] = useState<ScheduledItem[] | null>(null);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (!open) return;
    setError("");
    startTransition(async () => {
      try {
        const result = await getScheduled();
        setItems(result.items);
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Could not load the queue.");
      }
    });
  }, [open]);

  const groups = items ? groupByDate(items) : [];

  return (
    <Modal open={open} onClose={onClose} title="Scheduled sends" widthClassName="max-w-lg">
      {pending && !items && <p className="text-sm text-muted">Loading…</p>}
      {error && <p className="text-sm text-danger">{error}</p>}

      {items && items.length === 0 && (
        <p className="text-sm text-muted">Nothing is queued right now.</p>
      )}

      <div className="flex flex-col gap-5">
        {groups.map(([date, dayItems]) => (
          <div key={date}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{date}</h3>
            <div className="flex flex-col gap-1">
              {dayItems.map((item) => (
                <Link
                  key={`${item.target_id}-${item.step}`}
                  href={`/targets/${item.target_id}`}
                  onClick={onClose}
                  className="flex items-center justify-between rounded-lg px-3 py-2 hover:bg-bg"
                >
                  <div>
                    <div className="text-sm font-medium text-fg">{item.name || item.email}</div>
                    <div className="text-xs text-muted">
                      {item.company || "—"} · touch {item.step}
                    </div>
                  </div>
                  <div className="text-xs font-medium text-muted">{timeOf(item.due_at)}</div>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Modal>
  );
}
