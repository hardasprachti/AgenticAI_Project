"""MCP client for the Google Workspace server (architecture section 7).

The agent holds no Google credentials and no Google SDK: it launches the server (mcp-server-4) as a
stdio subprocess and calls two of its tools. This module is the only place that talks to it, and it
enforces three rules:

* Allowlist: only the tools mapped in `config.mcp.tools` can be called. `gmail_send_email` is never
  callable, even if someone adds it to the config.
* Startup check: the server must list every tool we map, or we stop before doing any work.
* Writes are not retried blindly. Neither tool is idempotent and the server cannot read back what
  it did, so after an ambiguous failure (a timeout, a dropped connection, a 5xx from Google) the
  caller must find out what happened, not repeat the call. Only a rate-limit rejection, which
  Google issues before acting, is retried.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any

from mcp import Client, StdioServerParameters

from pulse.config import McpConfig

# Never callable, whatever the config says: it sends mail immediately.
FORBIDDEN_TOOLS = frozenset({"gmail_send_email"})

REQUIRED_OPERATIONS = ("append_to_document", "create_draft")

# The only error code that means "rejected before anything happened", so safe to retry.
RETRY_SAFE_CODES = frozenset({"GOOGLE_RATE_LIMITED"})

_REAUTHORIZE = (
    "Re-authorize the Google account by running `npm run auth` in the MCP server directory "
    "({server_dir}), then run again."
)
_HINTS = {
    "GOOGLE_AUTH_REQUIRED": _REAUTHORIZE,
    "GOOGLE_TOKEN_REFRESH_FAILED": _REAUTHORIZE,
    "INSUFFICIENT_SCOPE": _REAUTHORIZE,
    "AUTH_NOT_CONFIGURED": _REAUTHORIZE,
    "DOC_PERMISSION_DENIED": (
        "The Google account authorized in the MCP server ({server_dir}) needs edit access to "
        "Doc {document_id}. Share the Doc with that account, or re-authorize with the account "
        "that owns it."
    ),
    "DOC_NOT_FOUND": "Check mcp.document_id in config.yaml (currently {document_id}).",
}


class McpError(RuntimeError):
    """Base class for everything the MCP layer raises."""


class McpSetupError(McpError):
    """The server cannot be started or does not offer what we need. Nothing was called."""


class ToolNotAllowed(McpError):
    """A tool outside the allowlist was requested. The call never left this process."""


class OutcomeUnknown(McpError):
    """The call may or may not have taken effect (timeout, dropped connection).

    The caller must not repeat it. Check the Doc / Drafts folder first.
    """


class McpToolError(McpError):
    """The server answered with an error envelope."""

    def __init__(self, tool: str, code: str, message: str, retryable: bool, hint: str = "") -> None:
        self.tool, self.code, self.server_message = tool, code, message
        self.retryable, self.hint = retryable, hint
        text = f"{tool} failed with {code}: {message}"
        super().__init__(f"{text}. {hint}" if hint else text)


def _envelope(result: Any) -> dict[str, Any] | None:
    """The server's JSON envelope: structured content, or the JSON text it also sends."""
    if isinstance(result.structured_content, dict):
        return result.structured_content
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None


