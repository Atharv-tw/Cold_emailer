import { notFound } from "next/navigation";

import AdminPanel from "@/components/AdminPanel";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { AdminPayment, AdminUserRow, SessionUser } from "@/lib/types";

/**
 * The operator panel.
 *
 * The check here is a courtesy, not the boundary: every `/v1/admin` route
 * refuses without the role regardless of what this page decides, so a
 * non-operator who guesses the URL gets nothing either way. This exists so
 * they get a 404 rather than a page of failed fetches.
 *
 * `notFound()` rather than a redirect, because to an account that is not an
 * operator this page genuinely does not exist.
 */
export default async function AdminPage() {
  await requireAuth();

  const me = await api<SessionUser>("/v1/auth/me");
  if (!me.is_admin) notFound();

  const [users, payments] = await Promise.all([
    api<AdminUserRow[]>("/v1/admin/users"),
    api<AdminPayment[]>("/v1/admin/payments"),
  ]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Admin</h1>
          <p>Payment claims and accounts</p>
        </div>
      </div>

      <AdminPanel users={users} payments={payments} />
    </>
  );
}
