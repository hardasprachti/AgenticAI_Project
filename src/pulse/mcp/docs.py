"""Append the weekly note to the rolling Google Doc (architecture section 4.7).

The server can append but not create, read or update a Doc, and returns no URL. So each week is a
new section appended to one pre-created Doc, the link is built here, and the only verification
possible is checking the server's own response.
"""

from __future__ import annotations

from dataclasses import dataclass

from pulse.mcp.client import McpClient, McpError


class PublishVerificationError(McpError):
    """The server answered, but not with what we sent. The write probably happened.

    Do not repeat the call; check the Doc / Drafts folder.
    """


@dataclass(frozen=True)
class AppendResult:
    document_id: str
    characters_appended: int
    revision_id: str | None
    url: str


def doc_url(document_id: str) -> str:
    return f"https://docs.google.com/document/d/{document_id}/edit"


async def append_note(client: McpClient, note: str) -> AppendResult:
    """Append `note` as a new section and check the response against what was sent."""
    # The blank-line separator keeps each week readable as its own section. It is part of the
    # content, so the server's character count is for exactly this text (the server adds a leading
    # newline only if the content lacks one, and we always supply it).
    content = "\n" + note
    response = await client.append_to_document(content)

    if response.get("status") != "appended":
        raise PublishVerificationError(
            f"Expected status 'appended' from the Docs append, got {response.get('status')!r}"
        )
    expected_id = client.config.document_id
    if response.get("documentId") != expected_id:
        raise PublishVerificationError(
            f"The append reports document {response.get('documentId')!r}, expected {expected_id!r}"
        )
    if response.get("charactersAppended") != len(content):
        raise PublishVerificationError(
            f"The server reports {response.get('charactersAppended')!r} characters appended, "
            f"but {len(content)} were sent"
        )
    assert expected_id is not None  # McpClient refuses to start without a document id
    return AppendResult(
        document_id=expected_id,
        characters_appended=len(content),
        revision_id=response.get("revisionId"),
        url=doc_url(expected_id),
    )
