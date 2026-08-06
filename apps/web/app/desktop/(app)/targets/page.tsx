import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import TargetFilters from "@/components/TargetFilters";
import { api } from "@/lib/api";
import type { Target } from "@/lib/types";

type Search = Record<string, string | string[] | undefined>;

const FACETS = ["status", "target_type", "company_type", "intent", "q"] as const;

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
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
    <>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Contacts</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            {targets.length} {targets.length === 1 ? "person" : "people"} match these filters
          </p>
        </div>
        <div className="header-actions">
          <Link href="/import">
            <button className="secondary" style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}>
              Import Data
            </button>
          </Link>
          <Link href="/targets/new">
            <button className="primary" style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: "600" }}>
              + Add Contact
            </button>
          </Link>
        </div>
      </div>

      <div className="dz-card" style={{ padding: "0", overflow: "hidden" }}>
        <div style={{ padding: "1.5rem", borderBottom: "1px solid var(--line)", background: "#fcfcfc" }}>
          <TargetFilters active={active} />
        </div>

        {targets.length === 0 ? (
          <div style={{ padding: "4rem", textAlign: "center", color: "var(--muted)" }}>
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>📭</div>
            <h3>Nobody found</h3>
            <p>Try adjusting your filters or adding a new contact.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="preview">
              <thead style={{ background: "#fcfcfc" }}>
                <tr>
                  <th>Name</th>
                  <th>Company</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Touches</th>
                </tr>
              </thead>
              <tbody>
                {targets.map((target) => (
                  <tr key={target.id}>
                    <td>
                      <Link href={`/targets/${target.id}`} style={{ fontWeight: "600", color: "var(--fg)" }}>
                        {target.name || target.email}
                      </Link>
                    </td>
                    <td>{target.company || <span className="muted">—</span>}</td>
                    <td className="muted">{target.target_type.replace(/_/g, " ")}</td>
                    <td>
                      <span className={`badge ${target.status === 'completed' ? 'badge-completed' : target.status === 'bounced' ? 'badge-danger' : 'badge-pending'}`}>
                        {target.status}
                      </span>
                      {target.status_detail && (
                        <span className="muted" style={{ fontSize: "12px", marginLeft: "0.5rem" }}>
                          {target.status_detail}
                        </span>
                      )}
                    </td>
                    <td className="muted">
                      {target.touches_sent}/{target.touches_sent + target.touches_remaining}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
