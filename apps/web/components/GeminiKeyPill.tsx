"use client";

import { useState } from "react";

import Modal from "@/components/Modal";
import { useGeminiKey } from "@/lib/useGeminiKey";

export default function GeminiKeyPill() {
  const { key, setKey, clearKey, hasKey } = useGeminiKey();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(key);

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setDraft(key);
          setOpen(true);
        }}
        className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
          hasKey ? "border-accent bg-accent-light text-accent" : "border-line bg-surface text-muted"
        }`}
      >
        {hasKey ? "Gemini key set" : "Gemini key: not set"}
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title="Your Gemini API key" widthClassName="max-w-sm">
        <p className="mb-3 text-sm text-muted">
          Used for drafting emails and reading resumes. Kept only in this browser tab — it&rsquo;s
          gone the moment you close it, and never stored on the server.
        </p>
        <input
          type="password"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="AIza…"
          className="mb-3 w-full"
          autoFocus
        />
        <div className="flex gap-2">
          <button
            type="button"
            className="primary"
            onClick={() => {
              setKey(draft);
              setOpen(false);
            }}
          >
            Save
          </button>
          {hasKey && (
            <button
              type="button"
              className="secondary"
              onClick={() => {
                clearKey();
                setDraft("");
                setOpen(false);
              }}
            >
              Clear
            </button>
          )}
        </div>
        <p className="mt-3 text-xs text-muted">
          Don&rsquo;t have one? Get a free key at{" "}
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="underline">
            aistudio.google.com/apikey
          </a>
          .
        </p>
      </Modal>
    </>
  );
}
