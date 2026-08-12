import Icon from "@/components/Icon";
import PoolAddButton from "@/components/PoolAddButton";
import PoolFilters from "@/components/PoolFilters";
import PoolLocked from "@/components/PoolLocked";
import PoolPager from "@/components/PoolPager";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Billing, PoolPage, SessionUser } from "@/lib/types";

const PAGE_SIZE = 60;
type Search = Record<string, string | string[] | undefined>;
const FACETS = ["target_type", "company_type", "q"] as const;

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

export default async function PoolPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  await requireAuth();

  const me = await api<SessionUser>("/v1/auth/me");
  if (!me.is_paid) {
    const billing = await api<Billing>("/v1/billing").catch(() => null);
    return (
      <>
        <div className="page-header">
          <div>
            <h1>Contact pool</h1>
          </div>
        </div>
        <PoolLocked status={billing?.request_status ?? ""} priceInr={billing?.price_inr} />
      </>
    );
  }

  const params = await searchParams;
  const query = new URLSearchParams();
  for (const key of FACETS) {
    const value = one(params[key]).trim();
    if (value) query.set(key, value);
  }
  const offset = Math.max(0, Number.parseInt(one(params.offset), 10) || 0);
  if (offset) query.set("offset", String(offset));
  const suffix = query.toString();
  const page = await api<PoolPage>(`/v1/pool${suffix ? `?${suffix}` : ""}`);
  const contacts = page.items;

  const active: Record<string, string> = {};
  for (const key of FACETS) active[key] = one(params[key]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Contact pool</h1>
          <p>
            {page.total} {page.total === 1 ? "person" : "people"} you have not contacted yet.
          </p>
        </div>
      </div>

      <PoolFilters active={active} />

      {contacts.length === 0 ? (
        <div className="dz-card items-center py-12 text-center">
          <Icon name="users" size={32} className="mb-3 text-muted opacity-40" />
          <p className="muted">
            Either the filters are too narrow, or you have already added everyone matching.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {contacts.map((contact) => (
            <div key={contact.id} className="dz-card gap-2">
              <div className="flex flex-col gap-0.5">
                <strong className="text-[16px] text-fg">{contact.name || contact.email}</strong>
                <span className="text-sm text-muted">
                  {contact.role || "—"} <span className="mx-1 opacity-50">·</span>{" "}
                  {contact.company || "—"}
                </span>
              </div>

              {contact.company_description && (
                <p className="line-clamp-2 text-[13px] leading-relaxed text-muted">
                  {contact.company_description}
                </p>
              )}

              {contact.verification?.status === "risky" && (
                <div
                  className="flex items-start gap-1.5 rounded-lg px-2.5 py-1.5 text-[12px] text-warning"
                  style={{ background: "var(--warning-light)" }}
                >
                  <Icon name="info" size={14} className="mt-[1px] shrink-0" />
                  <span>Address unverified — check before sending.</span>
                </div>
              )}

              {contact.links?.linkedin && (
                <a
                  href={contact.links.linkedin}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex w-max items-center gap-1.5 text-[13px] font-medium text-accent underline"
                >
                  <Icon name="link" size={14} />
                  <span>LinkedIn Profile</span>
                </a>
              )}

              <div className="mt-1 border-t border-line pt-3">
                <PoolAddButton contactId={contact.id} />
              </div>
            </div>
          ))}
        </div>
      )}

      <PoolPager total={page.total} limit={PAGE_SIZE} offset={offset} />
    </>
  );
}
