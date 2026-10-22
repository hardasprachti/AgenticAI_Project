"""The orchestrator: stages 1-9, the publishing ledger, failure statuses and --resume (Phase 6)."""

import csv
import dataclasses
import json
from datetime import date
from pathlib import Path

import pytest

from fake_mcp import DOC_TOOL, DRAFT_TOOL, SEND_TOOL, FakeGoogleServer, make_config, no_sleep
from fakes import scripted_llm, valid_compose_reply
from pulse.config import load_config
from pulse.mcp.client import McpClient
from pulse.mcp.ledger import Ledger, Step, StepState
from pulse.models import RunStatus
from pulse.orchestrator import ManualCheckRequired, ResumeError, run_week
from pulse.sources.csv_source import CsvSource

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "evals" / "fixtures" / "reviews.csv"
AS_OF = date(2026, 10, 19)
WEEK = "2026-W43"
DRAFT_TO = "me@example.com"


class Killed(BaseException):
    """Stands in for the process dying: not an Exception, so nothing in the code under test may
    catch it and tidy up."""


@pytest.fixture
def config(tmp_path):
    cfg = load_config(REPO_ROOT / "config.yaml")
    return dataclasses.replace(
        cfg,
        data_dir=tmp_path / "data",
        prompts_dir=REPO_ROOT / "prompts",
        mcp=make_config(),
        draft_to=DRAFT_TO,
    )


@pytest.fixture
def fake():
    return FakeGoogleServer()


def _factory(fake):
    return lambda: McpClient(make_config(), transport=fake.server, sleep=no_sleep)


def _run(config, fake, llm=None, **kwargs):
    llm = llm or scripted_llm()
    kwargs.setdefault("as_of", AS_OF)
    return run_week(
        source=CsvSource(FIXTURE),
        config=config,
        llm_factory=lambda: llm,
        client_factory=_factory(fake),
        **kwargs,
    )


def _ledger(config) -> Ledger:
    return Ledger(config.data_dir / "ledger.json")


def _record(result):
    return json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))


# --- the happy path and the run record ------------------------------------------------------


def test_a_run_publishes_one_section_and_one_draft_and_records_it(config, fake):
    result = _run(config, fake)

    assert result.run.status is RunStatus.COMPLETED
    assert fake.doc_text == "\n" + result.note
    assert len(fake.drafts) == 1 and fake.drafts[0]["to"] == [DRAFT_TO]
    assert fake.calls_to(SEND_TOOL) == []

    record = _record(result)
    assert record["doc_id"] == "doc-123"
    assert record["doc_url"] == "https://docs.google.com/document/d/doc-123/edit"
    assert record["doc_revision_id"].startswith("rev-")
    assert record["draft_id"] == "draft-1"
    assert [s["name"] for s in record["stages"]][-2:] == ["publish_doc", "publish_draft"]

    ledger = _ledger(config)
    assert ledger.state(WEEK, Step.DOC) is StepState.DONE
    assert ledger.state(WEEK, Step.DRAFT) is StepState.DONE
    assert ledger.entry(WEEK, Step.DOC)["run_id"] == result.run.run_id


def test_the_run_record_keeps_the_analysis_stages_too(config, fake):
    names = [s["name"] for s in _record(_run(config, fake))["stages"]]
    assert names[:6] == ["ingest", "sanitize", "theme", "rank", "compose", "render"]


# --- idempotency ----------------------------------------------------------------------------


def test_running_the_same_week_twice_appends_and_drafts_exactly_once(config, fake):
    first = _run(config, fake)
    llm = scripted_llm()
    second = _run(config, fake, llm=llm)

    assert second.run.status is RunStatus.ALREADY_PUBLISHED
    assert len(fake.calls_to(DOC_TOOL)) == 1
    assert len(fake.calls_to(DRAFT_TOOL)) == 1
    assert fake.doc_text.count("Groww Weekly Review Pulse - 2026-W43") == 1
    assert llm.calls == []  # nothing was fetched or analysed again
    assert second.run.run_id != first.run.run_id
    assert _record(second)["status"] == "already_published"
    assert _record(second)["doc_url"] == _record(first)["doc_url"]


def test_a_new_week_gets_its_own_section_and_draft(config, fake):
    _run(config, fake)
    _run(config, fake, as_of=date(2026, 10, 12))

    assert len(fake.calls_to(DOC_TOOL)) == 2
    assert len(fake.calls_to(DRAFT_TOOL)) == 2


def test_dry_run_touches_neither_google_nor_the_ledger(config, fake):
    def no_client():
        raise AssertionError("a dry run must not start the MCP server")

    result = run_week(
        source=CsvSource(FIXTURE),
        config=config,
        llm_factory=scripted_llm,
        client_factory=no_client,
        as_of=AS_OF,
        dry_run=True,
    )

    assert result.run.status is RunStatus.COMPLETED
    assert (result.run_dir / "note.txt").exists()
    assert not (config.data_dir / "ledger.json").exists()
    assert result.run.doc_id is None and result.run.draft_id is None


