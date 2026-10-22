"""Guardrails: every constraint from the problem statement, enforced in code (architecture 4.6).

Validation returns a list of structured `Violation`s instead of raising, so the composer can feed
the exact failures back to the model on retry, and the evals can assert on specific codes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from pulse.models import Pulse, Review, Theme
from pulse.pii import find_pii
from pulse.render import count_words, render_note

REQUIRED_THEMES = 3
REQUIRED_QUOTES = 3
REQUIRED_ACTIONS = 3
DEFAULT_MAX_WORDS = 250
DEFAULT_MAX_THEMES = 5
DEFAULT_MIN_QUOTE_WORDS = 3


class ViolationCode(StrEnum):
    THEME_CAP_EXCEEDED = "theme_cap_exceeded"
    THEME_COUNT = "theme_count"
    THEME_DUPLICATE = "theme_duplicate"
    THEME_SHARE_INVALID = "theme_share_invalid"
    THEME_SUMMARY_EMPTY = "theme_summary_empty"
    QUOTE_COUNT = "quote_count"
    QUOTE_TOO_SHORT = "quote_too_short"
    QUOTE_UNKNOWN_REVIEW = "quote_unknown_review"
    QUOTE_NOT_VERBATIM = "quote_not_verbatim"
    QUOTE_RATING_MISMATCH = "quote_rating_mismatch"
    QUOTE_DUPLICATE = "quote_duplicate"
    QUOTE_THEME_NOT_TOP = "quote_theme_not_top"
    ACTION_COUNT = "action_count"
    ACTION_EMPTY = "action_empty"
    ACTION_THEME_NOT_TOP = "action_theme_not_top"
    WORD_LIMIT = "word_limit"
    PII_DETECTED = "pii_detected"
    AUTHOR_NAME_LEAK = "author_name_leak"


@dataclass(frozen=True)
class Violation:
    code: ViolationCode
    message: str

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"


_WS_RE = re.compile(r"\s+")
_QUOTE_TRANSLATION = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', " ": " "})


def normalize_for_match(text: str) -> str:
    """Normalization for the verbatim check: case, whitespace and typographic quotes only."""
    return _WS_RE.sub(" ", text.translate(_QUOTE_TRANSLATION)).strip().casefold()


def format_violations(violations: Iterable[Violation]) -> str:
    """Feedback text for a compose retry."""
    return "\n".join(f"- {v}" for v in violations)


def validate_theme_cap(
    themes: Sequence[Theme], max_themes: int = DEFAULT_MAX_THEMES
) -> list[Violation]:
    """Clustering-stage check: at most `max_themes` themes."""
    if len(themes) > max_themes:
        return [
            Violation(
                ViolationCode.THEME_CAP_EXCEEDED,
                f"{len(themes)} themes, but at most {max_themes} are allowed",
            )
        ]
    return []


def validate_pulse(
    pulse: Pulse,
    reviews: Sequence[Review],
    *,
    max_words: int = DEFAULT_MAX_WORDS,
    min_quote_words: int = DEFAULT_MIN_QUOTE_WORDS,
    known_author_names: Iterable[str] = (),
) -> list[Violation]:
    """Check a composed pulse against every constraint. An empty list means it may be published."""
    violations: list[Violation] = []
    by_id = {r.review_id: r for r in reviews}
    top_ids = {t.theme_id for t in pulse.themes}

    # Themes: exactly the top 3, distinct, with sane shares.
    if len(pulse.themes) != REQUIRED_THEMES:
        violations.append(
            Violation(
                ViolationCode.THEME_COUNT,
                f"expected {REQUIRED_THEMES} top themes, got {len(pulse.themes)}",
            )
        )
    if len(top_ids) != len(pulse.themes):
        violations.append(Violation(ViolationCode.THEME_DUPLICATE, "top themes must be distinct"))
    for theme in pulse.themes:
        if not theme.summary.strip():
            violations.append(
                Violation(
                    ViolationCode.THEME_SUMMARY_EMPTY,
                    f"theme '{theme.label}' has no one-line summary",
                )
            )
        if not 0.0 <= theme.share <= 1.0:
            violations.append(
                Violation(
                    ViolationCode.THEME_SHARE_INVALID,
                    f"theme '{theme.label}' has share {theme.share}, expected 0.0 to 1.0",
                )
            )

    # Quotes: exactly 3, distinct, real, verbatim.
    if len(pulse.quotes) != REQUIRED_QUOTES:
        violations.append(
            Violation(
                ViolationCode.QUOTE_COUNT,
                f"expected {REQUIRED_QUOTES} quotes, got {len(pulse.quotes)}",
            )
        )
    seen_quotes: set[tuple[str, str]] = set()
    for i, quote in enumerate(pulse.quotes, start=1):
        normalized = normalize_for_match(quote.text)

        if len(normalized.split()) < min_quote_words:
            violations.append(
                Violation(
                    ViolationCode.QUOTE_TOO_SHORT,
                    f"quote {i} has fewer than {min_quote_words} words",
                )
            )

        key = (quote.review_id, normalized)
        if key in seen_quotes:
            violations.append(
                Violation(ViolationCode.QUOTE_DUPLICATE, f"quote {i} repeats an earlier quote")
            )
        seen_quotes.add(key)

        if quote.theme_id not in top_ids:
            violations.append(
                Violation(
                    ViolationCode.QUOTE_THEME_NOT_TOP,
                    f"quote {i} is tagged '{quote.theme_id}', which is not a top-3 theme",
                )
            )

        review = by_id.get(quote.review_id)
        if review is None:
            violations.append(
                Violation(
                    ViolationCode.QUOTE_UNKNOWN_REVIEW,
                    f"quote {i} cites review '{quote.review_id}', which is not in the dataset",
                )
            )
            continue

        if normalized and not any(
            normalized in normalize_for_match(source) for source in (review.title, review.text)
        ):
            violations.append(
                Violation(
                    ViolationCode.QUOTE_NOT_VERBATIM,
                    f"quote {i} is not a verbatim snippet of review '{quote.review_id}': "
                    f'"{quote.text}"',
                )
            )
        if quote.rating != review.rating:
            violations.append(
                Violation(
                    ViolationCode.QUOTE_RATING_MISMATCH,
                    f"quote {i} says {quote.rating} stars but the review has {review.rating}",
                )
            )

    # Actions: exactly 3, non-empty, tied to a top-3 theme.
    if len(pulse.actions) != REQUIRED_ACTIONS:
        violations.append(
            Violation(
                ViolationCode.ACTION_COUNT,
                f"expected {REQUIRED_ACTIONS} action ideas, got {len(pulse.actions)}",
            )
        )
    for i, action in enumerate(pulse.actions, start=1):
        if not action.text.strip():
            violations.append(Violation(ViolationCode.ACTION_EMPTY, f"action {i} is empty"))
        if action.theme_id not in top_ids:
            violations.append(
                Violation(
                    ViolationCode.ACTION_THEME_NOT_TOP,
                    f"action {i} is tied to '{action.theme_id}', which is not a top-3 theme",
                )
            )

    # The rendered note is what gets published, so length and PII are checked on that text.
    note = render_note(pulse)
    words = count_words(note)
    if words > max_words:
        violations.append(
            Violation(
                ViolationCode.WORD_LIMIT,
                f"note is {words} words, over the {max_words}-word limit by {words - max_words}",
            )
        )
    violations.extend(validate_text_pii(note, known_author_names))

    return violations


def validate_text_pii(text: str, known_author_names: Iterable[str] = ()) -> list[Violation]:
    """Scan final text for PII patterns and for any author name seen in the raw data."""
    violations: list[Violation] = []
    for match in find_pii(text):
        # Report the kind only; echoing the matched value would copy PII into logs.
        violations.append(
            Violation(ViolationCode.PII_DETECTED, f"possible {match.kind} found in the note")
        )

    lowered = text.casefold()
    for name in known_author_names:
        name = name.strip()
        if name and re.search(rf"(?<!\w){re.escape(name.casefold())}(?!\w)", lowered):
            violations.append(
                Violation(ViolationCode.AUTHOR_NAME_LEAK, "a reviewer's name appears in the note")
            )
    return violations
