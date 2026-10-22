"""An in-process fake of the Google Workspace MCP server (mcp-server-4).

It exposes the same three tools with the same argument names and response envelopes
(`{ok, action, status, ...}` on success, `{ok: false, action, error: {code, message, retryable}}`
with `isError` on failure), records every call it receives, and can be told to fail. It stands in
for the real server so the publishing code is tested without Google or Node.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp_types import CallToolResult, TextContent

from pulse.config import McpConfig
from pulse.mcp.client import McpClient

DOC_TOOL = "google_docs_append_content"
DRAFT_TOOL = "gmail_create_draft"
SEND_TOOL = "gmail_send_email"
ALL_TOOLS = (DRAFT_TOOL, SEND_TOOL, DOC_TOOL)


def error_envelope(action: str, code: str, message: str, retryable: bool = False) -> dict:
    return {
        "ok": False,
        "action": action,
        "error": {"code": code, "message": message, "retryable": retryable},
    }


def _result(envelope: dict) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(envelope))],
        structured_content=envelope,
        is_error=not envelope["ok"],
    )


class FakeGoogleServer:
    def __init__(self, tools: tuple[str, ...] = ALL_TOOLS) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.doc_text = ""
        self.drafts: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []
        # Errors to return, oldest first, one per matching call; then calls succeed again.
        self.queued_errors: dict[str, list[dict]] = {}
        self.chars_delta = 0  # added to charactersAppended to simulate a wrong response
        self.document_id_override: str | None = None
        self.server = MCPServer("fake-google-workspace")
        registered = {
            DRAFT_TOOL: self._create_draft,
            SEND_TOOL: self._send_email,
            DOC_TOOL: self._append,
        }
        for name in tools:
            self.server.tool(name=name)(registered[name])

    def fail(self, tool: str, code: str, message: str = "boom", *, retryable: bool = False) -> None:
        self.queued_errors.setdefault(tool, []).append(
            error_envelope(tool, code, message, retryable)
        )

    def calls_to(self, tool: str) -> list[dict[str, Any]]:
        return [args for name, args in self.calls if name == tool]

    def _next_error(self, tool: str) -> CallToolResult | None:
        queue = self.queued_errors.get(tool)
        return _result(queue.pop(0)) if queue else None

    def _create_draft(
        self,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        bodyType: str = "text",
    ) -> CallToolResult:
        args = {"to": to, "subject": subject, "body": body, "bodyType": bodyType}
        self.calls.append((DRAFT_TOOL, args))
        if (failure := self._next_error(DRAFT_TOOL)) is not None:
            return failure
        self.drafts.append(args)
        draft_id = f"draft-{len(self.drafts)}"
        return _result(
            {
                "ok": True,
                "action": DRAFT_TOOL,
                "status": "draft_created",
                "draftId": draft_id,
                "threadId": f"thread-{len(self.drafts)}",
            }
        )

    def _send_email(
        self, to: list[str], subject: str, body: str, bodyType: str = "text"
    ) -> CallToolResult:
        args = {"to": to, "subject": subject, "body": body, "bodyType": bodyType}
        self.calls.append((SEND_TOOL, args))
        self.sent.append(args)
        return _result(
            {"ok": True, "action": SEND_TOOL, "status": "sent", "messageId": "m1", "threadId": "t1"}
        )

    def _append(
        self,
        documentId: str,
        content: str,
        tabId: str | None = None,
        ensureLeadingNewline: bool = False,
    ) -> CallToolResult:
        args = {
            "documentId": documentId,
            "content": content,
            "ensureLeadingNewline": ensureLeadingNewline,
        }
        self.calls.append((DOC_TOOL, args))
        if (failure := self._next_error(DOC_TOOL)) is not None:
            return failure
        text = content
        if ensureLeadingNewline and not text.startswith("\n"):
            text = "\n" + text  # what the real server does, and counts in charactersAppended
        self.doc_text += text
        return _result(
            {
                "ok": True,
                "action": DOC_TOOL,
                "status": "appended",
                "documentId": self.document_id_override or documentId,
                "charactersAppended": len(text) + self.chars_delta,
                "revisionId": f"rev-{len(self.calls)}",
            }
        )


DOC_ID = "doc-123"


def make_config(**overrides) -> McpConfig:
    base = dict(
        server_dir=Path("unused"),
        command="node",
        entrypoint="dist/index.js",
        document_id=DOC_ID,
        tools={"append_to_document": DOC_TOOL, "create_draft": DRAFT_TOOL},
    )
    base.update(overrides)
    return McpConfig(**base)


async def no_sleep(_: float) -> None:
    return None


def run_with_client(fake, coro_fn, config=None, **client_kwargs):
    async def main():
        client = McpClient(
            config or make_config(), transport=fake.server, sleep=no_sleep, **client_kwargs
        )
        async with client:
            return await coro_fn(client)

    return asyncio.run(main())
