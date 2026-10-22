"""The deterministic eval suite (architecture 8.1) as pytest, runnable offline and in CI.

A pipeline run with scripted model replies must pass every check; then each check is shown to be
able to fail by corrupting a copy of the run directory in exactly the way it guards against.
"""

import dataclasses
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from evals.checks import Artifacts, Thresholds, run_checks
from evals.golden import GoldenSet
from fakes import scripted_llm
from pulse.config import load_config
from pulse.pipeline import run_pipeline
from pulse.sources.csv_source import CsvSource

REPO_ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 19)
THRESHOLDS = Thresholds(theme_agreement_min=0.85)


@pytest.fixture(scope="module")
def golden():
    return GoldenSet.load()


@pytest.fixture(scope="module")
def good_run(tmp_path_factory):
    config = dataclasses.replace(
        load_config(REPO_ROOT / "config.yaml"),
        data_dir=tmp_path_factory.mktemp("data"),
        prompts_dir=REPO_ROOT / "prompts",
    )
    result = run_pipeline(
        source=CsvSource(REPO_ROOT / "evals" / "fixtures" / "reviews.csv"),
        config=config,
        llm=scripted_llm(),
        as_of=AS_OF,
    )
    return result.run_dir


@pytest.fixture
def run_copy(good_run, tmp_path):
    """A private, editable copy of the good run directory."""
    target = tmp_path / "run"
    shutil.copytree(good_run, target)
    return target


def outcome(run_dir: Path, golden: GoldenSet, thresholds=THRESHOLDS) -> dict[str, bool]:
    results = run_checks(Artifacts.load(run_dir), golden, thresholds)
    return {c.name: c.passed for c in results}


def edit_json(path: Path, change) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def edit_note(run_dir: Path, change) -> None:
    path = run_dir / "note.txt"
    path.write_text(change(path.read_text(encoding="utf-8")), encoding="utf-8")


def only_failure(results: dict[str, bool]) -> set[str]:
    return {name for name, passed in results.items() if not passed}


# --- a healthy run passes everything ---


def test_healthy_run_passes_every_check(good_run, golden):
    results = outcome(good_run, golden)
    assert set(results) == {
        "run_completed",
        "theme_cap",
        "exactly_three",
        "quote_fidelity",
        "length",
        "pii_leakage",
        "injection_resistance",
        "action_groundedness",
        "theme_agreement",
    }
    assert only_failure(results) == set()


# --- each check can fail ---


def test_failed_run_is_caught(run_copy, golden):
    edit_json(run_copy / "run.json", lambda d: d.update(status="failed_validation"))
    assert "run_completed" in only_failure(outcome(run_copy, golden))


def test_sixth_named_theme_breaks_the_cap(run_copy, golden):
    def add(d):
        d["themes"].append({"theme_id": "extra", "label": "Extra", "description": ""})

    edit_json(run_copy / "themes.json", add)
    assert "theme_cap" in only_failure(outcome(run_copy, golden))


def test_other_does_not_count_toward_the_cap(run_copy, golden):
    # The healthy run already has five named themes plus Other; the cap check must still pass.
    themes = json.loads((run_copy / "themes.json").read_text(encoding="utf-8"))["themes"]
    assert any(t["theme_id"] == "other" for t in themes)
    assert "theme_cap" not in only_failure(outcome(run_copy, golden))


@pytest.mark.parametrize("section", ["themes", "quotes", "actions"])
def test_wrong_counts_are_caught(run_copy, golden, section):
    edit_json(run_copy / "pulse.json", lambda d: d[section].pop())
    assert "exactly_three" in only_failure(outcome(run_copy, golden))


def test_invented_quote_is_caught(run_copy, golden):
    edit_json(
        run_copy / "pulse.json",
        lambda d: d["quotes"][0].update(text="a sentence no reviewer ever wrote"),
    )
    assert "quote_fidelity" in only_failure(outcome(run_copy, golden))


def test_quote_citing_a_missing_review_is_caught(run_copy, golden):
    edit_json(run_copy / "pulse.json", lambda d: d["quotes"][0].update(review_id="nope"))
    assert "quote_fidelity" in only_failure(outcome(run_copy, golden))


def test_quote_case_and_spacing_differences_are_still_verbatim(run_copy, golden):
    def shout(d):
        d["quotes"][0]["text"] = "  " + d["quotes"][0]["text"].upper().replace(" ", "  ") + " "

    edit_json(run_copy / "pulse.json", shout)
    assert "quote_fidelity" not in only_failure(outcome(run_copy, golden))


def test_over_length_note_is_caught(run_copy, golden):
    edit_note(run_copy, lambda text: text + " word" * 200)
    assert "length" in only_failure(outcome(run_copy, golden))


def test_missing_note_is_caught(run_copy, golden):
    (run_copy / "note.txt").unlink()
    assert "length" in only_failure(outcome(run_copy, golden))


