import Link from "next/link";

/**
 * What an account without pool access sees instead of the pool.
 *
 * Deliberately descriptive rather than coy. Somebody deciding whether to pay
 * needs to know what is behind this - how many people, who they are, and what
 * a purchase actually hands them - and "upgrade to unlock" tells them none of
 * it. The numbers here are the real ones from the loader.
 *
 * The loud styling is in `.pool-gate` in globals.css. It is the one screen in
 * the app that has to sell something, and it reads as an ask rather than as
 * another row of cards.
 *
 * Rendered instead of calling `/v1/pool` at all. The API would answer 402, but
 * an expected error on every page load is noise that makes a real failure
 * harder to see in the logs.
 */
export default function PoolLocked({
  status,
  priceInr,
}: {
  status: "" | "pending" | "approved" | "rejected";
  // From `/v1/billing`, the same field the UPI QR is built from, so the number
  // on the badge cannot drift away from the amount somebody is actually asked
  // to pay. Absent when that call failed - the page still has to render, so
  // the price simply goes unsaid rather than being guessed at.
  priceInr?: number | null;
}) {
  if (status === "pending") {
    return (
      <div className="pool-gate">
        <div className="pool-gate-glow pool-gate-glow-1" />
        <div className="pool-gate-inner pool-gate-inner-wide">
          <div className="pool-gate-art pool-gate-art-wide">
            <img src="/checking.jpg" alt="" />
            <span className="pool-gate-sticker">COUNTING</span>
          </div>
          <div className="pool-gate-copy">
            <p className="pool-gate-eyebrow">Almost there</p>
            <h2>
              Money received. <em>Checking it.</em>
            </h2>
            <p className="pool-gate-lede">
              Someone looks at these by hand, so it is not instant. Nothing else is
              needed from you — the list turns up here once it is approved.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="pool-gate">
      <div className="pool-gate-glow pool-gate-glow-1" />
      <div className="pool-gate-glow pool-gate-glow-2" />
      <div className="pool-gate-inner">
        <div className="pool-gate-art">
          <img src="/image.png" alt="" />
          {/* The bigger badge is for the number only - "PAY UP" at that size
              does not fit the circle. */}
          <span className={`pool-gate-sticker${priceInr ? " pool-gate-sticker-price" : ""}`}>
            {priceInr ? `₹${priceInr}` : "PAY UP"}
          </span>
        </div>

        <div className="pool-gate-copy">
          <p className="pool-gate-eyebrow">Contact pool</p>
          <h2>
            Yes, it&rsquo;s <em>paid.</em>
          </h2>
          <p className="pool-gate-lede">
            Around 500 founders, co-founders and hiring leads at Indian startups — with
            the company, the role and a LinkedIn profile.
          </p>

          <div className="pool-gate-chips">
            <span className="pool-gate-chip">
              <strong>~500</strong> contacts
            </span>
            <span className="pool-gate-chip">Founders &amp; hiring leads</span>
            <span className="pool-gate-chip">Indian startups</span>
          </div>

          {status === "rejected" && (
            <p className="pool-gate-warn">
              Your last payment could not be confirmed. Try again below.
            </p>
          )}

          <Link href="/pool/purchase">
            <button className="pool-gate-cta">
              {priceInr ? `Get access for ₹${priceInr} →` : "Get access →"}
            </button>
          </Link>

          <p className="pool-gate-fine">
            Anyone you add becomes an ordinary contact on your own list. Nobody else
            sees what you write or who replied.
          </p>
        </div>
      </div>
    </div>
  );
}
