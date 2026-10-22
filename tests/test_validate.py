import dataclasses

from pulse.models import Action, Quote, Theme, ThemeSummary
from pulse.validate import (
    ViolationCode,
    format_violations,
    normalize_for_match,
    validate_pulse,
    validate_text_pii,
    validate_theme_cap,
)


def codes(violations):
    return [v.code for v in violations]


def test_valid_pulse_passes(valid_pulse, reviews):
    assert validate_pulse(valid_pulse, reviews) == []


# --- theme cap (clustering stage) ---------------------------------------------------------------


def test_six_themes_exceed_cap():
    themes = [Theme(f"t{i}", f"Theme {i}") for i in range(6)]
    assert codes(validate_theme_cap(themes)) == [ViolationCode.THEME_CAP_EXCEEDED]


def test_five_themes_ok():
    themes = [Theme(f"t{i}", f"Theme {i}") for i in range(5)]
    assert validate_theme_cap(themes) == []


# --- counts ---------------------------------------------------------------------------------------


def test_wrong_theme_count(valid_pulse, reviews):
    valid_pulse.themes = valid_pulse.themes[:2]
    # The dropped theme's quote and action now point outside the top themes too.
    found = codes(validate_pulse(valid_pulse, reviews))
    assert ViolationCode.THEME_COUNT in found


def test_wrong_quote_count(valid_pulse, reviews):
    valid_pulse.quotes = valid_pulse.quotes[:2]
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.QUOTE_COUNT]


def test_wrong_action_count(valid_pulse, reviews):
    valid_pulse.actions = valid_pulse.actions + [Action("Extra idea", "kyc")]
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.ACTION_COUNT]


def test_duplicate_theme(valid_pulse, reviews):
    valid_pulse.themes[1] = dataclasses.replace(valid_pulse.themes[1], theme_id="kyc")
    assert ViolationCode.THEME_DUPLICATE in codes(validate_pulse(valid_pulse, reviews))


def test_theme_share_out_of_range(valid_pulse, reviews):
    valid_pulse.themes[0] = dataclasses.replace(valid_pulse.themes[0], share=1.4)
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.THEME_SHARE_INVALID]


# --- quotes ---------------------------------------------------------------------------------------


def test_invented_quote_is_rejected(valid_pulse, reviews):
    valid_pulse.quotes[0] = Quote("Groww is the worst app ever made", "kyc", 1, "r1")
    violations = validate_pulse(valid_pulse, reviews)
    assert codes(violations) == [ViolationCode.QUOTE_NOT_VERBATIM]
    assert "quote 1" in str(violations[0])


def test_paraphrased_quote_is_rejected(valid_pulse, reviews):
    valid_pulse.quotes[1] = Quote("Withdrawal took 4 days to reach my bank", "pay", 2, "r2")
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.QUOTE_NOT_VERBATIM]


def test_quote_match_ignores_case_whitespace_and_curly_quotes(valid_pulse, reviews):
    valid_pulse.quotes[0] = Quote("MY  KYC verification\nhas been pending", "kyc", 1, "r1")
    assert validate_pulse(valid_pulse, reviews) == []
    assert normalize_for_match("It’s  “fine”") == 'it\'s "fine"'


def test_quote_may_come_from_title(valid_pulse, reviews):
    reviews[0] = dataclasses.replace(reviews[0], title="KYC stuck for days now")
    valid_pulse.quotes[0] = Quote("KYC stuck for days", "kyc", 1, "r1")
    assert validate_pulse(valid_pulse, reviews) == []


def test_quote_cannot_span_title_and_text(valid_pulse, reviews):
    # Title is "KYC stuck"; text starts "My KYC verification". Joining them is not verbatim.
    valid_pulse.quotes[0] = Quote("KYC stuck My KYC verification", "kyc", 1, "r1")
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.QUOTE_NOT_VERBATIM]


def test_quote_from_unknown_review(valid_pulse, reviews):
    valid_pulse.quotes[0] = Quote("My KYC verification has been pending", "kyc", 1, "nope")
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.QUOTE_UNKNOWN_REVIEW]


def test_empty_quote_is_not_treated_as_verbatim(valid_pulse, reviews):
    valid_pulse.quotes[0] = Quote("   ", "kyc", 1, "r1")
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.QUOTE_TOO_SHORT]


def test_quote_rating_must_match_review(valid_pulse, reviews):
    valid_pulse.quotes[0] = dataclasses.replace(valid_pulse.quotes[0], rating=5)
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.QUOTE_RATING_MISMATCH]


def test_duplicate_quote(valid_pulse, reviews):
    valid_pulse.quotes[1] = dataclasses.replace(
        valid_pulse.quotes[0], text=valid_pulse.quotes[0].text.upper()
    )
    assert ViolationCode.QUOTE_DUPLICATE in codes(validate_pulse(valid_pulse, reviews))


def test_quote_tagged_with_non_top_theme(valid_pulse, reviews):
    valid_pulse.quotes[2] = dataclasses.replace(valid_pulse.quotes[2], theme_id="support")
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.QUOTE_THEME_NOT_TOP]


# --- actions --------------------------------------------------------------------------------------