def test_a_dry_run_does_not_count_as_publishing(config, fake):
    run_week(
        source=CsvSource(FIXTURE),
        config=config,
        llm_factory=scripted_llm,
        client_factory=_factory(fake),
        as_of=AS_OF,
        dry_run=True,
    )
    result = _run(config, fake)
    assert result.run.status is RunStatus.COMPLETED
    assert len(fake.drafts) == 1


# --- failure statuses -----------------------------------------------------------------------


def test_failed_validation_publishes_nothing_and_leaves_the_ledger_alone(config, fake):
    def bad(user):
        reply = valid_compose_reply(user)
        reply["quotes"][0]["snippet"] = "words that no reviewer ever wrote"
        return reply

    result = _run(config, fake, llm=scripted_llm(compose=bad))

    assert result.run.status is RunStatus.FAILED_VALIDATION
    assert fake.calls == []
    assert not (config.data_dir / "ledger.json").exists()


def test_a_draft_failure_after_the_append_ends_partial_and_keeps_the_section(config, fake):
    fake.fail(DRAFT_TOOL, "INVALID_INPUT", "bad recipient")

    result = _run(config, fake)

    assert result.run.status is RunStatus.PARTIAL
    assert fake.doc_text  # the appended section stays
    assert result.run.doc_url and result.run.draft_id is None
    assert any("INVALID_INPUT" in v for v in result.run.violations)
    ledger = _ledger(config)
    assert ledger.state(WEEK, Step.DOC) is StepState.DONE
    assert ledger.state(WEEK, Step.DRAFT) is StepState.NONE  # rejected before writing: retryable


def test_rerunning_after_a_partial_retries_only_the_draft_with_the_same_note(config, fake):
    fake.fail(DRAFT_TOOL, "INVALID_INPUT", "bad recipient")
    first = _run(config, fake)
    llm = scripted_llm()

    second = _run(config, fake, llm=llm)

    assert second.run.status is RunStatus.COMPLETED
    assert len(fake.calls_to(DOC_TOOL)) == 1  # not appended again
    assert len(fake.drafts) == 1
    assert llm.calls == []  # the note already in the Doc is reused, not regenerated
    assert second.run.run_id == first.run.run_id
    assert first.note and first.note.splitlines()[0] in fake.drafts[0]["body"]
    assert _record(second)["draft_id"] == "draft-1"


def test_an_ambiguous_draft_failure_blocks_reruns_until_a_person_checks(config, fake):
    fake.fail(DRAFT_TOOL, "GMAIL_DRAFT_CREATE_FAILED", "unclear", retryable=True)
    result = _run(config, fake)

    assert result.run.status is RunStatus.PARTIAL
    assert _ledger(config).state(WEEK, Step.DRAFT) is StepState.PENDING
    assert any("Drafts" in v for v in result.run.violations)

    with pytest.raises(ManualCheckRequired, match="Drafts"):
        _run(config, fake)
    assert len(fake.calls_to(DRAFT_TOOL)) == 1


def test_a_rejected_append_ends_failed_without_a_draft_and_can_be_rerun(config, fake):
    fake.fail(DOC_TOOL, "DOC_PERMISSION_DENIED", "no access")

    result = _run(config, fake)

    assert result.run.status is RunStatus.FAILED
    assert fake.calls_to(DRAFT_TOOL) == []  # no dangling pointer to a Doc section that is not there
    assert any("DOC_PERMISSION_DENIED" in v for v in result.run.violations)
    assert _ledger(config).state(WEEK, Step.DOC) is StepState.NONE

    again = _run(config, fake)  # access fixed
    assert again.run.status is RunStatus.COMPLETED
    assert len(fake.drafts) == 1


def test_an_ambiguous_append_failure_blocks_reruns(config, fake):
    fake.fail(DOC_TOOL, "DOC_APPEND_FAILED", "unclear", retryable=True)

    result = _run(config, fake)

    assert result.run.status is RunStatus.FAILED
    assert fake.calls_to(DRAFT_TOOL) == []
    assert _ledger(config).state(WEEK, Step.DOC) is StepState.PENDING
    assert any("Doc" in v and "check" in v.lower() for v in result.run.violations)
    with pytest.raises(ManualCheckRequired, match="Doc"):
        _run(config, fake)
    assert len(fake.calls_to(DOC_TOOL)) == 1


def test_a_kill_between_the_append_and_the_ledger_write_is_refused_on_rerun(
    config, fake, monkeypatch
):
    def die(self, *args, **kwargs):
        raise Killed

    monkeypatch.setattr(Ledger, "mark_done", die)
    with pytest.raises(Killed):
        _run(config, fake)
    monkeypatch.undo()

    assert len(fake.calls_to(DOC_TOOL)) == 1  # the Doc did get the section
    assert _ledger(config).state(WEEK, Step.DOC) is StepState.PENDING

    with pytest.raises(ManualCheckRequired) as err:
        _run(config, fake)
    assert "ledger" in str(err.value) and WEEK in str(err.value)
    assert len(fake.calls_to(DOC_TOOL)) == 1  # still exactly one section


