import AnalyticsTabs from "@/components/AnalyticsTabs";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Analytics } from "@/lib/types";

function pct(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

/**
 * The three rates, then the same facet breakdown desktop shows.
 *
 * The previous version of this page hand-rolled its own facet tables and wrote
 * the totals into `.bucket` markup - a class that does not exist in
 * `globals.css`, so it rendered unstyled. `AnalyticsTabs` is what desktop
 * already uses for the same three facets, and sharing it is what stops the two
 * screens disagreeing about what a reply rate is.
 */
export default async function AnalyticsPage() {
  await requireAuth();

  const data = await api<Analytics>("/v1/analytics");
  const t = data.totals;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Analytics</h1>
          <p>
            {t.sent} sent · {t.contacted} people contacted · {t.replied} replied
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="dz-card items-center py-4 text-center">
          <span className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted">Reply</span>
          <div className="stat-value">{pct(t.reply_rate)}</div>
        </div>
        <div className="dz-card items-center py-4 text-center">
          <span className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted">Bounce</span>
          <div className="stat-value">{pct(t.bounce_rate)}</div>
        </div>
        <div className="dz-card items-center py-4 text-center">
          <span className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted">Opt-out</span>
          <div className="stat-value">{pct(t.opt_out_rate)}</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted">
        <span>
          <strong className="text-fg">{data.active_sequences}</strong> active
        </span>
        <span>
          <strong className="text-fg">{data.follow_ups_due}</strong> follow-ups due
        </span>
        <span>
          <strong className="text-fg">{data.stale}</strong> gone quiet
        </span>
      </div>

      <p className="text-xs text-muted">
        Rates are against people contacted, not messages sent — {t.bounced} bounced, {t.opted_out}{" "}
        opted out.
      </p>

      <AnalyticsTabs
        byTargetType={data.by_target_type}
        byCompanyType={data.by_company_type}
        byIntent={data.by_intent}
      />
    </>
  );
}
