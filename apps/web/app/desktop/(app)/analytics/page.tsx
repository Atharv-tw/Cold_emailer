import AnalyticsTabs from "@/components/AnalyticsTabs";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Analytics } from "@/lib/types";

function pct(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

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
        <div className="header-actions">
          <button
            className="secondary"
            disabled
            title="Coming soon: sends these metrics to your Gemini key for advice on what to change"
            style={{ opacity: 0.6, cursor: "not-allowed" }}
          >
            ✨ Insight
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div className="dz-card items-center py-6 text-center">
          <span className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Reply rate</span>
          <div className="stat-value">{pct(t.reply_rate)}</div>
        </div>
        <div className="dz-card items-center py-6 text-center">
          <span className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Bounce rate</span>
          <div className="stat-value">{pct(t.bounce_rate)}</div>
        </div>
        <div className="dz-card items-center py-6 text-center">
          <span className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Opt-out rate</span>
          <div className="stat-value">{pct(t.opt_out_rate)}</div>
        </div>
      </div>

      <div className="flex gap-6 text-sm text-muted">
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

      <AnalyticsTabs
        byTargetType={data.by_target_type}
        byCompanyType={data.by_company_type}
        byIntent={data.by_intent}
      />
    </>
  );
}
