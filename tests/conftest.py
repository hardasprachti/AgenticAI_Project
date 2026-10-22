from datetime import date

import pytest

from pulse.models import Action, Pulse, Quote, Review, ThemeSummary


@pytest.fixture
def reviews() -> list[Review]:
    def make(rid: str, rating: int, title: str, text: str, day: int) -> Review:
        return Review(
            review_id=rid,
            store="play",
            rating=rating,
            title=title,
            text=text,
            date=date(2026, 9, day),
        )

    return [
        make("r1", 1, "KYC stuck", "My KYC verification has been pending for ten days now.", 1),
        make("r2", 2, "Withdrawal slow", "Withdrawal to my bank took four days, no updates.", 2),
        make("r3", 3, "Laggy", "The app freezes when the market opens in the morning.", 3),
        make("r4", 5, "Great", "Love the clean design and easy mutual fund SIP setup.", 4),
        make("r5", 1, "Support", "Customer care never replies to my tickets.", 5),
        make("r6", 4, "Statements", "Please add a downloadable capital gains statement.", 6),
    ]


@pytest.fixture
def valid_pulse() -> Pulse:
    return Pulse(
        week_label="2026-W37",
        window_start=date(2026, 7, 6),
        window_end=date(2026, 9, 13),
        review_count=6,
        themes=[
            ThemeSummary("kyc", "Onboarding and KYC", "Verification is taking too long.", 0.35),
            ThemeSummary("pay", "Payments and Withdrawals", "Payouts are slow, no status.", 0.30),
            ThemeSummary("perf", "App Performance", "Freezes at market open.", 0.20),
        ],
        quotes=[
            Quote("My KYC verification has been pending for ten days now.", "kyc", 1, "r1"),
            Quote("Withdrawal to my bank took four days", "pay", 2, "r2"),
            Quote("The app freezes when the market opens", "perf", 3, "r3"),
        ],
        actions=[
            Action("Add a live KYC status tracker with an expected completion date.", "kyc"),
            Action("Show withdrawal progress and send a push update when funds are sent.", "pay"),
            Action("Load-test the app at market open and cache the watchlist.", "perf"),
        ],
    )
