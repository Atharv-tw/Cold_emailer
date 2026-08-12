"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { logout } from "@/app/actions";
import Icon, { type IconName } from "@/components/Icon";

type Item = { label: string; href: string; icon: IconName };

/**
 * Everything the five-slot tab bar cannot hold.
 *
 * The desktop rail can afford ten destinations stacked in a column; a phone
 * gets five before the targets stop being thumb-sized. The split is by
 * frequency rather than importance - Analytics and Settings matter, but they
 * are not what somebody opens the app to do, and a tab bar should reflect the
 * common case.
 *
 * Anchored to the bottom edge rather than centred like `Modal`: it is opened
 * from a tab bar button, and a sheet that animates away from the thumb that
 * summoned it reads as a different, unrelated surface.
 */
export default function MobileMoreSheet({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: Item[];
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Same three concerns as `Modal`: restore focus, close on Escape, and stop
  // the page behind from scrolling under the sheet.
  useEffect(() => {
    if (!open) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    panelRef.current?.querySelector<HTMLElement>("a, button")?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[60] flex flex-col justify-end bg-black/40" onClick={onClose}>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="More"
        className="max-h-[80dvh] overflow-y-auto rounded-t-2xl bg-surface pb-[env(safe-area-inset-bottom)] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-lg font-semibold text-fg">More</h2>
          <button type="button" className="quiet p-2" onClick={onClose} aria-label="Close">
            <Icon name="x" size={16} />
          </button>
        </div>

        <nav className="flex flex-col p-2">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-fg hover:bg-paper"
            >
              <span className="text-muted">
                <Icon name={item.icon} size={19} />
              </span>
              {item.label}
            </Link>
          ))}

          <form action={logout} className="contents">
            <button
              type="submit"
              className="flex w-full items-center gap-3 rounded-xl bg-transparent px-3 py-3 text-left text-sm font-medium text-danger hover:bg-danger-light"
            >
              <Icon name="logout" size={19} />
              Logout
            </button>
          </form>
        </nav>
      </div>
    </div>,
    document.body,
  );
}