def test_clearing_the_pending_entry_by_hand_unblocks_the_week(config, fake, monkeypatch):
    monkeypatch.setattr(Ledger, "mark_done", lambda *a, **k: (_ for _ in ()).throw(Killed()))
    with pytest.raises(Killed):
        _run(config, fake)
    monkeypatch.undo()

    _ledger(config).clear(WEEK, Step.DOC)

    assert _run(config, fake).run.status is RunStatus.COMPLETED


def test_a_server_that_cannot_start_fails_the_run_before_any_write(config):
    def broken():
        return McpClient(
            dataclasses.replace(make_config(), server_dir=Path("missing-dir")), sleep=no_sleep
        )

    result = run_week(
        source=CsvSource(FIXTURE),
        config=config,
        llm_factory=scripted_llm,
        client_factory=broken,
        as_of=AS_OF,
    )

    assert result.run.status is RunStatus.FAILED
    assert any("server_dir" in v for v in result.run.violations)
    assert _ledger(config).state(WEEK, Step.DOC) is StepState.NONE


# --- resume ---------------------------------------------------------------------------------


def test_resume_after_the_analysis_finished_goes_straight_to_publishing(config, fake):
    # Google is down for this attempt, so the analysis completes and the append is rejected.
    fake.fail(DOC_TOOL, "GOOGLE_AUTH_REQUIRED", "token expired")
    first = _run(config, fake)
    assert first.run.status is RunStatus.FAILED
    llm = scripted_llm()

    def no_source_call(*_a, **_k):
        raise AssertionError("resume must not fetch reviews again")

    source = CsvSource(FIXTURE)
    source.fetch = no_source_call  # type: ignore[method-assign]
    resumed = run_week(
        source=source,
        config=config,
        llm_factory=lambda: llm,
        client_factory=_factory(fake),
        as_of=date(2030, 1, 1),  # ignored: the resumed run keeps its own week
        resume=first.run.run_id,
    )

    assert resumed.run.status is RunStatus.COMPLETED
    assert resumed.run.run_id == first.run.run_id
    assert llm.calls == []
    assert fake.doc_text == "\n" + first.note
    record = _record(resumed)
    assert [s["name"] for s in record["stages"]][:6] == [
        "ingest",
        "sanitize",
        "theme",
        "rank",
        "compose",
        "render",
    ]


def test_resume_of_a_run_that_died_mid_analysis_reuses_the_theme_cache(config, fake):
    def dies(user):
        raise RuntimeError("model went away")

    with pytest.raises(RuntimeError):
        _run(config, fake, llm=scripted_llm(compose=dies))
    (run_dir,) = (config.data_dir / "runs").iterdir()
    assert not (run_dir / "pulse.json").exists()
    llm = scripted_llm()

    resumed = _run(config, fake, llm=llm, resume=run_dir.name)

    assert resumed.run.status is RunStatus.COMPLETED
    assert resumed.run.run_id == run_dir.name
    assert not [c for c in llm.calls if c[0] == "theme_assign"]  # theming finished before the kill
    assert len(fake.drafts) == 1


def test_resuming_a_run_that_does_not_exist_is_an_error(config, fake):
    with pytest.raises(ResumeError, match="nope"):
        _run(config, fake, resume="nope")


def test_resume_never_republishes_what_the_ledger_says_is_done(config, fake):
    first = _run(config, fake)

    again = _run(config, fake, resume=first.run.run_id)

    assert again.run.status is RunStatus.COMPLETED
    assert len(fake.calls_to(DOC_TOOL)) == 1
    assert len(fake.calls_to(DRAFT_TOOL)) == 1


def test_nothing_in_a_published_run_directory_or_the_ledger_names_a_reviewer(config, fake):
    with FIXTURE.open(encoding="utf-8") as handle:
        identities = {
            value
            for row in csv.DictReader(handle)
            for value in (row["author_name"], row["author_id"])
            if value
        }
    result = _run(config, fake)
    files = [*result.run_dir.iterdir(), config.data_dir / "ledger.json"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not [i for i in identities if i in text], f"{path.name} contains reviewer identity"
    assert "@" not in (config.data_dir / "ledger.json").read_text(encoding="utf-8")


def test_a_partial_week_whose_run_folder_is_gone_explains_itself(config, fake):
    import shutil

    fake.fail(DRAFT_TOOL, "INVALID_INPUT", "bad recipient")
    first = _run(config, fake)
    shutil.rmtree(first.run_dir)

    with pytest.raises(ResumeError, match="already in the Doc"):
        _run(config, fake)
    assert len(fake.calls_to(DOC_TOOL)) == 1
