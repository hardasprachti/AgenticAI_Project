import json
from datetime import UTC, datetime

from pulse.models import Pulse, Run, RunStatus, StageRecord, to_jsonable


def _roundtrip(obj):
    return json.loads(json.dumps(to_jsonable(obj)))


def test_pulse_survives_a_json_round_trip(valid_pulse):
    valid_pulse.analysed_count = 5
    assert Pulse.from_json(_roundtrip(valid_pulse)) == valid_pulse


def test_run_survives_a_json_round_trip():
    run = Run(
        run_id="20261019-101500",
        week_label="2026-W43",
        status=RunStatus.PARTIAL,
        started_at=datetime(2026, 10, 19, 10, 15, tzinfo=UTC),
        stages=[StageRecord("ingest", 1.5, {"fetched": 10}, ["a note"])],
        theme_scores={"kyc": {"score": 0.5}},
        prompt_versions={"compose": "compose@1"},
        retries=1,
        violations=["v"],
        word_count=200,
        llm_usage={"compose": {"calls": 1}},
        doc_id="d",
        doc_url="u",
        doc_revision_id="rev",
        draft_id="dr",
    )
    assert Run.from_json(_roundtrip(run)) == run


def test_run_status_round_trips_as_an_enum():
    run = Run.from_json(_roundtrip(Run(run_id="r", week_label="w", status=RunStatus.FAILED)))
    assert run.status is RunStatus.FAILED
    assert run.started_at is None
