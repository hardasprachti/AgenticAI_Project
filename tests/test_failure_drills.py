"""Failure drills (Phase 7 task 1): one per row of the error-handling table in architecture 11, plus
the MCP-server-specific failures. Each drives the whole orchestrator and checks the end state: the
run status, what reached Google, and what the ledger says.

Rows covered elsewhere at unit level are repeated here end to end so the table has one place to
check: source down, too few reviews, invalid LLM output, validation failure, Docs MCP down, Gmail
MCP down after the Doc succeeded. MCP-specific: expired token, Doc not shared, server not built, a
kill between a call and its ledger write.
"""

import dataclasses
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from fake_mcp import DOC_ID, DOC_TOOL, DRAFT_TOOL, FakeGoogleServer, make_config, no_sleep
from fakes import scripted_llm, valid_compose_reply
from pulse.config import load_config
from pulse.llm import GroqLLM, LLMError
from pulse.mcp.client import McpClient, OutcomeUnknown
from pulse.mcp.ledger import Ledger, Step, StepState
from pulse.models import RunStatus
from pulse.orchestrator import ManualCheckRequired, run_week
from pulse.sources.base import SourceUnavailable
from pulse.sources.csv_source import CsvSource
from pulse.sources.fallback import FallbackSource

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "evals" / "fixtures" / "reviews.csv"
AS_OF = date(2026, 10, 19)
WEEK = "2026-W43"


@pytest.fixture
def config(tmp_path):
    cfg = load_config(REPO_ROOT / "config.yaml")
    return dataclasses.replace(
        cfg,
        data_dir=tmp_path / "data",
        prompts_dir=REPO_ROOT / "prompts",
        mcp=make_config(),
        draft_to="me@example.com",
    )


@pytest.fixture
def fake():
    return FakeGoogleServer()


class DownSource:
    def fetch(self, since, until):
        raise SourceUnavailable("Play Store did not answer after 3 attempts")


def drill(config, fake, *, source=None, llm=None, client_factory=None):
    llm = llm or scripted_llm()
    return run_week(
        source=source or CsvSource(FIXTURE),
        config=config,
        llm_factory=lambda: llm,
        client_factory=client_factory
        or (lambda: McpClient(make_config(), transport=fake.server, sleep=no_sleep)),
        as_of=AS_OF,
    )


def ledger(config) -> Ledger:
    return Ledger(config.data_dir / "ledger.json")


def only_run_record(config) -> dict:
    (run_dir,) = (config.data_dir / "runs").iterdir()
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))


# --- row 1: source unavailable --------------------------------------------------------------


def test_source_down_without_a_fallback_fails_the_run_and_touches_nothing(config, fake):
    with pytest.raises(SourceUnavailable):
        drill(config, fake, source=DownSource())

    assert only_run_record(config)["status"] == "failed"
    assert fake.calls == [] and not (config.data_dir / "ledger.json").exists()


def test_source_down_with_a_csv_export_falls_back_and_completes(config, fake):
    source = FallbackSource(DownSource(), CsvSource(FIXTURE))

    result = drill(config, fake, source=source)

    assert source.used_fallback and "did not answer" in source.primary_error
    assert result.run.status is RunStatus.COMPLETED
    assert len(fake.drafts) == 1


# --- row 2: too few reviews -----------------------------------------------------------------


def test_too_few_reviews_stops_before_the_model_and_publishes_nothing(config, fake, tmp_path):
    small = tmp_path / "small.csv"
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    small.write_text("\n".join(lines[:11]) + "\n", encoding="utf-8")
    llm = scripted_llm()

    result = drill(config, fake, source=CsvSource(small), llm=llm)

    assert result.run.status is RunStatus.FAILED
    assert "usable reviews" in result.run.violations[0]
    assert llm.calls == [] and fake.calls == []  # no tokens spent, nothing invented or published


# --- row 3: invalid LLM output --------------------------------------------------------------


def test_a_model_that_only_returns_garbage_fails_after_bounded_retries(config, fake):
    attempts = []

    def create(**params):
        attempts.append(params)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="not json at all"))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    llm = GroqLLM(
        {"theme_assign": "m", "compose": "m"}, config.llm, client=client, sleep=lambda _s: None
    )

    with pytest.raises(LLMError):
        drill(config, fake, llm=llm)

    assert 1 < len(attempts) <= config.llm.max_retries + 1  # retried, but not forever
    assert only_run_record(config)["status"] == "failed"
    assert fake.calls == []


# --- row 4: validation failure after retries ------------------------------------------------


