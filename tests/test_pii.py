import pytest

from pulse.pii import REDACTED, find_pii, scrub


@pytest.mark.parametrize(
    "text, kind",
    [
        ("mail me at john.doe@gmail.com please", "email"),
        ("send money to rahul@okhdfcbank", "email"),  # UPI id
        ("see https://groww.in/help/kyc for details", "url"),
        ("go to www.example.org now", "url"),
        ("check groww.com/support", "url"),
        ("call 9876543210 asap", "number"),
        ("call +91 98765 43210 asap", "number"),
        ("call +91-98765-43210 asap", "number"),
        ("my aadhaar 1234 5678 9012 was rejected", "number"),
        ("card 4111 1111 1111 1111 declined", "number"),
        ("PAN ABCDE1234F is linked", "pan"),
        ("order 3f2a9c1b-7d4e-4a8b-9c3d-1e2f3a4b5c6d failed", "uuid"),
        ("device a1b2c3d4e5f6a7b8 crashed", "id_token"),
        ("ref TXN12345678AB pending", "id_token"),
        ("ping @rahul_k on twitter", "handle"),
    ],
)
def test_scrub_removes_pii(text, kind):
    cleaned, counts = scrub(text)
    assert REDACTED in cleaned
    assert counts[kind] >= 1
    assert find_pii(cleaned) == []


@pytest.mark.parametrize(
    "text",
    [
        "The app is slow during market open",
        "Lost 150000 rupees in one day",  # 6 digits: an amount, not an id
        "Charged 1,25,000 as brokerage",
        "Updated on 2026-07-28 and again 05/10/2026",
        "Between 28 Jul - 5 Oct 2026 it crashed 14 times",
        "Version 5.4.2 is worse than 5.3.9",
        "Rated 1 star, 2 stars, 5 stars",
    ],
)
def test_scrub_leaves_ordinary_text_alone(text):
    cleaned, counts = scrub(text)
    assert cleaned == text
    assert not counts
    assert find_pii(text) == []


def test_find_pii_ignores_existing_placeholders():
    assert find_pii(f"contact {REDACTED} for help") == []


def test_find_pii_reports_remaining_pii():
    kinds = {m.kind for m in find_pii("write to a@b.com or call 9876543210")}
    assert {"email", "number"} <= kinds


def test_email_domain_not_double_matched_as_url():
    cleaned, counts = scrub("a@b.com")
    assert cleaned == REDACTED
    assert counts["email"] == 1
    assert counts["url"] == 0
