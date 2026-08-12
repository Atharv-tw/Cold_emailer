/**
 * Pass-through layout for the `/mobile` segment.
 *
 * `not-found.tsx` only catches unmatched nested paths if this segment has a
 * layout boundary at all - without one, Next falls back to its generic
 * built-in 404 instead of ours. The real chrome (header/tab bar) lives one
 * level down, in `(app)/layout.tsx`, scoped only to the authenticated pages.
 */
export default function MobileLayout({ children }: { children: React.ReactNode }) {
  return children;
}
