"""Ranking: choose the top themes for the note (architecture section 4.4).

    score = w_volume * share_of_reviews + w_recency * share_of_recent_reviews
          + w_severity * (1 - normalized_avg_rating)

All three components are in [0, 1] and are returned with the score so the run record can explain
every ranking. "Other" is a catch-all bucket, so it only appears in the top set if there are not
enough real themes to fill it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from pulse.config import RankingConfig
from pulse.models import Review, Theme, ThemeAssignment
from pulse.theming import OTHER, theme_id_for

TOP_N = 3


class InsufficientThemes(ValueError):
    """Fewer distinct themes than the pulse needs."""


@dataclass(frozen=True)
class RankedTheme:
    theme: Theme
    review_count: int
    share: float  # review_count / all reviews in the window
    avg_rating: float
    score: float
    components: dict[str, float]  # volume, recency, severity (raw, 0..1)

    @property
    def theme_id(self) -> str:
        return self.theme.theme_id


def rank_themes(
    reviews: Sequence[Review],
    assignments: Sequence[ThemeAssignment],
    themes: Sequence[Theme],
    weights: RankingConfig,
    as_of: date,
) -> list[RankedTheme]:
    """All themes, best first. Ties break on review count, then label, so output is stable."""
    if not reviews:
        raise ValueError("No reviews to rank")
    theme_of = {a.review_id: a.theme_id for a in assignments}
    recent_from = as_of - timedelta(weeks=weights.recency_window_weeks)

    by_theme: dict[str, list[Review]] = defaultdict(list)
    for review in reviews:
        by_theme[theme_of[review.review_id]].append(review)
    total = len(reviews)
    total_recent = sum(1 for r in reviews if r.date > recent_from)

    ranked: list[RankedTheme] = []
    for theme in themes:
        members = by_theme.get(theme.theme_id, [])
        if not members:
            continue
        count = len(members)
        avg = sum(r.rating for r in members) / count
        volume = count / total
        recent = sum(1 for r in members if r.date > recent_from)
        recency = recent / total_recent if total_recent else 0.0
        severity = 1 - (avg - 1) / 4  # 1-star average -> 1.0, 5-star average -> 0.0
        score = weights.volume * volume + weights.recency * recency + weights.severity * severity
        ranked.append(
            RankedTheme(
                theme=theme,
                review_count=count,
                share=volume,
                avg_rating=avg,
                score=score,
                components={"volume": volume, "recency": recency, "severity": severity},
            )
        )
    ranked.sort(key=lambda t: (-t.score, -t.review_count, t.theme.label))
    return ranked


def top_themes(ranked: Sequence[RankedTheme], n: int = TOP_N) -> list[RankedTheme]:
    """The top `n`, with "Other" only used to fill a shortfall."""
    other_id = theme_id_for(OTHER)
    real = [t for t in ranked if t.theme_id != other_id]
    chosen = real[:n]
    if len(chosen) < n:
        chosen += [t for t in ranked if t.theme_id == other_id][: n - len(chosen)]
    if len(chosen) < n:
        raise InsufficientThemes(f"Need {n} themes but the reviews only form {len(chosen)}")
    return chosen
