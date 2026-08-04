import Link from "next/link";
import { redirect } from "next/navigation";

import { auth, signOut } from "@/auth";
import PwaSetup from "@/components/PwaSetup";
import { api } from "@/lib/api";
import type { Dashboard } from "@/lib/types";

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// The operating panel. Each bucket is a count from the dashboard payload and,
// where a status maps to it, a link into the filtered people list.
const BUCKETS: { key: string; label: string; href: string }[] = [
  { key: "draft", label: "Drafts needed", href: "/targets?status=draft" },
  { key: "scheduled", label: "Scheduled", href: "/targets?status=active" },
  { key: "active", label: "In flight", href: "/targets?status=active" },
  { key: "replied", label: "Replied", href: "/targets?status=replied" },
  { key: "paused", label: "Paused", href: "/targets?status=paused" },
  { key: "completed", label: "Completed", href: "/targets?status=completed" },
  { key: "bounced", label: "Bounced", href: "/targets?status=bounced" },
  { key: "opted_out", label: "Opted out", href: "/targets?status=opted_out" },
];

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const user = session.apiUser;
  const [data, pushKey] = await Promise.all([
    api<Dashboard>("/v1/dashboard"),
    api<{ key: string }>("/v1/push/key").catch(() => ({ key: "" })),
  ]);

  return (
    <main>
      <h1>Dashboard</h1>

      {!user.connected && (
        <div className="note">
          <strong>Google is not connected.</strong> Nothing will send until you
          sign in again.
        </div>
      )}

      {user.missing_scopes.length > 0 && (
        <div className="note">
          <strong>Some permissions were not granted.</strong> Without{" "}
          <code>gmail.readonly</code> this can send but cannot see replies —
          the one state it must not run in. Sign in again and leave every box
          ticked.
        </div>
      )}

      {/* Pinned at the top on purpose: this is the fallback that works when
          notifications are denied, revoked, or silently dropped. */}
      <section>
        <h2>Due today</h2>
        {data.due.length === 0 ? (
          <p className="muted">Nothing due. </p>
        ) : (
          <ul>
            {data.due.map((item) => (
              <li key={`${item.target_id}-${item.step}`}>
                <Link href={`/targets/${item.target_id}`}>
                  {item.name || item.email}
                </Link>{" "}
                {item.company && <span className="muted">· {item.company}</span>}{" "}
                <span className="muted">
                  · touch {item.step} · {when(item.due_at)}
                </span>{" "}
                {!item.has_draft && <span className="badge">needs writing</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <PwaSetup vapidKey={pushKey.key} />

      <section>
        <h2>Where everyone is</h2>
        <div className="buckets">
          {BUCKETS.map((bucket) => (
            <Link key={bucket.label} href={bucket.href} className="bucket">
              <span className="bucket-count">{data.counts[bucket.key] ?? 0}</span>
              <span className="bucket-label">{bucket.label}</span>
            </Link>
          ))}
        </div>
        <p className="muted">
          {data.counts.sent} sent in total · {data.suppressed} on your
          do-not-contact list
        </p>
      </section>

      <section>
        <h2>People</h2>
        <p>
          <Link href="/targets">See everyone</Link> ·{" "}
          <Link href="/targets/new">Add someone</Link> ·{" "}
          <Link href="/import">Import a list</Link> ·{" "}
          <Link href="/profile">Your profile</Link>
        </p>
        {data.targets.length === 0 && <p className="muted">Nobody yet.</p>}
      </section>

      <section>
        <h2>Recent</h2>
        {data.recent.length === 0 ? (
          <p className="muted">Nothing has happened yet.</p>
        ) : (
          <ul>
            {data.recent.map((entry, index) => (
              <li key={index} className="muted">
                {when(entry.at)} — {entry.type}
                {entry.detail && `: ${entry.detail}`}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <form
          action={async () => {
            "use server";
            await signOut({ redirectTo: "/" });
          }}
        >
          <button type="submit" className="quiet">
            Sign out ({user.email})
          </button>
        </form>
      </section>
    </main>
  );
}
