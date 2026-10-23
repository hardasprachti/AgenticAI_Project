"""The analysed sample for a run: sanitized.json joined with themes.json.

Only those two files are read. The raw Play Store cache (which carries reviewer names) is never
touched, and `store` is dropped from every row.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from api.files import read_json
from api.safe_paths import RunNotFound, safe_run_dir
from api.schemas import ReviewPage, ReviewRow, ReviewSummary, ThemeBucket, WeekBucket
from api.settings import Settings

_CACHE_LIMIT = 16
_cache: dict[tuple, tuple[ReviewRow, ...]] = {}
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class ReviewFilters:
    themes: list[str] = field(default_factory=list)
    ratings: list[int] = field(default_factory=list)
    review_ids: list[str] = field(default_factory=list)
    q: str | None = None


def _stamp(path: Path) -> tuple[int, int] | None:
    """Change marker for the cache key: mtime plus size, in case a rewrite lands in one tick."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _rating(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _theme_by_review(themes: Any) -> dict[str, str]:
    assignments = themes.get("assignments") if isinstance(themes, dict) else None
    mapping: dict[str, str] = {}
    for item in assignments if isinstance(assignments, list) else []:
        if (
            isinstance(item, dict)
            and isinstance(item.get("review_id"), str)
            and isinstance(item.get("theme_id"), str)
        ):
            mapping[item["review_id"]] = item["theme_id"]
    return mapping


def _load_rows(folder: Path) -> tuple[ReviewRow, ...]:
    sanitized_path, themes_path = folder / "sanitized.json", folder / "themes.json"
    key = (str(sanitized_path), _stamp(sanitized_path), _stamp(themes_path))
    with _cache_lock:
        if key in _cache:
            return _cache[key]

    reviews, _ = read_json(sanitized_path)
    themes, _ = read_json(themes_path)
    theme_for = _theme_by_review(themes)
    rows = []
    for item in reviews if isinstance(reviews, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("review_id"), str):
            continue
        rows.append(
            ReviewRow(
                review_id=item["review_id"],
                rating=_rating(item.get("rating")),
                title=_text(item.get("title")),
                text=_text(item.get("text")),
                date=_optional_text(item.get("date")),
                app_version=_optional_text(item.get("app_version")),
                theme_id=theme_for.get(item["review_id"]),
            )
        )
    result = tuple(rows)

    with _cache_lock:
        if len(_cache) >= _CACHE_LIMIT:
            _cache.pop(next(iter(_cache)))
        _cache[key] = result
    return result


def _run_folder(settings: Settings, run_id: str) -> Path:
    folder = safe_run_dir(settings, run_id)
    if not folder.is_dir():
        raise RunNotFound(run_id)
    return folder


def _matches(row: ReviewRow, filters: ReviewFilters) -> bool:
    if filters.themes and row.theme_id not in filters.themes:
        return False
    if filters.ratings and row.rating not in filters.ratings:
        return False
    if filters.review_ids and row.review_id not in filters.review_ids:
        return False
    if filters.q:
        needle = filters.q.casefold()
        if needle not in row.title.casefold() and needle not in row.text.casefold():
            return False
    return True


def get_reviews(
    settings: Settings, run_id: str, filters: ReviewFilters, page: int, page_size: int
) -> ReviewPage:
    rows = [r for r in _load_rows(_run_folder(settings, run_id)) if _matches(r, filters)]
    start = (page - 1) * page_size
    return ReviewPage(
        items=rows[start : start + page_size], total=len(rows), page=page, page_size=page_size
    )


def _average(ratings: list[int]) -> float | None:
    return round(sum(ratings) / len(ratings), 3) if ratings else None


def _week_start(day: str | None) -> str | None:
    try:
        parsed = date.fromisoformat(day) if day else None
    except ValueError:
        return None
    return (parsed - timedelta(days=parsed.weekday())).isoformat() if parsed else None


def get_summary(settings: Settings, run_id: str) -> ReviewSummary:
    rows = _load_rows(_run_folder(settings, run_id))
    rating_counts = {str(n): 0 for n in range(1, 6)}
    weekly: dict[str, list[ReviewRow]] = defaultdict(list)
    by_theme: dict[str | None, list[ReviewRow]] = defaultdict(list)
    for row in rows:
        if row.rating is not None and str(row.rating) in rating_counts:
            rating_counts[str(row.rating)] += 1
        if (week := _week_start(row.date)) is not None:
            weekly[week].append(row)
        by_theme[row.theme_id].append(row)

    def stats(group: list[ReviewRow]) -> tuple[int, float | None]:
        return len(group), _average([r.rating for r in group if r.rating is not None])

    return ReviewSummary(
        total=len(rows),
        rating=rating_counts,
        weekly=[
            WeekBucket(week_start=week, count=stats(group)[0], avg_rating=stats(group)[1])
            for week, group in sorted(weekly.items())
        ],
        by_theme=[
            ThemeBucket(theme_id=theme, count=stats(group)[0], avg_rating=stats(group)[1])
            for theme, group in sorted(by_theme.items(), key=lambda kv: (kv[0] is None, kv[0]))
        ],
    )
