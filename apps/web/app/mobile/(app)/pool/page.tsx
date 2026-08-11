import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import PoolAddButton from "@/components/PoolAddButton";
import PoolFilters from "@/components/PoolFilters";
import PoolLocked from "@/components/PoolLocked";
import PoolPager from "@/components/PoolPager";
import Icon from "@/components/Icon";
import { api } from "@/lib/api";
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
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const me = await api<SessionUser>("/v1/auth/me");
  if (!me.is_paid) {
    const billing = await api<Billing>("/v1/billing").catch(() => null);
    return (
      <div className="flex flex-col gap-6 pt-2">
        <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>Contact pool</h1>
        <PoolLocked
          status={billing?.request_status ?? ""}
          priceInr={billing?.price_inr}
        />
      </div>
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
    <div className="flex flex-col gap-6 pt-2">
      <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>Contact pool</h1>

      <PoolFilters active={active} />

      <p className="text-sm text-white/50 -mt-2">
        {page.total} {page.total === 1 ? "person" : "people"} you have not contacted yet.
      </p>

      {contacts.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 bg-white/5 border border-white/10 rounded-2xl">
          <Icon name="users" size={32} className="text-white/20 mb-3" />
          <p className="text-white/50 text-center">
            Either the filters are too narrow, or you have already added everyone matching.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {contacts.map((contact) => (
            <div key={contact.id} className="flex flex-col gap-3 p-5 bg-white/5 border border-white/10 rounded-2xl">
              <div className="flex flex-col gap-1">
                <strong className="text-white text-[16px]">{contact.name || contact.email}</strong>
                <span className="text-sm text-white/60">
                  {contact.role || "—"} <span className="mx-1 opacity-50">·</span> {contact.company || "—"}
                </span>
              </div>
              
              {contact.company_description && (
                <p className="text-[13px] text-white/50 line-clamp-2 mt-1 leading-relaxed">{contact.company_description}</p>
              )}
              
              {contact.verification?.status === "risky" && (
                <div className="flex items-start gap-1.5 text-[12px] text-yellow-400/90 mt-1 bg-yellow-400/10 px-2.5 py-1.5 rounded-lg">
                  <Icon name="info" size={14} className="shrink-0 mt-[1px]" />
                  <span>Address unverified — check before sending.</span>
                </div>
              )}
              
              {contact.links?.linkedin && (
                <a href={contact.links.linkedin} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-[13px] text-blue-400 hover:text-blue-300 w-max mt-1">
                  <Icon name="link" size={14} />
                  <span>LinkedIn Profile</span>
                </a>
              )}
              
              <div className="mt-2 pt-4 border-t border-white/10">
                <PoolAddButton contactId={contact.id} />
              </div>
            </div>
          ))}
        </div>
      )}

      <PoolPager total={page.total} limit={PAGE_SIZE} offset={offset} />
    </div>
  );
}
