import { notFound } from "next/navigation";

/**
 * Next only renders a nested `not-found.tsx` when `notFound()` is thrown
 * within a matched segment - a URL with no matching route at all falls
 * through to the framework's generic 404 instead. This catch-all exists
 * purely to give every otherwise-unmatched `/desktop/*` path a route to
 * match, so it can call `notFound()` and surface our styled one.
 */
export default function CatchAll() {
  notFound();
}
