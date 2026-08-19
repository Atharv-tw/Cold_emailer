"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { Session } from "next-auth";

import GeminiKeyPill from "@/components/GeminiKeyPill";
import Icon, { type IconName } from "@/components/Icon";
import MobileMoreSheet from "@/components/MobileMoreSheet";
import type { Ops } from "@/lib/types";

type ChromeUser = NonNullable<Session["apiUser"]>;

/**
 * Five destinations, unprefixed.
 *
 * They used to read `/mobile/dashboard`, which the middleware then rewrote a
 * second time into `/mobile/mobile/dashboard` - so every tab 404'd on a real
 * phone, and the active state never matched either, because `usePathname()`
 * reports the path before the rewrite. Both bugs come from the same prefix.
 */
const TABS: { label: string; href: string; icon: IconName }[] = [
  { label: "Home", href: "/dashboard", icon: "grid" },
  { label: "People", href: "/targets", icon: "users" },
  { label: "Emails", href: "/emails", icon: "send" },
  { label: "Pool", href: "/pool", icon: "sparkle" },
];

// The rest of the desktop rail, reached through the More sheet. Split by how
// often somebody opens them, not by how much they matter.
const MORE_ITEMS: { label: string; href: string; icon: IconName }[] = [
  { label: "Trackers", href: "/trackers", icon: "bell" },
  { label: "Analytics", href: "/analytics", icon: "chart" },
  { label: "Profile", href: "/profile", icon: "user" },
  { label: "Settings", href: "/settings", icon: "settings" },
  { label: "Help", href: "/help", icon: "help" },
  { label: "Health", href: "/ops", icon: "info" },
];

function TabLink({ href, icon, label, active }: { href: string; icon: IconName; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className="flex w-full flex-col items-center justify-center gap-1 py-2"
    >
      <span
        className={`flex h-7 w-12 items-center justify-center rounded-full transition-colors ${
          active ? "bg-lime-tint text-accent" : "text-muted"
        }`}
      >
        <Icon name={icon} size={20} strokeWidth={active ? 2.2 : 1.7} />
      </span>
      <span className={`text-[10px] font-semibold ${active ? "text-accent" : "text-muted"}`}>{label}</span>
    </Link>
  );
}

/**
 * Header + bottom tab bar for every authenticated mobile page.
 *
 * Deliberately paints no background of its own. `body` already carries the
 * cream, the ruled grid and the lime wash, and this shell used to cover all
 * three with `bg-[var(--ink)] text-white` - which then collided with every
 * shared component, since `ProfileForm`, `DraftEditor` and the rest render
 * `.dz-card` (a white card with no colour of its own). White text on a white
 * card was the result. Letting the light theme through is what makes those
 * components reusable here rather than needing mobile twins.
 */
export default function MobileChrome({
  user,
  ops,
  children,
}: {
  user: ChromeUser;
  ops: Ops | null;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);

  const initials = (user.name || user.email || "?").trim().charAt(0).toUpperCase();
  const workerDown = ops ? !ops.worker_running : false;
  const googleDown = ops ? !ops.connected : !user.connected;

  // Only operators see it, and only operators can use it - the API refuses
  // every /v1/admin route without the role regardless of what this renders.
  const moreItems = user.is_admin
    ? [...MORE_ITEMS, { label: "Admin", href: "/admin", icon: "briefcase" as IconName }]
    : MORE_ITEMS;

  const moreActive = moreItems.some((item) => pathname === item.href || pathname.startsWith(item.href + "/"));

  return (
    <div className="mobile-shell flex min-h-[100dvh] flex-col pb-[76px]">
      <header className="sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-line bg-surface/90 px-4 py-3 backdrop-blur">
        <Link href="/dashboard" className="flex items-center gap-2">
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full pt-[1px] text-[14px] font-bold"
            style={{ background: "var(--lime)", color: "var(--ink)", fontFamily: "var(--font-display)" }}
          >
            O
          </span>
          <span
            className="whitespace-nowrap text-[16px] font-bold text-fg"
            style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}
          >
            Outreach
          </span>
        </Link>

        <div className="flex shrink-0 items-center gap-2">
          <GeminiKeyPill />
          <Link href="/profile" aria-label="Your profile">
            {user.avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={user.avatar} alt="" className="h-8 w-8 rounded-full object-cover" />
            ) : (
              <div className="avatar">{initials}</div>
            )}
          </Link>
        </div>
      </header>

      {(workerDown || googleDown) && (
        <div className="bg-danger-light px-4 py-2 text-center text-xs font-semibold text-danger">
          {workerDown ? "Background worker offline" : "Google disconnected"}
        </div>
      )}

      {/* `overflow-x-hidden` is the safety net, not the fix - anything wide
          enough to need it should be scrolling inside its own container. */}
      <main className="flex w-full max-w-full flex-1 flex-col gap-4 overflow-x-hidden px-4 pb-6 pt-3">
        {children}
      </main>

      <nav className="fixed bottom-0 left-0 right-0 z-50 flex items-stretch justify-around border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]">
        {TABS.map((item) => (
          <TabLink
            key={item.href}
            {...item}
            active={pathname === item.href || pathname.startsWith(item.href + "/")}
          />
        ))}

        <button
          type="button"
          onClick={() => setMoreOpen(true)}
          aria-expanded={moreOpen}
          className="flex w-full flex-col items-center justify-center gap-1 bg-transparent py-2"
        >
          <span
            className={`flex h-7 w-12 items-center justify-center rounded-full transition-colors ${
              moreActive ? "bg-lime-tint text-accent" : "text-muted"
            }`}
          >
            <Icon name="more" size={20} />
          </span>
          <span className={`text-[10px] font-semibold ${moreActive ? "text-accent" : "text-muted"}`}>More</span>
        </button>
      </nav>

      <MobileMoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} items={moreItems} />
    </div>
  );
}
