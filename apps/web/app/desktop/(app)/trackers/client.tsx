"use client";

import { useState, useTransition } from "react";
import { 
  createTrackedThread, 
  deleteTrackedThread, 
  createTrackedSender, 
  deleteTrackedSender 
} from "./actions";

export function TrackedThreadsList({ threads }: { threads: any[] }) {
  const [newThreadId, setNewThreadId] = useState("");
  const [newThreadSubject, setNewThreadSubject] = useState("");
  const [pending, startTransition] = useTransition();

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      await createTrackedThread({ gmail_thread_id: newThreadId, subject: newThreadSubject });
      setNewThreadId("");
      setNewThreadSubject("");
    });
  };

  const handleDelete = (id: string) => {
    startTransition(async () => {
      await deleteTrackedThread(id);
    });
  };

  return (
    <div className="dz-card gap-4">
      <h2 className="text-xl font-semibold">Tracked Threads</h2>
      <form onSubmit={handleAdd} className="flex flex-col gap-2">
        <input 
          type="text" 
          placeholder="Gmail Thread ID" 
          className="input" 
          value={newThreadId}
          onChange={e => setNewThreadId(e.target.value)}
          required
          disabled={pending}
        />
        <input 
          type="text" 
          placeholder="Subject (optional)" 
          className="input" 
          value={newThreadSubject}
          onChange={e => setNewThreadSubject(e.target.value)}
          disabled={pending}
        />
        <button type="submit" disabled={pending} className="primary py-2 px-4 rounded-full font-semibold self-start mt-2">
          {pending ? "Adding..." : "Add Thread"}
        </button>
      </form>
      
      <div className="flex flex-col gap-2 mt-4">
        {threads.map(t => (
          <div key={t.id} className="flex justify-between p-3 border border-border rounded-xl bg-bg">
            <div>
              <div className="font-semibold text-fg">{t.subject || "No subject"}</div>
              <div className="text-xs text-muted font-mono mt-1">ID: {t.gmail_thread_id}</div>
              <div className="text-sm mt-2">
                <span className={`badge ${t.status === 'replied' ? 'badge-completed' : 'badge-pending'}`}>
                  {t.status}
                </span>
              </div>
            </div>
            <button onClick={() => handleDelete(t.id)} disabled={pending} className="text-danger text-sm font-semibold hover:underline">
              Delete
            </button>
          </div>
        ))}
        {threads.length === 0 && <div className="text-muted text-sm py-4 text-center border border-dashed border-border rounded-xl">No tracked threads yet.</div>}
      </div>
    </div>
  );
}

export function TrackedSendersList({ senders }: { senders: any[] }) {
  const [newSenderEmail, setNewSenderEmail] = useState("");
  const [pending, startTransition] = useTransition();

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      await createTrackedSender({ email: newSenderEmail });
      setNewSenderEmail("");
    });
  };

  const handleDelete = (id: string) => {
    startTransition(async () => {
      await deleteTrackedSender(id);
    });
  };

  return (
    <div className="dz-card gap-4">
      <h2 className="text-xl font-semibold">Tracked Senders</h2>
      <form onSubmit={handleAdd} className="flex flex-col gap-2">
        <input 
          type="email" 
          placeholder="Sender Email Address" 
          className="input" 
          value={newSenderEmail}
          onChange={e => setNewSenderEmail(e.target.value)}
          required
          disabled={pending}
        />
        <button type="submit" disabled={pending} className="primary py-2 px-4 rounded-full font-semibold self-start mt-2">
          {pending ? "Adding..." : "Add Sender"}
        </button>
      </form>
      
      <div className="flex flex-col gap-2 mt-4">
        {senders.map(s => (
          <div key={s.id} className="flex justify-between p-3 border border-border rounded-xl bg-bg">
            <div>
              <div className="font-semibold text-fg">{s.email}</div>
              <div className="text-sm mt-2">
                <span className={`badge ${s.status === 'active' ? 'badge-completed' : 'badge-pending'}`}>
                  {s.status}
                </span>
              </div>
              <div className="text-xs text-muted mt-2">
                Last received: {s.last_received_at ? new Date(s.last_received_at).toLocaleString() : 'Never'}
              </div>
            </div>
            <button onClick={() => handleDelete(s.id)} disabled={pending} className="text-danger text-sm font-semibold hover:underline">
              Delete
            </button>
          </div>
        ))}
        {senders.length === 0 && <div className="text-muted text-sm py-4 text-center border border-dashed border-border rounded-xl">No tracked senders yet.</div>}
      </div>
    </div>
  );
}
