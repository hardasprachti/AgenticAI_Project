"""The pipeline driven by PlayStoreSource, using the fixture reviews served as Play-shaped pages."""

import csv
import dataclasses
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from fakes import scripted_llm
from pulse.config import load_config
from pulse.models import RawReview, RunStatus
from pulse.pipeline import run_pipeline, sample_reviews
from pulse.sanitize import sanitize_reviews
from pulse.sources.play_store import Page, PlayStoreSource

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "evals" / "fixtures" / "reviews.csv"
AS_OF = date(2026, 10, 19)
PAGE = 50


def fixture_items() -> list[dict]:
    """Fixture rows in the shape the library returns, newest first."""
    with FIXTURE.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    items = [
        {
            "reviewId": r["review_id"],
            "userName": r["author_name"],
            "userImage": f"https://example.invalid/{r['author_id']}",
            "content": r["text"],
            "score": int(r["rating"]),
            "at": datetime.fromisoformat(r["date"]) + timedelta(hours=9),
            "reviewCreatedVersion": r["app_version"],
            "replyContent": None,
        }
        for r in rows
    ]
    return sorted(items, key=lambda i: i["at"], reverse=True)


def served(items: list[dict]):
    pages = [items[i : i + PAGE] for i in range(0, len(items), PAGE)]

    def fetch(cursor):
        index = 0 if cursor is None else int(cursor)
        more = str(index + 1) if index + 1 < len(pages) else None
        return Page(items=pages[index], next=more)

    return fetch


def play_source(items=None, **kwargs):
    params = {"delay_s": 0.0, "sleep": lambda s: None, **kwargs}
    return PlayStoreSource("com.example.app", fetch_page=served(items or fixture_items()), **params)


@pytest.fixture
def config(tmp_path):
    cfg = load_config(REPO_ROOT / "config.yaml")
    return dataclasses.replace(cfg, data_dir=tmp_path / "data", prompts_dir=REPO_ROOT / "prompts")


def run(config, source=None, **kwargs):
    return run_pipeline(
        source=source or play_source(),
        config=config,
        llm=scripted_llm(),
        as_of=AS_OF,
        cache_raw=True,
        **kwargs,
    )


def stage(result, name):
    return next(s for s in result.run.stages if s.name == name)


def test_full_dry_run_from_the_play_source_passes_the_guardrails(config):
    result = run(config)
    assert result.run.status is RunStatus.COMPLETED
    assert len(result.pulse.themes) == len(result.pulse.quotes) == len(result.pulse.actions) == 3
    assert result.run.word_count <= 250


def test_ingest_records_how_the_fetch_went(config):
    counts = stage(run(config), "ingest").counts
    assert counts["pages"] >= 2 and counts["window_start_reached"] == 1
    assert counts["fetched"] == counts["kept"] and counts["truncated"] == 0


def test_fetched_reviews_fall_inside_the_configured_window(config):
    result = run(config)
    sanitized = json.loads((result.run_dir / "sanitized.json").read_text(encoding="utf-8"))
    since = AS_OF - timedelta(weeks=config.window_weeks)
    days = [date.fromisoformat(r["date"]) for r in sanitized]
    assert since <= min(days) and max(days) <= AS_OF
    assert (result.pulse.window_start, result.pulse.window_end) == (since, AS_OF)


def test_reviewer_identity_reaches_neither_the_run_directory_nor_the_note(config):
    result = run(config)
    names = {i["userName"] for i in fixture_items()}
    for path in result.run_dir.iterdir():
        text = path.read_text(encoding="utf-8")
        assert not [n for n in names if n in text], f"{path.name} contains a reviewer name"
        assert "example.invalid" not in text  # avatar URLs are dropped at the source


def test_raw_cache_is_written_outside_the_run_directory_and_never_read_back(config):
    result = run(config)
    cache = config.data_dir / "raw" / result.run.run_id / "reviews.json"
    assert cache.is_file()
    assert not (result.run_dir / "reviews.json").exists()
    assert "raw cache" in " ".join(stage(result, "ingest").notes)


def test_raw_cache_is_off_unless_requested(config):
    run_pipeline(
        source=play_source(), config=config, llm=scripted_llm(), as_of=AS_OF, cache_raw=False
    )
    assert not (config.data_dir / "raw").exists()


