"""What to say to whom.

These replace the YAML sequences. The difference is not cosmetic: a template
has holes to fill, and mail assembled by filling holes reads exactly like mail
assembled by filling holes. A playbook is guidance handed to the writer -
what this kind of person actually cares about, what a reasonable ask looks
like, and what marks the sender as someone who sends a hundred of these.

Each block is prose because it is going into a prompt, and prose is what the
model reads best. Keep them short; a long playbook crowds out the actual
profile and the actual person.
"""

from __future__ import annotations

TARGET_PLAYBOOKS: dict[str, str] = {
    "founder": """\
Founders read their own inbox and have no time. They care about whether you
understood what the company is actually doing, and whether you can do
something they currently need done. Lead with the specific thing you noticed,
not with who you are. One concrete piece of evidence beats three claims. The
ask should cost them one reply, not a meeting.
Do not describe yourself as passionate, do not call the company a rocket ship,
and do not offer to "add value".""",
    "hiring_manager": """\
Hiring managers are reading against a role they already have in their head.
Say early which kind of work you want, so they can place you in two seconds.
Point at one thing you built that resembles what their team does. If there is
an open role, name it. The ask is whether it is worth a conversation, not for
a job.
Do not attach a cover letter's worth of text, and do not restate your CV.""",
    "recruiter": """\
Recruiters are matching people to open requisitions and moving on. Be
concrete and skimmable: what you do, what you have shipped, what you are
looking for, and when you are available. They will forgive plainness and will
not forgive vagueness. The ask is whether anything on their desk fits.
Do not write a personal essay - it slows down the only thing they can do
with your email.""",
    "engineer": """\
Engineers respond to technical specificity and nothing else. Reference the
actual work - a paper, a library, a design decision - and say something true
about it. A question they would enjoy answering works better than a request.
Do not ask them to refer you in the first email; you have not earned it, and
they know that.
Do not flatter, and do not pretend to have read something you have not.""",
    "professor": """\
Academics get a great many of these and can tell within one line whether you
read the work. Name the specific paper or project and say what in it you
engaged with. Be honest about your level. The ask should be small and
concrete - whether they are taking students, whether there is space in a
group - and should make it easy to say no.
Do not claim to have read everything they have written, and do not attach
anything unrequested.""",
}

DEFAULT_PLAYBOOK = """\
Write to this person as an individual. Lead with the specific reason you are
writing to them rather than to anyone else, give one concrete piece of
evidence that you can do what you say, and make the ask small enough to answer
in one line."""

INTENT_GUIDANCE: dict[str, str] = {
    "internship": "You are asking about an internship. Be clear about your availability and how long for.",
    "full_time": "You are asking about full-time work. Be clear about what kind of role and roughly when.",
    "freelance": "You are offering to do a specific piece of work. Say what, and keep money out of the first email.",
    "research": "You are asking about research. Engage with the actual work before asking for anything.",
    "partnership": "You are proposing working together. Say what you would bring, briefly and concretely.",
    "feedback": "You are asking for feedback or advice. Ask one specific question, not for their time in general.",
}

COMPANY_CONTEXT: dict[str, str] = {
    "edtech": "Education technology - outcomes and access matter more than novelty.",
    "ai": "An AI company - assume they have read every generic AI email already this week.",
    "fintech": "Fintech - correctness, compliance and reliability are the currency.",
    "faang": "A large tech company - process is fixed, so a personal note is about the person, not the pipeline.",
    "agency": "An agency - they think in client work, throughput and turnaround.",
    "research_lab": "A research lab - engage with published work, not with the institution.",
    "other": "",
}

FIRST_TOUCH_RULES = """\
This is the first email to this person. They have never heard from you.

After the greeting, three paragraphs and nothing else:
1. Intro - their work, and a little about the sender.
2. The work - one named project or piece of the sender's experience.
3. The ask - what the sender wants.

Two sentences per paragraph. Say the thing and stop; do not explain why it is
relevant, do not justify, and do not stack clauses onto a sentence that was
already finished."""

FOLLOW_UP_RULES = """\
This is a follow-up in a thread they have not answered. It must be much
shorter than the first email - two or three sentences, and the three-paragraph
shape of a first email does not apply. Do not repeat the
pitch, do not re-introduce yourself, and do not imply they were rude to ignore
you; they were busy. Add one new thing or ask one narrower question, then
stop. If there is nothing new to say, say less.
Never use the words "just following up", "bumping this", or "circling back"."""

LAST_TOUCH_RULES = """\
This is the last email in this thread; nothing further will be sent whatever
happens. Say so plainly and without reproach - it reads as courteous, and it
is also true. Keep it to two sentences and leave the door open. The
three-paragraph shape of a first email does not apply here."""


def playbook_for(target_type: str) -> str:
    return TARGET_PLAYBOOKS.get(target_type, DEFAULT_PLAYBOOK)


def intent_for(intent: str) -> str:
    return INTENT_GUIDANCE.get(intent, "")


def company_context_for(company_type: str) -> str:
    return COMPANY_CONTEXT.get(company_type, "")


def touch_rules(step: int, max_touches: int) -> str:
    """Guidance that depends on where in the sequence this email sits."""
    if step <= 1:
        return FIRST_TOUCH_RULES
    if step >= max_touches:
        return LAST_TOUCH_RULES
    return FOLLOW_UP_RULES
