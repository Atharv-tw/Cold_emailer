"use client";

import { useState } from "react";

import type { AnalyticsFacetRow } from "@/lib/types";

function pct(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

function label(value: string): string {
  return value === "unset" ? "unset" : value.replace(/_/g, " ");
}

const TABS = [
  ["target_type", "Who"],
  ["company_type", "Company"],
  ["intent", "Goal"],
] as const;

export default function AnalyticsTabs({
  byTargetType,
  byCompanyType,
  byIntent,
}: {
  byTargetType: AnalyticsFacetRow[];
  byCompanyType: AnalyticsFacetRow[];
  byIntent: AnalyticsFacetRow[];
}) {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("target_type");
  const rows = {
    target_type: byTargetType,
    company_type: byCompanyType,
    intent: byIntent,
  }[tab].filter((row) => row.contacted > 0);

  return (
    <div className="dz-card" style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ padding: "1rem 1.5rem", borderBottom: "1px solid var(--line)", display: "flex", gap: "0.5rem" }}>
        {TABS.map(([value, text]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              tab === value ? "bg-accent-light text-accent" : "text-muted"
            }`}
          >
            {text}
          </button>
        ))}
      </div>

      {rows.length === 0 ? (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--muted)" }}>
          Nobody contacted yet in this breakdown.
        </div>
      ) : (
        <div className="table-scroll">
          <table className="preview">
            <thead style={{ background: "#fcfcfc" }}>
              <tr>
                <th>Breakdown</th>
                <th>Contacted</th>
                <th>Replied</th>
                <th>Reply rate</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.value}>
                  <td style={{ fontWeight: "500", color: "var(--fg)" }}>{label(row.value)}</td>
                  <td className="muted">{row.contacted}</td>
                  <td className="muted">{row.replied}</td>
                  <td>
                    <span className="badge badge-completed">
                      {pct(row.contacted ? row.replied / row.contacted : 0)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
