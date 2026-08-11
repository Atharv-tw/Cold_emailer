import MobileChrome from "@/components/MobileChrome";
import { requireAuth } from "@/lib/auth-guard";
import { api } from "@/lib/api";
import type { SessionUser } from "@/lib/types";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await requireAuth();

  // The NextAuth JWT only refreshes at sign-in, so `session.apiUser` can be
  // stale (a new avatar or name from the API won't show until next login).
  // Fetching `/v1/auth/me` here instead means every page load reflects
  // whatever is actually in the database.
  const user = await api<SessionUser>("/v1/auth/me").catch(() => session.apiUser);

  return (
    <MobileChrome user={user}>
      {children}
    </MobileChrome>
  );
}
