"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { searchTargets } from "@/app/desktop/(app)/emails/actions";
import Modal from "@/components/Modal";
import TargetForm from "@/components/TargetForm";
import type { Target } from "@/lib/types";

export default function NewEmailModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<"existing" | "new">("existing");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Target[]>([]);
  const [pending, startTransition] = useTransition();

  function onQueryChange(value: string) {
    setQuery(value);
    startTransition(async () => {
      setResults(await searchTargets(value));
    });
  }

  return (
    <Modal open={open} onClose={onClose} title="New email" widthClassName="max-w-lg">
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => setTab("existing")}
          className={`rounded-full px-3 py-1 text-xs font-semibold ${
            tab === "existing" ? "bg-accent-light text-accent" : "text-muted"
          }`}
        >
          Pick someone you&rsquo;ve added
        </button>
        <button
          type="button"
          onClick={() => setTab("new")}
          className={`rounded-full px-3 py-1 text-xs font-semibold ${
            tab === "new" ? "bg-accent-light text-accent" : "text-muted"
          }`}
        >
          Add someone new
        </button>
      </div>

      {tab === "existing" ? (
        <div className="flex flex-col gap-2">
          <input
            type="text"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search by name, company or email"
            autoFocus
          />
          {pending && <p className="text-xs text-muted">Searching…</p>}
          {!pending && query.trim() && results.length === 0 && (
            <p className="text-xs text-muted">Nobody matches — try &ldquo;Add someone new&rdquo; instead.</p>
          )}
          <div className="flex max-h-72 flex-col overflow-y-auto">
            {results.map((target) => (
              <Link
                key={target.id}
                href={`/targets/${target.id}`}
                onClick={onClose}
                className="flex items-center justify-between rounded-lg px-3 py-2 hover:bg-bg"
              >
                <div>
                  <div className="text-sm font-medium text-fg">{target.name || target.email}</div>
                  <div className="text-xs text-muted">{target.company || "—"}</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      ) : (
        <TargetForm />
      )}
    </Modal>
  );
}
