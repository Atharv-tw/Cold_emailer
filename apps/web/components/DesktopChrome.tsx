"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { Session } from "next-auth";

import { logout } from "@/app/desktop/(app)/actions";
import GeminiKeyPill from "@/components/GeminiKeyPill";
import Icon, { type IconName } from "@/components/Icon";
import type { Ops } from "@/lib/types";

type ChromeUser = NonNullable<Session["apiUser"]>;

const NAV_ITEMS: { label: string; href: string; icon: IconName }[] = [
  { label: "Dashboard", href: "/dashboard", icon: "grid" },
  { label: "Targets", href: "/targets", icon: "users" },
  { label: "Sent Emails", href: "/emails", icon: "send" },
  { label: "Analytics", href: "/analytics", icon: "chart" },
];

const GENERAL_ITEMS: { label: string; href: string; icon: IconName }[] = [
  { label: "Profile", href: "/profile", icon: "user" },
  { label: "Settings", href: "/settings", icon: "settings" },
  { label: "Help", href: "/help", icon: "help" },
];

function NavLink({ href, icon, label, active }: { href: string; icon: IconName; label: string; active: boolean }) {
  return (
    <Link href={href} className={`rail-link ${active ? "rail-link-active" : ""}`} title={label}>
      <span className="rail-icon">
        <Icon name={icon} size={19} strokeWidth={active ? 2 : 1.7} />
      </span>
      <span className="rail-label">{label}</span>
    </Link>
  );
}

/**
 * Sidebar + topbar shell for every authenticated desktop page.
 *
 * The rail floats - inset from every edge, rounded, shadowed - rather than
 * being welded to the viewport, so the ruled paper background reads as one
 * continuous surface the rail is resting on. It is `fixed` and 68px at rest,
 * 232px on hover, and it overlays the page rather than pushing it, because
 * `main` keeps a static left margin that never changes with the hover state.
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
    <div className="min-h-screen">
      <aside className="rail group">
        <Link href="/dashboard" className="flex items-center gap-3 px-2 py-1">
          <span className="rail-icon">
            <span
              className="flex h-7 w-7 items-center justify-center rounded-full text-[13px] font-bold"
              style={{ background: "var(--lime)", color: "var(--ink)", fontFamily: "var(--font-display)" }}
            >
              O
            </span>
          </span>
          <span
            className="rail-label text-[15px] font-bold whitespace-nowrap text-white"
            style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}
          >
            Outreach
          </span>
        </Link>

        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.href}
              {...item}
              active={pathname === item.href || pathname.startsWith(item.href + "/")}
            />
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-1">
          {GENERAL_ITEMS.map((item) => (
            <NavLink key={item.href} {...item} active={pathname === item.href} />
          ))}
          <form action={logout}>
            <button type="submit" className="rail-link w-full bg-transparent p-[0.65rem] text-left" title="Logout">
              <span className="rail-icon">
                <Icon name="logout" size={19} />
              </span>
              <span className="rail-label">Logout</span>
            </button>
          </form>
        </div>
      </aside>

      <div className="ml-[100px] flex min-h-screen flex-col pr-4">
        <header className="flex h-20 items-center justify-end gap-3">
          {(workerDown || googleDown) && (
            <span className="rounded-full bg-danger-light px-3 py-1.5 text-xs font-semibold text-danger">
              {workerDown ? "Background worker offline" : "Google disconnected"}
            </span>
          )}

          <GeminiKeyPill />

          <button className="icon-btn" aria-label="Notifications">
            <Icon name="bell" size={18} />
          </button>

          <div className="relative">
            <button type="button" onClick={() => setProfileOpen((value) => !value)} className="user-profile">
              {user.avatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.avatar} alt="" className="h-8 w-8 rounded-full object-cover" />
              ) : (
                <div className="avatar">{initials}</div>
              )}
              <div className="pr-1 text-left">
                <div className="text-[13px] font-semibold text-fg">{user.name || "Signed in"}</div>
                <div className="text-[11px] text-muted">{user.email}</div>
              </div>
            </button>

            {profileOpen && (
              <div
                className="absolute right-0 top-full z-50 mt-2 w-48 rounded-2xl bg-surface p-1.5 shadow-lg ring-1 ring-line"
                onMouseLeave={() => setProfileOpen(false)}
              >
                <Link
                  href="/profile"
                  className="block rounded-xl px-3 py-2 text-sm font-medium text-fg hover:bg-paper"
                  onClick={() => setProfileOpen(false)}
                >
                  Profile
                </Link>
                <Link
                  href="/settings"
                  className="block rounded-xl px-3 py-2 text-sm font-medium text-fg hover:bg-paper"
                  onClick={() => setProfileOpen(false)}
                >
                  Settings
                </Link>
                <form action={logout}>
                  <button
                    type="submit"
                    className="block w-full rounded-xl px-3 py-2 text-left text-sm font-medium text-danger hover:bg-danger-light"
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
