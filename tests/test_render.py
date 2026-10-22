import json
from datetime import date

from pulse.models import Run, RunStatus, to_jsonable
from pulse.render import (
    count_words,
    email_subject,
    format_date_range,
    render_doc_body,
    render_email_body,
    render_note,
)


def test_note_has_all_required_sections(valid_pulse):
    note = render_note(valid_pulse)
    assert note.startswith("Groww Weekly Review Pulse - 2026-W37")
    for heading in ("Top themes", "What users said", "Action ideas"):
        assert heading in note
    assert "1. Onboarding and KYC (35% of reviews): Verification is taking too long." in note
    assert '- "Withdrawal to my bank took four days" (2 stars, Payments and Withdrawals)' in note
    assert "3. Load-test the app at market open and cache the watchlist. [App Performance]" in note


def test_note_contains_every_quote_verbatim(valid_pulse):
    note = render_note(valid_pulse)
    for quote in valid_pulse.quotes:
        assert quote.text in note


def test_render_is_deterministic(valid_pulse):
    assert render_note(valid_pulse) == render_note(valid_pulse)


def test_doc_body_is_the_note(valid_pulse):
    assert render_doc_body(valid_pulse) == render_note(valid_pulse)


def test_valid_pulse_is_well_under_word_limit(valid_pulse):
    assert count_words(render_note(valid_pulse)) <= 250


def test_single_star_wording(valid_pulse):
    from dataclasses import replace

    valid_pulse.quotes[0] = replace(valid_pulse.quotes[0], rating=1)
    assert "(1 star," in render_note(valid_pulse)


def test_date_ranges():
    assert format_date_range(date(2026, 7, 6), date(2026, 9, 13)) == "6 Jul - 13 Sep 2026"
    assert format_date_range(date(2025, 12, 29), date(2026, 3, 8)) == "29 Dec 2025 - 8 Mar 2026"


def test_titles(valid_pulse):
    assert render_note(valid_pulse).splitlines()[0] == "Groww Weekly Review Pulse - 2026-W37"
    assert email_subject("2026-W37") == "Groww Weekly Review Pulse - 2026-W37"


def test_email_body_includes_note_and_link(valid_pulse):
    body = render_email_body(valid_pulse, "https://docs.example/abc")
    assert render_note(valid_pulse).rstrip("\n") in body
    assert body.rstrip().endswith("Full pulse: https://docs.example/abc")


def test_email_body_without_link(valid_pulse):
    assert "Full pulse:" not in render_email_body(valid_pulse)


def test_email_pointer_only_has_themes_and_link_but_no_quotes(valid_pulse):
    body = render_email_body(valid_pulse, "https://docs.example/abc", pointer_only=True)
    assert "Onboarding and KYC (35% of reviews)" in body
    assert "https://docs.example/abc" in body
    assert "What users said" not in body
    assert valid_pulse.quotes[0].text not in body


def test_run_record_serializes_to_json():
    run = Run(run_id="r1", week_label="2026-W37", status=RunStatus.PARTIAL)
    run.theme_scores = {"kyc": {"volume": 0.35}}
    data = json.loads(json.dumps(to_jsonable(run)))
    assert data["status"] == "partial"
    assert data["theme_scores"]["kyc"]["volume"] == 0.35
