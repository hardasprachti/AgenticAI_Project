import asyncio
from pathlib import Path

import pytest

from fake_mcp import (
    ALL_TOOLS,
    DOC_ID,
    DOC_TOOL,
    DRAFT_TOOL,
    SEND_TOOL,
    FakeGoogleServer,
    make_config,
    no_sleep,
    run_with_client,
)
from pulse.mcp.client import (
    McpClient,
    McpSetupError,
    McpToolError,
    OutcomeUnknown,
    ToolNotAllowed,
    write_not_applied,
)


def test_send_email_is_rejected_by_the_allowlist_and_never_reaches_the_server():
    fake = FakeGoogleServer()
    args = {"to": ["a@example.com"], "subject": "s", "body": "b"}

    async def attempt(client):
        await client.call_tool(SEND_TOOL, args)

    with pytest.raises(ToolNotAllowed, match=SEND_TOOL):
        run_with_client(fake, attempt)
    assert fake.calls_to(SEND_TOOL) == []
    assert fake.sent == []


def test_send_email_stays_blocked_even_if_it_is_put_in_the_config_tools():
    fake = FakeGoogleServer()
    config = make_config(
        tools={"append_to_document": DOC_TOOL, "create_draft": DRAFT_TOOL, "send": SEND_TOOL}
    )

    with pytest.raises(McpSetupError, match=SEND_TOOL):
        run_with_client(fake, lambda c: asyncio.sleep(0), config=config)


@pytest.mark.parametrize("missing", [DOC_TOOL, DRAFT_TOOL])
def test_startup_fails_when_the_server_lacks_an_allowed_tool(missing):
    fake = FakeGoogleServer(tools=tuple(t for t in ALL_TOOLS if t != missing))

    with pytest.raises(McpSetupError, match=missing):
        run_with_client(fake, lambda c: asyncio.sleep(0))


def test_startup_fails_when_a_logical_operation_is_not_mapped():
    fake = FakeGoogleServer()
    config = make_config(tools={"append_to_document": DOC_TOOL})

    with pytest.raises(McpSetupError, match="create_draft"):
        run_with_client(fake, lambda c: asyncio.sleep(0), config=config)


def test_startup_fails_when_no_document_id_is_configured():
    fake = FakeGoogleServer()

    with pytest.raises(McpSetupError, match="document_id"):
        run_with_client(fake, lambda c: asyncio.sleep(0), config=make_config(document_id=None))


def test_missing_server_build_is_reported_with_the_fix(tmp_path):
    config = make_config(server_dir=tmp_path)  # exists, but dist/index.js does not

    async def main():
        async with McpClient(config):
            pass

    with pytest.raises(McpSetupError, match="npm run build"):
        asyncio.run(main())


def test_missing_server_dir_is_reported(tmp_path):
    config = make_config(server_dir=tmp_path / "nope")

    async def main():
        async with McpClient(config):
            pass

    with pytest.raises(McpSetupError, match="server_dir"):
        asyncio.run(main())


def test_append_uses_the_configured_document_and_a_leading_newline():
    fake = FakeGoogleServer()

    result = run_with_client(fake, lambda c: c.append_to_document("hello"))

    assert result["status"] == "appended"
    assert fake.calls_to(DOC_TOOL) == [
        {"documentId": DOC_ID, "content": "hello", "ensureLeadingNewline": True}
    ]


def test_create_draft_sends_text_body_to_the_recipients():
    fake = FakeGoogleServer()

    result = run_with_client(
        fake, lambda c: c.create_draft(to=["me@example.com"], subject="S", body="B")
    )

    assert result["status"] == "draft_created"
    assert fake.calls_to(DRAFT_TOOL) == [
        {"to": ["me@example.com"], "subject": "S", "body": "B", "bodyType": "text"}
    ]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("GOOGLE_AUTH_REQUIRED", "npm run auth"),
        ("INSUFFICIENT_SCOPE", "npm run auth"),
        ("GOOGLE_TOKEN_REFRESH_FAILED", "npm run auth"),
        ("AUTH_NOT_CONFIGURED", "npm run auth"),
        ("DOC_PERMISSION_DENIED", DOC_ID),
        ("DOC_NOT_FOUND", "document_id"),
    ],
)
def test_fatal_errors_carry_an_instruction_for_the_user(code, expected):
    fake = FakeGoogleServer()
    fake.fail(DOC_TOOL, code, "server said no")

    with pytest.raises(McpToolError) as caught:
        run_with_client(fake, lambda c: c.append_to_document("x"))

    assert caught.value.code == code
    assert not caught.value.retryable
    assert expected in str(caught.value)
    assert len(fake.calls_to(DOC_TOOL)) == 1  # fatal: no retry


@pytest.mark.parametrize("code", ["INVALID_INPUT", "PAYLOAD_TOO_LARGE", "DOC_APPEND_FAILED"])
def test_other_fatal_errors_are_not_retried(code):
    fake = FakeGoogleServer()
    fake.fail(DOC_TOOL, code)

    with pytest.raises(McpToolError) as caught:
        run_with_client(fake, lambda c: c.append_to_document("x"))

    assert caught.value.code == code
    assert len(fake.calls_to(DOC_TOOL)) == 1


