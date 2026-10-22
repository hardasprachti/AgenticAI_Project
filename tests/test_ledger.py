import json

import pytest

from pulse.mcp.ledger import Ledger, LedgerError, Step, StepState


def test_an_empty_ledger_reports_every_step_pending_nothing(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    assert ledger.state("2026-W43", Step.DOC) is StepState.NONE
    assert ledger.state("2026-W43", Step.DRAFT) is StepState.NONE


def test_pending_is_on_disk_before_the_call_and_done_replaces_it(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = Ledger(path)

    ledger.mark_pending("2026-W43", Step.DOC, run_id="r1")
    # A second process (or the rerun after a crash) sees the pending mark.
    assert Ledger(path).state("2026-W43", Step.DOC) is StepState.PENDING

    ledger.mark_done("2026-W43", Step.DOC, revision_id="rev-1", characters_appended=10)
    reread = Ledger(path)
    assert reread.state("2026-W43", Step.DOC) is StepState.DONE
    entry = reread.entry("2026-W43", Step.DOC)
    assert entry["revision_id"] == "rev-1" and entry["run_id"] == "r1"


def test_weeks_and_steps_are_independent(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.mark_pending("2026-W43", Step.DOC, run_id="r1")
    ledger.mark_done("2026-W43", Step.DOC)

    assert ledger.state("2026-W43", Step.DRAFT) is StepState.NONE
    assert ledger.state("2026-W44", Step.DOC) is StepState.NONE


def test_clear_removes_one_step_only(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = Ledger(path)
    ledger.mark_pending("2026-W43", Step.DOC, run_id="r1")
    ledger.mark_done("2026-W43", Step.DOC)
    ledger.mark_pending("2026-W43", Step.DRAFT, run_id="r1")

    ledger.clear("2026-W43", Step.DRAFT)

    reread = Ledger(path)
    assert reread.state("2026-W43", Step.DRAFT) is StepState.NONE
    assert reread.state("2026-W43", Step.DOC) is StepState.DONE


def test_marking_done_without_a_pending_mark_is_a_bug(tmp_path):
    with pytest.raises(LedgerError, match="pending"):
        Ledger(tmp_path / "ledger.json").mark_done("2026-W43", Step.DOC)


def test_pending_over_a_done_step_is_refused(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.mark_pending("2026-W43", Step.DOC, run_id="r1")
    ledger.mark_done("2026-W43", Step.DOC)

    with pytest.raises(LedgerError, match="already"):
        ledger.mark_pending("2026-W43", Step.DOC, run_id="r2")


def test_a_corrupt_ledger_is_an_error_not_an_empty_ledger(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(LedgerError, match="not valid"):
        Ledger(path).state("2026-W43", Step.DOC)


def test_the_file_is_readable_json_keyed_by_week(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = Ledger(path)
    ledger.mark_pending("2026-W43", Step.DRAFT, run_id="r1")
    ledger.mark_done("2026-W43", Step.DRAFT, draft_id="d-1")

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["2026-W43"]["draft"]["state"] == "created"
    assert data["2026-W43"]["draft"]["draft_id"] == "d-1"


def test_done_state_names_follow_the_plan(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.mark_pending("w", Step.DOC, run_id="r")
    ledger.mark_done("w", Step.DOC)
    on_disk = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert on_disk["w"]["doc"]["state"] == "appended"  # plan: doc is pending | appended


def test_a_second_writer_cannot_take_over_a_pending_step(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.mark_pending("2026-W43", Step.DOC, run_id="r1")

    with pytest.raises(LedgerError, match="pending"):
        ledger.mark_pending("2026-W43", Step.DOC, run_id="r2")
    assert ledger.entry("2026-W43", Step.DOC)["run_id"] == "r1"
