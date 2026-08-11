import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import TargetFilters from "@/components/TargetFilters";
import Icon from "@/components/Icon";
import { api } from "@/lib/api";
import type { Target } from "@/lib/types";

type Search = Record<string, string | string[] | undefined>;

const FACETS = ["status", "target_type", "company_type", "intent", "q"] as const;

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function getStatusColor(status: string) {
  switch (status) {
    case "active": return "text-[var(--lime)]";
    case "paused": return "text-yellow-400";
    case "bounced": return "text-red-400";
    case "completed": return "text-green-400";
    default: return "text-white/60";
  }
}

export default async function TargetsPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

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
    <div className="flex flex-col gap-6 pt-2">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>People</h1>
        <div className="flex gap-2">
          <Link href="/mobile/import" className="flex items-center gap-1 bg-white/10 hover:bg-white/15 px-3 py-1.5 rounded-full text-xs font-semibold text-white transition-colors">
            <Icon name="upload" size={14} /> Import
          </Link>
          <Link href="/mobile/targets/new" className="flex items-center gap-1 bg-[var(--lime)] hover:opacity-90 px-3 py-1.5 rounded-full text-xs font-bold text-[var(--ink)] transition-colors">
            <Icon name="plus" size={14} /> Add
          </Link>
        </div>
      </div>

      <TargetFilters active={active} />

      <p className="text-sm text-white/50 -mt-2">
        {targets.length} {targets.length === 1 ? "person" : "people"}
        {suffix ? " match these filters" : ""}.
      </p>

      {targets.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 bg-white/5 border border-white/10 rounded-2xl">
          <Icon name="users" size={32} className="text-white/20 mb-3" />
          <p className="text-white/50">Nobody here.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {targets.map((target) => (
            <Link 
              key={target.id} 
              href={`/mobile/targets/${target.id}`}
              className="flex flex-col gap-3 p-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl transition-colors"
            >
              <div className="flex justify-between items-start">
                <div className="flex flex-col">
                  <span className="font-bold text-white text-[15px]">{target.name || target.email}</span>
                  <span className="text-sm text-white/60">{target.company || <span className="opacity-50">—</span>}</span>
                </div>
                <div className={`text-xs font-bold uppercase tracking-wider ${getStatusColor(target.status)} bg-white/5 px-2 py-1 rounded-md`}>
                  {target.status}
                </div>
              </div>

              <div className="flex items-center justify-between text-xs text-white/50 pt-2 border-t border-white/10">
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
    </div>
  );
}
