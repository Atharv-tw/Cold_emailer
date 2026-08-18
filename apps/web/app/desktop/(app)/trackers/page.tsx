import { api } from "@/lib/api";
import { requireAuth } from "@/lib/auth-guard";
import { TrackedThreadsList, TrackedSendersList } from "./client";

export default async function TrackersPage() {
  await requireAuth();

  let threads: any[] = [];
  let senders: any[] = [];
  
  try {
    threads = await api<any[]>("/v1/trackers/threads");
    senders = await api<any[]>("/v1/trackers/senders");
  } catch (e) {
    console.error("Failed to fetch trackers", e);
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Trackers</h1>
          <p>Monitor specific emails or senders outside of your campaigns.</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <TrackedThreadsList threads={threads} />
        <TrackedSendersList senders={senders} />
      </div>
    </>
  );
}
