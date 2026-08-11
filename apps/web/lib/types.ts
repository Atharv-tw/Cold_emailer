export type Project = {
  id?: string;
  name: string;
  summary: string;
  tech: string;
  url: string;
  demo_url: string;
  highlights: string[];
  categories: string[];
  best_for: string[];
};

export type Experience = {
  id?: string;
  company: string;
  role: string;
  started: string;
  ended: string;
  bullets: string[];
};

export type Completeness = {
  score: number;
  complete: boolean;
  missing: string[];
  prompts: string[];
};

export type Profile = {
  headline: string;
  bio: string;
  education: string;
  availability: string;
  links: Record<string, string>;
  sending_window: Record<string, unknown>;
  daily_cap: number;
  projects: Project[];
  experience: Experience[];
  completeness: Completeness;
};

export type ParsedResume = {
  resume_id: string;
  filename: string;
  machine_extracted: boolean;
  original_kept: boolean;
  name: string;
  headline: string;
  bio: string;
  education: string;
  links: Record<string, string>;
  projects: Project[];
  experience: Experience[];
};

export type Disclosure = Record<string, string>;

export type SessionUser = {
  id: string;
  email: string;
  name: string;
  avatar: string;
  connected: boolean;
  missing_scopes: string[];
  profile_complete: boolean;
  calendar_connected: boolean;
  // Optional so an older API response still typechecks; both default to false
  // server-side, and false is the safe reading of "absent" for an entitlement
  // and a role alike.
  is_paid?: boolean;
  is_admin?: boolean;
};

export type AvatarOut = { avatar_url: string };

export type PoolPage = {
  items: PoolContact[];
  // Matching the current filters, ignoring limit and offset - so the header
  // can say how many exist rather than how many were fetched.
  total: number;
};

export type Billing = {
  // False when the deployment has no UPI id, price or object storage set.
  available: boolean;
  price_inr: number;
  upi_id: string;
  payee_name: string;
  // "" when this account has never claimed.
  request_status: "" | "pending" | "approved" | "rejected";
  requested_at: string | null;
  is_paid: boolean;
};

export type PaymentRequestOut = {
  id: string;
  status: string;
  created_at: string;
};

export type AdminUserRow = {
  id: string;
  email: string;
  name: string;
  joined_at: string;
  is_paid: boolean;
  is_admin: boolean;
  connected: boolean;
};

export type AdminUserDetail = AdminUserRow & {
  targets: number;
  sent: number;
  last_sent_at: string | null;
};

export type AdminPayment = {
  id: string;
  user_id: string;
  user_email: string;
  user_name: string;
  upi_reference: string;
  status: string;
  created_at: string;
  reviewed_at: string | null;
  note: string;
  notify_error: string;
};

export type Verification = {
  status?: "deliverable" | "risky" | "undeliverable" | "unknown";
  reason?: string;
  detail?: string;
  did_you_mean?: string;
  source?: string;
  checked_at?: string;
};

/**
 * A person in the shared pool, before anyone has taken them.
 *
 * No `hook` and no `status`: both belong to one user's outreach rather than to
 * the person, and a pool row has neither until it is added to a list.
 */
export type PoolContact = {
  id: string;
  name: string;
  email: string;
  role: string;
  company: string;
  company_description: string;
  company_website: string;
  target_type: string;
  company_type: string;
  timezone: string;
  links: Record<string, string>;
  verification: Verification;
};

export type Target = {
  id: string;
  name: string;
  email: string;
  company: string;
  role: string;
  target_type: string;
  company_type: string;
  timezone: string;
  hook: string;
  intent: string;
  links: Record<string, string>;
  verification: Verification;
  status: string;
  status_detail: string;
  touches_sent: number;
  touches_remaining: number;
  last_touch_at: string | null;
  can_send: boolean;
  blocked_reason: string;
  gmail_thread_url: string;
};

export type Reply = {
  target_id: string;
  from_email: string;
  subject: string;
  body: string;
  received_at: string | null;
  read_at: string | null;
  gmail_thread_url: string;
};

export type Draft = {
  target_id: string;
  step: number;
  subject: string;
  body: string;
  warnings: string[];
  is_follow_up: boolean;
  touches_remaining: number;
};

export type EmailTemplate = {
  key: string;
  name: string;
  description: string;
};

