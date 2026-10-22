"""Entry point: python -m pulse <command>."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from dotenv import load_dotenv

from pulse.config import DEFAULT_CONFIG_PATH, Config, ConfigError, load_config
from pulse.llm import LLMError
from pulse.mcp.client import McpClient, McpError
from pulse.mcp.ledger import Ledger, LedgerError, Step, StepState
from pulse.models import RunStatus
from pulse.orchestrator import ManualCheckRequired, ResumeError
from pulse.sources.base import SourceUnavailable
from pulse.sources.csv_source import CsvSource, CsvSourceError
from pulse.sources.fallback import FallbackSource
from pulse.sources.play_store import PlayStoreSource

DEFAULT_FIXTURE = "evals/fixtures/reviews.csv"


def _load(args: argparse.Namespace) -> Config | None:
    try:
        return load_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return None


def _check_config(args: argparse.Namespace) -> int:
    cfg = _load(args)
    if cfg is None:
        return 1

    print(f"Config OK: {args.config}")
    print(f"  app:          {cfg.app.play_package} ({cfg.app.play_lang}_{cfg.app.play_country})")
    print(f"  window_weeks: {cfg.window_weeks}")
    print(f"  max_themes:   {cfg.max_themes}")
    mcp_state = "configured" if cfg.mcp.is_configured else "NOT configured yet"
    print(f"  MCP server:   {mcp_state}")
    print(f"  draft_to:     {cfg.draft_to or 'NOT set yet'}")
    return 0


def _check_llm(args: argparse.Namespace) -> int:
    """Verify the Groq key works and every configured model id is available to it."""
    from pulse.pipeline import build_llm

    cfg = _load(args)
    if cfg is None:
        return 1
    load_dotenv()
    try:
        available = set(build_llm(cfg).list_models())
    except LLMError as exc:
        print(f"LLM error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # network or auth failure from the SDK
        print(f"Could not list models: {type(exc).__name__}", file=sys.stderr)
        return 1

    missing = 0
    for task, model in sorted(cfg.models.items()):
        ok = model in available
        missing += not ok
        print(f"  {'ok     ' if ok else 'MISSING'} {task:<14} {model}")
    if missing:
        print(f"\nAvailable models: {', '.join(sorted(available))}", file=sys.stderr)
        return 1
    return 0


def _check_mcp(args: argparse.Namespace) -> int:
    """Start the Google Workspace MCP server and confirm it offers the tools we need.

    Read-only: it lists tools and calls none of them.
    """
    cfg = _load(args)
    if cfg is None:
        return 1

    async def probe() -> frozenset[str]:
        async with McpClient(cfg.mcp) as client:
            return client.offered_tools

    try:
        offered = asyncio.run(probe())
    except McpError as exc:
        print(f"MCP error: {exc}", file=sys.stderr)
        return 1
    for operation, tool in sorted(cfg.mcp.tools.items()):
        print(f"  ok      {operation:<18} {tool}")
    for tool in sorted(offered - cfg.mcp.allowed_tools):
        print(f"  blocked {'(not allowlisted)':<18} {tool}")
    print(f"\nDoc: https://docs.google.com/document/d/{cfg.mcp.document_id}/edit")
    print(f"Draft recipient: {cfg.draft_to or 'NOT set'}")
    return 0


def build_source(args: argparse.Namespace, cfg: Config):
    """The review source for `--source`, with an optional export to fall back on."""
    if args.source == "csv":
        return CsvSource(args.path)
    live = PlayStoreSource(
        cfg.app.play_package,
        cfg.app.play_lang,
        cfg.app.play_country,
        page_size=cfg.play.page_size,
        delay_s=cfg.play.delay_s,
        max_retries=cfg.play.max_retries,
        max_pages=cfg.play.max_pages,
        max_reviews=cfg.play.max_reviews,
    )
    return FallbackSource(live, CsvSource(args.fallback_csv)) if args.fallback_csv else live


def _run(args: argparse.Namespace) -> int:
    from pulse.orchestrator import run_week
    from pulse.pipeline import build_llm

    if args.week != "current":
        print("Only --week current is supported.", file=sys.stderr)
        return 2
    if args.dry_run and args.resume:
        print(
            "--resume continues a publishing run and cannot be combined with --dry-run.",
            file=sys.stderr,
        )
        return 2

    cfg = _load(args)
    if cfg is None:
        return 1
    load_dotenv()
    try:
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        source = build_source(args, cfg)
        result = run_week(
            source=source,
            config=cfg,
            llm_factory=lambda: build_llm(cfg),
            as_of=as_of,
            dry_run=args.dry_run,
            resume=args.resume,
            cache_raw=args.source != "csv",
        )
    except (ManualCheckRequired, LedgerError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 3
    except ResumeError as exc:
        print(f"Cannot resume: {exc}", file=sys.stderr)
        return 2
    except (LLMError, SourceUnavailable, CsvSourceError, ValueError) as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1

    if getattr(source, "used_fallback", False):
        print(f"Live fetch failed ({source.primary_error}); used {args.fallback_csv} instead.")
    run = result.run
    print(f"Run {run.run_id}: {run.status.value}  ({result.run_dir})")
    for stage in run.stages:
        counts = ", ".join(f"{k}={v}" for k, v in stage.counts.items() if v)
        print(f"  {stage.name:<13} {stage.duration_s:>6.2f}s  {counts}")
        for note in stage.notes:
            print(f"                note: {note}")

    if run.status is RunStatus.ALREADY_PUBLISHED:
        print(f"\n{run.week_label} is already published; nothing was run.")
        print(f"Doc:   {run.doc_url}\nDraft: {run.draft_id}")
        return 0
    if run.status is not RunStatus.COMPLETED:
        print(f"\nRun {run.status.value}. Problems:", file=sys.stderr)
        for line in run.violations[-6:]:
            print(f"  {line}", file=sys.stderr)
        if run.status is RunStatus.FAILED_VALIDATION:
            print("Nothing was published.", file=sys.stderr)
        elif result.pulse is not None:
            print(
                f"The note is saved. To publish it without analysing again once the problem "
                f"is fixed: python -m pulse run --resume {run.run_id}",
                file=sys.stderr,
            )
        return 1
    print(f"\n{result.note}")
    print(f"({run.word_count} words, {run.retries} compose retries)")
    if not args.dry_run:
        print(f"Doc:   {run.doc_url}\nDraft: {run.draft_id} (to {cfg.draft_to}; not sent)")
    return 0


def _ledger(args: argparse.Namespace) -> int:
    """Inspect or hand-resolve the publishing ledger (see Ledger and README)."""
    cfg = _load(args)
    if cfg is None:
        return 1
    ledger = Ledger(cfg.data_dir / "ledger.json")
    try:
        if args.action == "show":
            weeks = ledger.weeks()
            if not weeks:
                print("The ledger is empty: no week has been published from this machine.")
            for week, steps in sorted(weeks.items()):
                for step, entry in steps.items():
                    detail = ", ".join(f"{k}={v}" for k, v in entry.items() if k != "state")
                    print(f"{week}  {step:<6} {entry['state']:<9} {detail}")
            return 0

        step = Step(args.step)
        state = ledger.state(args.week, step)
        if args.action == "confirm":
            if state is not StepState.PENDING:
                print(
                    f"{args.week} {args.step} is not pending, so there is nothing to confirm.",
                    file=sys.stderr,
                )
                return 1
            ledger.mark_done(args.week, step, confirmed_by_hand=True)
            print(f"Recorded {args.week} {args.step} as done. Reruns will skip it.")
        else:  # clear
            if state is StepState.DONE and not args.force:
                print(
                    f"{args.week} {args.step} is recorded as done. Clearing it lets the next run "
                    "write it again, which duplicates it unless you removed the earlier one. "
                    "Pass --force if that is what you want.",
                    file=sys.stderr,
                )
                return 1
            ledger.clear(args.week, step)
            print(f"Cleared {args.week} {args.step}. The next run will write it again.")
        return 0
    except LedgerError as exc:
        print(f"Ledger error: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy code page; reviews and model text are Unicode.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="pulse", description="Groww Weekly Review Pulse")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_config(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))

    check = sub.add_parser("check-config", help="Validate config.yaml and show what is set")
    add_config(check)
    check.set_defaults(func=_check_config)

    llm = sub.add_parser("check-llm", help="Verify GROQ_API_KEY and the configured model ids")
    add_config(llm)
    llm.set_defaults(func=_check_llm)

    mcp_check = sub.add_parser(
        "check-mcp", help="Start the Google Workspace MCP server and verify its tools"
    )
    add_config(mcp_check)
    mcp_check.set_defaults(func=_check_mcp)

    run = sub.add_parser("run", help="Run the pipeline")
    add_config(run)
    run.add_argument("--source", choices=["csv", "play"], default="csv")
    run.add_argument("--path", default=DEFAULT_FIXTURE, help="CSV file for --source csv")
    run.add_argument(
        "--fallback-csv",
        help="With --source play: a Play Console export to use if the live fetch fails",
    )
    run.add_argument("--week", default="current")
    run.add_argument("--as-of", help="End of the review window, YYYY-MM-DD (default: today)")
    run.add_argument("--dry-run", action="store_true", help="Write the note to data/runs/ only")
    run.add_argument(
        "--resume",
        metavar="RUN_ID",
        help="Continue a saved run (a folder name under data/runs/): publish its finished note, "
        "or redo its analysis from the theme cache",
    )
    run.set_defaults(func=_run)

    ledger = sub.add_parser(
        "ledger", help="Show or hand-resolve the publishing ledger (duplicate protection)"
    )
    add_config(ledger)
    ledger_sub = ledger.add_subparsers(dest="action", required=True)
    ledger_sub.add_parser("show", help="List every week and step recorded")
    for name, text in (
        ("confirm", "A pending step did happen (the section/draft is there): record it as done"),
        ("clear", "Forget a step so the next run writes it again (nothing is there)"),
    ):
        action = ledger_sub.add_parser(name, help=text)
        action.add_argument("week", help="ISO week label, e.g. 2026-W43")
        action.add_argument("step", choices=[step.value for step in Step])
        if name == "clear":
            action.add_argument(
                "--force", action="store_true", help="Also clear a step recorded as done"
            )
    ledger.set_defaults(func=_ledger)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
