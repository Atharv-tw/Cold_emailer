import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import PoolAddButton from "@/components/PoolAddButton";
import PoolFilters from "@/components/PoolFilters";
import PoolLocked from "@/components/PoolLocked";
import { api } from "@/lib/api";
import type { Billing, PoolContact, SessionUser } from "@/lib/types";

type Search = Record<string, string | string[] | undefined>;

// No status or intent facet: a pool contact has neither until it is taken.
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

  // Fresh, not from the sign-in JWT - see the desktop page for why.
  const me = await api<SessionUser>("/v1/auth/me");
  if (!me.is_paid) {
    const billing = await api<Billing>("/v1/billing").catch(() => null);
    return (
      <main>
        <h1>Contact pool</h1>
        <p>
          <Link href="/dashboard">← Dashboard</Link>
        </p>
        <PoolLocked status={billing?.request_status ?? ""} />
      </main>
    );
  }

  const params = await searchParams;
  const query = new URLSearchParams();
  for (const key of FACETS) {
    const value = one(params[key]).trim();
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  const contacts = await api<PoolContact[]>(`/v1/pool${suffix ? `?${suffix}` : ""}`);

  const active: Record<string, string> = {};
  for (const key of FACETS) active[key] = one(params[key]);

  return (
    <main>
      <h1>Contact pool</h1>
      <p>
        <Link href="/dashboard">← Dashboard</Link> · <Link href="/targets">My people</Link>
      </p>

      <PoolFilters active={active} />

      <p className="muted">
        {contacts.length} {contacts.length === 1 ? "person" : "people"} you have not
        contacted yet.
      </p>

      {contacts.length === 0 ? (
        <p className="muted">
          Either the filters are too narrow, or you have already added everyone matching.
        </p>
      ) : (
        <ul className="tiles">
          {contacts.map((contact) => (
            <li key={contact.id} className="tile">
              <strong>{contact.name || contact.email}</strong>
              <div className="muted">
                {contact.role || "—"} · {contact.company || "—"}
              </div>
              {contact.company_description && (
                <p className="muted">{contact.company_description}</p>
              )}
              {contact.verification?.status === "risky" && (
                <p className="muted">Address unverified — check before sending.</p>
              )}
              {contact.links?.linkedin && (
                <p>
                  <a href={contact.links.linkedin} target="_blank" rel="noopener noreferrer">
                    LinkedIn
                  </a>
                </p>
              )}
              <PoolAddButton contactId={contact.id} />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
