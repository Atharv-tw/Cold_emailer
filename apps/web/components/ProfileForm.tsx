"use client";

import Link from "next/link";
import { useRef, useState, useTransition } from "react";

import {
  removeAvatar,
  saveExperience,
  saveProfile,
  saveProjects,
  uploadAvatar,
  uploadResume,
} from "@/app/desktop/(app)/profile/actions";
import Icon, { type IconName } from "@/components/Icon";
import Modal from "@/components/Modal";
import { useGeminiKey } from "@/lib/useGeminiKey";
import type { Disclosure, Profile, Project, Experience, SessionUser } from "@/lib/types";

/**
 * The profile screen.
 *
 * Three rules shape this component.
 *
 * Nothing a model extracted is saved without the user seeing it, so an upload
 * fills the form and marks every field it touched rather than writing to the
 * profile.
 *
 * The disclosure is one line at the point of upload, with the full text one
 * click away behind the info button - the earlier version put six lines of
 * legal-sounding copy above the control, which is the reliable way to get
 * something skimmed past rather than read.
 *
 * And there is exactly one save button on the page. It lives in a bar that
 * follows you down the screen and only lights up when there is something to
 * save, so "did that save?" is never a question.
 */

type Props = {
  profile: Profile;
  disclosure: Disclosure;
  user: SessionUser;
};

const FIELD_LABELS: Record<string, string> = {
  headline: "Headline",
  bio: "About you",
  evidence: "Projects or experience",
  links: "A link",
  education: "Education",
  availability: "Availability",
};

const LINK_FIELDS = [
  ["portfolio", "Portfolio"],
  ["resume", "Resume link"],
  ["github", "GitHub"],
  ["linkedin", "LinkedIn"],
  ["other", "Other"],
] as const;

function commaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

/** Education is one text column in the API. On screen it is a list of lines. */
function toLines(value: string): string[] {
  const lines = value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.length > 0 ? lines : [""];
}

