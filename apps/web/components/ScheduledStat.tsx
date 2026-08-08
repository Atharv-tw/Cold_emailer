"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import ScheduledModal from "@/components/ScheduledModal";

export default function ScheduledStat({ count }: { count: number }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="dz-card dz-card-quiet w-full items-start rounded-[var(--radius-lg)] p-6 text-left transition-shadow hover:shadow-md"
      >
        <div className="stat-title w-full">
          <span className="eyebrow">Scheduled</span>
          <span className="stat-icon" style={{ color: "var(--accent)" }}>
            <Icon name="clock" size={15} />
          </span>
        </div>
        <div className="stat-value">{count}</div>
        <div className="stat-trend muted">Click to see the queue</div>
      </button>
      <ScheduledModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
