import json
import re
from datetime import date
from pathlib import Path

import pytest

from fakes import FakeLLM
from pulse.models import Review
from pulse.prompts import load_prompt
from pulse.theming import (
    OTHER,
    AssignmentCache,
    ThemingStats,
    assign_themes,
    enforce_theme_cap,
    taxonomy_hash,
    theme_id_for,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = ["Onboarding and KYC", "Payments and Withdrawals", "App Performance"]
PROMPT = load_prompt("theme_assign", REPO_ROOT / "prompts")
KEYWORDS = {
    "kyc": "Onboarding and KYC",
    "withdraw": "Payments and Withdrawals",
    "freeze": "App Performance",
}


def _review(i: int, text: str) -> Review:
    return Review(f"r{i:03d}", "play", 3, "", text, date(2026, 9, 1))


def _payload(user: str) -> list[dict]:
    return json.loads(re.search(r"<reviews>\n(.*)\n</reviews>", user, re.DOTALL).group(1))


def keyword_llm(overrides=None, drop=()):
    """Fake model: labels by keyword. `overrides` maps review_id -> label; `drop` skips ids."""

    def handler(task, system, user):
        out = []
        for item in _payload(user):
            if item["review_id"] in drop:
                continue
            label = next((v for k, v in KEYWORDS.items() if k in item["text"]), "Other")
            out.append(
                {
                    "review_id": item["review_id"],
                    "theme": (overrides or {}).get(item["review_id"], label),
                }
            )
        return {"assignments": out}

    return FakeLLM(handler)


def _run(reviews, llm, **kwargs):
    defaults = {
        "taxonomy": TAXONOMY,
        "prompt": PROMPT,
        "model": "m",
        "batch_size": 40,
        "max_themes": 5,
    }
    return assign_themes(reviews, llm=llm, **{**defaults, **kwargs})


REVIEWS = [
    _review(1, "kyc pending"),
    _review(2, "withdraw stuck"),
    _review(3, "app will freeze"),
    _review(4, "love it"),
]


def test_assigns_each_review_once_and_builds_themes():
    result = _run(REVIEWS, keyword_llm())
    by_review = {a.review_id: a.theme_id for a in result.assignments}
    assert by_review == {
        "r001": "onboarding-and-kyc",
        "r002": "payments-and-withdrawals",
        "r003": "app-performance",
        "r004": "other",
    }
    assert [t.label for t in result.themes] == [*TAXONOMY, OTHER]
    assert result.counts()["other"] == 1


def test_themes_without_reviews_are_omitted():
    result = _run([_review(1, "kyc pending"), _review(2, "kyc again")], keyword_llm())
    assert [t.label for t in result.themes] == ["Onboarding and KYC"]


def test_batches_by_batch_size_with_stable_order():
    reviews = [_review(i, "kyc") for i in range(7)]
    llm = keyword_llm()
    _run(reviews, llm, batch_size=3)
    sizes = [len(_payload(user)) for _, _, user in llm.calls]
    assert sizes == [3, 3, 1]
    assert [i["review_id"] for i in _payload(llm.calls[0][2])] == ["r000", "r001", "r002"]


def test_unknown_label_maps_to_other_and_is_counted():
    llm = keyword_llm(overrides={"r001": "Made Up Theme"})
    result = _run(REVIEWS, llm)
    assert {a.review_id: a.theme_id for a in result.assignments}["r001"] == "other"
    assert result.stats.unknown_labels == 1


def test_label_match_ignores_case_and_whitespace():
    llm = keyword_llm(overrides={"r004": "  app performance "})
    result = _run(REVIEWS, llm)
    assert {a.review_id: a.theme_id for a in result.assignments}["r004"] == "app-performance"


def test_skipped_reviews_are_reasked_once_then_defaulted_to_other():
    llm = keyword_llm(drop={"r002"})
    result = _run(REVIEWS, llm)
    assert result.stats.llm_calls == 2  # initial + one re-ask
    assert len(_payload(llm.calls[1][2])) == 1
    assert {a.review_id: a.theme_id for a in result.assignments}["r002"] == "other"
    assert result.stats.missing_after_retry == 1


def test_extra_and_duplicate_ids_from_the_model_are_ignored():
    def handler(task, system, user):
        ids = [i["review_id"] for i in _payload(user)]
        rows = [{"review_id": i, "theme": TAXONOMY[0]} for i in ids]
        return {
            "assignments": [
                *rows,
                {"review_id": "ghost", "theme": TAXONOMY[1]},
                {"review_id": ids[0], "theme": TAXONOMY[2]},
            ]
        }

    result = _run(REVIEWS, FakeLLM(handler))
    assert len(result.assignments) == 4
    assert {a.theme_id for a in result.assignments} == {"onboarding-and-kyc"}


def test_cache_prevents_repeat_calls_and_keeps_labels_stable(tmp_path):
    path = tmp_path / "cache.json"
    namespace = taxonomy_hash(TAXONOMY, PROMPT.version, "m")
    first = _run(REVIEWS, keyword_llm(), cache=AssignmentCache(path, namespace))
    assert first.stats.llm_calls == 1

    flipping = keyword_llm(overrides={"r001": "App Performance"})  # would flip r001 if asked again
    second = _run(REVIEWS, flipping, cache=AssignmentCache(path, namespace))
    assert second.stats.llm_calls == 0 and second.stats.cache_hits == 4
    assert second.assignments == first.assignments


def test_cache_is_invalidated_by_taxonomy_prompt_or_model_change(tmp_path):
    path = tmp_path / "cache.json"
    AssignmentCache(path, taxonomy_hash(TAXONOMY, PROMPT.version, "m")).put_many({"r001": "Other"})
    assert (
        AssignmentCache(path, taxonomy_hash(TAXONOMY, PROMPT.version, "m")).get("r001") == "Other"
    )
    assert (
        AssignmentCache(path, taxonomy_hash([*TAXONOMY, "New"], PROMPT.version, "m")).get("r001")
        is None
    )
    assert AssignmentCache(path, taxonomy_hash(TAXONOMY, "theme_assign@2", "m")).get("r001") is None
    assert (
        AssignmentCache(path, taxonomy_hash(TAXONOMY, PROMPT.version, "other-model")).get("r001")
        is None
    )


def test_corrupt_cache_file_is_ignored(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("{not json", encoding="utf-8")
    assert AssignmentCache(path, "ns").get("r001") is None


def test_prompt_payload_has_review_data_only():
    llm = keyword_llm()
    _run(REVIEWS, llm)
    [item, *_] = _payload(llm.calls[0][2])
    assert set(item) == {"review_id", "rating", "title", "text"}


def test_long_text_is_truncated_in_the_prompt():
    llm = keyword_llm()
    _run([_review(1, "kyc " + "x" * 5000)], llm)
    assert len(_payload(llm.calls[0][2])[0]["text"]) == 600


# --- cap enforcement (architecture 4.3: enforced in code, whatever the model returned) ---


def test_cap_folds_smallest_themes_into_other_when_other_exists():
    labels = {
        f"r{i}": label
        for i, label in enumerate(
            ["A"] * 5 + ["B"] * 4 + ["C"] * 3 + ["D"] * 2 + ["E"] * 1 + [OTHER] * 6
        )
    }
    stats = ThemingStats()
    capped = enforce_theme_cap(labels, 5, stats)
    assert set(capped.values()) == {"A", "B", "C", "D", OTHER}
    assert stats.merged_into_other == ["E"]


def test_cap_creates_other_by_folding_two_when_absent():
    labels = {
        f"r{i}": label
        for i, label in enumerate(
            ["A"] * 5 + ["B"] * 4 + ["C"] * 3 + ["D"] * 2 + ["E"] * 1 + ["F"] * 1
        )
    }
    capped = enforce_theme_cap(labels, 5)
    assert len(set(capped.values())) == 5
    assert set(capped.values()) == {"A", "B", "C", "D", OTHER}
    assert sum(1 for v in capped.values() if v == OTHER) == 2


def test_cap_leaves_small_sets_alone():
    labels = {"r1": "A", "r2": "B"}
    assert enforce_theme_cap(labels, 5) == labels


def test_cap_applies_end_to_end_even_if_taxonomy_plus_other_exceeds_it():
    taxonomy = [f"T{i}" for i in range(5)]
    reviews = [_review(i, f"text {i}") for i in range(12)]

    def handler(task, system, user):
        return {
            "assignments": [
                {
                    "review_id": i["review_id"],
                    "theme": taxonomy[int(i["review_id"][1:]) % 5]
                    if int(i["review_id"][1:]) < 10
                    else "Other",
                }
                for i in _payload(user)
            ]
        }

    result = _run(reviews, FakeLLM(handler), taxonomy=taxonomy, max_themes=5)
    assert len(result.themes) <= 5
    assert len({a.theme_id for a in result.assignments}) <= 5


def test_other_is_reserved_in_taxonomy():
    with pytest.raises(ValueError, match="reserved"):
        _run(REVIEWS, keyword_llm(), taxonomy=[*TAXONOMY, "other"])


def test_no_reviews_rejected():
    with pytest.raises(ValueError, match="No reviews"):
        _run([], keyword_llm())


def test_theme_id_slug():
    assert (
        theme_id_for("Trading Experience & App Performance") == "trading-experience-app-performance"
    )
