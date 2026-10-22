"""Phase 0 smoke test for the Google Workspace MCP server.

Launches the server over stdio exactly as the pipeline will (cwd = server_dir, so the server reads
its own .env and tokens.json), runs `tools/list`, and checks the expected tools are present.

    python scripts/smoke_mcp.py                # list tools only; touches nothing in Google
    python scripts/smoke_mcp.py --live-check   # also create a test draft and append a marker

`--live-check` writes to the real Doc and Gmail account (a draft to `draft_to`, never a send), so it
needs `document_id` in config.yaml and a completed `npm run auth`. Delete the marker line and the
test draft afterwards.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from pulse.config import DEFAULT_CONFIG_PATH, ConfigError, load_config

# Everything the server should offer. gmail_send_email must be present (we verify it exists) but is
# never called: it is not in the allowlist in config.yaml.
EXPECTED_TOOLS = {"gmail_create_draft", "gmail_send_email", "google_docs_append_content"}
MARKER = "[pulse smoke test - delete this line]"


def _payload(result) -> object:
    """Best-effort decode of a tool result's text content."""
    text = "".join(getattr(block, "text", "") for block in result.content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def _run(config_path: Path, live_check: bool) -> int:
    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    mcp = cfg.mcp
    if mcp.server_dir is None:
        print("mcp.server_dir is not set in config.yaml", file=sys.stderr)
        return 1
    entry = mcp.server_dir / mcp.entrypoint
    if not entry.is_file():
        print(f"Server not built: {entry} is missing (run `npm run build`)", file=sys.stderr)
        return 1

    if not (mcp.server_dir / ".env").is_file():
        print(
            f"No {mcp.server_dir / '.env'}: the server will not start without GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET. Create it (Phase 0, task 6.3-6.5), then `npm run auth`.",
            file=sys.stderr,
        )
        return 1

    params = StdioServerParameters(command=mcp.command, args=[str(entry)], cwd=mcp.server_dir)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        listed = await session.list_tools()
        tools = {tool.name: tool for tool in listed.tools}

        print(f"Server tools ({len(tools)}):")
        for name, tool in sorted(tools.items()):
            props = sorted((tool.input_schema or {}).get("properties", {}))
            print(f"  {name}: {', '.join(props)}")

        missing = EXPECTED_TOOLS - tools.keys()
        if missing:
            print(f"FAIL: missing tools: {', '.join(sorted(missing))}", file=sys.stderr)
            return 1
        unmapped = set(mcp.tools.values()) - tools.keys()
        if unmapped:
            names = ", ".join(sorted(unmapped))
            print(f"FAIL: config maps unknown tools: {names}", file=sys.stderr)
            return 1
        print("OK: all expected tools present; allowlist =", ", ".join(sorted(mcp.allowed_tools)))

        if not live_check:
            return 0

        if not mcp.document_id or not cfg.draft_to:
            print("FAIL: --live-check needs mcp.document_id and draft_to", file=sys.stderr)
            return 1

        append = await session.call_tool(
            mcp.tools["append_to_document"],
            {"documentId": mcp.document_id, "content": MARKER, "ensureLeadingNewline": True},
        )
        print("append:", _payload(append))
        draft = await session.call_tool(
            mcp.tools["create_draft"],
            {
                "to": [cfg.draft_to],
                "subject": "Pulse smoke test (safe to delete)",
                "body": MARKER,
                "bodyType": "text",
            },
        )
        print("draft:", _payload(draft))
        if append.is_error or draft.is_error:
            print("FAIL: a live call returned an error", file=sys.stderr)
            return 1
        print("Now delete the marker line from the Doc and the test draft from Gmail.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--live-check", action="store_true", help="also write a marker + draft")
    args = parser.parse_args()
    return asyncio.run(_run(Path(args.config), args.live_check))


if __name__ == "__main__":
    raise SystemExit(main())
