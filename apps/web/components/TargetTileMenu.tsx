"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { deleteTarget, updateTarget } from "@/app/desktop/(app)/dashboard/actions";
import Modal from "@/components/Modal";
import type { Target } from "@/lib/types";

/**
 * The per-contact menu on a tile.
 *
 * The tile is a link, so every control in here has to stop the click from
 * reaching it - otherwise opening the menu navigates away from the thing you
 * were trying to act on.
 *
 * The email address is shown but not editable. Changing it would carry the
 * verification result, the touch count and the Gmail thread across to a
 * different person, so the API refuses it; offering the field and then
 * throwing it away would be worse than not offering it.
 */

const TARGET_TYPES = [
  ["founder", "Founder"],
  ["hiring_manager", "Hiring manager"],
  ["recruiter", "Recruiter"],
  ["engineer", "Engineer"],
  ["professor", "Professor / researcher"],
] as const;

const COMPANY_TYPES = [
  ["ai", "AI"],
  ["edtech", "Edtech"],
  ["fintech", "Fintech"],
  ["faang", "Big tech"],
  ["agency", "Agency"],
  ["research_lab", "Research lab"],
  ["other", "Something else"],
] as const;

const INTENTS = [
  ["internship", "An internship"],
  ["full_time", "Full-time work"],
  ["freelance", "Freelance work"],
  ["research", "Research"],
  ["partnership", "Working together"],
  ["feedback", "Advice or feedback"],
] as const;

function stop(event: React.MouseEvent) {
  event.preventDefault();
  event.stopPropagation();
}

export default function TargetTileMenu({ target }: { target: Target }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const wrapRef = useRef<HTMLDivElement>(null);

  const [form, setForm] = useState({
    name: target.name ?? "",
    company: target.company ?? "",
    role: target.role ?? "",
    hook: target.hook ?? "",
    target_type: target.target_type ?? "founder",
    company_type: target.company_type ?? "other",
    intent: target.intent ?? "internship",
  });

  // Click-away. Without it the menu stays open behind the next thing you click.
  useEffect(() => {
    if (!open) return;
    function onDown(event: MouseEvent) {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  function field(key: keyof typeof form) {
    return (
      event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
    ) => setForm({ ...form, [key]: event.target.value });
  }

  function onSave() {
    setError("");
    startTransition(async () => {
      try {
        await updateTarget(target.id, form);
        setEditing(false);
        router.refresh();
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Could not save.");
      }
    });
  }

  function onDelete() {
    setError("");
    startTransition(async () => {
      try {
        await deleteTarget(target.id);
        setConfirming(false);
        router.refresh();
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Could not delete.");
      }
    });
  }

  return (
    <div ref={wrapRef} className="relative" onClick={stop}>
      <button
        type="button"
        className="quiet small"
        aria-label={`Actions for ${target.name || target.email}`}
        aria-expanded={open}
        onClick={(event) => {
          stop(event);
          setOpen(!open);
        }}
      >
        ⋯
      </button>

      {open && (
        <div className="dz-card absolute right-0 z-20 mt-1 w-40 gap-1 p-1 shadow-md">
          <button
            type="button"
            className="quiet small w-full justify-start text-left"
            onClick={(event) => {
              stop(event);
              setOpen(false);
              setEditing(true);
            }}
          >
            Edit contact
          </button>
          <button
            type="button"
            className="quiet small w-full justify-start text-left text-danger"
            onClick={(event) => {
              stop(event);
              setOpen(false);
              setConfirming(true);
            }}
          >
            Delete
          </button>
        </div>
      )}

      <Modal open={editing} onClose={() => setEditing(false)} title="Edit contact">
        <div className="flex flex-col gap-3">
          <p className="muted text-[12.5px]">
            {target.email} — the address cannot be changed. Delete and re-add to
            write to someone else.
          </p>

          <label className="mb-0">
            Their name
            <input value={form.name} onChange={field("name")} />
          </label>
          <label className="mb-0">
            Company
            <input value={form.company} onChange={field("company")} />
          </label>
          <label className="mb-0">
            Their job title
            <input value={form.role} onChange={field("role")} />
          </label>

          <label className="mb-0">
            Which approach fits them?
            <select value={form.target_type} onChange={field("target_type")}>
              {TARGET_TYPES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="mb-0">
            What kind of company?
            <select value={form.company_type} onChange={field("company_type")}>
              {COMPANY_TYPES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="mb-0">
            What are you asking about?
            <select value={form.intent} onChange={field("intent")}>
              {INTENTS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label className="mb-0">
            What made you pick this person?
            <textarea rows={3} value={form.hook} onChange={field("hook")} />
          </label>

          {error && <p className="error">{error}</p>}

          <div className="flex gap-2">
            <button type="button" className="accent" disabled={pending} onClick={onSave}>
              {pending ? "Saving…" : "Save changes"}
            </button>
            <button
              type="button"
              className="quiet"
              disabled={pending}
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      </Modal>

      <Modal open={confirming} onClose={() => setConfirming(false)} title="Delete this contact?">
        <div className="flex flex-col gap-3">
          <p>
            <strong>{target.name || target.email}</strong> and everything written
            for them — drafts, thread history, and anything queued — will be
            removed. This cannot be undone.
          </p>
          <p className="muted text-[12.5px]">
            To stop emailing someone without losing the record, use Stop on their
            page instead.
          </p>

          {error && <p className="error">{error}</p>}

          <div className="flex gap-2">
            <button type="button" className="danger" disabled={pending} onClick={onDelete}>
              {pending ? "Deleting…" : "Delete permanently"}
            </button>
            <button
              type="button"
              className="quiet"
              disabled={pending}
              onClick={() => setConfirming(false)}
            >
              Keep them
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
