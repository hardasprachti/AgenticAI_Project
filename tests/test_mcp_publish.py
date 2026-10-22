import asyncio

import pytest

from fake_mcp import (
    DOC_ID,
    DOC_TOOL,
    DRAFT_TOOL,
    SEND_TOOL,
    FakeGoogleServer,
    make_config,
    run_with_client,
)
from pulse.mcp.client import McpClient, McpToolError
from pulse.mcp.docs import PublishVerificationError, append_note, doc_url
from pulse.mcp.gmail import create_weekly_draft
from pulse.render import email_subject, render_note

DRAFT_TO = "me@example.com"


def test_doc_url_is_built_from_the_document_id():
    assert doc_url("abc") == "https://docs.google.com/document/d/abc/edit"


def test_append_note_adds_a_blank_line_separated_section_and_verifies_the_response(valid_pulse):
    fake = FakeGoogleServer()
    note = render_note(valid_pulse)

    result = run_with_client(fake, lambda c: append_note(c, note))

    assert fake.doc_text == "\n" + note
    assert result.document_id == DOC_ID
    assert result.characters_appended == len("\n" + note)
    assert result.revision_id
    assert result.url == doc_url(DOC_ID)


def test_two_weekly_notes_are_separated_by_a_blank_line(valid_pulse):
    fake = FakeGoogleServer()
    note = render_note(valid_pulse)

    async def twice(client):
        await append_note(client, note)
        await append_note(client, note)

    run_with_client(fake, twice)

    assert fake.doc_text.count("Groww Weekly Review Pulse - 2026-W37") == 2
    assert note + "\n" + note in fake.doc_text


def test_append_with_wrong_character_count_is_a_verification_failure(valid_pulse):
    fake = FakeGoogleServer()
    fake.chars_delta = -5

    with pytest.raises(PublishVerificationError, match="characters"):
        run_with_client(fake, lambda c: append_note(c, render_note(valid_pulse)))


def test_append_to_a_different_document_is_a_verification_failure(valid_pulse):
    fake = FakeGoogleServer()
    fake.document_id_override = "some-other-doc"

    with pytest.raises(PublishVerificationError, match="document"):
        run_with_client(fake, lambda c: append_note(c, render_note(valid_pulse)))


def test_append_with_unexpected_status_is_a_verification_failure(valid_pulse):
    fake = FakeGoogleServer()

    async def main():
        async with McpClient(make_config(), transport=fake.server) as client:

            async def wrong_status(*_a, **_k):
                return {"ok": True, "status": "queued", "documentId": DOC_ID}

            client.append_to_document = wrong_status
            await append_note(client, render_note(valid_pulse))

    with pytest.raises(PublishVerificationError, match="appended"):
        asyncio.run(main())


def test_append_errors_propagate_without_a_second_call(valid_pulse):
    fake = FakeGoogleServer()
    fake.fail(DOC_TOOL, "DOC_PERMISSION_DENIED")

    with pytest.raises(McpToolError):
        run_with_client(fake, lambda c: append_note(c, render_note(valid_pulse)))
    assert len(fake.calls_to(DOC_TOOL)) == 1


def test_draft_is_created_for_the_recipient_with_note_and_link(valid_pulse):
    fake = FakeGoogleServer()
    url = doc_url(DOC_ID)

    result = run_with_client(
        fake, lambda c: create_weekly_draft(c, valid_pulse, draft_to=DRAFT_TO, doc_link=url)
    )

    assert result.draft_id == "draft-1"
    assert result.thread_id == "thread-1"
    (sent,) = fake.calls_to(DRAFT_TOOL)
    assert sent["to"] == [DRAFT_TO]
    assert sent["subject"] == email_subject("2026-W37")
    assert sent["bodyType"] == "text"
    assert render_note(valid_pulse).rstrip("\n") in sent["body"]
    assert url in sent["body"]
    assert result.pointer_only is False


def test_draft_falls_back_to_themes_and_link_when_the_body_is_too_long(valid_pulse):
    fake = FakeGoogleServer()
    url = doc_url(DOC_ID)

    result = run_with_client(
        fake,
        lambda c: create_weekly_draft(
            c, valid_pulse, draft_to=DRAFT_TO, doc_link=url, max_body_bytes=400
        ),
    )

    (sent,) = fake.calls_to(DRAFT_TOOL)
    assert result.pointer_only is True
    assert url in sent["body"]
    for theme in valid_pulse.themes:
        assert theme.label in sent["body"]
    assert "What users said" not in sent["body"]


def test_draft_without_a_recipient_is_refused_before_any_call(valid_pulse):
    fake = FakeGoogleServer()

    with pytest.raises(ValueError, match="draft_to"):
        run_with_client(
            fake, lambda c: create_weekly_draft(c, valid_pulse, draft_to=None, doc_link="u")
        )
    assert fake.calls == []


def test_draft_response_must_say_draft_created(valid_pulse):
    fake = FakeGoogleServer()

    async def main():
        async with McpClient(make_config(), transport=fake.server) as client:

            async def wrong(*_a, **_k):
                return {"ok": True, "status": "sent", "draftId": "x", "threadId": "t"}

            client.create_draft = wrong
            await create_weekly_draft(client, valid_pulse, draft_to=DRAFT_TO, doc_link="u")

    with pytest.raises(PublishVerificationError, match="draft_created"):
        asyncio.run(main())


def test_publishing_never_calls_the_send_tool(valid_pulse):
    fake = FakeGoogleServer()

    async def both(client):
        await append_note(client, render_note(valid_pulse))
        await create_weekly_draft(client, valid_pulse, draft_to=DRAFT_TO, doc_link=doc_url(DOC_ID))

    run_with_client(fake, both)

    assert fake.calls_to(SEND_TOOL) == []
    assert fake.sent == []
