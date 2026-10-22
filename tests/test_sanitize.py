import dataclasses
from datetime import date

from pulse.models import RawReview, Review
from pulse.pii import REDACTED
from pulse.sanitize import anonymous_review_id, sanitize_reviews


def raw(
    rid="1",
    text="The withdrawal to my bank account is taking very long.",
    title="Slow",
    rating=2,
    author="Rahul Sharma",
    day=1,
    **kw,
) -> RawReview:
    return RawReview(
        store="play",
        store_review_id=rid,
        rating=rating,
        title=title,
        text=text,
        date=date(2026, 9, day),
        author_name=author,
        author_id=f"uid-{rid}",
        **kw,
    )


def test_review_type_has_no_identity_fields():
    fields = {f.name for f in dataclasses.fields(Review)}
    assert not any("author" in f or "user" in f or "name" in f for f in fields)


def test_identity_is_dropped_and_id_is_anonymous():
    result = sanitize_reviews([raw(rid="abc123")])
    (review,) = result.reviews
    assert review.review_id != "abc123"
    assert "abc123" not in repr(review)
    assert "Rahul" not in repr(review)


def test_review_id_is_stable_and_salted():
    a = anonymous_review_id("play", "abc", "salt1")
    assert a == anonymous_review_id("play", "abc", "salt1")
    assert a != anonymous_review_id("play", "abc", "salt2")
    assert a != anonymous_review_id("play", "abd", "salt1")


def test_pii_in_text_and_title_is_scrubbed():
    result = sanitize_reviews(
        [
            raw(
                title="Call 9876543210",
                text="Email me at john@example.com, my PAN is ABCDE1234F and it still fails.",
            )
        ]
    )
    (review,) = result.reviews
    assert "9876543210" not in review.title
    assert "john@example.com" not in review.text
    assert "ABCDE1234F" not in review.text
    assert review.text.count(REDACTED) == 2
    assert result.stats.redactions["email"] == 1
    assert result.stats.redactions["pan"] == 1


def test_author_name_in_text_is_scrubbed_case_insensitively():
    result = sanitize_reviews(
        [raw(text="Please fix this. Thanks, rahul sharma. The KYC flow keeps failing.")]
    )
    (review,) = result.reviews
    assert "rahul" not in review.text.casefold()
    assert result.stats.redactions["author_name"] == 1
    assert "Rahul Sharma" in result.known_author_names


def test_generic_author_names_are_not_scrubbed_or_tracked():
    result = sanitize_reviews(
        [raw(author="A Google user", text="google user data is safe here ok")]
    )
    assert result.stats.redactions["author_name"] == 0
    assert not result.known_author_names


def test_short_and_empty_reviews_are_dropped():
    result = sanitize_reviews([raw(rid="1", text="ok", title=""), raw(rid="2", text="", title="")])
    assert result.reviews == []
    assert result.stats.dropped_short == 2


def test_review_that_is_only_pii_is_dropped():
    result = sanitize_reviews([raw(text="9876543210", title="")])
    assert result.reviews == []
    assert result.stats.dropped_short == 1


def test_invalid_rating_is_dropped():
    result = sanitize_reviews([raw(rating=0), raw(rid="2", rating=6), raw(rid="3", rating=4)])
    assert len(result.reviews) == 1
    assert result.stats.dropped_invalid == 2


def test_non_english_dropped_but_hinglish_kept():
    result = sanitize_reviews(
        [
            raw(rid="1", text="यह ऐप बहुत धीमा है और बार बार क्रैश होता है", title="धीमा"),
            raw(rid="2", text="App bahut slow hai aur paisa nikalne mein dikkat hoti hai"),
        ]
    )
    assert len(result.reviews) == 1
    assert result.stats.dropped_non_english == 1


def test_duplicates_removed_keeping_earliest():
    result = sanitize_reviews(
        [
            raw(rid="2", text="Withdrawal is very slow!!", day=5),
            raw(rid="1", text="withdrawal is very slow", day=2),
            raw(rid="3", text="Totally different complaint about the statements page", day=3),
        ]
    )
    assert len(result.reviews) == 2
    assert result.stats.dropped_duplicate == 1
    assert result.reviews[0].date == date(2026, 9, 2)


def test_same_store_review_id_twice_is_deduped():
    a = raw(rid="1", text="First text about slow KYC verification")
    b = raw(rid="1", text="Edited text about slow KYC verification!")
    result = sanitize_reviews([a, b])
    assert len(result.reviews) == 1


def test_output_is_deterministic_and_sorted():
    items = [
        raw(rid=str(i), text=f"Unique complaint number {i} about the app", day=d)
        for i, d in [(1, 9), (2, 3), (3, 6)]
    ]
    first = sanitize_reviews(items).reviews
    second = sanitize_reviews(list(reversed(items))).reviews
    assert first == second
    assert [r.date.day for r in first] == [3, 6, 9]


def test_whitespace_is_collapsed():
    result = sanitize_reviews([raw(text="Line one\n\nline   two   of the review text")])
    assert result.reviews[0].text == "Line one line two of the review text"


def test_stats_counts():
    result = sanitize_reviews([raw(rid="1"), raw(rid="2", rating=9), raw(rid="3", text="no")])
    counts = result.stats.as_counts()
    assert counts["fetched"] == 3
    assert counts["kept"] == 1
    assert counts["dropped_invalid"] == 1
    assert counts["dropped_short"] == 1


def test_raw_review_repr_hides_identity_and_text():
    r = raw(author="Rahul Sharma", text="secret text 9876543210")
    assert "Rahul" not in repr(r)
    assert "9876543210" not in repr(r)
