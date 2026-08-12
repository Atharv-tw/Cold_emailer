"use client";

import { useState } from "react";

import { reviewPayment, setUserPlan } from "@/app/desktop/(app)/admin/actions";
import type { AdminPayment, AdminUserRow } from "@/lib/types";

/**
 * The operator's two jobs: decide claims, and see who is on the platform.
 *
 * Claims come first because they are the only thing here with someone waiting
 * on the other end. The user list is reference material.
 */

function when(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function PaymentCard({ payment }: { payment: AdminPayment }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [resolved, setResolved] = useState(payment.status !== "pending" ? payment.status : "");

  async function decide(approve: boolean) {
    if (busy) return;
    setBusy(true);
    setError("");
    const result = await reviewPayment(payment.id, approve, note);
    setBusy(false);
    if (result.ok) setResolved(result.data.status);
    else setError(result.error.message || "That did not go through.");
  }

  return (
    <div className="dz-card gap-3">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="truncate font-semibold text-fg">
            {payment.user_name || "(no name)"}
          </div>
          <div className="truncate text-xs text-muted">{payment.user_email}</div>
        </div>
        <span className={`badge ${resolved === "approved" ? "badge-completed" : ""}`}>
          {resolved || "pending"}
        </span>
      </div>

      <div className="text-xs text-muted">
        Claimed {when(payment.created_at)}
        {payment.upi_reference && <> · ref {payment.upi_reference}</>}
      </div>

      {/* Surfaced rather than hidden: a claim whose email never arrived is
          exactly the one at risk of sitting here unnoticed. */}
      {payment.notify_error && (
        <p className="text-xs text-danger">
          The notification email failed: {payment.notify_error}
        </p>
      )}

      {/* Routed through the web app rather than pointed at the API, because
          the browser holds no API credential. The handler swaps this for a
          short-lived signed URL. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/api/admin/screenshot/${payment.id}`}
        alt={`Payment screenshot from ${payment.user_email}`}
        className="max-h-96 w-full rounded-xl object-contain"
        style={{ background: "var(--bg)" }}
      />

      {!resolved && (
        <>
          <input
            type="text"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Note (optional) — why you decided this way"
          />
          {error && <p className="text-sm text-danger">{error}</p>}
          <div className="flex gap-2">
            <button type="button" className="primary" disabled={busy} onClick={() => decide(true)}>
              {busy ? "Working…" : "Approve"}
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => decide(false)}>
              Reject
            </button>
          </div>
        </>
      )}

      {resolved && (
        <p className="text-xs text-muted">
          {resolved === "approved"
            ? "Access granted. They see the pool on their next page load."
            : "Rejected. They can claim again."}
        </p>
      )}
    </div>
  );
}

function UserRow({ user }: { user: AdminUserRow }) {
  const [isPaid, setIsPaid] = useState(user.is_paid);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function toggle() {
    if (busy) return;
    setBusy(true);
    setError("");
    const result = await setUserPlan(user.id, !isPaid);
    setBusy(false);
    if (result.ok) setIsPaid(result.data.is_paid);
    else setError(result.error.message || "That did not go through.");
  }

  return (
    <tr>
      <td>
        <div className="font-medium text-fg">{user.name || "(no name)"}</div>
        <div className="text-xs text-muted">{user.email}</div>
        {error && <div className="text-xs text-danger">{error}</div>}
      </td>
      <td className="text-xs text-muted">{when(user.joined_at)}</td>
      <td>
        {!user.connected && <span className="badge badge-danger">disconnected</span>}
        {user.is_admin && <span className="badge">operator</span>}
      </td>
      <td>
        <button type="button" className="quiet" disabled={busy} onClick={toggle}>
          {busy ? "…" : isPaid ? "Revoke access" : "Grant access"}
        </button>
      </td>
    </tr>
  );
}

export default function AdminPanel({
  users,
  payments,
}: {
  users: AdminUserRow[];
  payments: AdminPayment[];
}) {
  const pending = payments.filter((payment) => payment.status === "pending");
  const decided = payments.filter((payment) => payment.status !== "pending");

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2>
          Payments{" "}
          {pending.length > 0 && (
            <span className="text-muted">— {pending.length} waiting</span>
          )}
        </h2>

        {pending.length === 0 ? (
          <div className="dz-card text-muted">Nothing waiting on a decision.</div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(340px,1fr))] gap-4">
            {pending.map((payment) => (
              <PaymentCard key={payment.id} payment={payment} />
            ))}
          </div>
        )}

        {decided.length > 0 && (
          <details>
            <summary className="cursor-pointer text-sm text-muted">
              {decided.length} already decided
            </summary>
            <div className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(340px,1fr))] gap-4">
              {decided.map((payment) => (
                <PaymentCard key={payment.id} payment={payment} />
              ))}
            </div>
          </details>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2>
          Users <span className="text-muted">— {users.length}</span>
        </h2>
        {/* The only wide table here that was not wrapped - without this it
            widens the document instead of scrolling inside its own card. */}
        <div className="dz-card table-scroll">
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th>Joined</th>
                <th>State</th>
                <th>Pool access</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <UserRow key={user.id} user={user} />
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
