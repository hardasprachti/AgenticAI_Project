"""Opt-in end-to-end check against the real MCP server and Google account.

Skipped unless RUN_INTEGRATION_TESTS=1. It really appends a dummy section to the configured Doc
and creates a real (unsent) draft addressed to `draft_to`. Neither can be undone by the code:
delete the section and the draft by hand afterwards.
"""

import asyncio
import os
from dataclasses import replace
from pathlib import Path

import pytest

from pulse.config import load_config
from pulse.mcp.client import McpClient
from pulse.mcp.docs import append_note
from pulse.mcp.gmail import create_weekly_draft
from pulse.render import render_note

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1", reason="set RUN_INTEGRATION_TESTS=1 to run"
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_dummy_pulse_reaches_the_real_doc_and_a_real_draft(valid_pulse):
    config = load_config(REPO_ROOT / "config.yaml")
    pulse = replace(valid_pulse, week_label="TEST-DELETE-ME")

    async def main():
        async with McpClient(config.mcp) as client:
            appended = await append_note(client, render_note(pulse))
            draft = await create_weekly_draft(
                client, pulse, draft_to=config.draft_to, doc_link=appended.url
            )
            return appended, draft

    appended, draft = asyncio.run(main())

    assert appended.characters_appended > 0
    assert draft.draft_id
