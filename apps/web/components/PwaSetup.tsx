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

/**
 * Whether this is iOS and the site is not already installed.
 *
 * Safari has never implemented `beforeinstallprompt`, so the install button
 * below is unreachable there and iOS users were shown nothing at all - the one
 * platform where installing actually changes something, since web push only
 * works from the home screen. There is no API to trigger it, so the only
 * honest option is to describe the manual steps.
 *
 * iPadOS 13 and later report a Macintosh user agent, which is why touch points
 * are checked too - a real Mac reports 0.
 */
function isUninstalledIos(): boolean {
  if (typeof window === "undefined") return false;

  const ua = navigator.userAgent;
  const iphone = /iP(hone|od|ad)/.test(ua);
  const ipad = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
  if (!iphone && !ipad) return false;

  // `navigator.standalone` is the iOS-only signal for "launched from the home
  // screen"; the media query covers installed PWAs generally.
  const standalone =
    (navigator as Navigator & { standalone?: boolean }).standalone === true ||
    window.matchMedia("(display-mode: standalone)").matches;

  return !standalone;
}

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
  const [iosInstall, setIosInstall] = useState(false);
  const [pushState, setPushState] = useState<"unknown" | "on" | "off" | "denied">("unknown");

  useEffect(() => {
    // Set in an effect, not during render: it reads `navigator`, and the
    // server has no opinion about what device this is.
    setIosInstall(isUninstalledIos());

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

  if (!installEvent && !iosInstall && pushState !== "off" && pushState !== "denied") return null;

  return (
    <div className="note">
      {iosInstall && (
        <p>
          <span className="muted">
            To install this: tap the Share button, then <strong>Add to Home Screen</strong>.
            It gets its own icon and window, and it is the only way reminders can reach
            you on an iPhone.
          </span>
        </p>
      )}

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
