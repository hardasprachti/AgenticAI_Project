"""Theming: group reviews into at most `max_themes` themes (architecture section 4.3).

The model assigns each review to exactly one theme from a closed taxonomy, or to "Other". Code
owns everything around that call: unknown labels are mapped to "Other", reviews the model skipped
are re-asked once, results are cached by (review_id, taxonomy hash) so reruns do not flip a review
between themes, and the theme cap is enforced here regardless of what the model returned.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from pulse.llm import LLMClient
from pulse.models import Review, Theme, ThemeAssignment
from pulse.prompts import Prompt

OTHER = "Other"
OTHER_DESCRIPTION = "Reviews that do not fit a main theme"
TASK = "theme_assign"
MAX_FIELD_CHARS = 600  # per title/text, to bound prompt size


class _Item(BaseModel):
    review_id: str
    theme: str


class _Batch(BaseModel):
    assignments: list[_Item]


@dataclass
class ThemingStats:
    reviews: int = 0
    cache_hits: int = 0
    llm_calls: int = 0
    unknown_labels: int = 0  # model labels outside the taxonomy, mapped to Other
    missing_after_retry: int = 0  # reviews the model never labeled, mapped to Other
    merged_into_other: list[str] = field(default_factory=list)  # labels folded by the cap


@dataclass
class ThemingResult:
    themes: list[Theme]
    assignments: list[ThemeAssignment]
    stats: ThemingStats

    def counts(self) -> dict[str, int]:
        return dict(Counter(a.theme_id for a in self.assignments))


def theme_id_for(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def taxonomy_hash(taxonomy: Sequence[str], prompt_version: str, model: str) -> str:
    """Cache namespace: changing the taxonomy, prompt or model invalidates cached assignments."""
    payload = json.dumps([list(taxonomy), prompt_version, model], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class AssignmentCache:
    """Persistent `review_id -> label` cache for one taxonomy hash. In-memory if path is None."""

    def __init__(self, path: Path | None, namespace: str) -> None:
        self._path = path
        self._namespace = namespace
        self._data: dict[str, str] = {}
        if path is not None and path.is_file():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                stored = {}
            if stored.get("namespace") == namespace:
                self._data = dict(stored.get("labels", {}))

    def get(self, review_id: str) -> str | None:
        return self._data.get(review_id)

    def put_many(self, labels: dict[str, str]) -> None:
        self._data.update(labels)
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"namespace": self._namespace, "labels": self._data}
            self._path.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")


def _review_payload(review: Review) -> dict[str, object]:
    return {
        "review_id": review.review_id,
        "rating": review.rating,
        "title": review.title[:MAX_FIELD_CHARS],
        "text": review.text[:MAX_FIELD_CHARS],
    }


def _ask(
    llm: LLMClient,
    prompt: Prompt,
    taxonomy: Sequence[str],
    batch: Sequence[Review],
    stats: ThemingStats,
) -> dict[str, str]:
    """One model call. Returns `review_id -> canonical label` for ids in the batch only."""
    system, user = prompt.render(
        taxonomy="\n".join(f"- {label}" for label in taxonomy),
        reviews=json.dumps([_review_payload(r) for r in batch], ensure_ascii=False, indent=1),
    )
    reply = llm.complete_json(task=TASK, system=system, user=user, schema=_Batch)
    stats.llm_calls += 1

    canonical = {label.casefold(): label for label in taxonomy}
    wanted = {r.review_id for r in batch}
    labels: dict[str, str] = {}
    for item in reply.assignments:
        if item.review_id not in wanted or item.review_id in labels:
            continue
        label = canonical.get(item.theme.strip().casefold())
        if label is None:
            if item.theme.strip().casefold() != OTHER.casefold():
                stats.unknown_labels += 1
            label = OTHER
        labels[item.review_id] = label
    return labels


def enforce_theme_cap(
    labels: dict[str, str], max_themes: int, stats: ThemingStats | None = None
) -> dict[str, str]:
    """Fold the smallest themes into "Other" until at most `max_themes` distinct labels remain."""
    labels = dict(labels)
    while True:
        counts = Counter(labels.values())
        if len(counts) <= max_themes:
            return labels
        small_first = sorted((c, label) for label, c in counts.items() if label != OTHER)
        # With no "Other" yet, folding one theme would only rename it, so fold two to make progress.
        fold = [label for _, label in small_first[: 1 if OTHER in counts else 2]]
        for review_id, label in labels.items():
            if label in fold:
                labels[review_id] = OTHER
        if stats is not None:
            stats.merged_into_other.extend(fold)


def assign_themes(
    reviews: Sequence[Review],
    taxonomy: Sequence[str],
    *,
    llm: LLMClient,
    prompt: Prompt,
    model: str,
    batch_size: int,
    max_themes: int,
    cache: AssignmentCache | None = None,
) -> ThemingResult:
    if not reviews:
        raise ValueError("No reviews to theme")
    if OTHER.casefold() in {t.casefold() for t in taxonomy}:
        raise ValueError(f"'{OTHER}' is reserved and cannot be in the taxonomy")
    cache = cache or AssignmentCache(None, taxonomy_hash(taxonomy, prompt.version, model))
    stats = ThemingStats(reviews=len(reviews))

    labels: dict[str, str] = {}
    pending: list[Review] = []
    for review in reviews:
        cached = cache.get(review.review_id)
        if cached is None:
            pending.append(review)
        else:
            labels[review.review_id] = cached
            stats.cache_hits += 1

    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        got = _ask(llm, prompt, taxonomy, batch, stats)
        missing = [r for r in batch if r.review_id not in got]
        if missing:  # re-ask once, only for what was skipped
            got.update(_ask(llm, prompt, taxonomy, missing, stats))
        for review in batch:
            if review.review_id not in got:
                got[review.review_id] = OTHER
                stats.missing_after_retry += 1
        cache.put_many(got)
        labels.update(got)

    labels = enforce_theme_cap(labels, max_themes, stats)

    counts = Counter(labels.values())
    themes = [
        Theme(theme_id_for(label), label, OTHER_DESCRIPTION if label == OTHER else "")
        for label in [*taxonomy, OTHER]
        if counts.get(label)
    ]
    assignments = [ThemeAssignment(r.review_id, theme_id_for(labels[r.review_id])) for r in reviews]
    return ThemingResult(themes=themes, assignments=assignments, stats=stats)
