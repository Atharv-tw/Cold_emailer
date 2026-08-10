import Link from "next/link";

/**
 * What an account without pool access sees instead of the pool.
 *
 * Deliberately descriptive rather than coy. Somebody deciding whether to pay
 * needs to know what is behind this - how many people, who they are, and what
 * has already been done to the list - and "upgrade to unlock" tells them none
 * of it. The numbers here are the real ones from the loader.
 *
 * Rendered instead of calling `/v1/pool` at all. The API would answer 402, but
 * an expected error on every page load is noise that makes a real failure
 * harder to see in the logs.
 */
export default function PoolLocked({
  status,
}: {
  status: "" | "pending" | "approved" | "rejected";
}) {
  if (status === "pending") {
    return (
      <div className="dz-card items-center py-16 text-center">
        <h3>Your payment is being checked</h3>
        <p className="text-muted">
          Someone looks at these by hand, so it is not instant. You will not need to do
          anything else — access appears here once it is approved.
        </p>
      </div>
    );
  }

  return (
    <div className="dz-card items-center py-16 text-center">
      <h3>The contact pool is a paid list</h3>
      <p className="mx-auto max-w-prose text-muted">
        Around 500 founders, co-founders and hiring leads at Indian startups, with the
        company, the role and a LinkedIn profile where there is one. Addresses that have
        bounced for anyone are already removed, and domains that do not resolve are
        marked — so the list does not spend your Gmail reputation proving what somebody
        else already found out.
      </p>
      <p className="mx-auto max-w-prose text-muted">
        Anyone you add from it becomes an ordinary contact on your own list. Nobody else
        can see what you write or who has replied.
      </p>
      {status === "rejected" && (
        <p className="text-muted">
          Your last payment could not be confirmed. You can try again below.
        </p>
      )}
      <Link href="/pool/purchase">
        <button className="primary" style={{ borderRadius: "2rem", padding: "0.6rem 1.5rem" }}>
          Get access
        </button>
      </Link>
    </div>
  );
}
