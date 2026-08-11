"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Session } from "next-auth";

import Icon, { type IconName } from "@/components/Icon";

type ChromeUser = NonNullable<Session["apiUser"]>;

const NAV_ITEMS: { label: string; href: string; icon: IconName }[] = [
  { label: "Dashboard", href: "/mobile/dashboard", icon: "grid" },
  { label: "Targets", href: "/mobile/targets", icon: "users" },
  { label: "Pool", href: "/mobile/pool", icon: "sparkle" },
  { label: "Profile", href: "/mobile/profile", icon: "user" },
];

function NavLink({ href, icon, label, active }: { href: string; icon: IconName; label: string; active: boolean }) {
  return (
    <Link 
      href={href} 
      className={`flex flex-col items-center justify-center w-full py-2 ${active ? "text-[var(--lime)]" : "text-white/60"} hover:bg-white/5`}
    >
      <Icon name={icon} size={24} strokeWidth={active ? 2.5 : 1.7} />
      <span className="text-[10px] mt-1 font-medium">{label}</span>
    </Link>
  );
}

export default function MobileChrome({
  user,
  children,
}: {
  user: ChromeUser;
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col min-h-[100dvh] bg-[var(--ink)] text-white pb-[68px]">
      <header className="sticky top-0 z-40 flex items-center justify-between p-4 bg-[var(--ink)]/90 backdrop-blur border-b border-white/10">
        <Link href="/mobile/dashboard" className="flex items-center gap-2">
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[14px] font-bold pt-[1px]"
            style={{ background: "var(--lime)", color: "var(--ink)", fontFamily: "var(--font-display)" }}
          >
            O
          </span>
          <span
            className="text-[16px] font-bold whitespace-nowrap text-white"
            style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}
          >
            Outreach
          </span>
        </Link>
        <Link href="/mobile/settings" className="text-white/60 hover:text-white">
          <Icon name="settings" size={20} />
        </Link>
      </header>
      
      <main className="flex-1 w-full max-w-full overflow-x-hidden p-4">
        {children}
      </main>

      <nav className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around bg-[var(--ink)] border-t border-white/10 pb-[env(safe-area-inset-bottom)]">
        {NAV_ITEMS.map((item) => {
          if (item.href === "/mobile/pool" && !user.is_paid) return null;
          return (
            <NavLink
              key={item.href}
              {...item}
              active={pathname === item.href || pathname.startsWith(item.href + "/")}
            />
          );
        })}
      </nav>
    </div>
  );
}
