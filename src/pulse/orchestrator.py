"""The orchestrator: one command from reviews to Doc section and Gmail draft (architecture 4.9).

Stages 1-7 (analysis) live in pipeline.py. This module wraps them with the parts that make a run
safe to repeat:

* Before anything else it consults the publishing ledger (mcp/ledger.py). A week that is already
  fully published is not fetched or analysed again; a week whose Doc section went in but whose
  draft did not is finished from the note already in the Doc; a step left `pending` stops the run.
* Stages 8 and 9 (append to the Doc, create the draft) write `pending` before each MCP call and the
  final state right after it, and treat any failure that is not provably "nothing was written" as
  ambiguous.
* `--resume <run_id>` continues a saved run. Resume points are the two durable checkpoints: if the
  run finished its analysis (`pulse.json` and `note.txt` exist) it goes straight to publishing;
  otherwise the analysis reruns in the same run directory, cheaply because theme assignments are
  cached. Reviewer names are deliberately never persisted, and compose needs them for its final PII
  check, so an analysis cannot restart mid-way.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import AsyncExitStack
from datetime import UTC, date, datetime
from pathlib import Path

from pulse.config import Config
from pulse.llm import LLMClient
from pulse.mcp.client import McpClient, McpError, write_not_applied
from pulse.mcp.docs import append_note, doc_url
from pulse.mcp.gmail import create_weekly_draft
from pulse.mcp.ledger import Ledger, Step, StepState
from pulse.models import Pulse, Run, RunStatus
from pulse.pipeline import PipelineResult, Stages, run_pipeline, week_label_for, write_json
from pulse.sources.base import ReviewSource

STEP_LABEL = {Step.DOC: "Doc section", Step.DRAFT: "Gmail draft"}


class ManualCheckRequired(RuntimeError):
    """A previous run died or failed ambiguously during a write. Nothing was done this time."""


class ResumeError(RuntimeError):
    """The run to resume is missing or unusable."""


def unique_run_id(runs_dir: Path, as_of: date, started: datetime) -> str:
    """`<as_of>-<HHMMSS>`, with a suffix if that run already exists (two runs in one second)."""
    base = f"{as_of:%Y%m%d}-{started:%H%M%S}"
    run_id, n = base, 1
    while (runs_dir / run_id).exists():
        n += 1
        run_id = f"{base}-{n}"
    return run_id


def pending_message(config: Config, week: str, step: Step) -> str:
    where = (
        f"the Doc ({doc_url(config.mcp.document_id)})"
        if step is Step.DOC and config.mcp.document_id
        else "the Drafts folder in Gmail"
    )
    return (
        f"The {STEP_LABEL[step]} for {week} is marked pending in the ledger: an earlier run "
        f"started writing it and never recorded the result, so it may already exist. "
        f"Nothing was done. Check {where}. If it is there, run "
        f"`python -m pulse ledger confirm {week} {step.value}`; if it is not (or you deleted it), "
        f"run `python -m pulse ledger clear {week} {step.value}`. Then run again."
    )


def _save(run_dir: Path, run: Run) -> None:
    write_json(run_dir / "run.json", run)


def run_week(
    *,
    source: ReviewSource,
    config: Config,
    llm_factory: Callable[[], LLMClient],
    as_of: date,
    dry_run: bool = False,
    resume: str | None = None,
    cache_raw: bool = False,
    ledger: Ledger | None = None,
    client_factory: Callable[[], McpClient] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PipelineResult:
    ledger = ledger or Ledger(config.data_dir / "ledger.json")
    client_factory = client_factory or (lambda: McpClient(config.mcp))
    runs_dir = config.data_dir / "runs"

    if resume is None:
        week = week_label_for(as_of)
        if not dry_run:
            doc, draft = ledger.state(week, Step.DOC), ledger.state(week, Step.DRAFT)
            for step, state in ((Step.DOC, doc), (Step.DRAFT, draft)):
                if state is StepState.PENDING:
                    raise ManualCheckRequired(pending_message(config, week, step))
            if doc is StepState.DONE and draft is StepState.DONE:
                return _already_published(config, ledger, week, as_of, now())
            if doc is StepState.DONE:
                # The section is in the Doc but the draft is missing. Finish from that same note
                # rather than analysing again, which could produce a different one.
                saved = ledger.entry(week, Step.DOC).get("run_id")
                if not saved or not (runs_dir / saved / "note.txt").is_file():
                    raise ResumeError(
                        f"The section for {week} is already in the Doc but its draft is missing, "
                        f"and the saved note (run {saved}) is gone, so the draft cannot be built "
                        "from what is in the Doc. Create the draft by hand, or run `ledger clear "
                        f"{week} doc --force` after deleting that section to start the week over."
                    )
                return run_week(
                    source=source,
                    config=config,
                    llm_factory=llm_factory,
                    as_of=as_of,
                    resume=saved,
                    ledger=ledger,
                    client_factory=client_factory,
                    now=now,
                )
        started = now()
        run_id = unique_run_id(runs_dir, as_of, started)
        result = _analyse(source, config, llm_factory, as_of, cache_raw, run_id, now)
    else:
        run_dir = runs_dir / resume
        if not (run_dir / "run.json").is_file():
            raise ResumeError(
                f"There is no saved run {resume!r} under {runs_dir}. Runs are listed there."
            )
        run = Run.from_json(json.loads((run_dir / "run.json").read_text(encoding="utf-8")))
        if not dry_run:
            for step in Step:
                if ledger.state(run.week_label, step) is StepState.PENDING:
                    raise ManualCheckRequired(pending_message(config, run.week_label, step))
        if (run_dir / "pulse.json").is_file() and (run_dir / "note.txt").is_file():
            pulse = Pulse.from_json(
                json.loads((run_dir / "pulse.json").read_text(encoding="utf-8"))
            )
            note = (run_dir / "note.txt").read_text(encoding="utf-8")
            result = PipelineResult(run=run, run_dir=run_dir, pulse=pulse, note=note)
        else:
            # The run id starts with the end of its review window.
            window_end = datetime.strptime(resume[:8], "%Y%m%d").date()
            result = _analyse(source, config, llm_factory, window_end, cache_raw, resume, now)

    # No pulse means validation failed or the run could not produce one: publish nothing. (A
    # resumed run's old status is not consulted; the checkpoint files decide.)
    if dry_run or result.pulse is None or result.note is None:
        return result

    # Not finished until it is published: a kill from here on must not leave a "completed" record.
    result.run.status = RunStatus.RUNNING
    _save(result.run_dir, result.run)
    result.run.status = asyncio.run(
        _publish(
            result.run, result.run_dir, result.pulse, result.note, config, ledger, client_factory
        )
    )
    _save(result.run_dir, result.run)
    return result


def _analyse(source, config, llm_factory, as_of, cache_raw, run_id, now) -> PipelineResult:
    return run_pipeline(
        source=source,
        config=config,
        llm=llm_factory(),
        as_of=as_of,
        cache_raw=cache_raw,
        run_id=run_id,
        now=now,
    )


def _already_published(
    config: Config, ledger: Ledger, week: str, as_of: date, started: datetime
) -> PipelineResult:
    runs_dir = config.data_dir / "runs"
    run = Run(
        run_id=unique_run_id(runs_dir, as_of, started),
        week_label=week,
        status=RunStatus.ALREADY_PUBLISHED,
        started_at=started,
    )
    run_dir = runs_dir / run.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _fill_from_ledger(run, config, ledger)
    _save(run_dir, run)
    return PipelineResult(run=run, run_dir=run_dir)


def _fill_from_ledger(run: Run, config: Config, ledger: Ledger) -> None:
    doc = ledger.entry(run.week_label, Step.DOC)
    if doc:
        run.doc_id = doc.get("document_id") or config.mcp.document_id
        run.doc_url = doc_url(run.doc_id) if run.doc_id else None
        run.doc_revision_id = doc.get("revision_id")
    run.draft_id = ledger.entry(run.week_label, Step.DRAFT).get("draft_id")


async def _publish(
    run: Run,
    run_dir: Path,
    pulse: Pulse,
    note: str,
    config: Config,
    ledger: Ledger,
    client_factory: Callable[[], McpClient],
) -> RunStatus:
    """Stages 8 (Doc) and 9 (draft). Returns the final status; raises only on a bug or a kill."""
    week = run.week_label
    stages = Stages(run)

    async with AsyncExitStack() as stack:
        try:
            client = await stack.enter_async_context(client_factory())
        except McpError as exc:
            run.violations.append(f"The Google Workspace MCP server is not usable: {exc}")
            return RunStatus.FAILED

        # 8. Append the note to the Doc
        record = stages.start("publish_doc")
        if ledger.state(week, Step.DOC) is StepState.DONE:
            _fill_from_ledger(run, config, ledger)
            record.notes.append("already appended according to the ledger; skipped")
            stages.finish(record)
        else:
            ledger.mark_pending(week, Step.DOC, run_id=run.run_id)
            try:
                appended = await append_note(client, note)
            except Exception as exc:
                _write_failed(run, ledger, config, Step.DOC, exc)
                stages.finish(record)
                return RunStatus.FAILED
            ledger.mark_done(
                week,
                Step.DOC,
                document_id=appended.document_id,
                revision_id=appended.revision_id,
                characters_appended=appended.characters_appended,
            )
            run.doc_id, run.doc_url = appended.document_id, appended.url
            run.doc_revision_id = appended.revision_id
            stages.finish(record, characters_appended=appended.characters_appended)
        _save(run_dir, run)

        # 9. Create the draft. Only reached with a Doc section in place, so it never points at one
        # that does not exist.
        record = stages.start("publish_draft")
        if ledger.state(week, Step.DRAFT) is StepState.DONE:
            _fill_from_ledger(run, config, ledger)
            record.notes.append("already created according to the ledger; skipped")
            stages.finish(record)
            return RunStatus.COMPLETED
        if not config.draft_to:
            run.violations.append("draft_to is not set in config.yaml; no draft was created.")
            stages.finish(record)
            return RunStatus.PARTIAL
        assert run.doc_url is not None
        ledger.mark_pending(week, Step.DRAFT, run_id=run.run_id)
        try:
            draft = await create_weekly_draft(
                client,
                pulse,
                draft_to=config.draft_to,
                doc_link=run.doc_url,
                max_words=config.max_words,
                max_body_bytes=config.mcp.max_email_body_bytes,
            )
        except Exception as exc:
            _write_failed(run, ledger, config, Step.DRAFT, exc)
            stages.finish(record)
            return RunStatus.PARTIAL
        ledger.mark_done(
            week,
            Step.DRAFT,
            draft_id=draft.draft_id,
            thread_id=draft.thread_id,
            subject=draft.subject,
        )
        run.draft_id = draft.draft_id
        if draft.pointer_only:
            record.notes.append("body was too long; the draft has the three themes and the link")
        stages.finish(record)
        return RunStatus.COMPLETED


def _write_failed(run: Run, ledger: Ledger, config: Config, step: Step, exc: Exception) -> None:
    """Record a failed write. Provably unwritten: forget the attempt so a rerun can retry it.
    Anything else: leave it pending, because the Doc / draft may already have it."""
    week = run.week_label
    if write_not_applied(exc):
        ledger.clear(week, step)
        run.violations.append(f"The {STEP_LABEL[step]} was not written: {exc}")
    else:
        run.violations.append(
            f"The outcome of the {STEP_LABEL[step]} is unknown ({exc}). "
            + pending_message(config, week, step)
        )
