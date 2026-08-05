import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { api } from "@/lib/api";
import type { Ops } from "@/lib/types";

function when(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : "never";
}

export default async function OpsPage() {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const data = await api<Ops>("/v1/ops");

  return (
    <main>
      <h1>Health</h1>
      <p>
        <Link href="/dashboard">← Dashboard</Link>
      </p>

      {!data.worker_running && (
        <div className="note">
          <strong>The background worker looks stopped.</strong> Nothing will
          send and replies will not be noticed until it is running again.
        </div>
      )}
      {!data.connected && (
        <div className="note">
          <strong>Google is disconnected.</strong>{" "}
          {data.disconnected_reason || "Sign in again to reconnect."}
        </div>
      )}

      <section>
        <h2>Background worker</h2>
        <p className={data.worker_running ? "ok" : "error"}>
          {data.worker_running ? "Running" : "Not running"}
        </p>
        {data.jobs.length === 0 ? (
          <p className="muted">No job has run yet.</p>
        ) : (
          <ul>
            {data.jobs.map((job) => (
              <li key={job.job} className="muted">
                {job.job} — {when(job.at)}
                {job.detail && ` · ${job.detail}`}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Gmail</h2>
        <p className="muted">
          Reply watch: {data.watch_healthy ? "active" : "not active"} · last
          renewed {when(data.watch_last_renewed)} · expires{" "}
          {when(data.watch_expires_at)}.
        </p>
        <p className="muted">
          Threads last read {when(data.reconcile_last_read)} · {data.follow_ups_due}{" "}
          follow-up{data.follow_ups_due === 1 ? "" : "s"} due now.
        </p>
      </section>

      <section>
        <h2>Failed sends</h2>
        {data.failed_sends.length === 0 ? (
          <p className="muted">None. Every send has gone through.</p>
        ) : (
          <ul>
            {data.failed_sends.map((failure, index) => (
              <li key={`${failure.target_id}-${index}`}>
                <Link href={`/targets/${failure.target_id}`}>
                  {failure.email || "a target"}
                </Link>{" "}
                <span className="error">· {failure.error || "failed"}</span>{" "}
                <span className="muted">· {when(failure.at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
