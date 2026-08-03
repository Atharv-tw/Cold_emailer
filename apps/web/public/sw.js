/**
 * Service worker.
 *
 * Deliberately does not cache anything. A cold-outreach dashboard showing
 * stale state is worse than one that fails to load: the whole product depends
 * on "have they replied yet" being current, and a cached "no" is exactly the
 * wrong answer. This exists so the site is installable and can receive push.
 */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let payload = { title: "Cold outreach", body: "You have follow-ups due.", url: "/dashboard" };
  try {
    if (event.data) payload = { ...payload, ...event.data.json() };
  } catch {
    // A malformed payload should still produce a usable notification.
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      // Replaces rather than stacks: five "follow-ups due" notifications say
      // nothing that one does not.
      tag: "due-today",
      data: { url: payload.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/dashboard";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      // Focus an open tab rather than opening a fourth copy of the dashboard.
      for (const client of windows) {
        if (client.url.includes(url) && "focus" in client) return client.focus();
      }
      return self.clients.openWindow(url);
    }),
  );
});
