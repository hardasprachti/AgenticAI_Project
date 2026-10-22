from datetime import date

import pytest

from pulse.config import RankingConfig
from pulse.models import Review, Theme, ThemeAssignment
from pulse.ranking import InsufficientThemes, rank_themes, top_themes

AS_OF = date(2026, 10, 19)
WEIGHTS = RankingConfig(volume=0.5, recency=0.2, severity=0.3, recency_window_weeks=2)
THEMES = [Theme(t, t.title()) for t in ("a", "b", "c", "d", "other")]


def _data(spec):
    """spec: list of (theme_id, rating, date). Returns reviews and assignments."""
    reviews, assignments = [], []
    for i, (theme, rating, day) in enumerate(spec):
        rid = f"r{i}"
        reviews.append(Review(rid, "play", rating, "", "text", day))
        assignments.append(ThemeAssignment(rid, theme))
    return reviews, assignments


OLD, NEW = date(2026, 9, 1), date(2026, 10, 15)


def _rank(spec, themes=THEMES):
    reviews, assignments = _data(spec)
    return rank_themes(reviews, assignments, themes, WEIGHTS, AS_OF)


def test_components_are_computed_and_exposed():
    ranked = _rank([("a", 1, NEW), ("a", 3, OLD), ("b", 5, OLD), ("b", 5, OLD)])
    a = next(t for t in ranked if t.theme_id == "a")
    assert a.review_count == 2 and a.share == 0.5
    assert a.components["volume"] == 0.5
    assert a.components["recency"] == 1.0  # the only recent review is in theme a
    assert a.components["severity"] == pytest.approx(1 - (2 - 1) / 4)
    assert a.avg_rating == 2
    assert a.score == pytest.approx(0.5 * 0.5 + 0.2 * 1.0 + 0.3 * 0.75)


def test_volume_dominates_with_default_weights():
    spec = [("a", 3, OLD)] * 6 + [("b", 3, OLD)] * 2
    assert [t.theme_id for t in _rank(spec)] == ["a", "b"]


def test_low_ratings_lift_a_smaller_theme_above_a_larger_cheerful_one():
    spec = [("a", 5, OLD)] * 5 + [("b", 1, OLD)] * 4
    assert _rank(spec)[0].theme_id == "b"


def test_recent_surge_lifts_a_theme():
    spec = [("a", 3, OLD)] * 4 + [("b", 3, OLD)] * 3 + [("b", 3, NEW)] * 2
    assert _rank(spec)[0].theme_id == "b"


def test_recency_is_zero_for_all_when_nothing_is_recent():
    ranked = _rank([("a", 3, OLD), ("b", 3, OLD)])
    assert all(t.components["recency"] == 0.0 for t in ranked)


def test_ties_break_deterministically_by_count_then_label():
    ranked = _rank([("b", 3, OLD), ("a", 3, OLD)])
    assert [t.theme_id for t in ranked] == ["a", "b"]


def test_themes_without_reviews_are_skipped():
    assert [t.theme_id for t in _rank([("a", 3, OLD)])] == ["a"]


def test_no_reviews_rejected():
    with pytest.raises(ValueError, match="No reviews"):
        rank_themes([], [], THEMES, WEIGHTS, AS_OF)


def test_top_three_excludes_other_even_when_it_ranks_first():
    spec = (
        [("other", 1, NEW)] * 10
        + [("a", 3, OLD)] * 3
        + [("b", 3, OLD)] * 2
        + [("c", 3, OLD)] * 2
        + [("d", 3, OLD)]
    )
    ranked = _rank(spec)
    assert ranked[0].theme_id == "other"
    assert [t.theme_id for t in top_themes(ranked)] == ["a", "b", "c"]


def test_other_fills_a_shortfall():
    ranked = _rank([("a", 3, OLD), ("b", 3, OLD), ("other", 3, OLD)])
    assert [t.theme_id for t in top_themes(ranked)] == ["a", "b", "other"]


def test_too_few_themes_raises():
    with pytest.raises(InsufficientThemes):
        top_themes(_rank([("a", 3, OLD), ("b", 3, OLD)]))
