import Link from "next/link";

import Icon from "@/components/Icon";
import TargetFilters from "@/components/TargetFilters";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Target } from "@/lib/types";

type Search = Record<string, string | string[] | undefined>;

const FACETS = ["status", "target_type", "company_type", "intent", "q"] as const;

// The same badge vocabulary the emails list uses, rather than a second set of
// status colours invented for this screen.
const STATUS_BADGE: Record<string, string> = {
  active: "badge-pending",
  paused: "badge-pending",
  bounced: "badge-danger",
  opted_out: "badge-danger",
  replied: "badge-completed",
  completed: "badge-completed",
};

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

export default async function TargetsPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  await requireAuth();

  const params = await searchParams;
  const query = new URLSearchParams();
  for (const key of FACETS) {
    const value = one(params[key]).trim();
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  const targets = await api<Target[]>(`/v1/targets${suffix ? `?${suffix}` : ""}`);

  const active: Record<string, string> = {};
  for (const key of FACETS) active[key] = one(params[key]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>People</h1>
          <p>
            {targets.length} {targets.length === 1 ? "person" : "people"}
            {suffix ? " match these filters" : ""}.
          </p>
        </div>
        <div className="header-actions">
          <Link href="/import" className="flex-1">
            <button className="secondary flex w-full items-center justify-center gap-1.5">
              <Icon name="upload" size={15} /> Import
            </button>
          </Link>
          <Link href="/targets/new" className="flex-1">
            <button className="accent flex w-full items-center justify-center gap-1.5">
              <Icon name="plus" size={15} strokeWidth={2.2} /> Add
            </button>
          </Link>
        </div>
      </div>

      <TargetFilters active={active} />

      {targets.length === 0 ? (
        <div className="dz-card items-center py-12 text-center">
          <Icon name="users" size={32} className="mb-3 text-muted opacity-40" />
          <p className="muted">Nobody here.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {targets.map((target) => (
            <Link
              key={target.id}
              href={`/targets/${target.id}`}
              className="flex flex-col gap-3 rounded-xl bg-surface p-4 ring-1 ring-line"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 flex-col">
                  <span className="truncate text-[15px] font-bold text-fg">
                    {target.name || target.email}
                  </span>
                  <span className="truncate text-sm text-muted">{target.company || "—"}</span>
                </div>
                <span className={`badge shrink-0 ${STATUS_BADGE[target.status] ?? "badge-pending"}`}>
                  {target.status.replace(/_/g, " ")}
                </span>
              </div>

              <div className="flex items-center justify-between border-t border-line pt-2 text-xs text-muted">
                <span>{target.target_type.replace(/_/g, " ")}</span>
                <span className="flex items-center gap-1">
                  <Icon name="send" size={12} />
                  {target.touches_sent} / {target.touches_sent + target.touches_remaining} touches
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
