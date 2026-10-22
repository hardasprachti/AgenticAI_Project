"""LLM-as-judge (architecture section 8.3). Advisory only: scores are recorded and trended, but a
low score never fails a run. Only the deterministic checks can do that."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, Field

from evals.checks import Artifacts
from pulse.llm import LLMClient
from pulse.prompts import Prompt

TASK = "judge"
SAMPLES_PER_THEME = 4
SAMPLE_CHARS = 300
CRITERIA = ("actionability", "faithfulness", "scannability")


class _Score(BaseModel):
    score: int = Field(ge=1, le=5)
    reason: str


class JudgeReply(BaseModel):
    actionability: _Score
    faithfulness: _Score
    scannability: _Score


@dataclass(frozen=True)
class JudgeResult:
    scores: dict[str, int]
    reasons: dict[str, str]
    prompt_version: str

    @property
    def mean(self) -> float:
        return sum(self.scores.values()) / len(self.scores)


def _evidence(a: Artifacts) -> str:
    """Reviews supporting each theme in the note: first the reviews the note quotes (so the judge
    can check quotes against their source), then a few more samples of the same theme."""
    theme_of = {x["review_id"]: x["theme_id"] for x in a.themes["assignments"]}
    quoted = {q["review_id"] for q in a.pulse["quotes"]}
    ordered = sorted(a.sanitized, key=lambda r: (r["review_id"] not in quoted, r["review_id"]))

    by_theme: dict[str, list[dict]] = {t["theme_id"]: [] for t in a.pulse["themes"]}
    for review in ordered:
        bucket = by_theme.get(theme_of.get(review["review_id"], ""))
        if bucket is not None and len(bucket) < SAMPLES_PER_THEME:
            bucket.append({"rating": review["rating"], "text": review["text"][:SAMPLE_CHARS]})
    labels = {t["theme_id"]: t["label"] for t in a.pulse["themes"]}
    return json.dumps(
        {labels[t]: samples for t, samples in by_theme.items()}, ensure_ascii=False, indent=1
    )


def judge_pulse(llm: LLMClient, prompt: Prompt, a: Artifacts) -> JudgeResult | None:
    """Score the run's note, or None if the run produced no note."""
    if a.pulse is None or a.note is None:
        return None
    system, user = prompt.render(note=a.note, evidence=_evidence(a))
    reply = llm.complete_json(task=TASK, system=system, user=user, schema=JudgeReply)
    return JudgeResult(
        scores={c: getattr(reply, c).score for c in CRITERIA},
        reasons={c: getattr(reply, c).reason for c in CRITERIA},
        prompt_version=prompt.version,
    )