@pytest.mark.parametrize("leak", ["author_id", "author_name", "first_name", "email", "phone"])
def test_seeded_pii_in_any_artifact_is_caught(run_copy, golden, leak):
    row = next(r for r in golden.rows if r["author_name"] and r["author_id"])
    pii_rows = [r for r in golden.rows if "@example.com" in r["text"]]
    phone_rows = [r for r in golden.rows if r["text"].count("98") and "Call me on" in r["text"]]
    value = {
        "author_id": row["author_id"],
        "author_name": row["author_name"],
        "first_name": row["author_name"].split()[0],
        "email": pii_rows[0]["text"].split("mail me at ")[1].split(" about")[0],
        "phone": phone_rows[0]["text"].split("Call me on ")[1].split(" to resolve")[0],
    }[leak]
    # Leak it into a file other than the note: the check covers the whole run directory.
    edit_json(run_copy / "run.json", lambda d: d.update(note_to_self=f"contact {value}"))
    assert "pii_leakage" in only_failure(outcome(run_copy, golden))


def test_innocent_text_does_not_trip_the_pii_check(run_copy, golden):
    edit_note(run_copy, lambda text: text + "\nNothing personal here: 3 days, 12 reviews.")
    assert "pii_leakage" not in only_failure(outcome(run_copy, golden))


def test_quoting_an_injection_review_is_caught(run_copy, golden):
    injected_id = sorted(golden.injected_review_ids)[0]
    edit_json(run_copy / "pulse.json", lambda d: d["quotes"][0].update(review_id=injected_id))
    assert "injection_resistance" in only_failure(outcome(run_copy, golden))


def test_echoing_injected_text_into_the_note_is_caught(run_copy, golden):
    echoed = " ".join(golden.injected_texts()[0].split()[:8])
    edit_note(run_copy, lambda text: text + f"\n{echoed}")
    assert "injection_resistance" in only_failure(outcome(run_copy, golden))


def test_injection_that_changes_the_structure_is_caught(run_copy, golden):
    edit_json(run_copy / "pulse.json", lambda d: d.update(actions=[], quotes=[]))
    failed = only_failure(outcome(run_copy, golden))
    assert {"injection_resistance", "exactly_three"} <= failed


def test_action_tied_to_a_non_top_theme_is_caught(run_copy, golden):
    edit_json(run_copy / "pulse.json", lambda d: d["actions"][0].update(theme_id="billing"))
    assert "action_groundedness" in only_failure(outcome(run_copy, golden))


def test_action_unrelated_to_its_reviews_is_caught(run_copy, golden):
    text = "Launch a loyalty programme with seasonal discounts for premium subscribers."
    edit_json(run_copy / "pulse.json", lambda d: d["actions"][0].update(text=text))
    assert "action_groundedness" in only_failure(outcome(run_copy, golden))


def test_scrambled_theme_assignments_are_caught(run_copy, golden):
    def rotate(d):
        ids = [t["theme_id"] for t in d["themes"]]
        shift = {a: b for a, b in zip(ids, ids[1:] + ids[:1], strict=True)}
        for item in d["assignments"]:
            item["theme_id"] = shift[item["theme_id"]]

    edit_json(run_copy / "themes.json", rotate)
    assert "theme_agreement" in only_failure(outcome(run_copy, golden))


def test_agreement_threshold_is_enforced(good_run, golden):
    strict = Thresholds(theme_agreement_min=0.999)
    assert "theme_agreement" in only_failure(outcome(good_run, golden, strict))


# --- the golden set itself ---


def test_golden_set_covers_what_the_evals_rely_on(golden):
    assert len(golden.rows) > 300
    assert golden.injected_review_ids
    assert any("@" in s for s in golden.seeded_pii_strings)
    assert golden.seeded_name_words
    assert set(golden.labels.values()) >= {
        "kyc",
        "pay",
        "perf",
        "stmt",
        "support",
        "other",
        "injection",
        "dropped",
        "out_of_window",
    }


def test_theme_agreement_counts_only_labeled_reviews(golden):
    expected = golden.expected_theme_ids
    some = next(iter(expected))
    right = golden.theme_agreement([{"review_id": some, "theme_id": expected[some]}])
    wrong = golden.theme_agreement([{"review_id": some, "theme_id": "nonsense"}])
    unlabeled = golden.theme_agreement([{"review_id": "not-in-fixture", "theme_id": "x"}])
    assert (right.accuracy, wrong.accuracy) == (1.0, 0.0)
    assert unlabeled.evaluated == 0 and unlabeled.accuracy == 0.0


def test_domain_acronyms_count_as_grounding(run_copy, golden):
    """KYC and UPI are 3 letters but are exactly what an action should be grounded in."""
    edit_json(
        run_copy / "pulse.json",
        lambda d: d["actions"][0].update(
            theme_id="onboarding-and-kyc",
            text="Show KYC verification status and the expected completion date.",
        ),
    )
    assert "action_groundedness" not in only_failure(outcome(run_copy, golden))


def test_ordinary_short_words_alone_do_not_ground_an_action(run_copy, golden):
    edit_json(
        run_copy / "pulse.json",
        lambda d: d["actions"][0].update(
            theme_id="onboarding-and-kyc", text="Add one for all with the new plan."
        ),
    )
    assert "action_groundedness" in only_failure(outcome(run_copy, golden))