export type SendResult = {
  sent: boolean;
  reason: string;
  scheduled_for: string | null;
  touches_sent: number;
};

export type DueItem = {
  target_id: string;
  name: string;
  email: string;
  company: string;
  step: number;
  due_at: string;
  has_draft: boolean;
};

export type TimelineEntry = { at: string; type: string; detail: string };

export type TargetSummary = {
  id: string;
  name: string;
  email: string;
  company: string;
  status: string;
  status_detail: string;
  touches_sent: number;
  last_touch_at: string | null;
};

export type SentByDay = { date: string; count: number };

export type ReplyItem = {
  target_id: string;
  name: string;
  company: string;
  at: string;
  unread: boolean;
};

export type Dashboard = {
  counts: Record<string, number>;
  due: DueItem[];
  recent: TimelineEntry[];
  targets: TargetSummary[];
  suppressed: number;
  sent_by_day: SentByDay[];
  replies: ReplyItem[];
};

export type ScheduledItem = {
  target_id: string;
  name: string;
  email: string;
  company: string;
  step: number;
  due_at: string;
  /** A slot with no draft written for it sends nothing when its time comes. */
  drafted: boolean;
  /** Parked by the worker: due, never written, no longer being scanned. */
  needs_draft: boolean;
  /** 0 parked, 1 unwritten and due within a day, 2 everything else. */
  urgency: number;
};

export type ScheduledOut = { items: ScheduledItem[] };

export type ImportField = { key: string; label: string; required: boolean };

export type ImportRowStatus =
  | "ok"
  | "needs_hook"
  | "duplicate"
  | "suppressed"
  // Hard-bounced for somebody on this platform, so nobody can import it.
  // Distinct from `suppressed`, which is this user's own choice.
  | "undeliverable"
  | "invalid";

export type ImportRow = {
  index: number;
  name: string;
  email: string;
  company: string;
  role: string;
  status: ImportRowStatus;
  issues: string[];
  importable: boolean;
};

export type ImportSummary = {
  total: number;
  importable: number;
  needs_hook: number;
  duplicates: number;
  suppressed: number;
  undeliverable: number;
  invalid: number;
};

export type ImportPreview = {
  headers: string[];
  fields: ImportField[];
  mapping: Record<string, string>;
  unmapped_required: string[];
  rows: ImportRow[];
  summary: ImportSummary;
};

export type ImportCommitResult = {
  created: number;
  skipped: number;
  skipped_reasons: Record<string, number>;
  summary: ImportSummary;
};

export type AnalyticsFacetRow = { value: string; contacted: number; replied: number };

export type Analytics = {
  totals: {
    sent: number;
    contacted: number;
    replied: number;
    bounced: number;
    opted_out: number;
    reply_rate: number;
    bounce_rate: number;
    opt_out_rate: number;
  };
  active_sequences: number;
  follow_ups_due: number;
  stale: number;
  by_target_type: AnalyticsFacetRow[];
  by_company_type: AnalyticsFacetRow[];
  by_intent: AnalyticsFacetRow[];
};

export type OpsJob = { job: string; at: string; detail: string };

export type OpsFailedSend = {
  target_id: string;
  email: string;
  error: string;
  at: string | null;
};

export type Ops = {
  worker_running: boolean;
  jobs: OpsJob[];
  connected: boolean;
  disconnected_reason: string;
  watch_last_renewed: string | null;
  watch_expires_at: string | null;
  watch_healthy: boolean;
  reconcile_last_read: string | null;
  follow_ups_due: number;
  failed_sends: OpsFailedSend[];
};

export type MessageOut = {
  id: string;
  target_id: string;
  target_name: string;
  target_company: string;
  target_email: string;
  step: number;
  subject: string;
  body: string;
  status: string;
  sent_at: string | null;
  error: string;
  is_reply: boolean;
  is_undeliverable: boolean;
};

export type ThreadMessage = {
  step: number;
  subject: string;
  body: string;
  status: string;
  sent_at: string | null;
  error: string;
  /** Set when this draft is queued. A queued message is still status "draft". */
  queued_for: string | null;
};

export type TargetDetail = {
  target: TargetSummary;
  messages: ThreadMessage[];
  timeline: TimelineEntry[];
  touches_remaining: number;
  queued_for: string | null;
  queued_step: number | null;
};
