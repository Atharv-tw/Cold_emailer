"use client";

import { useEffect, useState } from "react";

/**
 * A timestamp in the reader's own timezone.
 *
 * `toLocaleString()` inside a server component formats in the *server's* zone,
 * not the reader's - and the server runs in UTC. A send made at 17:00 IST came
 * back reading 11:30 AM, which is the same instant and the wrong answer to the
 * only question a timeline answers.
 *
 * So the formatting happens on the client. The first paint is deliberately UTC
 * with the zone named, because the server has to render *something* and a
 * label that admits which zone it is in beats one that quietly lies; the effect
 * then replaces it on hydration. `suppressHydrationWarning` covers the gap
 * between the two, which is expected here rather than a bug.
 *
 * Client components that already format dates - DraftEditor, ThreadPanel,
 * ScheduledModal - were never affected, since their code runs in the browser
 * to begin with.
 */
export default function LocalTime({
  iso,
  options,
}: {
  iso: string | null | undefined;
  options?: Intl.DateTimeFormatOptions;
}) {
  const [text, setText] = useState(() =>
    iso ? new Date(iso).toLocaleString(undefined, { ...options, timeZone: "UTC" }) + " UTC" : "",
  );

  useEffect(() => {
    if (iso) setText(new Date(iso).toLocaleString(undefined, options));
  }, [iso, options]);

  if (!iso) return null;
  return (
    <time dateTime={iso} suppressHydrationWarning>
      {text}
    </time>
  );
}
