"""Turning a profile and a target into a draft.

Nothing here sends anything. Generation produces a draft, the draft goes into
an editor, and the user presses send. That ordering is not a UX preference -
it is the only thing standing between a language model and a stranger's inbox.

The prompt is assembled from four things: the hard rules that came over from
the CLI, the playbook for this kind of recipient, the sender's own profile,
and what the user said about this specific person. The last one carries the
most weight, because it is the only part the model could not have guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from outreach_core.limits import MAX_TOUCHES
from outreach_core.templating import lint

from .gemini import SYSTEM_RULES, AIError, GeminiClient
from .playbooks import company_context_for, intent_for, playbook_for, touch_rules


@dataclass(frozen=True)
class Draft:
    subject: str
    body: str
    warnings: list[str] = field(default_factory=list)
    step: int = 1


def _block(title: str, pairs: dict[str, Any]) -> str:
    rows = "\n".join(
        f"- {key}: {value}" for key, value in pairs.items() if str(value or "").strip()
    )
    return f"{title}\n{rows or '- (nothing supplied)'}"


def sender_block(profile, projects: list, experience: list) -> str:
    lines = _block(
        "About the sender:",
        {
            "headline": profile.headline,
            "about": profile.bio,
            "education": profile.education,
            "availability": profile.availability,
            **{f"link ({k})": v for k, v in (profile.links or {}).items()},
        },
    )

    if projects:
        rendered = "\n".join(
            f"- {p.name}: {p.summary}" + (f" ({p.tech})" if p.tech else "")
            for p in projects[:5]
        )
        lines += f"\n\nThe sender's projects:\n{rendered}"

    if experience:
        rendered = "\n".join(
            f"- {e.role} at {e.company} ({e.started}–{e.ended or 'present'})"
            + ("\n  " + "; ".join(e.bullets[:2]) if e.bullets else "")
            for e in experience[:4]
        )
        lines += f"\n\nThe sender's experience:\n{rendered}"

    return lines


def recipient_block(target) -> str:
    return _block(
        "About the recipient:",
        {
            "name": target.name,
            "role": target.role,
            "company": target.company,
            "what the sender noticed about them": target.hook,
            **{f"link ({k})": v for k, v in (target.links or {}).items()},
        },
    )


def build_prompt(
    *,
    profile,
    projects: list,
    experience: list,
    target,
    step: int,
    thread: list[tuple[str, str]] | None = None,
    instruction: str = "",
) -> str:
    """Assemble the full prompt for one email."""
    company_context = company_context_for(target.company_type)
    intent = intent_for(target.intent)

    parts = [
        SYSTEM_RULES,
        touch_rules(step, MAX_TOUCHES),
        f"Who you are writing to:\n{playbook_for(target.target_type)}",
    ]
    if company_context:
        parts.append(f"Their company: {company_context}")
    if intent:
        parts.append(intent)

    parts.append(sender_block(profile, projects, experience))
    parts.append(recipient_block(target))

    if not (target.hook or "").strip():
        # Better to say this than to let the model paper over the gap with a
        # compliment it invented.
        parts.append(
            "The sender did not say what made them pick this person. Do not "
            "invent a reason. Write around it."
        )

    if thread:
        rendered = "\n\n".join(
            f"--- email {index + 1} (already sent) ---\nSubject: {subject}\n{body}"
            for index, (subject, body) in enumerate(thread)
        )
        parts.append(
            "Emails already sent in this thread, which they have not answered. "
            "Do not repeat anything in them:\n\n" + rendered
        )

    if instruction.strip():
        parts.append(
            "Instruction from the sender, which overrides the style guidance "
            f"above:\n{instruction.strip()}"
        )

    parts.append("Write the email now.")
    return "\n\n".join(parts)


def split_subject(text: str) -> tuple[str, str]:
    """Pull 'Subject: ...' off the front. Models sometimes skip it."""
    lines = text.splitlines()
    subject = ""
    start = 0
    for index, line in enumerate(lines[:4]):
        stripped = line.strip()
        if stripped.lower().startswith("subject:"):
            subject = stripped.split(":", 1)[1].strip()
            start = index + 1
            break
    return subject, "\n".join(lines[start:]).strip()


async def generate(
    client: GeminiClient,
    *,
    profile,
    projects: list,
    experience: list,
    target,
    step: int,
    thread: list[tuple[str, str]] | None = None,
    instruction: str = "",
    temperature: float = 0.7,
) -> Draft:
    prompt = build_prompt(
        profile=profile,
        projects=projects,
        experience=experience,
        target=target,
        step=step,
        thread=thread,
        instruction=instruction,
    )
    text = await client.generate_text(prompt, temperature=temperature, max_output_tokens=1024)
    subject, body = split_subject(text)

    if not body:
        raise AIError("The model returned a subject with no body. Try regenerating.")

    # A follow-up replies in the existing thread, so it needs no subject of its
    # own; a first email without one is a failure worth reporting.
    if step == 1 and not subject:
        raise AIError("The model returned no subject line. Try regenerating.")

    return Draft(subject=subject, body=body, warnings=lint(body), step=step)
