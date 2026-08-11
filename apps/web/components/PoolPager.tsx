"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

/**
 * Previous / next across the pool.
 *
 * The offset lives in the URL alongside the filters, for the same reason they
 * do: the page is a server component that reads the query string, so a
 * position in the list survives a reload and can be linked to.
 *
 * Changing any filter has to reset the offset, which is why this only ever
 * writes `offset` and leaves everything else in place - `PoolFilters` rebuilds
 * the query string from scratch and drops it, so a narrowed filter cannot
 * strand you on page 7 of a two-page result.
 */
export default function PoolPager({
  total,
  limit,
  offset,
}: {
  total: number;
  limit: number;
  offset: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  if (total <= limit) return null;

  const first = offset + 1;
  const last = Math.min(offset + limit, total);

  function go(nextOffset: number) {
    const next = new URLSearchParams(params.toString());
    if (nextOffset <= 0) next.delete("offset");
    else next.set("offset", String(nextOffset));
    const query = next.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="text-sm text-muted">
        Showing {first}–{last} of {total}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          className="secondary"
          disabled={offset <= 0}
          onClick={() => go(Math.max(0, offset - limit))}
        >
          Previous
        </button>
        <button
          type="button"
          className="secondary"
          disabled={last >= total}
          onClick={() => go(offset + limit)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
