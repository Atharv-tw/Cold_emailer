"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { createTarget } from "@/app/desktop/(app)/dashboard/actions";

/**
 * Adding someone.
 *
 * Every question is in plain language. There is no merge field here and no
 * jargon: "what made you pick this person" is the field that used to be called
 * `specific`, asked in a way that needs no explanation and produces a better
 * answer because of it.
 */

const TARGET_TYPES = [
  ["founder", "Founder"],
  ["hiring_manager", "Hiring manager"],
  ["recruiter", "Recruiter"],
  ["engineer", "Engineer"],
  ["professor", "Professor / researcher"],
] as const;

const COMPANY_TYPES = [
  ["ai", "AI"],
  ["edtech", "Edtech"],
  ["fintech", "Fintech"],
  ["faang", "Big tech"],
  ["agency", "Agency"],
  ["research_lab", "Research lab"],
  ["other", "Something else"],
] as const;

const INTENTS = [
  ["internship", "An internship"],
  ["full_time", "Full-time work"],
  ["freelance", "Freelance work"],
  ["research", "Research"],
  ["partnership", "Working together"],
  ["feedback", "Advice or feedback"],
] as const;

export default function TargetForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  const [form, setForm] = useState({
    name: "",
    email: "",
    company: "",
    role: "",
    target_type: "founder",
    company_type: "ai",
    intent: "internship",
    hook: "",
    timezone: "",
  });
  const [links, setLinks] = useState({ portfolio: "", linkedin: "", github: "", other: "" });

  function set(field: keyof typeof form) {
    return (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm({ ...form, [field]: event.target.value });
  }

  function submit() {
    setError("");
    startTransition(async () => {
      try {
        const target = await createTarget({ ...form, links });
        router.push(`/targets/${target.id}`);
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Could not add them.");
      }
    });
  }

  return (
    <div className="stack">
      {error && <p className="error">{error}</p>}

      <section>
        <label>
          Their name
          <input value={form.name} onChange={set("name")} placeholder="Alex Chen" />
        </label>
        <label>
          Their email
          <input value={form.email} onChange={set("email")} placeholder="alex@example.com" />
        </label>
        <label>
          Company
          <input value={form.company} onChange={set("company")} />
        </label>
        <label>
          Their role
          <input value={form.role} onChange={set("role")} placeholder="Founder" />
        </label>
      </section>

      <section>
        <label>
          Who are they?
          <select value={form.target_type} onChange={set("target_type")}>
            {TARGET_TYPES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          What kind of company?
          <select value={form.company_type} onChange={set("company_type")}>
            {COMPANY_TYPES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          What are you asking about?
          <select value={form.intent} onChange={set("intent")}>
            {INTENTS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section>
        <label>
          What made you pick this person?
          <textarea
            rows={3}
            value={form.hook}
            onChange={set("hook")}
            placeholder="Their post on cutting inference cost by batching at the edge"
          />
        </label>
        <p className="muted">
          This is the one thing the email cannot be written without. Be specific
          — a real detail here is the difference between a note they answer and
          one they delete. If you leave it blank, nothing will be invented in
          its place.
        </p>
      </section>

      <section>
        <fieldset>
          <legend>Their links (optional)</legend>
          {(["linkedin", "portfolio", "other"] as const).map((key) => (
            <label key={key}>
              {key}
              <input
                value={links[key]}
                onChange={(event) => setLinks({ ...links, [key]: event.target.value })}
              />
            </label>
          ))}
        </fieldset>
      </section>

      <section>
        <button type="button" onClick={submit} disabled={pending || !form.email}>
          {pending ? "Checking the address…" : "Add them"}
        </button>
        <p className="muted">
          The address is checked when you save. Nothing is sent — you write and
          send each email yourself.
        </p>
      </section>
    </div>
  );
}
