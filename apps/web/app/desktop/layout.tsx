/**
 * Pass-through layout for the `/desktop` segment.
 *
 * `not-found.tsx` in this same directory only catches unmatched nested paths
 * (e.g. `/desktop/whatever`) if this segment has a layout boundary at all -
 * without one, Next falls back to its generic built-in 404 instead of ours.
 * The real chrome (sidebar/topbar) lives one level down, in `(app)/layout.tsx`,
 * scoped only to the authenticated pages.
 */
export default function DesktopLayout({ children }: { children: React.ReactNode }) {
  return children;
}
