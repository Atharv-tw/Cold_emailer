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
    <main>
      <h1>People</h1>
      <p>
        <Link href="/dashboard">← Dashboard</Link> ·{" "}
        <Link href="/targets/new">Add someone</Link> ·{" "}
        <Link href="/import">Import a list</Link>
      </p>

      <TargetFilters active={active} />

      <p className="muted">
        {targets.length} {targets.length === 1 ? "person" : "people"}
        {suffix ? " match these filters" : ""}.
      </p>

      {targets.length === 0 ? (
        <p className="muted">Nobody here.</p>
      ) : (
        <div className="table-scroll">
          <table className="preview">
            <thead>
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
                    <Link href={`/targets/${target.id}`}>
                      {target.name || target.email}
                    </Link>
                  </td>
                  <td>{target.company || <span className="muted">—</span>}</td>
                  <td className="muted">{target.target_type.replace(/_/g, " ")}</td>
                  <td>
                    {target.status}
                    {target.status_detail && (
                      <span className="muted"> · {target.status_detail}</span>
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
    </main>
  );
}
