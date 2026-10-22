"""The `run` and `ledger` commands, driven through main() with a fake Google server."""

from pathlib import Path

import pytest
import yaml

from fake_mcp import DOC_TOOL, DRAFT_TOOL, FakeGoogleServer, make_config, no_sleep
from fakes import scripted_llm
from pulse.__main__ import main
from pulse.mcp.client import McpClient
from pulse.mcp.ledger import Ledger, Step, StepState

REPO_ROOT = Path(__file__).resolve().parents[1]
WEEK = "2026-W43"


@pytest.fixture
def cli(tmp_path, monkeypatch):
    raw = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))
    raw["paths"] = {"data_dir": str(tmp_path / "data"), "prompts_dir": str(REPO_ROOT / "prompts")}
    raw["draft_to"] = "me@example.com"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    fake = FakeGoogleServer()
    monkeypatch.setattr(
        "pulse.orchestrator.McpClient",
        lambda _cfg: McpClient(make_config(), transport=fake.server, sleep=no_sleep),
    )
    monkeypatch.setattr("pulse.pipeline.build_llm", lambda _cfg: scripted_llm())
    monkeypatch.setattr("pulse.__main__.load_dotenv", lambda: None)

    class Cli:
        ledger = Ledger(tmp_path / "data" / "ledger.json")
        server = fake

        def __call__(self, *args):
            return main([args[0], "--config", str(config_path), *args[1:]])

    return Cli()


RUN = ("run", "--as-of", "2026-10-19")


def test_run_publishes_and_reports_where(cli, capsys):
    assert cli(*RUN) == 0
    out = capsys.readouterr().out
    assert "completed" in out
    assert "https://docs.google.com/document/d/doc-123/edit" in out
    assert "draft-1" in out
    assert len(cli.server.calls_to(DOC_TOOL)) == 1


def test_running_again_says_it_is_already_published_and_succeeds(cli, capsys):
    cli(*RUN)
    capsys.readouterr()

    assert cli(*RUN) == 0

    assert "already published" in capsys.readouterr().out.lower()
    assert len(cli.server.calls_to(DOC_TOOL)) == 1
    assert len(cli.server.calls_to(DRAFT_TOOL)) == 1


def test_dry_run_publishes_nothing(cli):
    assert cli(*RUN, "--dry-run") == 0
    assert cli.server.calls == []


def test_dry_run_and_resume_cannot_be_combined(cli, capsys):
    assert cli(*RUN, "--dry-run", "--resume", "x") == 2
    assert "resume" in capsys.readouterr().err


def test_a_partial_run_exits_nonzero_and_names_the_resume_command(cli, capsys):
    cli.server.fail(DRAFT_TOOL, "INVALID_INPUT", "bad recipient")

    assert cli(*RUN) == 1

    err = capsys.readouterr().err
    assert "partial" in err and "--resume" in err


def test_a_week_waiting_for_a_manual_check_exits_with_instructions(cli, capsys):
    cli.ledger.mark_pending(WEEK, Step.DOC, run_id="r1")

    assert cli(*RUN) == 3

    err = capsys.readouterr().err
    assert f"ledger confirm {WEEK} doc" in err and f"ledger clear {WEEK} doc" in err
    assert cli.server.calls == []


def test_resuming_an_unknown_run_is_a_clear_error(cli, capsys):
    assert cli(*RUN, "--resume", "nope") == 2
    assert "nope" in capsys.readouterr().err


# --- the ledger command ---------------------------------------------------------------------


def test_ledger_show_lists_weeks_and_steps(cli, capsys):
    cli.ledger.mark_pending(WEEK, Step.DOC, run_id="r1")
    cli.ledger.mark_done(WEEK, Step.DOC, revision_id="rev-9")

    assert cli("ledger", "show") == 0

    out = capsys.readouterr().out
    assert WEEK in out and "doc" in out and "appended" in out


def test_ledger_show_on_an_empty_ledger_says_so(cli, capsys):
    assert cli("ledger", "show") == 0
    assert "empty" in capsys.readouterr().out.lower()


def test_ledger_clear_unblocks_a_pending_step(cli):
    cli.ledger.mark_pending(WEEK, Step.DRAFT, run_id="r1")

    assert cli("ledger", "clear", WEEK, "draft") == 0

    assert cli.ledger.state(WEEK, Step.DRAFT) is StepState.NONE


def test_ledger_confirm_records_that_a_pending_step_did_happen(cli):
    cli.ledger.mark_pending(WEEK, Step.DOC, run_id="r1")

    assert cli("ledger", "confirm", WEEK, "doc") == 0

    assert cli.ledger.state(WEEK, Step.DOC) is StepState.DONE
    assert cli.ledger.entry(WEEK, Step.DOC)["confirmed_by_hand"] is True


def test_ledger_confirm_refuses_a_step_that_is_not_pending(cli, capsys):
    assert cli("ledger", "confirm", WEEK, "doc") == 1
    assert "pending" in capsys.readouterr().err


def test_ledger_clear_of_a_finished_step_needs_force(cli, capsys):
    cli.ledger.mark_pending(WEEK, Step.DOC, run_id="r1")
    cli.ledger.mark_done(WEEK, Step.DOC)

    assert cli("ledger", "clear", WEEK, "doc") == 1
    assert "--force" in capsys.readouterr().err
    assert cli.ledger.state(WEEK, Step.DOC) is StepState.DONE

    assert cli("ledger", "clear", WEEK, "doc", "--force") == 0
    assert cli.ledger.state(WEEK, Step.DOC) is StepState.NONE
