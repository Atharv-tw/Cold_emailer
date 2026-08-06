"use client";

import { useEffect, useState } from "react";

import { savePushSubscription } from "@/app/desktop/(app)/dashboard/actions";

/**
 * Registers the service worker, offers installation, and offers notifications.
 *
 * Both offers are offers. Notifications get denied, revoked, and silently
 * dropped by platforms, and on iOS they only work once the site is on the home
 * screen - so nothing here is load-bearing. The dashboard's "due today" list
 * is the mechanism; this is the convenience on top.
 *
 * The install prompt is not fired on load. A permission dialog before anyone
 * has seen the product is how you get a permanent "no".
 */

type InstallEvent = Event & { prompt: () => Promise<void> };

function toUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = atob(padded);
  // Backed by a plain ArrayBuffer, which is what applicationServerKey wants -
  // a bare Uint8Array may be backed by a SharedArrayBuffer as far as the type
  // system is concerned.
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let index = 0; index < raw.length; index += 1) {
    bytes[index] = raw.charCodeAt(index);
  }
  return bytes;
}

export default function PwaSetup({ vapidKey }: { vapidKey: string }) {
  const [installEvent, setInstallEvent] = useState<InstallEvent | null>(null);
  const [pushState, setPushState] = useState<"unknown" | "on" | "off" | "denied">("unknown");

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Registration fails on http:// origins other than localhost. Nothing
      // else on the page depends on it.
    });

    const onPrompt = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as InstallEvent);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);

    if ("Notification" in window) {
      if (Notification.permission === "denied") setPushState("denied");
      else {
        navigator.serviceWorker.ready
          .then((registration) => registration.pushManager.getSubscription())
          .then((subscription) => setPushState(subscription ? "on" : "off"))
          .catch(() => setPushState("off"));
      }
    }

    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  async function enablePush() {
    if (!vapidKey) return;
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setPushState(permission === "denied" ? "denied" : "off");
      return;
    }

    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: toUint8Array(vapidKey),
    });

    const raw = subscription.toJSON() as { endpoint?: string; keys?: Record<string, string> };
    await savePushSubscription({ endpoint: raw.endpoint ?? "", keys: raw.keys ?? {} });
    setPushState("on");
  }

  if (!installEvent && pushState !== "off" && pushState !== "denied") return null;

  return (
    <div className="note">
      {installEvent && (
        <p>
          <button
            type="button"
            className="quiet"
            onClick={async () => {
              await installEvent.prompt();
              setInstallEvent(null);
            }}
          >
            Install this as an app
          </button>{" "}
          <span className="muted">
            Same site, its own window and icon. Nothing is downloaded from a store.
          </span>
        </p>
      )}

      {pushState === "off" && vapidKey && (
        <p>
          <button type="button" className="quiet" onClick={enablePush}>
            Turn on follow-up reminders
          </button>{" "}
          <span className="muted">
            Optional. Whatever you choose, anything due still shows at the top of
            this page.
          </span>
        </p>
      )}

      {pushState === "denied" && (
        <p className="muted">
          Notifications are blocked for this site, so reminders will only appear
          here. That is enough — the list below is the real one.
        </p>
      )}
    </div>
  );
}
