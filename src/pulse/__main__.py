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
from pulse.models import RunStatus
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
    from pulse.pipeline import build_llm, run_pipeline

    if not args.dry_run:
        print(
            "Publishing from `run` arrives with the orchestrator and its duplicate-protection "
            "ledger (Phase 6). Re-run with --dry-run.",
            file=sys.stderr,
        )
        return 2
    if args.week != "current":
        print("Only --week current is supported.", file=sys.stderr)
        return 2

    cfg = _load(args)
    if cfg is None:
        return 1
    load_dotenv()
    try:
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        source = build_source(args, cfg)
        result = run_pipeline(
            source=source,
            config=cfg,
            llm=build_llm(cfg),
            as_of=as_of,
            cache_raw=args.source != "csv",
        )
    except (LLMError, SourceUnavailable, CsvSourceError, ValueError) as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1

    if getattr(source, "used_fallback", False):
        print(f"Live fetch failed ({source.primary_error}); used {args.fallback_csv} instead.")
    run = result.run
    print(f"Run {run.run_id}: {run.status.value}  ({result.run_dir})")
    for stage in run.stages:
        counts = ", ".join(f"{k}={v}" for k, v in stage.counts.items() if v)
        print(f"  {stage.name:<9} {stage.duration_s:>6.2f}s  {counts}")
        for note in stage.notes:
            print(f"            note: {note}")
    if run.status is not RunStatus.COMPLETED:
        print("\nNothing was written. Problems:", file=sys.stderr)
        for line in run.violations[-6:]:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"\n{result.note}")
    print(f"({run.word_count} words, {run.retries} compose retries)")
    return 0


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
    run.set_defaults(func=_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
