import pytest

RUN = "20261022-121514"
THEMES = ["customer-support", "payments-and-withdrawals", "other"]


def review(n: int, **overrides) -> dict:
    row = {
        "review_id": f"rev{n:05d}",
        "store": "play",
        "rating": (n % 5) + 1,
        "title": f"Title {n}",
        "text": f"Review text number {n} about the app",
        "date": f"2026-09-{(n % 28) + 1:02d}",
        "app_version": "18.13.2",
    }
    return row | overrides


def themes_file(reviews: list[dict], theme_for) -> dict:
    return {
        "themes": [{"theme_id": t, "label": t, "description": ""} for t in THEMES],
        "assignments": [
            {"review_id": r["review_id"], "theme_id": theme_for(i)} for i, r in enumerate(reviews)
        ],
    }


@pytest.fixture
def sample(write_run):
    """500 reviews, themes cycling through THEMES; returns the review list."""
    reviews = [review(n) for n in range(500)]
    write_run(RUN, sanitized=reviews, themes=themes_file(reviews, lambda i: THEMES[i % 3]))
    return reviews


def get(client, path="", **params):
    return client.get(f"/api/runs/{RUN}/reviews{path}", params=params)


def test_reads_non_ascii_reviews(client, write_run):
    # Review Focus 1: these files are UTF-8; the platform default codec must never be used.
    reviews = [
        review(1, text="Withdrawal fees of ₹295 are too high"),
        review(2, text="सही है, bahut accha app"),
        review(3, text="Love it \U0001f600\U0001f44d"),
    ]
    write_run(RUN, sanitized=reviews, themes=themes_file(reviews, lambda i: "other"))
    body = get(client).json()
    assert [r["text"] for r in body["items"]] == [r["text"] for r in reviews]


def test_row_has_exactly_the_allowed_keys(client, sample):
    row = get(client).json()["items"][0]
    assert set(row) == {
        "review_id",
        "rating",
        "title",
        "text",
        "date",
        "app_version",
        "theme_id",
    }
    assert row["theme_id"] == "customer-support"


def test_filters_compose(client, write_run):
    reviews = [
        review(1, rating=1, text="Support never gave a REPLY"),
        review(2, rating=1, text="No reply from payments team"),
        review(3, rating=5, text="Quick reply from support"),
        review(4, rating=1, text="Support is slow"),
        review(5, rating=1, title="Reply please", text="Support helpless"),
    ]
    assigned = ["customer-support", "payments-and-withdrawals", "customer-support"]
    write_run(
        RUN,
        sanitized=reviews,
        themes=themes_file(reviews, lambda i: assigned[i] if i < 3 else "customer-support"),
    )
    body = get(client, theme="customer-support", rating=1, q="reply").json()
    assert [r["review_id"] for r in body["items"]] == ["rev00001", "rev00005"]
    assert body["total"] == 2


def test_theme_and_rating_are_repeatable(client, sample):
    body = get(client, theme=["customer-support", "other"], rating=[1, 2]).json()
    assert body["total"] > 0
    assert {r["theme_id"] for r in body["items"]} <= {"customer-support", "other"}
    assert {r["rating"] for r in body["items"]} <= {1, 2}
    expected = [
        r
        for i, r in enumerate(sample)
        if THEMES[i % 3] in ("customer-support", "other") and r["rating"] in (1, 2)
    ]
    assert body["total"] == len(expected)


def test_review_id_filter_repeatable(client, sample):
    ids = ["rev00007", "rev00123", "rev00400"]
    body = get(client, review_id=ids).json()
    assert [r["review_id"] for r in body["items"]] == ids
    assert body["total"] == 3


def test_pagination(client, sample):
    body = get(client, page=20, page_size=25).json()
    assert len(body["items"]) == 25
    assert (body["total"], body["page"], body["page_size"]) == (500, 20, 25)
    assert body["items"][0]["review_id"] == "rev00475"
    assert get(client, page=21, page_size=25).json()["items"] == []
    assert get(client, page_size=101).status_code == 422
    assert get(client, page_size=100).status_code == 200
    assert get(client, page=0).status_code == 422


def test_bad_rating_is_422(client, sample):
    assert get(client, rating=9).status_code == 422
    assert get(client, rating="x").status_code == 422


