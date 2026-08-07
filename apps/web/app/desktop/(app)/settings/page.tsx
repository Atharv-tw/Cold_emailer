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
          <h1 style={{ fontSize: "28px", fontWeight: "700" }}>Settings</h1>
          <p style={{ marginTop: "0.25rem", color: "var(--muted)" }}>
            Your AI key, your Google connection, and account-level controls.
          </p>
        </div>
      </div>

      <SettingsForm user={user} />
    </>
  );
}
