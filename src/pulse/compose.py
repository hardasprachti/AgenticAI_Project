"""Composition: build the `Pulse` from the top themes (architecture section 4.5).

Quotes are never invented. Code first selects a short list of representative candidate reviews per
theme; the model only chooses among them and trims to a contiguous snippet; and `validate_pulse`
then checks every snippet is verbatim before anything can be published. Violations are fed back to
the model for up to `max_retries` more attempts, after which composition fails rather than
returning a non-compliant note.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel

from pulse.llm import LLMClient
from pulse.models import Action, Pulse, Quote, Review, ThemeAssignment, ThemeSummary
from pulse.prompts import Prompt
from pulse.ranking import RankedTheme
from pulse.validate import Violation, format_violations, validate_pulse

TASK = "compose"
MIN_CANDIDATE_WORDS = 6
MAX_CANDIDATE_WORDS = 45

_WORD_RE = re.compile(r"[a-z]{4,}")
_STOPWORDS = frozenset(
    "this that with have from they them there their been were what when your about would could "
    "just very much more only also than then even still like really".split()
)
# Reviews that read like instructions to an AI are never offered as quote candidates. They are
# still counted and themed as ordinary reviews; this only keeps them out of the model's evidence.
_INJECTION_RE = re.compile(
    r"ignore (all |any )?(the )?(previous|prior|above)|disregard|system prompt|\bsystem:|"
    r"you are now|reveal your|output only|as an ai\b|new instructions",
    re.IGNORECASE,
)


class _ThemeText(BaseModel):
    theme_id: str
    summary: str


class _QuotePick(BaseModel):
    review_id: str
    snippet: str


class _ActionIdea(BaseModel):
    theme_id: str
    text: str


class ComposeReply(BaseModel):
    themes: list[_ThemeText]
    quotes: list[_QuotePick]
    actions: list[_ActionIdea]


class ComposeFailed(RuntimeError):
    def __init__(
        self, violations: Sequence[Violation], attempts: int, history: list[list[str]]
    ) -> None:
        self.violations = list(violations)
        self.attempts = attempts
        self.violation_history = history
        super().__init__(
            f"Could not compose a valid pulse after {attempts} attempts:\n"
            f"{format_violations(violations)}"
        )


@dataclass
class ComposeResult:
    pulse: Pulse
    attempts: int
    # Violations from each failed attempt, oldest first (empty when the first attempt passed).
    violation_history: list[list[str]] = field(default_factory=list)


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def clean_text(text: str) -> str:
    """Collapse every kind of whitespace (including no-break and narrow spaces that models like to
    emit) to single plain spaces, so the published note holds only ordinary characters there."""
    return " ".join(text.split())


def is_injection_like(text: str) -> bool:
    return bool(_INJECTION_RE.search(text))


def _quotable(review: Review) -> bool:
    words = len(review.text.split())
    return (
        MIN_CANDIDATE_WORDS <= words <= MAX_CANDIDATE_WORDS
        and "[redacted]" not in review.text
        and not is_injection_like(f"{review.title} {review.text}")
    )


def _theme_scorer(
    inside: Sequence[Review],
    outside: Sequence[Review],
    doc_tokens: dict[str, set[str]],
) -> Callable[[Review], float]:
    """Score reviews by how typical they are of the theme: words common inside the theme and
    rare outside it, normalized for length, plus a small bonus for a clear (non-3-star) rating."""
    inside_df = Counter(t for r in inside for t in doc_tokens[r.review_id])
    outside_df = Counter(t for r in outside for t in doc_tokens[r.review_id])
    n_in, n_out = max(len(inside), 1), max(len(outside), 1)

    def score(review: Review) -> float:
        tokens = doc_tokens[review.review_id]
        if not tokens:
            return 0.0
        typical = sum((inside_df[t] / n_in) * (1 - outside_df[t] / n_out) for t in tokens)
        return typical / math.sqrt(len(tokens)) + 0.05 * abs(review.rating - 3)

    return score


def select_candidates(
    reviews: Sequence[Review],
    assignments: Sequence[ThemeAssignment],
    top: Sequence[RankedTheme],
    per_theme: int,
) -> dict[str, list[Review]]:
    """Representative, quotable reviews per top theme.

    Quotable means moderate length, no redaction placeholder, and nothing that reads like an
    instruction to an AI. Candidates are the most theme-typical of those, de-duplicated by text.
    Everything is deterministic, so reruns offer the model the same candidates.
    """
    theme_of = {a.review_id: a.theme_id for a in assignments}
    doc_tokens = {r.review_id: _tokens(f"{r.title} {r.text}") for r in reviews}

    out: dict[str, list[Review]] = {}
    for ranked in top:
        inside = [r for r in reviews if theme_of[r.review_id] == ranked.theme_id]
        outside = [r for r in reviews if theme_of[r.review_id] != ranked.theme_id]
        score = _theme_scorer(inside, outside, doc_tokens)

        seen: set[str] = set()
        picked: list[Review] = []
        for review in sorted(filter(_quotable, inside), key=lambda r: (-score(r), r.review_id)):
            key = " ".join(review.text.lower().split())
            if key in seen:
                continue
            seen.add(key)
            picked.append(review)
            if len(picked) == per_theme:
                break
        out[ranked.theme_id] = picked
    return out


def _themes_payload(top: Sequence[RankedTheme]) -> str:
    return json.dumps(
        [
            {
                "theme_id": t.theme_id,
                "label": t.theme.label,
                "review_count": t.review_count,
                "share_percent": round(t.share * 100),
                "average_rating": round(t.avg_rating, 1),
            }
            for t in top
        ],
        indent=1,
    )


def _candidates_payload(candidates: dict[str, list[Review]]) -> str:
    return json.dumps(
        {
            theme_id: [
                {"review_id": r.review_id, "rating": r.rating, "text": r.text} for r in reviews
            ]
            for theme_id, reviews in candidates.items()
        },
        ensure_ascii=False,
        indent=1,
    )


def build_pulse(
    reply: ComposeReply,
    *,
    top: Sequence[RankedTheme],
    reviews: Sequence[Review],
    assignments: Sequence[ThemeAssignment],
    week_label: str,
    window_start: date,
    window_end: date,
) -> Pulse:
    """Assemble a `Pulse` from the model's reply. Ratings and quote themes come from the data,
    not the model; anything the model got wrong is left as-is for `validate_pulse` to report."""
    by_id = {r.review_id: r for r in reviews}
    theme_of = {a.review_id: a.theme_id for a in assignments}
    order = {t.theme_id: i for i, t in enumerate(top)}
    summaries = {t.theme_id: clean_text(t.summary) for t in reply.themes}

    quotes = []
    for pick in reply.quotes:
        review = by_id.get(pick.review_id)
        quotes.append(
            Quote(
                text=clean_text(pick.snippet),
                theme_id=theme_of.get(pick.review_id, "") if review else "",
                rating=review.rating if review else 0,
                review_id=pick.review_id,
            )
        )
    quotes.sort(key=lambda q: order.get(q.theme_id, len(order)))

    actions = sorted(
        (Action(text=clean_text(a.text), theme_id=a.theme_id) for a in reply.actions),
        key=lambda a: order.get(a.theme_id, len(order)),
    )
    return Pulse(
        week_label=week_label,
        window_start=window_start,
        window_end=window_end,
        review_count=len(reviews),
        themes=[
            ThemeSummary(t.theme_id, t.theme.label, summaries.get(t.theme_id, ""), t.share)
            for t in top
        ],
        quotes=quotes,
        actions=actions,
    )


def _feedback_block(violations: Iterable[Violation] | None) -> str:
    if not violations:
        return ""
    return (
        "\nYour previous reply was rejected by automatic checks. Fix every problem below "
        "and reply again with the full JSON object:\n" + format_violations(violations) + "\n"
    )


def compose_pulse(
    *,
    llm: LLMClient,
    prompt: Prompt,
    top: Sequence[RankedTheme],
    reviews: Sequence[Review],
    assignments: Sequence[ThemeAssignment],
    week_label: str,
    window_start: date,
    window_end: date,
    candidates_per_theme: int = 5,
    max_retries: int = 2,
    max_words: int = 250,
    known_author_names: Iterable[str] = (),
) -> ComposeResult:
    candidates = select_candidates(reviews, assignments, top, candidates_per_theme)
    themes_json = _themes_payload(top)
    candidates_json = _candidates_payload(candidates)
    names = frozenset(known_author_names)

    history: list[list[str]] = []
    violations: list[Violation] = []
    for attempt in range(1, max_retries + 2):
        system, user = prompt.render(
            themes=themes_json, candidates=candidates_json, feedback=_feedback_block(violations)
        )
        reply = llm.complete_json(task=TASK, system=system, user=user, schema=ComposeReply)
        pulse = build_pulse(
            reply,
            top=top,
            reviews=reviews,
            assignments=assignments,
            week_label=week_label,
            window_start=window_start,
            window_end=window_end,
        )
        violations = validate_pulse(pulse, reviews, max_words=max_words, known_author_names=names)
        if not violations:
            return ComposeResult(pulse=pulse, attempts=attempt, violation_history=history)
        history.append([str(v) for v in violations])

    raise ComposeFailed(violations, attempts=max_retries + 1, history=history)
