"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Facet and search controls over the people list.
 *
 * The filters live in the URL, not in this component's state: the page is a
 * server component that reads the query string and asks the API, so a filtered
 * view is shareable and survives a reload. This only edits the URL.
 *
 * Each facet is single-select - the API only accepts one value per facet
 * today (`status`, `target_type`, etc. are plain query params, not lists) -
 * so these render as chip toggles rather than a multi-select control.
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

function SelectGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly (readonly [string, string])[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-line bg-surface px-2 py-1 text-sm text-fg outline-none focus:border-accent"
      >
        {options.map(([optionValue, text]) => (
          <option key={optionValue} value={optionValue}>
            {text}
          </option>
        ))}
      </select>
    </div>
  );
}

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
    <div className="flex flex-col gap-3">
      <form
        className="flex gap-2"
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
          className="flex-1"
        />
        <button type="submit" className="primary">
          Search
        </button>
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

      <div className="flex flex-wrap items-center gap-4 pt-2">
        <SelectGroup label="Status" options={STATUSES} value={active.status ?? ""} onChange={(v) => apply({ status: v })} />
        <SelectGroup label="Who" options={TARGET_TYPES} value={active.target_type ?? ""} onChange={(v) => apply({ target_type: v })} />
        <SelectGroup
          label="Company"
          options={COMPANY_TYPES}
          value={active.company_type ?? ""}
          onChange={(v) => apply({ company_type: v })}
        />
        <SelectGroup label="Goal" options={INTENTS} value={active.intent ?? ""} onChange={(v) => apply({ intent: v })} />
      </div>
    </div>
  );
}
