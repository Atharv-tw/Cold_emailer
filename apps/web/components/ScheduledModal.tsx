"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";

import { getScheduled } from "@/app/desktop/(app)/dashboard/actions";
import Modal from "@/components/Modal";
import type { ActionError } from "@/lib/result";
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
  const [error, setError] = useState<ActionError | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (!open) return;
    setError(null);
    startTransition(async () => {
      const result = await getScheduled();
      if (result.ok) setItems(result.data.items);
      else setError(result.error);
    });
  }, [open]);

  const groups = items ? groupByDate(items) : [];

  return (
    <Modal open={open} onClose={onClose} title="Scheduled sends" widthClassName="max-w-lg">
      {pending && !items && <p className="text-sm text-muted">Loading…</p>}
      {error && (
        <p className="text-sm text-danger">
          {error.message || "Could not load the queue."}
        </p>
      )}

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
                  {/* A time here reads as a promise, and a slot with nothing
                      written in it cannot keep one - the worker looks for a
                      draft at that step and skips the row when there is none.
                      So say what is actually true of it instead. */}
                  {item.needs_draft ? (
                    <div className="text-xs font-semibold text-danger">Needs writing</div>
                  ) : item.drafted ? (
                    <div className="text-xs font-medium text-muted">{timeOf(item.due_at)}</div>
                  ) : (
                    <div className="text-right">
                      <div className="text-xs font-medium text-muted">{timeOf(item.due_at)}</div>
                      <div className="text-xs text-muted">not written yet</div>
                    </div>
                  )}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Modal>
  );
}