def test_action_tied_to_non_top_theme(valid_pulse, reviews):
    valid_pulse.actions[0] = Action("Hire more support agents.", "support")
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.ACTION_THEME_NOT_TOP]


def test_empty_action(valid_pulse, reviews):
    valid_pulse.actions[0] = Action("  ", "kyc")
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.ACTION_EMPTY]


# --- word limit -----------------------------------------------------------------------------------


def test_note_over_250_words_is_rejected(valid_pulse, reviews):
    padding = " ".join(["word"] * 240)
    valid_pulse.themes[0] = dataclasses.replace(valid_pulse.themes[0], summary=padding)
    violations = validate_pulse(valid_pulse, reviews)
    assert codes(violations) == [ViolationCode.WORD_LIMIT]
    assert "over the 250-word limit" in str(violations[0])


def test_note_at_the_limit_passes(valid_pulse, reviews):
    from pulse.render import count_words, render_note

    base = count_words(render_note(valid_pulse))
    filler = " ".join(["word"] * (250 - base))
    valid_pulse.themes[0] = dataclasses.replace(
        valid_pulse.themes[0], summary=valid_pulse.themes[0].summary + " " + filler
    )
    assert count_words(render_note(valid_pulse)) == 250
    assert validate_pulse(valid_pulse, reviews) == []

    valid_pulse.themes[0] = dataclasses.replace(
        valid_pulse.themes[0], summary=valid_pulse.themes[0].summary + " one"
    )
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.WORD_LIMIT]


def test_max_words_is_configurable(valid_pulse, reviews):
    assert codes(validate_pulse(valid_pulse, reviews, max_words=50)) == [ViolationCode.WORD_LIMIT]


# --- PII ------------------------------------------------------------------------------------------


def test_email_in_note_is_rejected(valid_pulse, reviews):
    valid_pulse.actions[0] = Action("Reply to john.doe@gmail.com about KYC delays.", "kyc")
    violations = validate_pulse(valid_pulse, reviews)
    assert codes(violations) == [ViolationCode.PII_DETECTED]
    assert "john.doe" not in str(violations[0])  # never echo the PII itself


def test_phone_number_in_note_is_rejected(valid_pulse, reviews):
    valid_pulse.themes[0] = dataclasses.replace(
        valid_pulse.themes[0], summary="Users call 9876543210 for KYC help."
    )
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.PII_DETECTED]


def test_pii_inside_a_quote_is_caught_even_if_verbatim(valid_pulse, reviews):
    leaky = dataclasses.replace(
        reviews[0], text="Call me on 9876543210 because my KYC has been pending"
    )
    reviews[0] = leaky
    valid_pulse.quotes[0] = Quote("Call me on 9876543210 because my KYC", "kyc", 1, "r1")
    assert codes(validate_pulse(valid_pulse, reviews)) == [ViolationCode.PII_DETECTED]


def test_author_name_in_note_is_rejected(valid_pulse, reviews):
    valid_pulse.actions[0] = Action("Ask Priya Nair to review the KYC flow.", "kyc")
    violations = validate_pulse(valid_pulse, reviews, known_author_names=["Priya Nair"])
    assert codes(violations) == [ViolationCode.AUTHOR_NAME_LEAK]


def test_author_name_check_is_word_bounded(valid_pulse, reviews):
    # "Nair" must not trigger on "Nairobi"; names only match as whole words.
    valid_pulse.actions[0] = Action("Expand support hours for Nairobi users.", "kyc")
    assert validate_pulse(valid_pulse, reviews, known_author_names=["Nair"]) == []


def test_validate_text_pii_clean_text():
    assert validate_text_pii("The KYC flow is slow.") == []


def test_redacted_placeholders_do_not_count_as_pii(valid_pulse, reviews):
    reviews[0] = dataclasses.replace(
        reviews[0], text="My KYC for [redacted] has been pending for ten days now."
    )
    valid_pulse.quotes[0] = Quote("My KYC for [redacted] has been pending", "kyc", 1, "r1")
    assert validate_pulse(valid_pulse, reviews) == []


# --- reporting ------------------------------------------------------------------------------------


def test_multiple_violations_are_all_reported(valid_pulse, reviews):
    valid_pulse.quotes[0] = Quote("completely made up words here", "kyc", 1, "r1")
    valid_pulse.actions[1] = Action("Fix it.", "nope")
    found = codes(validate_pulse(valid_pulse, reviews))
    assert ViolationCode.QUOTE_NOT_VERBATIM in found
    assert ViolationCode.ACTION_THEME_NOT_TOP in found


def test_format_violations_for_retry_feedback(valid_pulse, reviews):
    valid_pulse.quotes[0] = Quote("completely made up words here", "kyc", 1, "r1")
    text = format_violations(validate_pulse(valid_pulse, reviews))
    assert text.startswith("- [quote_not_verbatim] quote 1")


def test_validation_does_not_mutate_pulse(valid_pulse, reviews):
    before = dataclasses.replace(valid_pulse)
    validate_pulse(valid_pulse, reviews)
    assert valid_pulse == before
    assert isinstance(valid_pulse.themes[0], ThemeSummary)
