"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { Session } from "next-auth";

import { logout } from "@/app/desktop/(app)/actions";
import GeminiKeyPill from "@/components/GeminiKeyPill";
import type { Ops } from "@/lib/types";

type ChromeUser = NonNullable<Session["apiUser"]>;

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: "⊞" },
  { label: "Targets", href: "/targets", icon: "👥" },
  { label: "Sent Emails", href: "/emails", icon: "📤" },
  { label: "Analytics", href: "/analytics", icon: "📊" },
];

const GENERAL_ITEMS = [
  { label: "Settings", href: "/profile", icon: "⚙️" },
  { label: "Help", href: "/help", icon: "❔" },
];

function NavLink({ href, icon, label, active }: { href: string; icon: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 rounded-lg px-3 py-2.5 font-medium whitespace-nowrap transition-colors ${
        active ? "bg-accent-light text-accent" : "text-muted hover:bg-bg hover:text-fg"
      }`}
    >
      <span className="w-5 shrink-0 text-center">{icon}</span>
      <span className="opacity-0 transition-opacity duration-150 group-hover:opacity-100">{label}</span>
    </Link>
  );
}

/**
 * Sidebar + topbar shell for every authenticated desktop page.
 *
 * The rail is `fixed` and `w-16` at rest, `w-64` on hover - it overlays the
 * page rather than pushing it, because `main` keeps a static `ml-16` that
 * never changes with the rail's hover state.
 */
export default function DesktopChrome({
  user,
  ops,
  children,
}: {
  user: ChromeUser;
  ops: Ops | null;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [profileOpen, setProfileOpen] = useState(false);

  const initials = (user.name || user.email || "?").trim().charAt(0).toUpperCase();
  const workerDown = ops ? !ops.worker_running : false;
  const googleDown = ops ? !ops.connected : !user.connected;

  return (
    <div className="min-h-screen bg-bg">
      <aside className="group fixed left-0 top-0 z-40 flex h-screen w-16 flex-col gap-6 overflow-hidden border-r border-line bg-surface py-8 transition-[width] duration-200 ease-out hover:w-64">
        <Link href="/dashboard" className="flex items-center gap-3 px-4 text-xl font-bold text-accent">
          <span className="shrink-0 text-2xl">◎</span>
          <span className="whitespace-nowrap opacity-0 transition-opacity duration-150 group-hover:opacity-100">
            Outreach
          </span>
        </Link>

        <nav className="flex flex-col gap-1 px-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.href}
              {...item}
              active={pathname === item.href || pathname.startsWith(item.href + "/")}
            />
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-1 px-3">
          {GENERAL_ITEMS.map((item) => (
            <NavLink key={item.href} {...item} active={pathname === item.href} />
          ))}
          <form action={logout}>
            <button
              type="submit"
              className="flex w-full items-center gap-3 rounded-lg bg-transparent px-3 py-2.5 text-left font-medium whitespace-nowrap text-muted transition-colors hover:bg-bg hover:text-fg"
            >
              <span className="w-5 shrink-0 text-center">🚪</span>
              <span className="opacity-0 transition-opacity duration-150 group-hover:opacity-100">Logout</span>
            </button>
          </form>
        </div>
      </aside>

      <div className="ml-16 flex min-h-screen flex-col">
        <header className="flex h-20 items-center justify-end gap-4 px-10">
          {(workerDown || googleDown) && (
            <span className="rounded-full bg-danger-light px-3 py-1 text-xs font-medium text-danger">
              {workerDown ? "Background worker offline" : "Google disconnected"}
            </span>
          )}

          <GeminiKeyPill />

          <button className="icon-btn" aria-label="Notifications">
            🔔
          </button>

          <div className="relative">
            <button type="button" onClick={() => setProfileOpen((value) => !value)} className="user-profile">
              {user.avatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.avatar} alt="" className="h-8 w-8 rounded-full object-cover" />
              ) : (
                <div className="avatar">{initials}</div>
              )}
              <div className="pr-2 text-left">
                <div className="text-[13px] font-semibold text-fg">{user.name || "Signed in"}</div>
                <div className="text-[11px] text-muted">{user.email}</div>
              </div>
            </button>

            {profileOpen && (
              <div
                className="absolute right-0 top-full z-50 mt-2 w-48 rounded-xl border border-line bg-surface p-1.5 shadow-lg"
                onMouseLeave={() => setProfileOpen(false)}
              >
                <Link
                  href="/profile"
                  className="block rounded-lg px-3 py-2 text-sm font-medium text-fg hover:bg-bg"
                  onClick={() => setProfileOpen(false)}
                >
                  Settings
                </Link>
                <form action={logout}>
                  <button
                    type="submit"
                    className="block w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-danger hover:bg-danger-light"
                  >
                    Logout
                  </button>
                </form>
              </div>
            )}
          </div>
        </header>

        <main className="main-content flex-1">{children}</main>
      </div>
    </div>
  );
}