function SectionCard({
  icon,
  title,
  hint,
  badge,
  children,
}: {
  icon: IconName;
  title: string;
  hint?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="dz-card gap-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-lime-tint text-accent">
          <Icon name={icon} size={17} />
        </span>
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2>{title}</h2>
            {badge}
          </div>
          {hint && <p className="mt-0.5 text-[13px]">{hint}</p>}
        </div>
      </div>
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="mb-0">
      <span className="flex items-baseline justify-between gap-2">
        <span className="text-[12.5px] font-semibold text-fg">{label}</span>
        {hint && <span className="text-[11.5px] font-normal text-muted">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

/** A removable sub-record (a project, a role). Card, not a raw fieldset. */
function EntryCard({
  index,
  title,
  onRemove,
  children,
}: {
  index: number;
  title: string;
  onRemove: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[var(--radius-md)] bg-paper p-4 ring-1 ring-line">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="eyebrow">
          {title} {index + 1}
        </span>
        <button
          type="button"
          className="quiet flex items-center gap-1 text-[12px]"
          onClick={onRemove}
          aria-label={`Remove ${title.toLowerCase()} ${index + 1}`}
        >
          <Icon name="trash" size={14} />
          Remove
        </button>
      </div>
      <div className="flex flex-col gap-3">{children}</div>
    </div>
  );
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="secondary flex w-full items-center justify-center gap-1.5 border-dashed"
    >
      <Icon name="plus" size={16} strokeWidth={2.2} />
      {label}
    </button>
  );
}

export default function ProfileForm({ profile, disclosure, user }: Props) {
  const [headline, setHeadline] = useState(profile.headline);
  const [bio, setBio] = useState(profile.bio);
  const [education, setEducation] = useState<string[]>(toLines(profile.education));
  const [availability, setAvailability] = useState(profile.availability);
  const [links, setLinks] = useState<Record<string, string>>({
    portfolio: profile.links.portfolio ?? "",
    resume: profile.links.resume ?? "",
    linkedin: profile.links.linkedin ?? "",
    github: profile.links.github ?? "",
    other: profile.links.other ?? "",
  });
  const [projects, setProjects] = useState<Project[]>(profile.projects);
  const [experience, setExperience] = useState<Experience[]>(profile.experience);

  // Which fields came from a resume rather than from the user. Cleared as
  // soon as they touch one, because at that point it is theirs.
  const [extracted, setExtracted] = useState<Set<string>>(new Set());
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [pending, startTransition] = useTransition();
  const { key: geminiKey, hasKey: hasGeminiKey } = useGeminiKey();
  const [avatarPreview, setAvatarPreview] = useState(user.avatar);
  const [avatarPending, startAvatarTransition] = useTransition();

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [keepOriginal, setKeepOriginal] = useState(false);
  const [reading, setReading] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const resumeInput = useRef<HTMLInputElement>(null);

  function touch() {
    setDirty(true);
    setStatus("");
  }

  function claim(field: string) {
    touch();
    setExtracted((current) => {
      if (!current.has(field)) return current;
      const next = new Set(current);
      next.delete(field);
      return next;
    });
  }

  function badge(field: string) {
    if (!extracted.has(field)) return null;
    return (
      <span className="badge">
        <Icon name="sparkle" size={11} strokeWidth={2} />
        from your resume — check it
      </span>
    );
  }

  async function onRead() {
    setError("");
    if (!resumeFile) return;
    if (!hasGeminiKey) {
      setError("Add your Gemini API key from the top bar before reading a resume.");
      return;
    }
    setReading(true);
    setStatus("Reading your resume…");
    try {
      const form = new FormData();
      form.append("file", resumeFile);
      if (keepOriginal) form.append("keep_original", "on");

      const parsed = await uploadResume(form, geminiKey);
      const touched = new Set<string>();

      if (parsed.headline) {
        setHeadline(parsed.headline);
        touched.add("headline");
      }
      if (parsed.bio) {
        setBio(parsed.bio);
        touched.add("bio");
      }
      if (parsed.education) {
        setEducation(toLines(parsed.education));
        touched.add("education");
      }
      if (Object.keys(parsed.links).length > 0) {
        setLinks((current) => ({ ...current, ...parsed.links }));
        touched.add("links");
      }
      if (parsed.projects.length > 0) {
        setProjects(parsed.projects);
        touched.add("projects");
      }
      if (parsed.experience.length > 0) {
        setExperience(parsed.experience);
        touched.add("experience");
      }

      setExtracted(touched);
      setDirty(true);
      setStatus(
        parsed.original_kept
          ? "Read it. Check everything, then save — nothing is on your profile yet."
          : "Read it, and the file has been deleted. Check everything, then save.",
      );
    } catch (exception) {
      setStatus("");
      setError(exception instanceof Error ? exception.message : "Upload failed.");
    } finally {
      setReading(false);
    }
  }

  function onAvatarChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setAvatarPreview(URL.createObjectURL(file));
    startAvatarTransition(async () => {
      try {
        const form = new FormData();
        form.append("file", file);
        await uploadAvatar(form);
        setStatus("Photo updated.");
      } catch (exception) {
        setAvatarPreview(user.avatar);
        setError(exception instanceof Error ? exception.message : "Could not upload that image.");
      }
    });
  }

  function onAvatarRemove() {
    setError("");
    startAvatarTransition(async () => {
      try {
        await removeAvatar();
        setAvatarPreview("");
        setStatus("Photo removed.");
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Could not remove that image.");
      }
    });
  }

  function onSave() {
    setError("");
    startTransition(async () => {
      try {
        await saveProfile({
          headline,
          bio,
          education: education.map((line) => line.trim()).filter(Boolean).join("\n"),
          availability,
          links,
          sending_window: profile.sending_window ?? {},
        });
        await saveProjects(projects);
        await saveExperience(experience);
        setExtracted(new Set());
        setDirty(false);
        setStatus("Saved.");
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Could not save.");
      }
    });
  }

  const meter = profile.completeness;
  const ring = 2 * Math.PI * 26;
  const initial = (user.name || user.email || "?").charAt(0).toUpperCase();

  return (
    <>
      <div className="grid items-start gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        {/* ---------------- left column: who you are, and the shortcut ------- */}
        {/*
          Capped at the viewport with its own scroll: a sticky column taller
          than the screen pins its top and puts its bottom permanently out of
          reach, which is how the last line of the resume card became
          unreadable on a laptop.
        */}
        <aside className="flex flex-col gap-4 xl:sticky xl:top-4 xl:max-h-[calc(100dvh-2rem)] xl:overflow-y-auto">
          <section className="dz-card items-center gap-3 text-center">
            <div className="relative">
              {avatarPreview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={avatarPreview} alt="" className="h-20 w-20 rounded-full object-cover" />
              ) : (
                <div className="avatar h-20 w-20 text-2xl">{initial}</div>
              )}
              <label
                className="absolute -bottom-1 -right-1 m-0 flex h-8 w-8 cursor-pointer flex-row items-center justify-center rounded-full bg-ink text-white ring-2 ring-white transition-transform hover:scale-105"
                title="Upload a photo"
              >
                <Icon name={avatarPending ? "clock" : "image"} size={15} />
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={onAvatarChosen}
                  disabled={avatarPending}
                  className="hidden"
                />
                <span className="sr-only">Upload a photo</span>
              </label>
            </div>

            <div>
              <div
                className="text-[16px] font-bold text-fg"
                style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}
              >
                {user.name || "Your profile"}
              </div>
              <div className="text-[12px] text-muted">{user.email}</div>
            </div>

            {avatarPreview && (
              <button type="button" className="quiet small" onClick={onAvatarRemove} disabled={avatarPending}>
                Remove photo
              </button>
            )}
            <p className="text-[11.5px]">Falls back to your Google picture if you don&rsquo;t upload one.</p>
          </section>

          {/* Completeness, as a thing you can see rather than a percentage in
              a sentence. The list below it is the actual to-do. */}
          <section className="dz-card gap-3">
            <div className="flex items-center gap-3">
              <div className="relative h-16 w-16 shrink-0">
                <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90">
                  <circle cx="32" cy="32" r="26" fill="none" stroke="var(--line)" strokeWidth="7" />
                  <circle
                    cx="32"
                    cy="32"
                    r="26"
                    fill="none"
                    stroke={meter.complete ? "var(--lime)" : "var(--ink)"}
                    strokeWidth="7"
                    strokeLinecap="round"
                    strokeDasharray={`${(ring * meter.score) / 100} ${ring}`}
                  />
                </svg>
                <span
                  className="absolute inset-0 flex items-center justify-center text-[15px] font-bold"
                  style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.03em" }}
                >
                  {meter.score}%
                </span>
              </div>
              <div>
                <div className="card-title">{meter.complete ? "Ready to send" : "Profile incomplete"}</div>
                <p className="text-[12.5px]">
                  {meter.complete
                    ? "Everything an email needs is here."
                    : "You cannot add targets until this is filled in."}
                </p>
              </div>
            </div>

            {!meter.complete && (
              <ul className="flex flex-col gap-1.5 text-[12.5px] text-muted">
                {meter.prompts.map((prompt) => (
                  <li key={prompt} className="flex gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-lime-dark" />
                    {prompt}
                  </li>
                ))}
              </ul>
            )}

            <p className="text-[11.5px]">
              Missing: {meter.missing.map((key) => FIELD_LABELS[key] ?? key).join(", ") || "nothing"}
            </p>
          </section>

          {/* The shortcut. One line of disclosure, the rest behind the ⓘ. */}
          <section className="dz-card dz-card-dark gap-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <Icon name="sparkle" size={17} />
                <h2 className="text-[16px]">Autofill from resume</h2>
              </div>
              <button
                type="button"
                onClick={() => setInfoOpen(true)}
                className="quiet -mr-1 -mt-1 p-1.5 text-white/60 hover:bg-white/10 hover:text-white"
                aria-label="What happens to my resume?"
                title="What happens to my resume?"
              >
                <Icon name="info" size={16} />
              </button>
            </div>

            <label className="m-0 flex cursor-pointer flex-row items-center justify-center gap-2 rounded-full bg-lime px-4 py-2.5 text-[13px] font-semibold text-ink transition-colors hover:bg-lime-dark">
              <Icon name="upload" size={16} />
              {resumeFile ? "Choose a different file" : "Autofill profile with resume"}
              <input
                ref={resumeInput}
                type="file"
                accept=".pdf,.docx"
                className="hidden"
                onChange={(event) => {
                  setResumeFile(event.target.files?.[0] ?? null);
                  setError("");
                }}
              />
            </label>

            {resumeFile && (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2 rounded-[var(--radius-md)] bg-white/10 px-3 py-2 text-[12.5px]">
                  <Icon name="folder" size={15} />
                  <span className="min-w-0 flex-1 truncate">{resumeFile.name}</span>
                  <button
                    type="button"
                    className="quiet p-1 text-white/60 hover:bg-white/10 hover:text-white"
                    aria-label="Clear the chosen file"
                    onClick={() => {
                      setResumeFile(null);
                      if (resumeInput.current) resumeInput.current.value = "";
                    }}
                  >
                    <Icon name="x" size={14} />
                  </button>
                </div>

                <label className="m-0 flex items-center gap-2 text-[12.5px] text-white/70">
                  <input
                    type="checkbox"
                    checked={keepOriginal}
                    onChange={(event) => setKeepOriginal(event.target.checked)}
                  />
                  Keep the original file
                </label>

                <button
                  type="button"
                  className="secondary w-full"
                  onClick={onRead}
                  disabled={reading || !hasGeminiKey}
                >
                  {reading ? "Reading…" : "Read it"}
                </button>
              </div>
            )}

            {!hasGeminiKey && (
              <p className="text-[12px] text-white/70">
                Needs a Gemini key — add one from the button in the top bar, or in{" "}
                <Link href="/settings" className="underline">
                  Settings
                </Link>
                .
              </p>
            )}

            <p className="text-[11.5px] text-white/50">
              No resume? Everything on the right can be typed in by hand.
            </p>
          </section>
        </aside>

        {/* ---------------- right column: the profile itself ----------------- */}
        <div className="flex flex-col gap-5">
          <SectionCard
            icon="user"
            title="Basics"
            hint="The first thing an email gets written from. Specific beats impressive."
          >
            <Field label="Headline" hint="One line">
              {badge("headline")}
              <input
                value={headline}
                onChange={(event) => {
                  setHeadline(event.target.value);
                  claim("headline");
                }}
                placeholder="Backend engineer, distributed systems"
              />
            </Field>

            <Field label="About you">
              {badge("bio")}
              <textarea
                rows={4}
                value={bio}
                onChange={(event) => {
                  setBio(event.target.value);
                  claim("bio");
                }}
                placeholder="What you build, what you're good at, what you're looking for."
              />
            </Field>

            <Field label="Availability" hint="Optional">
              <input
                value={availability}
                onChange={(event) => {
                  setAvailability(event.target.value);
                  touch();
                }}
                placeholder="From June, part-time until then"
              />
            </Field>
          </SectionCard>

          <SectionCard
            icon="cap"
            title="Education"
            hint="One line per degree or school. Add as many as you need."
            badge={badge("education")}
          >
            {education.map((entry, index) => (
              <div key={index} className="flex items-center gap-2">
                <input
                  className="flex-1"
                  value={entry}
                  placeholder="BSc Computer Science, State University (2022–2026)"
                  onChange={(event) => {
                    const next = [...education];
                    next[index] = event.target.value;
                    setEducation(next);
                    claim("education");
                  }}
                />
                {education.length > 1 && (
                  <button
                    type="button"
                    className="quiet shrink-0 p-2"
                    aria-label={`Remove education entry ${index + 1}`}
                    onClick={() => {
                      setEducation(education.filter((_, i) => i !== index));
                      claim("education");
                    }}
                  >
                    <Icon name="trash" size={15} />
                  </button>
                )}
              </div>
            ))}
            <AddButton
              label="Add another"
              onClick={() => {
                setEducation([...education, ""]);
                touch();
              }}
            />
          </SectionCard>

          <SectionCard
            icon="link"
            title="Links"
            hint="An email is allowed one link. These are what it picks from."
            badge={badge("links")}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              {LINK_FIELDS.map(([key, label]) => (
                <Field key={key} label={label}>
                  <input
                    value={links[key] ?? ""}
                    placeholder="https://"
                    onChange={(event) => {
                      setLinks({ ...links, [key]: event.target.value });
                      claim("links");
                    }}
                  />
                </Field>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            icon="folder"
            title="Projects"
            hint="The evidence. A draft picks whichever one fits the person you're writing to."
            badge={badge("projects")}
          >
            {projects.map((project, index) => {
              function update(patch: Partial<Project>) {
                const next = [...projects];
                next[index] = { ...project, ...patch };
                setProjects(next);
                claim("projects");
              }

              return (
                <EntryCard
                  key={project.id ?? index}
                  index={index}
                  title="Project"
                  onRemove={() => {
                    setProjects(projects.filter((_, i) => i !== index));
                    claim("projects");
                  }}
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Name">
                      <input
                        value={project.name}
                        placeholder="Finstar"
                        onChange={(event) => update({ name: event.target.value })}
                      />
                    </Field>
                    <Field label="Tech used">
                      <input
                        value={project.tech ?? ""}
                        placeholder="FastAPI, Postgres, RAG"
                        onChange={(event) => update({ tech: event.target.value })}
                      />
                    </Field>
                  </div>

                  <Field label="What it does" hint="One sentence">
                    <input
                      value={project.summary}
                      placeholder="Turns a bank statement into a monthly spending breakdown."
                      onChange={(event) => update({ summary: event.target.value })}
                    />
                  </Field>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Live link" hint="Site, repo, app store">
                      <input
                        value={project.url ?? ""}
                        placeholder="https://"
                        onChange={(event) => update({ url: event.target.value })}
                      />
                    </Field>
                    <Field label="Demo video" hint="Optional">
                      <input
                        value={project.demo_url ?? ""}
                        placeholder="Loom or YouTube walkthrough"
                        onChange={(event) => update({ demo_url: event.target.value })}
                      />
                    </Field>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Categories" hint="Comma separated">
                      <input
                        value={(project.categories ?? []).join(", ")}
                        placeholder="ai, fintech, infra"
                        onChange={(event) => update({ categories: commaList(event.target.value) })}
                      />
                    </Field>
                    <Field label="Best for" hint="Who it impresses">
                      <input
                        value={(project.best_for ?? []).join(", ")}
                        placeholder="founder, recruiter, internship"
                        onChange={(event) => update({ best_for: commaList(event.target.value) })}
                      />
                    </Field>
                  </div>
                </EntryCard>
              );
            })}
            <AddButton
              label="Add a project"
              onClick={() => {
                setProjects([
                  ...projects,
                  {
                    name: "",
                    summary: "",
                    tech: "",
                    url: "",
                    demo_url: "",
                    highlights: [],
                    categories: [],
                    best_for: [],
                  },
                ]);
                touch();
              }}
            />
          </SectionCard>

          <SectionCard
            icon="briefcase"
            title="Experience"
            hint="Where you've worked. Roles carry weight a project can't."
            badge={badge("experience")}
          >
            {experience.map((role, index) => (
              <EntryCard
                key={role.id ?? index}
                index={index}
                title="Role"
                onRemove={() => {
                  setExperience(experience.filter((_, i) => i !== index));
                  claim("experience");
                }}
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Company">
                    <input
                      value={role.company}
                      placeholder="Acme"
                      onChange={(event) => {
                        const next = [...experience];
                        next[index] = { ...role, company: event.target.value };
                        setExperience(next);
                        claim("experience");
                      }}
                    />
                  </Field>
                  <Field label="Role">
                    <input
                      value={role.role}
                      placeholder="Backend engineering intern"
                      onChange={(event) => {
                        const next = [...experience];
                        next[index] = { ...role, role: event.target.value };
                        setExperience(next);
                        claim("experience");
                      }}
                    />
                  </Field>
                </div>
              </EntryCard>
            ))}
            <AddButton
              label="Add a role"
              onClick={() => {
                setExperience([
                  ...experience,
                  { company: "", role: "", started: "", ended: "", bullets: [] },
                ]);
                touch();
              }}
            />
          </SectionCard>

          {/*
            The only save button on the page, and it follows you down it. It
            lives inside the right column rather than spanning the whole
            width, because a full-width bar floats over the sticky left
            column and covers it - and because these are the fields it saves.
            The photo and the resume upload on the left save themselves.
          */}
          <div className="sticky bottom-4 z-30">
            <div className="flex items-center gap-3 rounded-full bg-surface p-2 pl-5 shadow-[var(--shadow-float)] ring-1 ring-line">
              <span className="min-w-0 flex-1 truncate text-[13px]">
                {error ? (
                  <span className="error">{error}</span>
                ) : status ? (
                  <span className="ok flex items-center gap-1.5">
                    <Icon name="check" size={14} strokeWidth={2.4} />
                    {status}
                  </span>
                ) : dirty ? (
                  <span className="font-medium text-fg">Unsaved changes</span>
                ) : (
                  <span className="muted">Everything here is saved.</span>
                )}
              </span>
              <button
                type="button"
                className={dirty ? "accent" : "secondary"}
                onClick={onSave}
                disabled={pending || !dirty}
              >
                {pending ? "Saving…" : "Save profile"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <Modal open={infoOpen} onClose={() => setInfoOpen(false)} title="What happens to your resume">
        <ul className="flex flex-col gap-2.5 text-[13.5px] text-fg">
          {Object.entries(disclosure).map(([key, line]) => (
            <li key={key} className="flex gap-2.5">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-lime-dark" />
              {line}
            </li>
          ))}
        </ul>
        <p className="mt-4 text-[13px]">
          More detail, including what to do about a scanned PDF, is on the{" "}
          <Link href="/help#resume" className="font-medium text-fg underline">
            help page
          </Link>
          .
        </p>
      </Modal>
    </>
  );
}
