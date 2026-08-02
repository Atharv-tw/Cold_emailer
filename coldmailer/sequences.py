"""Loading and validating drip sequences."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class SequenceError(Exception):
    pass


@dataclass
class Step:
    id: int
    delay_business_days: int
    body: str
    subject: str | None = None
    send_at_hour: int | None = None  # optional preferred local hour

    @property
    def is_followup(self) -> bool:
        return self.subject is None


@dataclass
class Sequence:
    name: str
    steps: list[Step]
    stop_on_reply: bool = True
    description: str = ""

    def step(self, step_id: int) -> Step | None:
        return next((s for s in self.steps if s.id == step_id), None)

    @property
    def last_step_id(self) -> int:
        return max(s.id for s in self.steps)


def load_sequence(path: str | Path) -> Sequence:
    path = Path(path)
    if not path.exists():
        raise SequenceError(f"no sequence file at {path}")

    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    name = raw.get("name") or path.stem
    steps_raw = raw.get("steps") or []
    if not steps_raw:
        raise SequenceError(f"sequence '{name}' has no steps")

    steps: list[Step] = []
    for index, step_raw in enumerate(steps_raw):
        step_id = int(step_raw.get("id", index + 1))
        body = step_raw.get("body")
        if not body or not str(body).strip():
            raise SequenceError(f"sequence '{name}' step {step_id} has an empty body")

        delay = int(step_raw.get("delay_business_days", 0 if index == 0 else 3))
        if delay < 0:
            raise SequenceError(f"sequence '{name}' step {step_id} has a negative delay")

        subject = step_raw.get("subject")
        subject = str(subject).strip() if subject else None

        hour = step_raw.get("send_at_hour")
        steps.append(
            Step(
                id=step_id,
                delay_business_days=delay,
                body=str(body),
                subject=subject,
                send_at_hour=int(hour) if hour is not None else None,
            )
        )

    steps.sort(key=lambda s: s.id)
    expected = list(range(1, len(steps) + 1))
    if [s.id for s in steps] != expected:
        raise SequenceError(
            f"sequence '{name}' step ids must be 1..{len(steps)}, got {[s.id for s in steps]}"
        )
    if steps[0].subject is None:
        raise SequenceError(f"sequence '{name}' step 1 must define a subject")
    if steps[0].delay_business_days != 0:
        raise SequenceError(f"sequence '{name}' step 1 must have delay_business_days: 0")

    return Sequence(
        name=name,
        steps=steps,
        stop_on_reply=bool(raw.get("stop_on_reply", True)),
        description=str(raw.get("description", "")),
    )


def load_all(directory: str | Path) -> dict[str, Sequence]:
    directory = Path(directory)
    if not directory.exists():
        return {}
    sequences: dict[str, Sequence] = {}
    for path in sorted(directory.glob("*.y*ml")):
        sequence = load_sequence(path)
        sequences[sequence.name] = sequence
    return sequences
