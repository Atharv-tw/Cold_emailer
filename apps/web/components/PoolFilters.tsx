"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Facet and search controls over the shared pool.
 *
 * The same URL-as-state approach as `TargetFilters`, and deliberately a
 * separate component rather than a prop on that one: the pool has no `status`
 * and no `intent` to filter by, because a contact acquires both only when
 * somebody adds them. Sharing the component would have meant a list of facets
 * to hide, which is how a filter for a field that does not exist ends up
 * shipped.
 */

const TARGET_TYPES = [
  ["", "Anyone"],
  ["founder", "Founder"],
  ["hiring_manager", "Hiring manager"],
] as const;

const COMPANY_TYPES = [
  ["", "Any company"],
  ["ai", "AI"],
  ["fintech", "Fintech"],
  ["edtech", "Edtech"],
  ["other", "Something else"],
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
        aria-label={`Filter by ${label.toLowerCase()}`}
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

export default function PoolFilters({ active }: { active: Record<string, string> }) {
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
          placeholder="Search name, company or role"
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
        <SelectGroup
          label="Who"
          options={TARGET_TYPES}
          value={active.target_type ?? ""}
          onChange={(v) => apply({ target_type: v })}
        />
        <SelectGroup
          label="Company"
          options={COMPANY_TYPES}
          value={active.company_type ?? ""}
          onChange={(v) => apply({ company_type: v })}
        />
      </div>
    </div>
  );
}