def test_summary_matches_sample(client, sample):
    body = get(client, "/summary").json()
    assert body["total"] == 500
    assert body["rating"] == {str(n): 100 for n in range(1, 6)}
    assert sum(body["rating"].values()) == body["total"]
    assert sum(t["count"] for t in body["by_theme"]) == body["total"]
    assert {t["theme_id"] for t in body["by_theme"]} == set(THEMES)
    assert all(t["avg_rating"] is not None for t in body["by_theme"])
    weeks = [w["week_start"] for w in body["weekly"]]
    assert weeks == sorted(weeks)
    assert sum(w["count"] for w in body["weekly"]) == 500


def test_weeks_start_on_monday(client, write_run):
    # 2026-09-06 is a Sunday, 2026-09-07 a Monday, 2026-09-13 the next Sunday.
    reviews = [
        review(1, date="2026-09-06", rating=2),
        review(2, date="2026-09-07", rating=4),
        review(3, date="2026-09-13", rating=5),
        review(4, date="not-a-date"),
    ]
    write_run(RUN, sanitized=reviews, themes=themes_file(reviews, lambda i: "other"))
    body = get(client, "/summary").json()
    assert body["weekly"] == [
        {"week_start": "2026-08-31", "count": 1, "avg_rating": 2.0},
        {"week_start": "2026-09-07", "count": 2, "avg_rating": 4.5},
    ]
    assert body["total"] == 4


def test_unassigned_review_has_null_theme(client, write_run):
    reviews = [review(1), review(2)]
    themes = {"themes": [], "assignments": [{"review_id": "rev00001", "theme_id": "other"}]}
    write_run(RUN, sanitized=reviews, themes=themes)
    items = get(client).json()["items"]
    assert [r["theme_id"] for r in items] == ["other", None]
    by_theme = get(client, "/summary").json()["by_theme"]
    assert sorted(by_theme, key=lambda t: t["theme_id"] or "") == [
        {"theme_id": None, "count": 1, "avg_rating": 3.0},
        {"theme_id": "other", "count": 1, "avg_rating": 2.0},
    ]


def test_missing_sanitized_returns_empty_not_500(client, write_run):
    write_run(RUN, run={"status": "failed", "stages": []})
    body = get(client).json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 25}
    summary = get(client, "/summary").json()
    assert summary["total"] == 0
    assert summary["rating"] == {str(n): 0 for n in range(1, 6)}
    assert summary["weekly"] == [] and summary["by_theme"] == []


def test_missing_themes_gives_null_theme(client, write_run):
    write_run(RUN, sanitized=[review(1), review(2)])
    body = get(client).json()
    assert body["total"] == 2
    assert [r["theme_id"] for r in body["items"]] == [None, None]


def test_garbage_files_do_not_500(client, write_run):
    write_run(RUN, sanitized='[{"review_id": ', themes="{")
    assert get(client).json()["total"] == 0
    assert get(client, "/summary").json()["total"] == 0


def test_odd_rows_are_skipped_not_fatal(client, write_run):
    rows = [review(1), "text", None, {"text": "no id"}, review(2, rating="five"), review(3)]
    write_run(RUN, sanitized=rows, themes={"assignments": ["x", {"review_id": "rev00001"}]})
    body = get(client).json()
    assert [r["review_id"] for r in body["items"]] == ["rev00001", "rev00002", "rev00003"]
    assert body["items"][1]["rating"] is None


def test_unknown_run_404(client):
    assert get(client).status_code == 404
    assert client.get("/api/runs/..%2f/reviews").status_code == 404
    assert client.get("/api/runs/not-a-run/reviews/summary").status_code == 404


def test_cache_follows_file_changes(client, write_run):
    write_run(RUN, sanitized=[review(1)])
    assert get(client).json()["total"] == 1
    write_run(RUN, sanitized=[review(1), review(2)])
    assert get(client).json()["total"] == 2


def test_never_touches_raw(client, settings, write_run):
    raw = settings.data_dir / "raw" / RUN
    raw.mkdir(parents=True)
    (raw / "reviews.json").write_text(
        '[{"author": "Sentinel Reviewer", "text": "x"}]', encoding="utf-8"
    )
    write_run(RUN, sanitized=[review(1)], themes=themes_file([review(1)], lambda i: "other"))
    for path in ("", "/summary"):
        assert "Sentinel Reviewer" not in get(client, path).text
