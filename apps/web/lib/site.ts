/**
 * Where this deployment thinks it lives.
 *
 * Next needs an absolute origin to turn relative Open Graph image paths into
 * the absolute URLs that Slack, iMessage and Twitter demand - a preview card
 * with a relative image path silently renders blank. Nothing in the repo knows
 * the production domain, so it is read from the environment and falls back
 * through Vercel's own variable before giving up on localhost.
 *
 * Set NEXT_PUBLIC_SITE_URL in production. The Vercel fallback is a safety net,
 * not the intended path: VERCEL_PROJECT_PRODUCTION_URL is the project's
 * production domain rather than a custom one, so cards would point at the
 * *.vercel.app address instead of the real site.
 */
export const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000");

/** Where "Contact us" and "Report an issue" go for someone who isn't signed
 *  in yet, so there is no session to send the message through. Falls back to
 *  the address the signed-in report flow uses server-side, so the two stay
 *  in sync without being set twice in normal operation. */
export const supportEmail =
  process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "support@example.com";

/** Paths behind the login. Everything here is per-user state, so it is kept
 *  out of search results rather than merely being uninteresting to rank. */
export const PRIVATE_PATHS = [
  "/dashboard",
  "/targets",
  "/emails",
  "/analytics",
  "/settings",
  "/profile",
  "/pool",
  "/admin",
  "/ops",
  "/import",
  "/help",
];