class McpClient:
    """Async context manager around one server session.

    `transport` is for tests: anything `mcp.Client` accepts in place of launching the real server.
    """

    def __init__(
        self,
        config: McpConfig,
        *,
        transport: Any = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.config = config
        self._transport = transport
        self._sleep = sleep
        self._stack: AsyncExitStack | None = None
        self._client: Client | None = None
        self.offered_tools: frozenset[str] = frozenset()

    # --- lifecycle -------------------------------------------------------------------------

    async def __aenter__(self) -> McpClient:
        self._check_config()
        target = self._transport if self._transport is not None else self._launch_params()
        stack = AsyncExitStack()
        try:
            client = await stack.enter_async_context(Client(target))
            offered = {tool.name for tool in (await client.list_tools()).tools}
        except McpError:
            await stack.aclose()
            raise
        except BaseException as exc:
            await stack.aclose()
            if isinstance(exc, asyncio.CancelledError | KeyboardInterrupt):
                raise
            raise McpSetupError(
                f"Could not start or talk to the MCP server: {type(exc).__name__}: {exc}"
            ) from exc

        missing = sorted(self.config.allowed_tools - offered)
        if missing:
            await stack.aclose()
            raise McpSetupError(
                f"The MCP server does not offer the required tool(s): {', '.join(missing)}. "
                f"It offers: {', '.join(sorted(offered)) or 'nothing'}. Is the server on the "
                "pinned commit from the implementation plan?"
            )
        self._stack, self._client = stack, client
        self.offered_tools = frozenset(offered)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = self._client = None

    def _check_config(self) -> None:
        cfg = self.config
        forbidden = sorted(FORBIDDEN_TOOLS & cfg.allowed_tools)
        if forbidden:
            raise McpSetupError(
                f"mcp.tools maps {', '.join(forbidden)}, which sends mail immediately and is "
                "never allowed. Remove it from config.yaml."
            )
        unmapped = [op for op in REQUIRED_OPERATIONS if op not in cfg.tools]
        if unmapped:
            raise McpSetupError(f"mcp.tools in config.yaml has no mapping for: {unmapped}")
        if not cfg.document_id:
            raise McpSetupError("mcp.document_id is not set in config.yaml")

    def _launch_params(self) -> StdioServerParameters:
        cfg = self.config
        if cfg.server_dir is None:
            raise McpSetupError("mcp.server_dir is not set in config.yaml")
        if not cfg.server_dir.is_dir():
            raise McpSetupError(f"mcp.server_dir does not exist: {cfg.server_dir}")
        entry = cfg.server_dir / cfg.entrypoint
        if not entry.is_file():
            raise McpSetupError(
                f"The MCP server is not built: {entry} is missing. "
                f"Run `npm install` and `npm run build` in {cfg.server_dir}."
            )
        command = shutil.which(cfg.command)
        if command is None:
            raise McpSetupError(f"`{cfg.command}` was not found on PATH (Node.js 20+ is required)")
        # The server prints a dotenv banner and JSON log lines on stdout, which is the protocol
        # pipe. The SDK skips lines it cannot parse but logs a traceback for each; silence that.
        logging.getLogger("mcp.client.stdio").setLevel(logging.CRITICAL)
        # cwd is the server directory so the server reads its own .env and tokens.json.
        return StdioServerParameters(
            command=command,
            args=[str(entry)],
            cwd=cfg.server_dir,
            env={"DOTENV_CONFIG_QUIET": "true"},
        )

    # --- calls -----------------------------------------------------------------------------

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an allowlisted tool and return its success envelope."""
        if name in FORBIDDEN_TOOLS or name not in self.config.allowed_tools:
            raise ToolNotAllowed(f"Tool {name!r} is not in the allowlist and cannot be called")
        if self._client is None:
            raise McpError("The MCP client is not connected")

        attempt = 0
        while True:
            try:
                return await self._call_once(name, arguments)
            except McpToolError as err:
                if err.code not in RETRY_SAFE_CODES or attempt >= self.config.max_retries:
                    raise
                await self._sleep(self.config.retry_base_s * 2**attempt)
                attempt += 1

    async def _call_once(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        assert self._client is not None
        try:
            async with asyncio.timeout(self.config.timeout_s):
                result = await self._client.call_tool(name, arguments)
        except Exception as exc:  # timeout, closed pipe, server crash: the outcome is unknown
            raise OutcomeUnknown(
                f"{name} did not complete ({type(exc).__name__}); it may or may not have taken "
                "effect. Check the Doc / Drafts folder before running again."
            ) from exc

        envelope = _envelope(result)
        if result.is_error or envelope is None or not envelope.get("ok", False):
            raise self._tool_error(name, envelope)
        return envelope

    def _tool_error(self, name: str, envelope: dict[str, Any] | None) -> McpToolError:
        detail = (envelope or {}).get("error") or {}
        code = str(detail.get("code") or "UNKNOWN")
        hint = _HINTS.get(code, "").format(
            server_dir=self.config.server_dir, document_id=self.config.document_id
        )
        return McpToolError(
            name,
            code,
            str(detail.get("message") or "no error details returned"),
            bool(detail.get("retryable", False)),
            hint,
        )

    # --- logical operations (architecture 7: the tool-mapping adapter) ---------------------

    async def append_to_document(
        self, content: str, *, ensure_leading_newline: bool = True
    ) -> dict[str, Any]:
        """Append to the configured Doc. The document id always comes from config, never a caller:
        the server's `documents` scope can edit any Doc the account reaches."""
        return await self.call_tool(
            self.config.tools["append_to_document"],
            {
                "documentId": self.config.document_id,
                "content": content,
                "ensureLeadingNewline": ensure_leading_newline,
            },
        )

    async def create_draft(self, *, to: list[str], subject: str, body: str) -> dict[str, Any]:
        """Create a Gmail draft. There is no send operation in this client."""
        return await self.call_tool(
            self.config.tools["create_draft"],
            {"to": to, "subject": subject, "body": body, "bodyType": "text"},
        )
