"""End-to-end dry run on the fixture set with scripted model replies (Phase 2 exit check)."""

import csv
import dataclasses
import json
from datetime import date
from pathlib import Path

import pytest

from fakes import candidates_in_prompt, scripted_llm, valid_compose_reply
from pulse.config import load_config
from pulse.models import RunStatus
from pulse.pii import find_pii
from pulse.pipeline import run_pipeline, week_label_for
from pulse.render import count_words
from pulse.sources.csv_source import CsvSource, CsvSourceError

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "evals" / "fixtures" / "reviews.csv"
AS_OF = date(2026, 10, 19)


@pytest.fixture
def config(tmp_path):
    cfg = load_config(REPO_ROOT / "config.yaml")
    return dataclasses.replace(cfg, data_dir=tmp_path / "data", prompts_dir=REPO_ROOT / "prompts")


def _run(config, llm=None, path=FIXTURE):
    return run_pipeline(
        source=CsvSource(path), config=config, llm=llm or scripted_llm(), as_of=AS_OF
    )


def test_dry_run_produces_a_note_that_passes_every_guardrail(config):
    result = _run(config)
    assert result.run.status is RunStatus.COMPLETED
    pulse = result.pulse
    assert len(pulse.themes) == 3 and len(pulse.quotes) == 3 and len(pulse.actions) == 3
    assert count_words(result.note) <= 250
    assert find_pii(result.note) == []
    assert result.run.week_label == "2026-W43" == week_label_for(AS_OF)

    themes = json.loads((result.run_dir / "themes.json").read_text(encoding="utf-8"))
    assert len(themes["themes"]) <= 5


def test_quotes_are_verbatim_substrings_of_sanitized_reviews(config):
    result = _run(config)
    sanitized = json.loads((result.run_dir / "sanitized.json").read_text(encoding="utf-8"))
    by_id = {r["review_id"]: f"{r['title']} {r['text']}".lower() for r in sanitized}
    for quote in result.pulse.quotes:
        assert quote.text.lower() in by_id[quote.review_id]


def test_run_directory_contains_every_stage_output(config):
    result = _run(config)
    names = {p.name for p in result.run_dir.iterdir()}
    assert {
        "sanitized.json",
        "themes.json",
        "ranking.json",
        "pulse.json",
        "note.txt",
        "run.json",
    } <= names
    assert (result.run_dir / "note.txt").read_text(encoding="utf-8") == result.note


def test_run_record_explains_the_run(config):
    run = json.loads((_run(config).run_dir / "run.json").read_text(encoding="utf-8"))
    assert run["status"] == "completed"
    assert run["prompt_versions"] == {"theme_assign": "theme_assign@1", "compose": "compose@1"}
    assert [s["name"] for s in run["stages"]] == [
        "ingest",
        "sanitize",
        "theme",
        "rank",
        "compose",
        "render",
    ]
    scores = run["theme_scores"]
    assert scores and all(
        {"volume", "recency", "severity", "score"} <= set(v) for v in scores.values()
    )
    sanitize = next(s for s in run["stages"] if s["name"] == "sanitize")
    assert sanitize["counts"]["kept"] < sanitize["counts"]["fetched"]
    assert run["word_count"] > 0


def test_no_reviewer_identity_in_any_file_the_run_writes(config):
    with FIXTURE.open(encoding="utf-8") as handle:
        identities = {
            value
            for row in csv.DictReader(handle)
            for value in (row["author_name"], row["author_id"])
            if value
        }
    result = _run(config)
    for path in result.run_dir.iterdir():
        text = path.read_text(encoding="utf-8")
        leaked = [i for i in identities if i in text]
        assert not leaked, f"{path.name} contains reviewer identity"
    cache = (config.data_dir / "cache" / "theme_assignments.json").read_text(encoding="utf-8")
    assert not [i for i in identities if i in cache]


def test_window_excludes_reviews_outside_it(config):
    result = _run(config)
    sanitize = next(s for s in result.run.stages if s.name == "sanitize")
    with FIXTURE.open(encoding="utf-8") as handle:
        total_rows = sum(1 for _ in csv.DictReader(handle))
    assert sanitize.counts["fetched"] < total_rows  # the out-of-window rows were not fetched


def test_injection_review_is_themed_but_never_offered_as_a_quote(config):
    llm = scripted_llm()
    result = _run(config, llm)
    sanitized = json.loads((result.run_dir / "sanitized.json").read_text(encoding="utf-8"))
    injected = {r["review_id"] for r in sanitized if "ignore all previous" in r["text"].lower()}
    assert injected  # the fixture's injection attempt survived sanitizing as an ordinary review
    for task, _, user in llm.calls:
        if task == "compose":
            offered = {c["review_id"] for v in candidates_in_prompt(user).values() for c in v}
            assert not offered & injected
    assert not {q.review_id for q in result.pulse.quotes} & injected


def test_second_run_reuses_the_theme_cache(config):
    first_llm, second_llm = scripted_llm(), scripted_llm()
    _run(config, first_llm)
    _run(config, second_llm)
    assert sum(t == "theme_assign" for t, _, _ in first_llm.calls) > 0
    assert sum(t == "theme_assign" for t, _, _ in second_llm.calls) == 0


def test_compose_that_never_validates_publishes_nothing(config):
    def bad(user):
        reply = valid_compose_reply(user)
        reply["quotes"][0]["snippet"] = "words that no reviewer ever wrote"
        return reply

    result = _run(config, scripted_llm(compose=bad))
    assert result.run.status is RunStatus.FAILED_VALIDATION
    assert result.pulse is None and result.note is None
    assert not (result.run_dir / "note.txt").exists()
    assert any("quote_not_verbatim" in v for v in result.run.violations)
    assert result.run.retries == config.compose.max_retries


def test_too_few_reviews_stops_the_run(config, tmp_path):
    small = tmp_path / "small.csv"
    with (
        FIXTURE.open(encoding="utf-8") as src,
        small.open("w", newline="", encoding="utf-8") as dst,
    ):
        rows = list(csv.reader(src))
        csv.writer(dst).writerows(rows[:11])
    result = _run(config, path=small)
    assert result.run.status is RunStatus.FAILED
    assert "usable reviews" in result.run.violations[0]
    assert result.pulse is None


def test_unexpected_error_is_recorded_then_raised(config):
    with pytest.raises(CsvSourceError):
        run_pipeline(
            source=CsvSource("missing.csv"), config=config, llm=scripted_llm(), as_of=AS_OF
        )
    run_dirs = list((config.data_dir / "runs").iterdir())
    record = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert record["status"] == "failed"
