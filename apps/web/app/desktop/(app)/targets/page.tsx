import Link from "next/link";

import Avatar from "@/components/Avatar";
import Icon from "@/components/Icon";
import ImportButton from "@/components/ImportButton";
import TargetFilters from "@/components/TargetFilters";
import TargetTileMenu from "@/components/TargetTileMenu";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Target } from "@/lib/types";

type Search = Record<string, string | string[] | undefined>;

const FACETS = ["status", "target_type", "company_type", "intent", "q"] as const;

const STATUS_TONE: Record<string, string> = {
  completed: "badge-completed",
  replied: "badge-completed",
  bounced: "badge-danger",
  opted_out: "badge-danger",
};

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function relative(iso: string | null): string {
  if (!iso) return "never contacted";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "touched today";
  if (days === 1) return "touched yesterday";
  return `touched ${days}d ago`;
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
          <h1>Contacts</h1>
          <p>
            {targets.length} {targets.length === 1 ? "person" : "people"} match these filters
          </p>
        </div>
        <div className="header-actions">
          <Link href="/pool">
            <button style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}>
              Browse pool
            </button>
          </Link>
          <ImportButton />
          <Link href="/targets/new">
            <button
              className="primary"
              style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}
            >
              + Add Contact
            </button>
          </Link>
        </div>
      </div>

      <div className="dz-card">
        <TargetFilters active={active} />
      </div>

      {targets.length === 0 ? (
        <div className="dz-card items-center py-16 text-center text-muted">
          <div style={{ marginBottom: "1rem" }}>
            <Icon name="users" size={48} />
          </div>
          <h3>Nobody found</h3>
          <p>Try adjusting your filters or adding a new contact.</p>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {targets.map((target) => (
            <Link
              key={target.id}
              href={`/targets/${target.id}`}
              className="dz-card gap-3 transition-shadow hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-3">
                  <Avatar name={target.name || target.email} />
                  <div>
                    <div className="font-semibold text-fg">{target.name || target.email}</div>
                    <div className="text-xs text-muted">{target.role || "—"}</div>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <span className={`badge ${STATUS_TONE[target.status] ?? "badge-pending"}`}>
                    {target.status.replace(/_/g, " ")}
                  </span>
                  <TargetTileMenu target={target} />
                </div>
              </div>

              <div className="text-sm text-fg">{target.company || "—"}</div>

              <div className="flex flex-wrap gap-1.5">
                {target.target_type && (
                  <span className="rounded-full bg-bg px-2.5 py-1 text-[11px] font-medium text-muted">
                    {target.target_type.replace(/_/g, " ")}
                  </span>
                )}
                {target.company_type && (
                  <span className="rounded-full bg-bg px-2.5 py-1 text-[11px] font-medium text-muted">
                    {target.company_type.replace(/_/g, " ")}
                  </span>
                )}
              </div>

              <div className="mt-auto text-xs text-muted">
                {target.touches_sent} touch{target.touches_sent === 1 ? "" : "es"} ·{" "}
                {relative(target.last_touch_at)}
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
