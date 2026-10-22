"""Test doubles for the LLM layer."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel


class FakeLLM:
    """LLMClient whose replies come from `handler(task, system, user) -> dict`.

    Replies go through the real schema, so a handler that returns the wrong shape fails here the
    same way it would against the live model. Every call is recorded in `calls`.
    """

    def __init__(self, handler: Callable[[str, str, str], dict[str, Any]]) -> None:
        self._handler = handler
        self.calls: list[tuple[str, str, str]] = []

    def complete_json(self, *, task: str, system: str, user: str, schema: type[BaseModel]):
        self.calls.append((task, system, user))
        return schema.model_validate(self._handler(task, system, user))


# --- scripted model behaviour shared by the pipeline and compose tests ---

_THEME_KEYWORDS = [  # first match wins; order matters
    (
        "Customer Support",
        ("support", "customer care", "ticket", "chat bot", "agents", "callback", "escalation"),
    ),
    (
        "Onboarding and KYC",
        (
            "kyc",
            "aadhaar",
            "selfie",
            "e-sign",
            "nominee",
            "signature",
            "account opening",
            "documents",
        ),
    ),
    (
        "Statements and Reports",
        ("statement", "report", "tax", "contract note", "dividend", "itr", "transaction history"),
    ),
    (
        "Payments and Withdrawals",
        (
            "withdraw",
            "upi",
            "payment",
            "payout",
            "refund",
            "money",
            "settlement",
            "funds",
            "debited",
        ),
    ),
    (
        "Trading Experience and App Performance",
        (
            "freez",
            "crash",
            "chart",
            "login",
            "slow",
            "lag",
            "order",
            "watchlist",
            "notification",
            "battery",
            "black screen",
            "stop loss",
        ),
    ),
]


def reviews_in_prompt(user: str) -> list[dict]:
    found = re.search(r"<reviews>\n(.*)\n</reviews>", user, re.DOTALL)
    return json.loads(found.group(1))


def keyword_theme_reply(user: str) -> dict:
    """What a sensible labeler would say for the fixture vocabulary."""
    out = []
    for item in reviews_in_prompt(user):
        text = f"{item['title']} {item['text']}".lower()
        label = next(
            (lab for lab, words in _THEME_KEYWORDS if any(w in text for w in words)), "Other"
        )
        out.append({"review_id": item["review_id"], "theme": label})
    return {"assignments": out}


def candidates_in_prompt(user: str) -> dict[str, list[dict]]:
    found = re.search(r"<candidates>\n(.*)\n</candidates>", user, re.DOTALL)
    return json.loads(found.group(1))


def valid_compose_reply(user: str) -> dict:
    """A well-formed compose reply built from the first candidate of each theme."""
    cands = candidates_in_prompt(user)
    return {
        "themes": [{"theme_id": t, "summary": f"Users report {t} problems."} for t in cands],
        "quotes": [
            {"review_id": c[0]["review_id"], "snippet": " ".join(c[0]["text"].split()[:9])}
            for c in cands.values()
        ],
        "actions": [
            {"theme_id": t, "text": f"Fix the {t} flow with a status tracker."} for t in cands
        ],
    }


def scripted_llm(compose=valid_compose_reply) -> FakeLLM:
    def handler(task: str, system: str, user: str) -> dict:
        if task == "theme_assign":
            return keyword_theme_reply(user)
        if task == "compose":
            return compose(user)
        raise AssertionError(f"unexpected task {task}")

    return FakeLLM(handler)
