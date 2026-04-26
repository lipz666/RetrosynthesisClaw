"""Route scoring helpers."""

from __future__ import annotations

from typing import Iterable

from .types import RetrosynthesisStep


def score_steps(steps: Iterable[RetrosynthesisStep]) -> float:
    steps = list(steps)
    if not steps:
        return 0.0
    return round(sum(step.confidence for step in steps) / len(steps), 4)
