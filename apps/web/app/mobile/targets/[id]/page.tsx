import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@/auth";
import DraftEditor from "@/components/DraftEditor";
import LocalTime from "@/components/LocalTime";
import { api } from "@/lib/api";
import type { Draft, EmailTemplate, Target, TargetDetail } from "@/lib/types";

const VERIFICATION_TONE: Record<string, string> = {
  deliverable: "ok",
  risky: "muted",
  undeliverable: "error",
  unknown: "muted",
};

export default async function TargetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await auth();
  if (!session?.apiUser) redirect("/");

  const { id } = await params;
  const [target, detail, draft, templates] = await Promise.all([
    api<Target>(`/v1/targets/${id}`),
    api<TargetDetail>(`/v1/targets/${id}/timeline`),
    // No draft yet is the normal state for a new target, not an error.
    api<Draft>(`/v1/targets/${id}/draft`).catch(() => null),
    api<EmailTemplate[]>("/v1/templates"),
  ]);

  const verification = target.verification ?? {};
  const tone = VERIFICATION_TONE[verification.status ?? "unknown"] ?? "muted";

  return (
    <main>
      <h1>{target.name || target.email}</h1>
      <p className="muted">
        {target.email}
        {target.company && ` · ${target.company}`}
        {target.role && ` · ${target.role}`}
      </p>

      {verification.status && verification.status !== "deliverable" && (
        <div className="note">
          <p className={tone}>{verification.detail}</p>
          {verification.did_you_mean && (
            <p className="muted">
              Suggested correction: {verification.did_you_mean}. The address
              cannot be edited — delete this and add them again.
            </p>
          )}
        </div>
      )}

      {target.hook && (
        <div className="note">
          <strong>Why them:</strong> {target.hook}
        </div>
      )}

      <DraftEditor target={target} initial={draft} templates={templates} />

      <section>
        <h2>Thread</h2>
        {detail.messages.length === 0 ? (
          <p className="muted">Nothing sent yet.</p>
        ) : (
          detail.messages.map((message) => (
            <fieldset key={message.step}>
              <legend>
                Touch {message.step} · {message.status}
                {message.sent_at && (
                  <>
                    {" · "}
                    <LocalTime iso={message.sent_at} />
                  </>
                )}
              </legend>
              <strong>{message.subject}</strong>
              <pre>{message.body}</pre>
              {message.error && <p className="error">{message.error}</p>}
            </fieldset>
          ))
        )}
      </section>

      <section>
        <h2>History</h2>
        <ul>
          {detail.timeline.map((entry, index) => (
            <li key={index} className="muted">
              <LocalTime iso={entry.at} /> — {entry.type}
              {entry.detail && `: ${entry.detail}`}
            </li>
          ))}
        </ul>
      </section>

      <p>
        <Link href="/dashboard">Back to the dashboard</Link>
      </p>
    </main>
  );
}
