"use client";

import { useEffect, useState, useTransition } from "react";

import { deleteMyData } from "@/app/desktop/(app)/profile/actions";
import { useGeminiKey } from "@/lib/useGeminiKey";
import type { SessionUser } from "@/lib/types";

/**
 * Integrations and account-level settings - separate from the Profile page,
 * which is about who you are (resume, links, projects). This page is about
 * what powers the app: your AI key and your Google connection.
 */
export default function SettingsForm({ user }: { user: SessionUser }) {
  const { key: geminiKey, setKey: setGeminiKey, hasKey: hasGeminiKey } = useGeminiKey();
  const [geminiDraft, setGeminiDraft] = useState(geminiKey);
  const [savedFlash, setSavedFlash] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  useEffect(() => setGeminiDraft(geminiKey), [geminiKey]);

  return (
    <div className="stack">
      <section
        className="rounded-2xl border-2 p-5"
        style={{
          borderColor: hasGeminiKey ? "var(--accent)" : "var(--warning)",
          background: hasGeminiKey ? "var(--accent-light)" : "var(--warning-light)",
        }}
      >
        <div className="mb-1 flex items-center gap-2">
          <span style={{ fontSize: "18px" }}>{hasGeminiKey ? "✅" : "⚠️"}</span>
          <h2 style={{ color: hasGeminiKey ? "var(--accent)" : "var(--warning)" }}>
            Gemini API key {hasGeminiKey ? "— connected" : "— required"}
          </h2>
        </div>
        <p style={{ fontSize: "13px", color: hasGeminiKey ? "var(--accent)" : "var(--warning)", marginBottom: "1rem" }}>
          {hasGeminiKey
            ? "Drafting emails and reading resumes will use this key."
            : "Without a key, drafting emails and reading resumes won't work anywhere in the app."}
        </p>

        <label style={{ color: "inherit" }}>
          Gemini API key
          <input
            type="password"
            value={geminiDraft}
            onChange={(event) => setGeminiDraft(event.target.value)}
            placeholder="AIza…"
          />
        </label>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="primary"
            onClick={() => {
              setGeminiKey(geminiDraft);
              setSavedFlash(true);
              setTimeout(() => setSavedFlash(false), 2000);
            }}
          >
            Save key
          </button>
          {hasGeminiKey && (
            <button
              type="button"
              className="quiet"
              onClick={() => {
                setGeminiKey("");
                setGeminiDraft("");
              }}
            >
              Clear
            </button>
          )}
          {savedFlash && <span style={{ fontSize: "12px", color: "var(--accent)" }}>Saved.</span>}
        </div>
        <p className="muted" style={{ fontSize: "12px", marginTop: "0.75rem" }}>
          Kept only in this browser tab — never sent anywhere but the API, and gone the moment you
          close the tab. There is no server-side key: this is the only one the app has. Get a free
          key at{" "}
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">
            aistudio.google.com/apikey
          </a>
          .
        </p>
      </section>

      <section className="dz-card">
        <h2 style={{ marginBottom: "1rem" }}>Google account</h2>
        <div className="flex flex-col gap-2 text-sm">
          <div className="flex items-center justify-between">
            <span>Connection</span>
            <span className={`badge ${user.connected ? "badge-completed" : "badge-danger"}`}>
              {user.connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span>Signed in as</span>
            <span className="text-fg">{user.email}</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Calendar reminders</span>
            <span className={`badge ${user.calendar_connected ? "badge-completed" : "badge-pending"}`}>
              {user.calendar_connected ? "On" : "Off"}
            </span>
          </div>
          {user.missing_scopes.length > 0 && (
            <p style={{ color: "var(--danger)", fontSize: "12px" }}>
              Missing permissions: {user.missing_scopes.join(", ")}. Sign out and back in to grant
              them.
            </p>
          )}
        </div>
      </section>

      {status && <p className="ok">{status}</p>}
      {error && <p className="error">{error}</p>}

      <section className="rounded-xl border p-4" style={{ borderColor: "var(--danger)" }}>
        <h2 style={{ color: "var(--danger)", marginBottom: "0.5rem" }}>Danger zone</h2>
        <p className="muted" style={{ marginBottom: "1rem" }}>
          Deletes every resume you have uploaded and everything extracted from one, files included.
          It cannot be undone.
        </p>
        <button
          type="button"
          className="danger"
          disabled={pending}
          onClick={() => {
            if (!confirm("Delete every resume and everything extracted from one?")) return;
            setError("");
            startTransition(async () => {
              const result = await deleteMyData();
              if (result.ok) setStatus("Deleted.");
              else setError(result.error.message || "Could not delete that.");
            });
          }}
        >
          Delete my resume and parsed data
        </button>
      </section>
    </div>
  );
}
