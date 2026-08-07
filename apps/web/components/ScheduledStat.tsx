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
        className="dz-card w-full items-start bg-purple-light text-left transition-shadow hover:shadow-md"
      >
        <div className="stat-title">
          <span className="text-purple">Scheduled</span>
          <span className="stat-icon" style={{ borderColor: "var(--purple)", color: "var(--purple)" }}>
            →
          </span>
        </div>
        <div className="stat-value text-purple">{count}</div>
        <div className="stat-trend" style={{ color: "var(--purple)", opacity: 0.75 }}>
          Tap to see the queue
        </div>
      </button>
      <ScheduledModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
