"""Entry point: python -m pulse <command>. Pipeline commands arrive in later phases."""

from __future__ import annotations

import argparse
import sys

from pulse.config import DEFAULT_CONFIG_PATH, ConfigError, load_config


def _check_config(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    print(f"Config OK: {args.config}")
    print(f"  app:          {cfg.app.play_package} ({cfg.app.play_lang}_{cfg.app.play_country})")
    print(f"  window_weeks: {cfg.window_weeks}")
    print(f"  max_themes:   {cfg.max_themes}")
    for label, server in (("docs MCP:", cfg.mcp_docs), ("gmail MCP:", cfg.mcp_gmail)):
        print(f"  {label:<13} {'configured' if server.is_configured else 'NOT configured yet'}")
    print(f"  draft_to:     {cfg.draft_to or 'NOT set yet'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pulse", description="Groww Weekly Review Pulse")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check-config", help="Validate config.yaml and show what is set")
    check.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    check.set_defaults(func=_check_config)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
