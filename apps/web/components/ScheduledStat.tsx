"use client";

import { useState } from "react";

import ScheduledModal from "@/components/ScheduledModal";

export default function ScheduledStat({ count }: { count: number }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="dz-card w-full items-start text-left transition-shadow hover:shadow-md"
      >
        <div className="stat-title">
          <span className="text-muted">Scheduled</span>
          <span className="stat-icon" style={{ borderColor: "var(--line)", color: "var(--fg)" }}>
            →
          </span>
        </div>
        <div className="stat-value">{count}</div>
        <div className="stat-trend text-muted">Tap to see the queue</div>
      </button>
      <ScheduledModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