def test_rate_limit_is_retried_with_backoff_then_succeeds():
    fake = FakeGoogleServer()
    fake.fail(DOC_TOOL, "GOOGLE_RATE_LIMITED", retryable=True)
    fake.fail(DOC_TOOL, "GOOGLE_RATE_LIMITED", retryable=True)
    waits: list[float] = []

    async def record_sleep(seconds: float) -> None:
        waits.append(seconds)

    async def main():
        async with McpClient(make_config(), transport=fake.server, sleep=record_sleep) as client:
            return await client.append_to_document("x")

    result = asyncio.run(main())

    assert result["status"] == "appended"
    assert len(fake.calls_to(DOC_TOOL)) == 3
    assert len(waits) == 2 and waits[1] > waits[0]


def test_rate_limit_gives_up_after_the_retry_budget():
    fake = FakeGoogleServer()
    for _ in range(10):
        fake.fail(DOC_TOOL, "GOOGLE_RATE_LIMITED", retryable=True)

    with pytest.raises(McpToolError) as caught:
        run_with_client(
            fake, lambda c: c.append_to_document("x"), config=make_config(max_retries=2)
        )

    assert caught.value.retryable
    assert len(fake.calls_to(DOC_TOOL)) == 3  # first try + 2 retries


def test_transient_server_error_is_not_retried_because_the_write_may_have_landed():
    fake = FakeGoogleServer()
    fake.fail(DOC_TOOL, "GOOGLE_API_UNAVAILABLE", retryable=True)

    with pytest.raises(McpToolError) as caught:
        run_with_client(fake, lambda c: c.append_to_document("x"))

    assert caught.value.retryable
    assert len(fake.calls_to(DOC_TOOL)) == 1


def test_a_call_that_times_out_is_reported_as_outcome_unknown_and_not_retried():
    fake = FakeGoogleServer()

    async def slow(*_a, **_k):
        await asyncio.sleep(5)

    async def main():
        config = make_config(timeout_s=0.05)
        async with McpClient(config, transport=fake.server, sleep=no_sleep) as client:
            client._client.call_tool = slow  # the transport hangs mid-call
            await client.append_to_document("x")

    with pytest.raises(OutcomeUnknown, match="may or may not"):
        asyncio.run(main())


def test_client_reports_every_tool_the_server_offers():
    fake = FakeGoogleServer()

    offered = run_with_client(fake, lambda c: asyncio.sleep(0, result=c.offered_tools))

    assert offered == frozenset(ALL_TOOLS)


def test_only_the_client_module_mentions_the_send_tool():
    src = Path(__file__).resolve().parents[1] / "src" / "pulse"
    mentions = {
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if SEND_TOOL in path.read_text(encoding="utf-8")
    }
    assert mentions == {"mcp/client.py"}  # and there only as the forbidden-tool constant


def test_server_is_launched_from_its_own_directory_with_quiet_dotenv(tmp_path):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.js").write_text("", encoding="utf-8")
    config = make_config(server_dir=tmp_path, command="python")

    params = McpClient(config)._launch_params()

    assert Path(params.cwd) == tmp_path  # so the server reads its own .env and tokens.json
    assert params.args == [str(tmp_path / "dist" / "index.js")]
    assert params.env == {"DOTENV_CONFIG_QUIET": "true"}  # keeps its banner off the protocol pipe


@pytest.mark.parametrize(
    "code",
    [
        "GOOGLE_AUTH_REQUIRED",
        "GOOGLE_TOKEN_REFRESH_FAILED",
        "INSUFFICIENT_SCOPE",
        "AUTH_NOT_CONFIGURED",
        "DOC_PERMISSION_DENIED",
        "DOC_NOT_FOUND",
        "INVALID_INPUT",
        "PAYLOAD_TOO_LARGE",
        "GOOGLE_RATE_LIMITED",
    ],
)
def test_rejections_made_before_any_write_are_classed_as_not_applied(code):
    assert write_not_applied(McpToolError("t", code, "m", False)) is True


@pytest.mark.parametrize(
    "code",
    ["DOC_APPEND_FAILED", "GMAIL_DRAFT_CREATE_FAILED", "GOOGLE_API_UNAVAILABLE", "WHO_KNOWS"],
)
def test_server_failures_that_may_have_written_are_ambiguous(code):
    assert write_not_applied(McpToolError("t", code, "m", True)) is False


def test_timeouts_and_odd_responses_are_ambiguous():
    assert write_not_applied(OutcomeUnknown("timed out")) is False
    assert write_not_applied(RuntimeError("anything else")) is False


def test_setup_and_allowlist_failures_never_reached_the_server():
    assert write_not_applied(McpSetupError("no server")) is True
    assert write_not_applied(ToolNotAllowed("nope")) is True
