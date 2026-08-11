import Link from "next/link";

import Avatar from "@/components/Avatar";
import PoolAddButton from "@/components/PoolAddButton";
import PoolFilters from "@/components/PoolFilters";
import PoolLocked from "@/components/PoolLocked";
import PoolPager from "@/components/PoolPager";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Billing, PoolPage, SessionUser } from "@/lib/types";

// Matches the API's own default. Kept here so the pager can work out which
// page it is on without the API having to tell it twice.
const PAGE_SIZE = 60;

type Search = Record<string, string | string[] | undefined>;

// Deliberately fewer facets than the people page: a pool contact has no status
// and no intent, because neither exists until somebody takes them.
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

  // Asked fresh rather than read off the sign-in JWT, which only refreshes at
  // sign-in - so an approval made a minute ago takes effect on this
  // navigation rather than after the user signs out and back in.
  const me = await api<SessionUser>("/v1/auth/me");
  if (!me.is_paid) {
    const billing = await api<Billing>("/v1/billing").catch(() => null);
    return (
      <>
        <div className="page-header">
          <div>
            <h1>Contact pool</h1>
            <p>A shared list of founders and hiring leads</p>
          </div>
        </div>
        <PoolLocked status={billing?.request_status ?? ""} />
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
            {page.total} {page.total === 1 ? "person" : "people"} you have not contacted
            yet
          </p>
        </div>
        <div className="header-actions">
          <Link href="/targets">
            <button className="secondary" style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}>
              My contacts
            </button>
          </Link>
        </div>
      </div>

      <div className="dz-card">
        <PoolFilters active={active} />
      </div>

      {contacts.length === 0 ? (
        <div className="dz-card items-center py-16 text-center text-muted">
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🗂️</div>
          <h3>Nobody left here</h3>
          <p>
            Either the filters are too narrow, or you have already added everyone in the
            pool who matches.
          </p>
        </div>
      ) : (
        <>
        <PoolPager total={page.total} limit={PAGE_SIZE} offset={offset} />
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
          {contacts.map((contact) => (
            <div key={contact.id} className="dz-card gap-3">
              <div className="flex items-start gap-3">
                <Avatar name={contact.name || contact.email} />
                <div className="min-w-0">
                  <div className="truncate font-semibold text-fg">
                    {contact.name || contact.email}
                  </div>
                  <div className="text-xs text-muted">{contact.role || "—"}</div>
                </div>
              </div>

              <div className="text-sm font-medium text-fg">{contact.company || "—"}</div>

              {contact.company_description && (
                <p className="line-clamp-3 text-xs leading-relaxed text-muted">
                  {contact.company_description}
                </p>
              )}

              <div className="flex flex-wrap gap-1.5">
                {contact.target_type && (
                  <span className="rounded-full bg-bg px-2.5 py-1 text-[11px] font-medium text-muted">
                    {contact.target_type.replace(/_/g, " ")}
                  </span>
                )}
                {contact.company_type && (
                  <span className="rounded-full bg-bg px-2.5 py-1 text-[11px] font-medium text-muted">
                    {contact.company_type.replace(/_/g, " ")}
                  </span>
                )}
                {/* A risky verdict is a warning, not a verdict: most of these
                    are real addresses whose domain simply differs from the
                    company website. Worth flagging, not worth hiding. */}
                {contact.verification?.status === "risky" && (
                  <span className="badge badge-pending">unverified address</span>
                )}
              </div>

              <div className="flex gap-3 text-xs">
                {contact.links?.linkedin && (
                  <a
                    href={contact.links.linkedin}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted underline"
                  >
                    LinkedIn
                  </a>
                )}
                {contact.company_website && (
                  <a
                    href={contact.company_website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted underline"
                  >
                    Website
                  </a>
                )}
              </div>

              <PoolAddButton contactId={contact.id} />
            </div>
          ))}
        </div>
        <PoolPager total={page.total} limit={PAGE_SIZE} offset={offset} />
        </>
      )}
    </>
  );
}
