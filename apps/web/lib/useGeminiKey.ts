"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * The user's own Gemini key, held only in this tab's sessionStorage.
 *
 * There is no server-side fallback key anymore (see deps.gemini_api_key on
 * the API): every AI action needs this passed through explicitly. It is
 * never written to a cookie, the database, or the NextAuth JWT - closing the
 * tab loses it on purpose, per how the user wanted this to work.
 *
 * sessionStorage's own `storage` event only fires in *other* tabs, not the
 * one that made the change, so the topbar pill and the Settings field - both
 * mounted in the same tab - need a same-tab signal to stay in sync.
 */
const STORAGE_KEY = "gemini_api_key";
const SYNC_EVENT = "gemini-key-changed";

function read(): string {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(STORAGE_KEY) ?? "";
}

export function useGeminiKey() {
  const [key, setKeyState] = useState("");

  useEffect(() => {
    setKeyState(read());
    function onSync() {
      setKeyState(read());
    }
    window.addEventListener(SYNC_EVENT, onSync);
    window.addEventListener("storage", onSync);
    return () => {
      window.removeEventListener(SYNC_EVENT, onSync);
      window.removeEventListener("storage", onSync);
    };
  }, []);

  const setKey = useCallback((value: string) => {
    const trimmed = value.trim();
    if (trimmed) {
      window.sessionStorage.setItem(STORAGE_KEY, trimmed);
    } else {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
    setKeyState(trimmed);
    window.dispatchEvent(new Event(SYNC_EVENT));
  }, []);

  const clearKey = useCallback(() => setKey(""), [setKey]);

  return { key, setKey, clearKey, hasKey: key.length > 0 };
}
