"use client";

import { useEffect, useState, useTransition } from "react";

import {
  deleteMyData,
  removeAvatar,
  saveExperience,
  saveProfile,
  saveProjects,
  uploadAvatar,
  uploadResume,
} from "@/app/desktop/(app)/profile/actions";
import { useGeminiKey } from "@/lib/useGeminiKey";
import type { Disclosure, Profile, Project, Experience, SessionUser } from "@/lib/types";

/**
 * The profile screen.
 *
 * Two rules shape this component. Nothing a model extracted is saved without
 * the user seeing it, so an upload fills the form and marks every field it
 * touched rather than writing to the profile. And the disclosure sits above
 * the upload control, not behind a link - the user should know the file is
 * going to Gemini before they choose it, not after.
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

function commaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

export default function ProfileForm({ profile, disclosure, user }: Props) {
  const [headline, setHeadline] = useState(profile.headline);
  const [bio, setBio] = useState(profile.bio);
  const [education, setEducation] = useState(profile.education);
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
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [pending, startTransition] = useTransition();
  const { key: geminiKey, setKey: setGeminiKey, hasKey: hasGeminiKey } = useGeminiKey();
  const [geminiDraft, setGeminiDraft] = useState(geminiKey);
  const [avatarPreview, setAvatarPreview] = useState(user.avatar);
  const [avatarPending, startAvatarTransition] = useTransition();

  useEffect(() => setGeminiDraft(geminiKey), [geminiKey]);

  function claim(field: string) {
    setExtracted((current) => {
      if (!current.has(field)) return current;
      const next = new Set(current);
      next.delete(field);
      return next;
    });
  }

  function badge(field: string) {
    if (!extracted.has(field)) return null;
    return <span className="badge">from your resume — check it</span>;
  }

  async function onUpload(form: FormData) {
    setError("");
    if (!hasGeminiKey) {
      setError("Add your Gemini API key above before uploading a resume.");
      return;
    }
    setStatus("Reading your resume…");
    try {
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
        setEducation(parsed.education);
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
      setStatus(
        parsed.original_kept
          ? "Read it. Check everything below, then save — nothing is stored on your profile yet."
          : "Read it, and the file has been deleted. Check everything below, then save.",
      );
    } catch (exception) {
      setStatus("");
      setError(exception instanceof Error ? exception.message : "Upload failed.");
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
          education,
          availability,
          links,
          sending_window: profile.sending_window ?? {},
        });
        await saveProjects(projects);
        await saveExperience(experience);
        setExtracted(new Set());
        setStatus("Saved.");
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Could not save.");
      }
    });
  }

  const meter = profile.completeness;

  return (
    <div className="stack">
      <section className="flex items-center gap-4">
        {avatarPreview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatarPreview} alt="" className="h-16 w-16 rounded-full object-cover" />
        ) : (
          <div className="avatar" style={{ width: "64px", height: "64px", fontSize: "24px" }}>
            {(user.name || user.email || "?").charAt(0).toUpperCase()}
          </div>
        )}
        <div>
          <h2 style={{ marginBottom: "0.25rem" }}>Profile picture</h2>
          <div className="flex gap-2">
            <label className="secondary" style={{ display: "inline-flex", cursor: "pointer" }}>
              {avatarPending ? "Uploading…" : "Upload photo"}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={onAvatarChosen}
                disabled={avatarPending}
                style={{ display: "none" }}
              />
            </label>
            {avatarPreview && (
              <button type="button" className="quiet" onClick={onAvatarRemove} disabled={avatarPending}>
                Remove
              </button>
            )}
          </div>
          <p className="muted" style={{ fontSize: "12px", marginTop: "0.25rem" }}>
            Falls back to your Google account picture if you don&rsquo;t upload one.
          </p>
        </div>
      </section>

      <section>
        <h2>AI</h2>
        <label>
          Gemini API key
          <input
            type="password"
            value={geminiDraft}
            onChange={(event) => setGeminiDraft(event.target.value)}
            placeholder="AIza…"
          />
        </label>
        <div className="flex gap-2">
          <button type="button" className="secondary" onClick={() => setGeminiKey(geminiDraft)}>
            Save key
          </button>
          {hasGeminiKey && (
            <button
              type="button"
              className="quiet"
              onClick={() => {
                setGeminiKey("");
                setGeminiDraft("");
              }}
            >
              Clear
            </button>
          )}
        </div>
        <p className="muted" style={{ fontSize: "12px" }}>
          Powers drafting and resume reading. Kept only in this browser tab — never sent anywhere
          but the API, and gone the moment you close the tab. Get a free key at{" "}
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">
            aistudio.google.com/apikey
          </a>
          .
        </p>
      </section>

      <section>
        <h2>Upload a resume</h2>
        <div className="note">
          <ul>
            {Object.entries(disclosure).map(([key, line]) => (
              <li key={key}>{line}</li>
            ))}
          </ul>
        </div>

        <form action={onUpload} className="stack">
          <input type="file" name="file" accept=".pdf,.docx" required />
          <label>
            <input type="checkbox" name="keep_original" /> Keep the original file
          </label>
          <button type="submit">Read it</button>
        </form>

        <p className="muted">
          No resume? Everything below can be filled in by hand — the form is the
          same either way.
        </p>
      </section>

      {status && <p className="ok">{status}</p>}
      {error && <p className="error">{error}</p>}

      <section>
        <h2>
          Profile <span className="muted">({meter.score}% complete)</span>
        </h2>
        {!meter.complete && (
          <div className="note">
            <strong>You cannot add targets yet.</strong> An email written from
            an empty profile has nothing specific to say, which is exactly the
            mail that gets deleted. Still needed:
            <ul>
              {meter.prompts.map((prompt) => (
                <li key={prompt}>{prompt}</li>
              ))}
            </ul>
          </div>
        )}

        <label>
          Headline {badge("headline")}
          <input
            value={headline}
            onChange={(event) => {
              setHeadline(event.target.value);
              claim("headline");
            }}
            placeholder="Backend engineer, distributed systems"
          />
        </label>

        <label>
          About you {badge("bio")}
          <textarea
            rows={4}
            value={bio}
            onChange={(event) => {
              setBio(event.target.value);
              claim("bio");
            }}
          />
        </label>

        <label>
          Education {badge("education")}
          <input
            value={education}
            onChange={(event) => {
              setEducation(event.target.value);
              claim("education");
            }}
          />
        </label>

        <label>
          Availability
          <input
            value={availability}
            onChange={(event) => setAvailability(event.target.value)}
            placeholder="From June, part-time until then"
          />
        </label>

        <fieldset>
          <legend>Links {badge("links")}</legend>
          {(
            [
              ["portfolio", "Portfolio"],
              ["resume", "Resume link"],
              ["github", "GitHub"],
              ["linkedin", "LinkedIn"],
              ["other", "Other"],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                value={links[key] ?? ""}
                onChange={(event) => {
                  setLinks({ ...links, [key]: event.target.value });
                  claim("links");
                }}
              />
            </label>
          ))}
          <p className="muted">
            An email is allowed one link. These are what it picks from.
          </p>
        </fieldset>
      </section>

      <section>
        <h2>Projects {badge("projects")}</h2>
        {projects.map((project, index) => (
          <fieldset key={project.id ?? index}>
            <input
              value={project.name}
              placeholder="Name"
              onChange={(event) => {
                const next = [...projects];
                next[index] = { ...project, name: event.target.value };
                setProjects(next);
                claim("projects");
              }}
            />
            <input
              value={project.summary}
              placeholder="One sentence on what it does"
              onChange={(event) => {
                const next = [...projects];
                next[index] = { ...project, summary: event.target.value };
                setProjects(next);
                claim("projects");
              }}
            />
            <input
              value={(project.tech ?? "")}
              placeholder="Tech used, e.g. FastAPI, Postgres, RAG"
              onChange={(event) => {
                const next = [...projects];
                next[index] = { ...project, tech: event.target.value };
                setProjects(next);
                claim("projects");
              }}
            />
            <input
              value={(project.url ?? "")}
              placeholder="Live link (site, repo, app store)"
              onChange={(event) => {
                const next = [...projects];
                next[index] = { ...project, url: event.target.value };
                setProjects(next);
                claim("projects");
              }}
            />
            <input
              value={(project.demo_url ?? "")}
              placeholder="Demo video link (optional, e.g. a Loom or YouTube walkthrough)"
              onChange={(event) => {
                const next = [...projects];
                next[index] = { ...project, demo_url: event.target.value };
                setProjects(next);
                claim("projects");
              }}
            />
            <input
              value={(project.categories ?? []).join(", ")}
              placeholder="Categories: ai, fintech, infra"
              onChange={(event) => {
                const next = [...projects];
                next[index] = { ...project, categories: commaList(event.target.value) };
                setProjects(next);
                claim("projects");
              }}
            />
            <input
              value={(project.best_for ?? []).join(", ")}
              placeholder="Best for: founder, recruiter, internship"
              onChange={(event) => {
                const next = [...projects];
                next[index] = { ...project, best_for: commaList(event.target.value) };
                setProjects(next);
                claim("projects");
              }}
            />
            <button
              type="button"
              className="quiet"
              onClick={() => setProjects(projects.filter((_, i) => i !== index))}
            >
              Remove
            </button>
          </fieldset>
        ))}
        <button
          type="button"
          className="quiet"
          onClick={() =>
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
            ])
          }
        >
          Add a project
        </button>
      </section>

      <section>
        <h2>Experience {badge("experience")}</h2>
        {experience.map((role, index) => (
          <fieldset key={role.id ?? index}>
            <input
              value={role.company}
              placeholder="Company"
              onChange={(event) => {
                const next = [...experience];
                next[index] = { ...role, company: event.target.value };
                setExperience(next);
                claim("experience");
              }}
            />
            <input
              value={role.role}
              placeholder="Role"
              onChange={(event) => {
                const next = [...experience];
                next[index] = { ...role, role: event.target.value };
                setExperience(next);
                claim("experience");
              }}
            />
            <button
              type="button"
              className="quiet"
              onClick={() => setExperience(experience.filter((_, i) => i !== index))}
            >
              Remove
            </button>
          </fieldset>
        ))}
        <button
          type="button"
          className="quiet"
          onClick={() =>
            setExperience([
              ...experience,
              { company: "", role: "", started: "", ended: "", bullets: [] },
            ])
          }
        >
          Add a role
        </button>
      </section>

      <section>
        <button type="button" onClick={onSave} disabled={pending}>
          {pending ? "Saving…" : "Save profile"}
        </button>
      </section>

      <section>
        <h2>Your data</h2>
        <p className="muted">
          Deletes every resume you have uploaded and everything extracted from
          one, files included. It cannot be undone.
        </p>
        <button
          type="button"
          className="danger"
          onClick={() => {
            if (!confirm("Delete every resume and everything extracted from one?")) return;
            startTransition(async () => {
              await deleteMyData();
              setHeadline("");
              setBio("");
              setEducation("");
              setLinks({ portfolio: "", resume: "", linkedin: "", github: "", other: "" });
              setProjects([]);
              setExperience([]);
              setExtracted(new Set());
              setStatus("Deleted.");
            });
          }}
        >
          Delete my resume and parsed data
        </button>
      </section>

      <p className="muted">
        Missing: {meter.missing.map((key) => FIELD_LABELS[key] ?? key).join(", ") || "nothing"}
      </p>
    </div>
  );
}
