"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import Icon from "@/components/Icon";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  widthClassName?: string;
};

/**
 * Shared portal-based modal. Nothing in this app had a dialog pattern before
 * this - Import, New Email and the scheduled-sends view all render through
 * this instead of each rolling their own overlay.
 */
export default function Modal({ open, onClose, title, children, widthClassName = "max-w-lg" }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    const focusable = panelRef.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    focusable?.focus();

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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`flex max-h-[85vh] w-full ${widthClassName} flex-col overflow-hidden rounded-2xl bg-surface shadow-2xl`}
        onClick={(event) => event.stopPropagation()}
      >
        {title && (
          <div className="flex shrink-0 items-center justify-between border-b border-line px-6 py-4">
            <h2 className="text-lg font-semibold text-fg">{title}</h2>
            <button type="button" className="quiet p-2" onClick={onClose} aria-label="Close">
              <Icon name="x" size={16} />
            </button>
          </div>
        )}
        <div className="overflow-y-auto p-6">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
