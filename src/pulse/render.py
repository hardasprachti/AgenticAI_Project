"""Fixed one-page template for the pulse (architecture section 4.5).

Rendering is deterministic code, not an LLM call, so every week reads the same way and the word
count and PII checks in `validate` run on exactly the text that gets published.

Output is plain text (no Markdown markup) so it displays the same through any Docs or Gmail MCP
server. Dates use "28 Jul - 5 Oct 2026" rather than ISO form so digit runs never look like ids.
"""

from __future__ import annotations

from datetime import date

from pulse.models import Pulse

NOTE_TITLE = "Groww Weekly Review Pulse"
SOURCE_LABEL = "Play Store reviews"


def count_words(text: str) -> int:
    return len(text.split())


def format_date_range(start: date, end: date) -> str:
    def part(d: date, with_year: bool) -> str:
        base = f"{d.day} {d.strftime('%b')}"
        return f"{base} {d.year}" if with_year else base

    if start.year == end.year:
        return f"{part(start, False)} - {part(end, True)}"
    return f"{part(start, True)} - {part(end, True)}"


def email_subject(week_label: str) -> str:
    return f"{NOTE_TITLE} - {week_label}"


def _review_count_phrase(pulse: Pulse) -> str:
    """ "331 Play Store reviews", or with the sample size when only some were analysed."""
    phrase = f"{pulse.review_count:,} {SOURCE_LABEL}"
    if pulse.analysed_count is not None and pulse.analysed_count < pulse.review_count:
        phrase += f" ({pulse.analysed_count:,} analysed)"
    return phrase


def _stars(rating: int) -> str:
    return f"{rating} star" if rating == 1 else f"{rating} stars"


def _theme_labels(pulse: Pulse) -> dict[str, str]:
    return {t.theme_id: t.label for t in pulse.themes}


def render_note(pulse: Pulse) -> str:
    """The one-page note. This is the text that is word-counted and PII-scanned."""
    labels = _theme_labels(pulse)
    lines: list[str] = [
        f"{NOTE_TITLE} - {pulse.week_label}",
        f"{format_date_range(pulse.window_start, pulse.window_end)} | "
        f"{_review_count_phrase(pulse)}",
        "",
        "Top themes",
    ]
    for i, theme in enumerate(pulse.themes, start=1):
        lines.append(f"{i}. {theme.label} ({theme.share:.0%} of reviews): {theme.summary}")

    lines += ["", "What users said"]
    for quote in pulse.quotes:
        label = labels.get(quote.theme_id, quote.theme_id)
        lines.append(f'- "{quote.text}" ({_stars(quote.rating)}, {label})')

    lines += ["", "Action ideas"]
    for i, action in enumerate(pulse.actions, start=1):
        label = labels.get(action.theme_id, action.theme_id)
        lines.append(f"{i}. {action.text} [{label}]")

    return "\n".join(lines) + "\n"


def render_doc_body(pulse: Pulse) -> str:
    """Body for the Google Doc. Its first line is the section heading in the rolling Doc."""
    return render_note(pulse)


def render_email_body(
    pulse: Pulse, doc_url: str | None = None, *, pointer_only: bool = False
) -> str:
    """Body for the Gmail draft.

    By default the full note is included. With `pointer_only=True` (the fallback when the note is
    too long for the draft) only the top theme names and the Doc link are included.
    """
    lines: list[str] = ["Hi,", ""]
    if pointer_only:
        lines.append(f"This week's Groww review pulse ({pulse.week_label}) is ready.")
        lines.append("")
        lines.append("Top themes:")
        for i, theme in enumerate(pulse.themes, start=1):
            lines.append(f"{i}. {theme.label} ({theme.share:.0%} of reviews)")
    else:
        lines.append("Here is this week's Groww review pulse.")
        lines.append("")
        lines.append(render_note(pulse).rstrip("\n"))

    if doc_url:
        lines += ["", f"Full pulse: {doc_url}"]
    return "\n".join(lines) + "\n"
