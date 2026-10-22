"""Domain models (architecture section 5).

PII boundary: `RawReview` is the only type that carries reviewer identity. It lives in ingestion
and sanitization and must never be persisted or passed on. `Review` has no field for it, so
nothing downstream can leak what it never received.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RawReview:
    """A review as returned by a source. Contains reviewer identity. Ingestion-only."""

    store: str
    store_review_id: str
    rating: int
    title: str
    text: str
    date: date
    app_version: str | None = None
    author_name: str | None = None
    author_id: str | None = None

    def __repr__(self) -> str:
        # Keep identity and free text out of logs and tracebacks.
        return f"RawReview(store={self.store!r}, rating={self.rating}, date={self.date})"


@dataclass(frozen=True)
class Review:
    """A sanitized review. No reviewer identity, anonymous id, scrubbed text."""

    review_id: str
    store: str
    rating: int
    title: str
    text: str
    date: date
    app_version: str | None = None


@dataclass(frozen=True)
class Theme:
    theme_id: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class ThemeAssignment:
    review_id: str
    theme_id: str


@dataclass(frozen=True)
class ThemeSummary:
    """One of the top themes highlighted in the pulse."""

    theme_id: str
    label: str
    summary: str
    share: float  # fraction of reviews in the window, 0.0 to 1.0


@dataclass(frozen=True)
class Quote:
    """A verbatim snippet of a sanitized review."""

    text: str
    theme_id: str
    rating: int
    review_id: str


@dataclass(frozen=True)
class Action:
    text: str
    theme_id: str


@dataclass
class Pulse:
    week_label: str  # ISO week, e.g. "2026-W42"
    window_start: date
    window_end: date
    review_count: int
    themes: list[ThemeSummary]
    quotes: list[Quote]
    actions: list[Action]


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED_VALIDATION = "failed_validation"  # nothing published
    PARTIAL = "partial"  # note appended to the Doc, draft failed
    FAILED = "failed"


@dataclass
class StageRecord:
    name: str
    duration_s: float = 0.0
    counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class Run:
    """Record of one pipeline run. Must contain no PII."""

    run_id: str
    week_label: str
    status: RunStatus = RunStatus.RUNNING
    started_at: datetime | None = None
    stages: list[StageRecord] = field(default_factory=list)
    theme_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    prompt_versions: dict[str, str] = field(default_factory=dict)
    retries: int = 0
    violations: list[str] = field(default_factory=list)
    word_count: int = 0
    llm_usage: dict[str, dict[str, int]] = field(default_factory=dict)
    doc_id: str | None = None
    doc_url: str | None = None
    doc_revision_id: str | None = None
    draft_id: str | None = None


def to_jsonable(obj: Any) -> Any:
    """Convert models (dataclasses, dates, enums, paths) to JSON-serializable values."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]
    return obj
