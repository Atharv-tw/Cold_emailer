"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Facet and search controls over the people list.
 *
 * The filters live in the URL, not in this component's state: the page is a
 * server component that reads the query string and asks the API, so a filtered
 * view is shareable and survives a reload. This only edits the URL.
 */

const STATUSES = [
  ["", "Any status"],
  ["draft", "Draft"],
  ["active", "In flight"],
  ["replied", "Replied"],
  ["paused", "Paused"],
  ["completed", "Completed"],
  ["bounced", "Bounced"],
  ["opted_out", "Opted out"],
] as const;

const TARGET_TYPES = [
  ["", "Anyone"],
  ["founder", "Founder"],
  ["hiring_manager", "Hiring manager"],
  ["recruiter", "Recruiter"],
  ["engineer", "Engineer"],
  ["professor", "Professor / researcher"],
] as const;

const COMPANY_TYPES = [
  ["", "Any company"],
  ["ai", "AI"],
  ["edtech", "Edtech"],
  ["fintech", "Fintech"],
  ["faang", "Big tech"],
  ["agency", "Agency"],
  ["research_lab", "Research lab"],
  ["other", "Something else"],
] as const;

const INTENTS = [
  ["", "Any goal"],
  ["internship", "Internship"],
  ["full_time", "Full-time"],
  ["freelance", "Freelance"],
  ["research", "Research"],
  ["partnership", "Working together"],
  ["feedback", "Advice / feedback"],
] as const;

export default function TargetFilters({ active }: { active: Record<string, string> }) {
  const router = useRouter();
  const pathname = usePathname();
  const [search, setSearch] = useState(active.q ?? "");

  function apply(next: Record<string, string>) {
    const params = new URLSearchParams();
    const merged = { ...active, q: search, ...next };
    for (const [key, value] of Object.entries(merged)) {
      if (value && value.trim()) params.set(key, value.trim());
    }
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  const anyActive = Object.values(active).some((value) => value && value.trim());

  return (
    <section style={{ display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "center", justifyContent: "space-between" }}>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        <select
          aria-label="Filter by status"
          value={active.status ?? ""}
          onChange={(e) => apply({ status: e.target.value })}
        >
          {STATUSES.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select
          aria-label="Filter by who they are"
          value={active.target_type ?? ""}
          onChange={(e) => apply({ target_type: e.target.value })}
        >
          {TARGET_TYPES.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select
          aria-label="Filter by company type"
          value={active.company_type ?? ""}
          onChange={(e) => apply({ company_type: e.target.value })}
        >
          {COMPANY_TYPES.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select
          aria-label="Filter by goal"
          value={active.intent ?? ""}
          onChange={(e) => apply({ intent: e.target.value })}
        >
          {INTENTS.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>
      <form
        style={{ display: "flex", gap: "0.5rem" }}
        onSubmit={(event) => {
          event.preventDefault();
          apply({ q: search });
        }}
      >
        <input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search name, company or email"
          aria-label="Search"
          style={{ width: "250px" }}
        />
        <button type="submit" className="primary">Search</button>
        {anyActive && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setSearch("");
              router.push(pathname);
            }}
          >
            Clear
          </button>
        )}
      </form>
    </section>
  );
}