# --- very large volume ---


def test_large_window_is_sampled_and_the_note_says_so(config):
    small = dataclasses.replace(config, max_analysed=120)
    result = run(small)
    sanitized = json.loads((result.run_dir / "sanitized.json").read_text(encoding="utf-8"))
    assert len(sanitized) == 120
    sanitize_counts = stage(result, "sanitize").counts
    assert sanitize_counts["analysed"] == 120 and sanitize_counts["clean"] > 120
    assert result.pulse.review_count == sanitize_counts["clean"]
    assert result.pulse.analysed_count == 120
    header = result.note.splitlines()[1]
    assert "(120 analysed)" in header and f"{sanitize_counts['clean']:,}" in header


def test_a_small_window_is_not_described_as_sampled(config):
    result = run(config)
    assert "analysed" not in result.note


def test_the_same_window_always_gives_the_same_sample(config, tmp_path):
    small = dataclasses.replace(config, max_analysed=120)
    first = run(small)
    second = run(dataclasses.replace(small, data_dir=tmp_path / "other"))
    ids = lambda r: [x["review_id"] for x in json.loads((r.run_dir / "sanitized.json").read_text())]  # noqa: E731
    assert ids(first) == ids(second)


def test_sample_is_chronological_and_independent_of_input_order():
    raw = [
        RawReview(
            "play",
            f"r{i}",
            3,
            "",
            f"review number {i} with enough words",
            date(2026, 9, 1 + i % 20),
        )
        for i in range(200)
    ]
    reviews = sanitize_reviews(raw).reviews
    sample = sample_reviews(reviews, 50)
    assert len(sample) == 50
    assert [r.date for r in sample] == sorted(r.date for r in sample)
    shuffled = sample_reviews(list(reversed(reviews)), 50)
    assert {r.review_id for r in shuffled} == {r.review_id for r in sample}


def test_sample_leaves_small_sets_untouched():
    reviews = sanitize_reviews(
        [RawReview("play", "a", 3, "", "enough words in this one", date(2026, 9, 1))]
    ).reviews
    assert sample_reviews(reviews, 10) == reviews


# --- short reviews ---


def test_content_free_reviews_are_dropped_before_sampling(config):
    items = fixture_items()
    filler = [
        {
            "reviewId": f"short-{n}",
            "userName": "Q R",
            "content": text,
            "score": 4,
            "at": datetime(2026, 10, 1, 12, n),
        }
        for n, text in enumerate(["good app", "nice", "very bad app", "worst"] * 5)
    ]
    items = sorted(items + filler, key=lambda i: i["at"], reverse=True)
    result = run(config, play_source(items))
    sanitize = stage(result, "sanitize").counts
    assert sanitize["dropped_short"] >= len(filler) - 4  # 4 distinct texts survive dedupe checks
    sanitized = json.loads((result.run_dir / "sanitized.json").read_text(encoding="utf-8"))
    assert all(len(r["text"].split()) >= config.min_words for r in sanitized)


def test_min_words_applies_to_the_sanitizer():
    raw = [
        RawReview("play", "a", 1, "", "good app", date(2026, 9, 1)),
        RawReview("play", "b", 1, "", "app keeps crashing today", date(2026, 9, 1)),
    ]
    result = sanitize_reviews(raw, min_words=4)
    assert [r.text for r in result.reviews] == ["app keeps crashing today"]
    assert result.stats.dropped_short == 1


# --- edge cases ---


def test_empty_window_fails_the_run_with_a_clear_reason(config):
    old = [dict(i, at=i["at"] - timedelta(days=400)) for i in fixture_items()]
    result = run(config, play_source(old))
    assert result.run.status is RunStatus.FAILED
    assert "No reviews were found" in result.run.violations[0]
    assert result.pulse is None


def test_incomplete_coverage_is_recorded_not_hidden(config):
    result = run(config, play_source(max_pages=2))
    notes = " ".join(stage(result, "ingest").notes)
    assert "never reached the start of the window" in notes
    assert stage(result, "ingest").counts["truncated"] == 1
    assert result.run.status is RunStatus.COMPLETED  # a partial window still yields a note
