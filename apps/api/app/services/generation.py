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
from .email_templates import DEFAULT_TEMPLATE_KEY, template_for
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
            f"- {p.name}: {p.summary}"
            + (f" ({p.tech})" if p.tech else "")
            + (f" [{', '.join(p.categories)}]" if getattr(p, "categories", None) else "")
            + (f" best for: {', '.join(p.best_for)}" if getattr(p, "best_for", None) else "")
            + (f" live link: {p.url}" if p.url else "")
            + (f" demo video: {p.demo_url}" if getattr(p, "demo_url", None) else "")
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


def _tokens(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        tokens.update(
            part.strip().lower()
            for part in str(value or "").replace("_", " ").replace("-", " ").split()
            if part.strip()
        )
    return tokens


def _match_score(project, target_terms: set[str]) -> int:
    categories = _tokens(*getattr(project, "categories", []) or [])
    best_for = _tokens(*getattr(project, "best_for", []) or [])
    tech = _tokens(getattr(project, "tech", ""))
    name = _tokens(getattr(project, "name", ""))
    summary = _tokens(getattr(project, "summary", ""))
    return (
        4 * len(best_for & target_terms)
        + 3 * len(categories & target_terms)
        + 2 * len(tech & target_terms)
        + len((name | summary) & target_terms)
    )


def _target_terms(target) -> set[str]:
    return _tokens(
        target.company_type,
        target.target_type,
        target.intent,
        target.role,
        target.company,
        target.hook,
    )


def ranked_projects(projects: list, target) -> list:
    """Put the most relevant sender evidence first for this target."""
    target_terms = _target_terms(target)

    def sort_key(project) -> tuple[int, int]:
        # Negative position keeps stable profile order as the tie-breaker.
        return _match_score(project, target_terms), -int(getattr(project, "position", 0) or 0)

    return sorted(projects, key=sort_key, reverse=True)


def selected_evidence_block(projects: list, target) -> str:
    """The one or two pieces of sender evidence most relevant to this target.

    Handing the model the whole project list and hoping it picks well is how
    you get an email about the wrong thing. Ranking and naming the best match
    explicitly is what makes the email specific instead of generic.
    """
    ranked = [p for p in ranked_projects(projects, target) if str(getattr(p, "name", "")).strip()]
    if not ranked:
        return ""

    target_terms = _target_terms(target)
    scored = [(p, _match_score(p, target_terms)) for p in ranked]

    def rows(project) -> dict[str, str]:
        return {
            "project": getattr(project, "name", ""),
            "summary": getattr(project, "summary", ""),
            "tech": getattr(project, "tech", ""),
            "live link": getattr(project, "url", ""),
            "demo video": getattr(project, "demo_url", ""),
            "categories": ", ".join(getattr(project, "categories", []) or []),
            "best for": ", ".join(getattr(project, "best_for", []) or []),
        }

    top_project, top_score = scored[0]
    if top_score > 0:
        blocks = [
            _block(
                "The best-matching project for this recipient - reference this one by name:",
                rows(top_project),
            )
        ]
        second_project, second_score = scored[1] if len(scored) > 1 else (None, 0)
        if second_project is not None and second_score > 0:
            blocks.append(
                _block("A second option, only if it fits the specific ask better:", rows(second_project))
            )
    else:
        # Nothing in the profile actually matches this recipient. Naming one
        # as "best matching" anyway is how the model invents relevance that
        # is not there, which reads as generic even when it namechecks a
        # real project. Offer it as a plain option instead.
        blocks = [
            _block(
                "Nothing in the sender's projects is a clear match for this "
                "recipient's context. This is just the sender's most prominent "
                "project - use it only if you can say something specific and "
                "true about it; otherwise lean on the recipient's own context "
                "(their hook, role, company) instead of forcing a project in:",
                rows(top_project),
            )
        ]
    return "\n\n".join(blocks)


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
    template_key: str = DEFAULT_TEMPLATE_KEY,
) -> str:
    """Assemble the full prompt for one email."""
    company_context = company_context_for(target.company_type)
    intent = intent_for(target.intent)
    template = template_for(template_key)

    parts = [
        SYSTEM_RULES,
        touch_rules(step, MAX_TOUCHES),
        f"Selected template: {template.name}\n{template.guidance}",
        f"Who you are writing to:\n{playbook_for(target.target_type)}",
    ]
    if company_context:
        parts.append(f"Their company: {company_context}")
    if intent:
        parts.append(intent)

    parts.append(sender_block(profile, projects, experience))
    evidence = selected_evidence_block(projects, target)
    if evidence:
        parts.append(evidence)
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
    template_key: str = DEFAULT_TEMPLATE_KEY,
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
        template_key=template_key,
    )
    text = await client.generate_text(prompt, temperature=temperature, max_output_tokens=4096)
    subject, body = split_subject(text)

    if not body:
        raise AIError("The model returned a subject with no body. Try regenerating.")

    # A follow-up replies in the existing thread, so it needs no subject of its
    # own; a first email without one is a failure worth reporting.
    if step == 1 and not subject:
        raise AIError("The model returned no subject line. Try regenerating.")

    return Draft(subject=subject, body=body, warnings=lint(body), step=step)
