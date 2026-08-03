export type Project = {
  id?: string;
  name: string;
  summary: string;
  tech: string;
  url: string;
  highlights: string[];
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
