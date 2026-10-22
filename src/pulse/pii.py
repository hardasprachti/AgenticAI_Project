"""Deterministic PII detection and scrubbing (architecture sections 4.2 and 4.6).

Used twice: `sanitize` scrubs review text on the way in, and `validate` re-scans the final rendered
note on the way out. The same patterns on both sides keep the two checks consistent.

These are heuristics tuned for an Indian investing app. They are a deterministic first line of
defence, not a guarantee; the final-text scan and seeded-PII evals are the backstops.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

REDACTED = "[redacted]"

# Order matters: more specific / longer patterns first so a later pattern cannot split an earlier
# match (e.g. the domain of an email must not be matched as a bare URL).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Emails and UPI ids (name@bank has no dot, so the TLD part is optional).
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*")),
    ("url", re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)),
    (
        "url",
        re.compile(
            r"(?<![\w@.])[\w-]+(?:\.[\w-]+)*\.(?:com|in|co|net|org|io|app|me|ly)\b(?:/\S*)?",
            re.IGNORECASE,
        ),
    ),
    (
        "uuid",
        re.compile(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b"),
    ),
    # Indian PAN: 5 letters, 4 digits, 1 letter.
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    # Phone, Aadhaar, card and account numbers: 9+ digits with at most two separator characters
    # between digits. Dates like 2026-07-28 (8 digits) and ranges like "28 - 2026" do not match.
    ("number", re.compile(r"(?<![\w+])\+?\d(?:[\s().-]{0,2}\d){8,}(?!\w)")),
    # Long mixed letter+digit tokens: order ids, device ids, reference numbers.
    (
        "id_token",
        re.compile(r"\b(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{12,}\b"),
    ),
    ("handle", re.compile(r"(?<!\w)@\w{3,}")),
]

_REDACTED_RE = re.compile(re.escape(REDACTED))


@dataclass(frozen=True)
class PiiMatch:
    kind: str
    text: str


def scrub(text: str) -> tuple[str, Counter[str]]:
    """Replace PII in `text` with `[redacted]`. Returns the new text and counts by kind."""
    counts: Counter[str] = Counter()
    for kind, pattern in _PATTERNS:
        text, n = pattern.subn(REDACTED, text)
        if n:
            counts[kind] += n
    return text, counts


def find_pii(text: str) -> list[PiiMatch]:
    """Report PII still present in `text`. Existing `[redacted]` placeholders are ignored."""
    masked = _REDACTED_RE.sub(" ", text)
    found: list[PiiMatch] = []
    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(masked):
            found.append(PiiMatch(kind, m.group(0)))
    return found


def strip_placeholders(text: str) -> str:
    """Text with `[redacted]` placeholders removed, for length and language checks."""
    return _REDACTED_RE.sub(" ", text)
