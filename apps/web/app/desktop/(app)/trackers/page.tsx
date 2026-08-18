"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function TrackersPage() {
  const [threads, setThreads] = useState<any[]>([]);
  const [senders, setSenders] = useState<any[]>([]);
  
  const [newThreadId, setNewThreadId] = useState("");
  const [newThreadSubject, setNewThreadSubject] = useState("");
  const [newSenderEmail, setNewSenderEmail] = useState("");

  const loadData = async () => {
    try {
      const ts = await api<any[]>("/v1/trackers/threads");
      setThreads(ts);
      const ss = await api<any[]>("/v1/trackers/senders");
      setSenders(ss);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const addThread = async (e: any) => {
    e.preventDefault();
    await api("/v1/trackers/threads", {
      method: "POST",
      body: JSON.stringify({ gmail_thread_id: newThreadId, subject: newThreadSubject })
    });
    setNewThreadId("");
    setNewThreadSubject("");
    loadData();
  };

  const addSender = async (e: any) => {
    e.preventDefault();
    await api("/v1/trackers/senders", {
      method: "POST",
      body: JSON.stringify({ email: newSenderEmail })
    });
    setNewSenderEmail("");
    loadData();
  };
  
  const deleteThread = async (id: string) => {
    await api(`/v1/trackers/threads/${id}`, { method: "DELETE" });
    loadData();
  };

  const deleteSender = async (id: string) => {
    await api(`/v1/trackers/senders/${id}`, { method: "DELETE" });
    loadData();
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Trackers</h1>
          <p>Monitor specific emails or senders outside of your campaigns.</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="dz-card gap-4">
          <h2 className="text-xl font-semibold">Tracked Threads</h2>
          <form onSubmit={addThread} className="flex flex-col gap-2">
            <input 
              type="text" 
              placeholder="Gmail Thread ID" 
              className="input" 
              value={newThreadId}
              onChange={e => setNewThreadId(e.target.value)}
              required
            />
            <input 
              type="text" 
              placeholder="Subject (optional)" 
              className="input" 
              value={newThreadSubject}
              onChange={e => setNewThreadSubject(e.target.value)}
            />
            <button type="submit" className="primary py-2 px-4 rounded-full font-semibold self-start mt-2">
              Add Thread
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
                <button onClick={() => deleteThread(t.id)} className="text-danger text-sm font-semibold hover:underline">
                  Delete
                </button>
              </div>
            ))}
            {threads.length === 0 && <div className="text-muted text-sm py-4 text-center border border-dashed border-border rounded-xl">No tracked threads yet.</div>}
          </div>
        </div>
        
        <div className="dz-card gap-4">
          <h2 className="text-xl font-semibold">Tracked Senders</h2>
          <form onSubmit={addSender} className="flex flex-col gap-2">
            <input 
              type="email" 
              placeholder="Sender Email Address" 
              className="input" 
              value={newSenderEmail}
              onChange={e => setNewSenderEmail(e.target.value)}
              required
            />
            <button type="submit" className="primary py-2 px-4 rounded-full font-semibold self-start mt-2">
              Add Sender
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
                <button onClick={() => deleteSender(s.id)} className="text-danger text-sm font-semibold hover:underline">
                  Delete
                </button>
              </div>
            ))}
            {senders.length === 0 && <div className="text-muted text-sm py-4 text-center border border-dashed border-border rounded-xl">No tracked senders yet.</div>}
          </div>
        </div>
      </div>
    </>
  );
}
