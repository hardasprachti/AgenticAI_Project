"""Normalization and sanitization: the PII boundary (architecture section 4.2).

`sanitize_reviews` turns `RawReview`s (which carry reviewer identity) into `Review`s (which cannot).
Identity is removed twice over: by omission (the `Review` type has no author fields) and by
scrubbing (free text is cleaned of emails, phone numbers, ids, URLs and the author's own name).
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from pulse.models import RawReview, Review
from pulse.pii import REDACTED, scrub, strip_placeholders

# Salt for anonymous review ids. Ids only need to be stable across runs (for the theme assignment
# cache) and unlinkable to the store's own ids; they are not secrets. Override via the `salt` arg.
DEFAULT_SALT = "groww-pulse-v1"

DEFAULT_MIN_CHARS = 10
DEFAULT_LATIN_THRESHOLD = 0.8
MIN_AUTHOR_NAME_CHARS = 3
MIN_NAME_TOKEN_CHARS = 3

# Play shows these for reviewers without a public name; they are not worth scrubbing from text.
_GENERIC_AUTHORS = {"a google user", "google user", "anonymous", "user"}

# Words that appear in display names but are also ordinary words; never scrubbed as names.
_NOT_NAME_WORDS = frozenset(
    "the and for you your app not but are can has had was its all any new old one two user users "
    "google play groww guest customer client trader investor account official".split()
)

_NAME_TOKEN_RE = re.compile(rf"[^\W\d_]{{{MIN_NAME_TOKEN_CHARS},}}")
_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[\W_]+")


@dataclass
class SanitizeStats:
    fetched: int = 0
    kept: int = 0
    dropped_invalid: int = 0
    dropped_short: int = 0
    dropped_non_english: int = 0
    dropped_duplicate: int = 0
    redactions: Counter[str] = field(default_factory=Counter)

    def as_counts(self) -> dict[str, int]:
        counts = {
            "fetched": self.fetched,
            "kept": self.kept,
            "dropped_invalid": self.dropped_invalid,
            "dropped_short": self.dropped_short,
            "dropped_non_english": self.dropped_non_english,
            "dropped_duplicate": self.dropped_duplicate,
        }
        counts.update({f"redacted_{k}": v for k, v in sorted(self.redactions.items())})
        return counts


@dataclass
class SanitizeResult:
    reviews: list[Review]
    stats: SanitizeStats
    # Author names seen in the raw data, kept in memory only so `validate` can confirm none of
    # them reached the final note. Never persist or log this field.
    known_author_names: frozenset[str] = field(default_factory=frozenset, repr=False)


def anonymous_review_id(store: str, store_review_id: str, salt: str = DEFAULT_SALT) -> str:
    digest = hashlib.sha256(f"{salt}|{store}|{store_review_id}".encode()).hexdigest()
    return digest[:16]


def _collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _author_pattern(name: str | None) -> re.Pattern[str] | None:
    """Matches the reviewer's full name, or any single word of it, as a whole word.

    Reviews often sign off or refer to themselves by first name only, so each name word of
    `MIN_NAME_TOKEN_CHARS` or more letters is scrubbed too. The full name is tried first so
    "Asha Rao" becomes one placeholder, not two. Common words are never treated as names, which
    keeps a display name like "The Trader" from redacting every "the".
    """
    if not name:
        return None
    name = _collapse_ws(name)
    if len(name) < MIN_AUTHOR_NAME_CHARS or name.casefold() in _GENERIC_AUTHORS:
        return None
    tokens = {t for t in _NAME_TOKEN_RE.findall(name) if t.casefold() not in _NOT_NAME_WORDS}
    alternatives = [name, *sorted(tokens, key=lambda t: (-len(t), t))]
    joined = "|".join(re.escape(a) for a in alternatives)
    return re.compile(rf"(?<!\w)(?:{joined})(?!\w)", re.IGNORECASE)


def _latin_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    # Basic Latin through Latin Extended-B covers English and romanized Hindi (Hinglish).
    return sum(1 for c in letters if ord(c) < 0x250) / len(letters)


def _dedupe_key(title: str, text: str) -> str:
    return _NON_ALNUM_RE.sub("", f"{title} {text}".casefold())


def _clean_field(value: str, author: re.Pattern[str] | None, redactions: Counter[str]) -> str:
    value = _collapse_ws(value or "")
    if author is not None:
        value, n = author.subn(REDACTED, value)
        if n:
            redactions["author_name"] += n
    value, counts = scrub(value)
    redactions.update(counts)
    return value


def sanitize_reviews(
    raw_reviews: Iterable[RawReview],
    *,
    salt: str = DEFAULT_SALT,
    min_chars: int = DEFAULT_MIN_CHARS,
    latin_threshold: float = DEFAULT_LATIN_THRESHOLD,
) -> SanitizeResult:
    """Sanitize reviews. Output is sorted by (date, review_id) so runs are deterministic."""
    stats = SanitizeStats()
    author_names: set[str] = set()
    candidates: list[Review] = []

    for raw in raw_reviews:
        stats.fetched += 1

        if not isinstance(raw.rating, int) or not 1 <= raw.rating <= 5 or raw.date is None:
            stats.dropped_invalid += 1
            continue

        author = _author_pattern(raw.author_name)
        if author is not None:
            author_names.add(_collapse_ws(raw.author_name or ""))

        title = _clean_field(raw.title, author, stats.redactions)
        text = _clean_field(raw.text, author, stats.redactions)
        combined = strip_placeholders(f"{title} {text}").strip()

        if len(combined) < min_chars:
            stats.dropped_short += 1
            continue
        if _latin_ratio(combined) < latin_threshold:
            stats.dropped_non_english += 1
            continue

        candidates.append(
            Review(
                review_id=anonymous_review_id(raw.store, raw.store_review_id, salt),
                store=raw.store,
                rating=raw.rating,
                title=title,
                text=text,
                date=raw.date,
                app_version=raw.app_version,
            )
        )

    # Sort first so "keep the earliest copy" is deterministic, then dedupe by id and by content.
    candidates.sort(key=lambda r: (r.date, r.review_id))
    seen_ids: set[str] = set()
    seen_content: set[str] = set()
    kept: list[Review] = []
    for review in candidates:
        key = _dedupe_key(review.title, review.text)
        if review.review_id in seen_ids or key in seen_content:
            stats.dropped_duplicate += 1
            continue
        seen_ids.add(review.review_id)
        seen_content.add(key)
        kept.append(review)

    stats.kept = len(kept)
    return SanitizeResult(reviews=kept, stats=stats, known_author_names=frozenset(author_names))
