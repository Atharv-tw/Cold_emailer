/**
 * Deterministic initials avatar - same name always renders the same color and
 * initials, since there's no real photo to show (target photos come from
 * nowhere: no LinkedIn scraping, nothing uploaded per-target).
 */
function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

export default function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const seed = name.trim() || "?";
  const hue = hashString(seed) % 360;

  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.38),
        background: `hsl(${hue}, 55%, 45%)`,
      }}
    >
      {initialsOf(seed)}
    </div>
  );
}