def test_validation_that_never_passes_publishes_nothing(config, fake):
    def invented_quote(user):
        reply = valid_compose_reply(user)
        reply["quotes"][0]["snippet"] = "a sentence no reviewer ever wrote"
        return reply

    result = drill(config, fake, llm=scripted_llm(compose=invented_quote))

    assert result.run.status is RunStatus.FAILED_VALIDATION
    assert result.run.retries == config.compose.max_retries
    assert fake.calls == [] and not (result.run_dir / "note.txt").exists()
    assert not (config.data_dir / "ledger.json").exists()


# --- row 5: Docs MCP down -------------------------------------------------------------------


def test_a_docs_call_with_an_unknown_outcome_blocks_the_week_and_skips_the_draft(
    config, fake, monkeypatch
):
    async def hangs(self, content, **_kw):
        raise OutcomeUnknown("google_docs_append_content did not complete (TimeoutError)")

    monkeypatch.setattr(McpClient, "append_to_document", hangs)

    result = drill(config, fake)

    assert result.run.status is RunStatus.FAILED
    assert fake.calls_to(DRAFT_TOOL) == []  # no dangling pointer to a section that may not exist
    assert result.note and (result.run_dir / "note.txt").exists()  # the note is saved locally
    assert ledger(config).state(WEEK, Step.DOC) is StepState.PENDING
    with pytest.raises(ManualCheckRequired):
        drill(config, fake)


# --- row 6: Gmail MCP down after the Doc succeeded ------------------------------------------


def test_a_gmail_outage_after_the_append_keeps_the_section_and_ends_partial(
    config, fake, monkeypatch
):
    async def hangs(self, **_kw):
        raise OutcomeUnknown("gmail_create_draft did not complete (TimeoutError)")

    monkeypatch.setattr(McpClient, "create_draft", hangs)

    result = drill(config, fake)

    assert result.run.status is RunStatus.PARTIAL
    assert fake.doc_text and result.run.doc_url  # the section stays, with its URL recorded
    assert ledger(config).state(WEEK, Step.DOC) is StepState.DONE
    assert ledger(config).state(WEEK, Step.DRAFT) is StepState.PENDING  # may exist: check Drafts


# --- MCP-server-specific drills -------------------------------------------------------------


def test_an_expired_google_token_tells_the_user_to_reauthorize_and_is_rerunnable(config, fake):
    fake.fail(DOC_TOOL, "GOOGLE_AUTH_REQUIRED", "invalid_grant")

    result = drill(config, fake)

    assert result.run.status is RunStatus.FAILED
    assert any("npm run auth" in v for v in result.run.violations)
    assert fake.calls_to(DRAFT_TOOL) == []
    assert ledger(config).state(WEEK, Step.DOC) is StepState.NONE  # nothing was written

    assert drill(config, fake).run.status is RunStatus.COMPLETED  # after re-authorizing


def test_a_doc_not_shared_with_the_account_names_the_doc_and_is_rerunnable(config, fake):
    fake.fail(DOC_TOOL, "DOC_PERMISSION_DENIED", "caller lacks permission")

    result = drill(config, fake)

    assert result.run.status is RunStatus.FAILED
    assert any(DOC_ID in v and "edit access" in v for v in result.run.violations)
    assert ledger(config).state(WEEK, Step.DOC) is StepState.NONE


def test_a_server_that_is_not_built_fails_before_any_write_with_the_fix(config, fake, tmp_path):
    server_dir = tmp_path / "mcp-server-4"
    server_dir.mkdir()  # cloned, but `npm run build` never ran: no dist/index.js
    unbuilt = dataclasses.replace(make_config(), server_dir=server_dir)

    result = drill(config, fake, client_factory=lambda: McpClient(unbuilt, sleep=no_sleep))

    assert result.run.status is RunStatus.FAILED
    assert any("npm run build" in v for v in result.run.violations)
    assert not (config.data_dir / "ledger.json").exists()
    assert result.note  # the analysis was fine and is saved for `--resume`


def test_a_missing_server_directory_fails_before_any_write(config, fake, tmp_path):
    gone = dataclasses.replace(make_config(), server_dir=tmp_path / "nowhere")

    result = drill(config, fake, client_factory=lambda: McpClient(gone, sleep=no_sleep))

    assert result.run.status is RunStatus.FAILED
    assert any("does not exist" in v for v in result.run.violations)


def test_a_kill_between_the_call_and_the_ledger_write_is_refused_on_rerun(
    config, fake, monkeypatch
):
    class Killed(BaseException):
        pass

    def die(self, *_a, **_k):
        raise Killed

    monkeypatch.setattr(Ledger, "mark_done", die)
    with pytest.raises(Killed):
        drill(config, fake)
    monkeypatch.undo()

    with pytest.raises(ManualCheckRequired, match="ledger confirm"):
        drill(config, fake)
    assert len(fake.calls_to(DOC_TOOL)) == 1  # one section, however many reruns
