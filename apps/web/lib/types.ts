export type Project = {
  id?: string;
  name: string;
  summary: string;
  tech: string;
  url: string;
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

export type Verification = {
  status?: "deliverable" | "risky" | "undeliverable" | "unknown";
  reason?: string;
  detail?: string;
  did_you_mean?: string;
  source?: string;
  checked_at?: string;
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

export type Dashboard = {
  counts: Record<string, number>;
  due: DueItem[];
  recent: TimelineEntry[];
  targets: TargetSummary[];
  suppressed: number;
};

export type ThreadMessage = {
  step: number;
  subject: string;
  body: string;
  status: string;
  sent_at: string | null;
  error: string;
};

export type TargetDetail = {
  target: TargetSummary;
  messages: ThreadMessage[];
  timeline: TimelineEntry[];
  touches_remaining: number;
};
