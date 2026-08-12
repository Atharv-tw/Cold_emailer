import SettingsForm from "@/components/SettingsForm";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { SessionUser } from "@/lib/types";

export default async function SettingsPage() {
  const session = await requireAuth();
  const user = await api<SessionUser>("/v1/auth/me").catch(() => session.apiUser);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Your AI key, your Google connection, and account-level controls.</p>
        </div>
      </div>

      <SettingsForm user={user} />
    </>
  );
}
