"""Offline tests for the golden-run harness: no network, no model."""

import json
from pathlib import Path

import pytest

from evals.checks import CheckResult
from evals.run_golden import (
    BASELINE_PATH,
    DEGRADED_DIR,
    build_prompts_dir,
    format_table,
    load_thresholds,
)
from pulse.prompts import PromptError, load_prompt

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_prompts_dir_is_a_copy_of_the_real_prompts(tmp_path):
    build_prompts_dir(tmp_path, REPO_ROOT / "prompts", degrade=[])
    assert {p.name for p in tmp_path.glob("*.md")} == {
        p.name for p in (REPO_ROOT / "prompts").glob("*.md")
    }
    assert load_prompt("theme_assign", tmp_path).version == "theme_assign@1"


def test_degrading_swaps_only_the_named_prompt(tmp_path):
    build_prompts_dir(tmp_path, REPO_ROOT / "prompts", degrade=["theme_assign"])
    assert load_prompt("theme_assign", tmp_path).version == "theme_assign@0"
    assert load_prompt("compose", tmp_path).version == "compose@1"


def test_unknown_degraded_prompt_is_rejected(tmp_path):
    with pytest.raises(PromptError, match="No degraded prompt"):
        build_prompts_dir(tmp_path, REPO_ROOT / "prompts", degrade=["nonexistent"])


def test_every_degraded_prompt_is_marked_and_loadable():
    files = list(DEGRADED_DIR.glob("*.md"))
    assert files
    for path in files:
        assert "DEGRADED on purpose" in path.read_text(encoding="utf-8")
        assert load_prompt(path.stem, DEGRADED_DIR).version.endswith("@0")


def test_degraded_prompts_keep_the_real_placeholders():
    """A degraded prompt must still render, or the run would fail for the wrong reason."""
    for path in DEGRADED_DIR.glob("*.md"):
        real = load_prompt(path.stem, REPO_ROOT / "prompts")
        degraded = load_prompt(path.stem, DEGRADED_DIR)
        assert degraded.user == real.user


def test_thresholds_file_is_sane():
    thresholds = load_thresholds(config_max_words=250, config_max_themes=5)
    assert 0.5 < thresholds.theme_agreement_min <= 1.0
    assert (thresholds.max_words, thresholds.max_themes) == (250, 5)


def test_table_shows_pass_and_fail():
    table = format_table(
        [
            CheckResult("length", True, "171 words", "<= 250 words"),
            CheckResult("quote_fidelity", False, "67%", "100% verbatim"),
        ]
    )
    lines = table.splitlines()
    assert lines[0].split()[:2] == ["check", "measured"] or "check" in lines[0]
    assert any(line.startswith("PASS") and "length" in line for line in lines)
    assert any(line.startswith("FAIL") and "quote_fidelity" in line for line in lines)


def test_committed_baseline_is_a_passing_run_on_the_current_prompts():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert baseline["passed"] and not baseline["degraded"]
    assert all(c["passed"] for c in baseline["checks"])
    current = {
        name: load_prompt(name, REPO_ROOT / "prompts").version
        for name in ("theme_assign", "compose")
    }
    assert baseline["prompt_versions"] == current, (
        "a prompt changed since the baseline was recorded: re-run evals/run_golden.py and "
        "save a new baseline with --save-baseline"
    )
