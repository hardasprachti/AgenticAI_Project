"""The golden set: the fixture reviews plus what we know about them (architecture section 8.2).

The labels come from `generate_reviews.py`, which records the intended theme of every synthetic
review. They are ground truth for the fixture, not human judgement, so agreement against them
measures whether the model recovers the structure that was written into the data.
"""

from __future__ import annotations

import csv
import functools
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from pulse.pii import find_pii
from pulse.sanitize import anonymous_review_id
from pulse.theming import theme_id_for

FIXTURES = Path(__file__).parent / "fixtures"

# Fixture label -> the taxonomy label it stands for. Labels not listed here
# ("injection", "dropped", "out_of_window") are not scored for theme agreement.
LABEL_TO_THEME = {
    "kyc": "Onboarding and KYC",
    "pay": "Payments and Withdrawals",
    "perf": "Trading Experience and App Performance",
    "stmt": "Statements and Reports",
    "support": "Customer Support",
    "other": "Other",
}

_NAME_WORD_RE = re.compile(r"[^\W\d_]{4,}")
MIN_SEEDED_LEN = 4  # shorter strings are too likely to match innocent text


@dataclass
class ThemeAgreement:
    accuracy: float
    evaluated: int
    per_theme_recall: dict[str, float] = field(default_factory=dict)


@dataclass
class GoldenSet:
    rows: list[dict[str, str]]
    labels: dict[str, str]  # fixture review id -> label

    @classmethod
    def load(
        cls,
        reviews: Path = FIXTURES / "reviews.csv",
        labels: Path = FIXTURES / "reviews_labels.csv",
    ) -> GoldenSet:
        with reviews.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        with labels.open(encoding="utf-8", newline="") as handle:
            label_map = {r["review_id"]: r["theme"] for r in csv.DictReader(handle)}
        return cls(rows=rows, labels=label_map)

    # --- what was seeded into the raw data ---

    @functools.cached_property
    def seeded_pii_strings(self) -> set[str]:
        """Identifiers that must never reach an output: raw ids, and every PII-looking value
        (emails, phones, long ids, URLs) found in the raw review text."""
        found: set[str] = set()
        for row in self.rows:
            if row.get("author_id"):
                found.add(row["author_id"])
            for match in find_pii(f"{row.get('title', '')} {row['text']}"):
                found.add(match.text)
        return {s for s in found if len(s) >= MIN_SEEDED_LEN}

    @functools.cached_property
    def seeded_name_words(self) -> set[str]:
        """Reviewer names: full names and each name word of 4+ letters."""
        names: set[str] = set()
        for row in self.rows:
            name = (row.get("author_name") or "").strip()
            if name:
                names.add(name)
                names.update(_NAME_WORD_RE.findall(name))
        return names

    def injected_texts(self) -> list[str]:
        return [r["text"] for r in self.rows if self.labels.get(r["review_id"]) == "injection"]

    @functools.cached_property
    def injected_review_ids(self) -> set[str]:
        """Anonymous ids (as they appear in pipeline output) of the injection-attempt reviews."""
        return {
            anonymous_review_id("play", r["review_id"])
            for r in self.rows
            if self.labels.get(r["review_id"]) == "injection"
        }

    # --- theme agreement ---

    @functools.cached_property
    def expected_theme_ids(self) -> dict[str, str]:
        """Anonymous review id -> the theme id the review was written to belong to."""
        return {
            anonymous_review_id("play", fixture_id): theme_id_for(LABEL_TO_THEME[label])
            for fixture_id, label in self.labels.items()
            if label in LABEL_TO_THEME
        }

    def theme_agreement(self, assignments: list[dict[str, str]]) -> ThemeAgreement:
        """Share of scoreable reviews whose assigned theme matches the label.

        Only reviews that survived sanitizing are scored (they are the ones in `assignments`).
        """
        expected = self.expected_theme_ids
        total = Counter[str]()
        correct = Counter[str]()
        by_theme: dict[str, list[bool]] = defaultdict(list)
        for item in assignments:
            want = expected.get(item["review_id"])
            if want is None:
                continue
            hit = item["theme_id"] == want
            total["all"] += 1
            correct["all"] += hit
            by_theme[want].append(hit)
        evaluated = total["all"]
        return ThemeAgreement(
            accuracy=correct["all"] / evaluated if evaluated else 0.0,
            evaluated=evaluated,
            per_theme_recall={t: sum(v) / len(v) for t, v in sorted(by_theme.items())},
        )
