"""Create the weekly Gmail draft (architecture section 4.8). Never sends.

Only draft creation is reachable: the client has no send operation and its allowlist blocks the
server's send tool.
"""

from __future__ import annotations

from dataclasses import dataclass

from pulse.mcp.client import McpClient
from pulse.mcp.docs import PublishVerificationError
from pulse.models import Pulse
from pulse.render import count_words, email_subject, render_email_body

# The 250-word limit is for the note itself; the greeting and link around it get a few extra lines.
EMAIL_WRAPPER_WORDS = 40
DEFAULT_MAX_BODY_BYTES = 1_048_576  # the server's MAX_EMAIL_BODY_BYTES default


@dataclass(frozen=True)
class DraftResult:
    draft_id: str
    thread_id: str | None
    subject: str
    pointer_only: bool  # True when the body fell back to the three themes plus the Doc link


async def create_weekly_draft(
    client: McpClient,
    pulse: Pulse,
    *,
    draft_to: str | None,
    doc_link: str,
    max_words: int = 250,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
) -> DraftResult:
    """Draft the note plus the Doc link; if that is too long, the themes plus the link."""
    if not draft_to:
        raise ValueError(
            "draft_to is not set in config.yaml; there is nobody to address the draft to"
        )

    body = render_email_body(pulse, doc_link)
    pointer_only = (
        len(body.encode("utf-8")) > max_body_bytes
        or count_words(body) > max_words + EMAIL_WRAPPER_WORDS
    )
    if pointer_only:
        body = render_email_body(pulse, doc_link, pointer_only=True)

    subject = email_subject(pulse.week_label)
    response = await client.create_draft(to=[draft_to], subject=subject, body=body)

    if response.get("status") != "draft_created" or not response.get("draftId"):
        raise PublishVerificationError(
            f"Expected status 'draft_created' with a draftId from Gmail, got "
            f"status={response.get('status')!r}, draftId={response.get('draftId')!r}"
        )
    return DraftResult(
        draft_id=str(response["draftId"]),
        thread_id=response.get("threadId"),
        subject=subject,
        pointer_only=pointer_only,
    )
