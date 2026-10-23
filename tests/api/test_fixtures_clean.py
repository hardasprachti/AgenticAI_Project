"""The committed web fixtures are real-run files with no identity in them (Task 8).

`web/fixtures` is what mock mode and the web tests read. It must hold only the files the API
serves, the review rows must carry exactly the allow-listed keys, and nothing that looks like an
email address or a phone number may survive in any review text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "web" / "fixtures"
RUNS = FIXTURES / "runs"

REVIEW_KEYS = {"review_id", "store", "rating", "title", "text", "date", "app_version"}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")
SUCCESS_RUN = "20261022-121514"
FAILED_RUN = "20261022-151338"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _fixture_reviews() -> list[tuple[str, dict]]:
    return [
        (run_dir.name, review)
        for run_dir in sorted(RUNS.iterdir())
        for review in _load(run_dir / "sanitized.json")
    ]


def test_fixtures_exist():
    assert (RUNS / SUCCESS_RUN / "run.json").is_file()
    assert (RUNS / FAILED_RUN / "run.json").is_file()
    assert (FIXTURES / "config.json").is_file()
    assert (FIXTURES / "ledger.json").is_file()
    assert (FIXTURES / "README.md").is_file()


def test_run_folders_hold_only_the_expected_files():
    assert {p.name for p in (RUNS / SUCCESS_RUN).iterdir()} == {
        "run.json",
        "pulse.json",
        "note.txt",
        "ranking.json",
        "themes.json",
        "sanitized.json",
    }
    assert {p.name for p in (RUNS / FAILED_RUN).iterdir()} == {"run.json", "sanitized.json"}


def test_reviews_have_exactly_the_allowed_keys():
    reviews = _fixture_reviews()
    assert len(reviews) > 100
    for run_id, review in reviews:
        assert set(review) == REVIEW_KEYS, (run_id, review["review_id"])


def test_sample_is_trimmed_to_150_reviews():
    for run_id in (SUCCESS_RUN, FAILED_RUN):
        assert len(_load(RUNS / run_id / "sanitized.json")) == 150


def test_no_email_or_phone_in_review_text():
    for run_id, review in _fixture_reviews():
        for field in ("title", "text"):
            assert not EMAIL_RE.search(review[field]), (run_id, review["review_id"], field)
            assert not PHONE_RE.search(review[field]), (run_id, review["review_id"], field)


def test_no_raw_path_anywhere_in_fixtures():
    for path in (p for p in FIXTURES.rglob("*") if p.is_file()):
        assert "raw" not in {part.lower() for part in path.relative_to(FIXTURES).parts}
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"data[\\/]+raw", text), path
        assert "raw cache" not in text, path


def test_run_json_fixtures_have_no_author_key():
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert "author" not in key.lower() or key.startswith("redacted_"), key
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for run_dir in RUNS.iterdir():
        walk(_load(run_dir / "run.json"))


def test_pulse_quotes_appear_verbatim_in_fixture_sample():
    pulse = _load(RUNS / SUCCESS_RUN / "pulse.json")
    by_id = {r["review_id"]: r for r in _load(RUNS / SUCCESS_RUN / "sanitized.json")}
    assert len(pulse["quotes"]) == 3
    for quote in pulse["quotes"]:
        review = by_id[quote["review_id"]]
        assert _normalize(quote["text"]) in _normalize(review["text"])


def test_theme_assignments_match_the_trimmed_sample():
    ids = {r["review_id"] for r in _load(RUNS / SUCCESS_RUN / "sanitized.json")}
    themes = _load(RUNS / SUCCESS_RUN / "themes.json")
    assert {a["review_id"] for a in themes["assignments"]} == ids
    assert {t["theme_id"] for t in themes["themes"]} >= {
        a["theme_id"] for a in themes["assignments"]
    }


def test_fixture_run_records_are_the_real_ones():
    run = _load(RUNS / SUCCESS_RUN / "run.json")
    assert run["status"] == "completed" and run["doc_url"] is None
    assert run["stages"][1]["counts"]["clean"] == 3029
    failed = _load(RUNS / FAILED_RUN / "run.json")
    assert failed["status"] == "failed" and failed["stages"][-1]["counts"] == {}


def test_config_fixture_is_the_allow_listed_view_with_placeholder_addresses():
    from api.routes import build_config_view
    from api.settings import Settings

    from pulse.config import DEFAULT_CONFIG_PATH

    settings = Settings.load(REPO_ROOT / DEFAULT_CONFIG_PATH)
    expected = build_config_view(settings).model_dump()
    fixture = _load(FIXTURES / "config.json")
    # The real recipient and Google Doc id are personal; the fixture carries placeholders.
    assert fixture.pop("draft_to") == "product-leads@example.com"
    assert fixture.pop("doc_url") == "https://docs.google.com/document/d/EXAMPLE_DOCUMENT_ID/edit"
    expected.pop("draft_to")
    expected.pop("doc_url")
    assert fixture == expected
    text = (FIXTURES / "config.json").read_text(encoding="utf-8")
    assert settings.config.mcp.document_id not in text
    assert settings.config.draft_to not in text


def test_ledger_fixture_is_synthetic_and_in_the_real_format():
    ledger = _load(FIXTURES / "ledger.json")
    allowed = {
        "state", "run_id", "document_id", "revision_id", "characters_appended",
        "draft_id", "thread_id", "subject", "confirmed_by_hand",
    }  # fmt: skip
    states = set()
    for week, steps in ledger.items():
        assert re.fullmatch(r"\d{4}-W\d{2}", week)
        assert set(steps) <= {"doc", "draft"}
        for step in steps.values():
            assert set(step) <= allowed
            states.add(step["state"])
    assert "pending" in states, "mock mode needs a pending step so the banner is visible"
    assert "synthetic" in (FIXTURES / "README.md").read_text(encoding="utf-8").lower()


@pytest.mark.parametrize("name", ["config.json", "ledger.json"])
def test_top_level_fixtures_parse(name):
    assert isinstance(_load(FIXTURES / name), dict)
