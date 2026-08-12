import Link from "next/link";

import LocalTime from "@/components/LocalTime";
import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import type { Ops } from "@/lib/types";

// Clock times render in the browser - see LocalTime. On the server they would
// be formatted in UTC, which for an operations page is a good way to
// misdiagnose a stalled job by five and a half hours.
function when(iso: string | null) {
  return iso ? <LocalTime iso={iso} /> : "never";
}

function Warning({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="dz-card"
      style={{ background: "var(--warning-light)", border: "1px solid #fde68a", padding: "1rem" }}
    >
      <p style={{ color: "var(--fg)" }}>{children}</p>
    </div>
  );
}

export default async function OpsPage() {
  await requireAuth();

  const data = await api<Ops>("/v1/ops");

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Health</h1>
          <p>What the background worker and the Gmail connection are actually doing.</p>
        </div>
      </div>

      {!data.worker_running && (
        <Warning>
          <strong>The background worker looks stopped.</strong> Nothing will send and replies will
          not be noticed until it is running again.
        </Warning>
      )}
      {!data.connected && (
        <Warning>
          <strong>Google is disconnected.</strong>{" "}
          {data.disconnected_reason || "Sign in again to reconnect."}
        </Warning>
      )}

      <div className="dz-card gap-2">
        <h2>Background worker</h2>
        <p className={data.worker_running ? "ok" : "error"}>
          {data.worker_running ? "Running" : "Not running"}
        </p>
        {data.jobs.length === 0 ? (
          <p className="muted">No job has run yet.</p>
        ) : (
          <ul className="flex flex-col gap-1.5 text-sm">
            {data.jobs.map((job) => (
              <li key={job.job} className="muted break-words">
                {job.job} — {when(job.at)}
                {job.detail && ` · ${job.detail}`}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="dz-card gap-2">
        <h2>Gmail</h2>
        <p className="muted">
          Reply watch: {data.watch_healthy ? "active" : "not active"} · last renewed{" "}
          {when(data.watch_last_renewed)} · expires {when(data.watch_expires_at)}.
        </p>
        <p className="muted">
          Threads last read {when(data.reconcile_last_read)} · {data.follow_ups_due} follow-up
          {data.follow_ups_due === 1 ? "" : "s"} due now.
        </p>
      </div>

      <div className="dz-card gap-2">
        <h2>Failed sends</h2>
        {data.failed_sends.length === 0 ? (
          <p className="muted">None. Every send has gone through.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {data.failed_sends.map((failure, index) => (
              <li key={`${failure.target_id}-${index}`} className="break-words">
                <Link href={`/targets/${failure.target_id}`} className="font-medium text-fg underline">
                  {failure.email || "a target"}
                </Link>{" "}
                <span className="error">· {failure.error || "failed"}</span>{" "}
                <span className="muted">· {when(failure.at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
