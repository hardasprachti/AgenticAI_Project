"""PlayStoreSource against recorded (synthetic) responses. No test here touches the network."""

import json
import ssl
import sys
import types
from datetime import date, datetime
from pathlib import Path

import pytest

from pulse.models import RawReview
from pulse.sources.base import SourceUnavailable
from pulse.sources.cache import write_raw_cache
from pulse.sources.fallback import FallbackSource
from pulse.sources.play_store import (
    Page,
    PlayAppNotFound,
    PlayFetchError,
    PlayStoreSource,
    google_scraper_fetcher,
)

PAGES_FILE = Path(__file__).parent / "data" / "play_pages.json"
SINCE, UNTIL = date(2026, 8, 10), date(2026, 10, 19)


def recorded_pages() -> list[list[dict]]:
    pages = json.loads(PAGES_FILE.read_text(encoding="utf-8"))
    for page in pages:
        for item in page:
            for key in ("at", "repliedAt"):
                if item.get(key):
                    item[key] = datetime.fromisoformat(item[key])
    return pages


class ScriptedPages:
    """A PageFetcher that serves recorded pages in order and counts the requests."""

    def __init__(self, pages):
        self.pages = pages
        self.cursors: list = []

    def __call__(self, cursor):
        self.cursors.append(cursor)
        index = 0 if cursor is None else int(cursor)
        if index >= len(self.pages):
            return Page(items=[], next=None)
        more = str(index + 1) if index + 1 < len(self.pages) else None
        return Page(items=self.pages[index], next=more)


def make_source(fetch, **kwargs):
    sleeps: list[float] = []
    params = {"delay_s": 1.0, "max_retries": 2, "sleep": sleeps.append, **kwargs}
    return PlayStoreSource("com.example.app", fetch_page=fetch, **params), sleeps


def fetch_window(source):
    return source.fetch(SINCE, UNTIL)


# --- normalization ---


def test_reviews_are_normalized_to_raw_review():
    source, _ = make_source(ScriptedPages(recorded_pages()))
    by_id = {r.store_review_id: r for r in fetch_window(source)}
    review = by_id["g-003"]
    assert isinstance(review, RawReview)
    assert (review.store, review.rating, review.date) == ("play", 1, date(2026, 10, 18))
    assert review.text == "Withdrawal has been stuck for four days now"
    assert review.title == ""
    assert review.app_version == "9.9.1"
    assert review.author_name == "Asha Rao" and review.author_id is None


def test_version_falls_back_to_the_app_version_field():
    source, _ = make_source(ScriptedPages(recorded_pages()))
    by_id = {r.store_review_id: r for r in fetch_window(source)}
    assert by_id["g-004"].app_version == "9.9.0"  # reviewCreatedVersion was null


def test_store_specific_fields_do_not_survive_normalization():
    source, _ = make_source(ScriptedPages(recorded_pages()))
    for review in fetch_window(source):
        assert not hasattr(review, "userImage") and not hasattr(review, "replyContent")
        blob = repr(review.__dict__)
        assert "avatar" not in blob and "Thanks for the feedback" not in blob


def test_missing_content_becomes_empty_text_not_an_error():
    source, _ = make_source(ScriptedPages(recorded_pages()))
    by_id = {r.store_review_id: r for r in fetch_window(source)}
    assert by_id["g-006"].text == ""  # the sanitizer drops it later


# --- window, pagination, stop rule ---


def test_keeps_only_reviews_inside_the_inclusive_window():
    source, _ = make_source(ScriptedPages(recorded_pages()))
    ids = sorted(r.store_review_id for r in fetch_window(source))
    assert ids == ["g-003", "g-004", "g-006", "g-009", "g-010", "g-011"]
    assert all(SINCE <= r.date <= UNTIL for r in fetch_window(source))


def test_reviews_newer_than_the_window_are_skipped_but_paging_continues():
    source, _ = make_source(ScriptedPages(recorded_pages()))
    fetch_window(source)
    assert source.stats.outside_window == 4  # g-001, g-002 (too new); g-012, g-013 (too old)
    assert source.stats.pages == 3


def test_stops_paging_once_a_review_older_than_the_window_is_seen():
    fetcher = ScriptedPages(recorded_pages())
    source, _ = make_source(fetcher)
    fetch_window(source)
    assert fetcher.cursors == [None, "1", "2"]  # page 3 (far too old) is never requested
    assert source.stats.reached_window_start is True and source.stats.truncated is False


def test_duplicate_review_ids_across_pages_are_dropped():
    source, _ = make_source(ScriptedPages(recorded_pages()))
    reviews = fetch_window(source)
    assert [r.store_review_id for r in reviews].count("g-004") == 1
    assert source.stats.duplicates == 1


def test_invalid_items_are_counted_and_skipped():
    source, _ = make_source(ScriptedPages(recorded_pages()))
    fetch_window(source)
    assert source.stats.invalid == 3  # no rating, no date, rating out of range


def test_polite_delay_between_pages_only():
    source, sleeps = make_source(ScriptedPages(recorded_pages()), delay_s=2.5)
    fetch_window(source)
    assert sleeps == [2.5, 2.5]  # three pages, so two pauses and none after the last


def test_window_in_the_future_returns_nothing_after_one_page():
    fetcher = ScriptedPages(recorded_pages())
    source, _ = make_source(fetcher)
    assert source.fetch(date(2026, 12, 1), date(2026, 12, 31)) == []
    assert fetcher.cursors == [None]  # everything is older than the window, so stop at once
    assert source.stats.reached_window_start is True


# --- very large volume ---


def endless_pages():
    """An unending stream of in-window reviews, 5 per page."""
    counter = {"n": 0}

    def fetch(cursor):
        items = []
        for _ in range(5):
            counter["n"] += 1
            items.append(
                {
                    "reviewId": f"e-{counter['n']}",
                    "at": datetime(2026, 9, 1, 12, 0),
                    "score": 3,
                    "content": "some review text here",
                    "userName": "X Y",
                }
            )
        return Page(items=items, next="more")

    return fetch


def test_max_reviews_stops_collection_and_flags_truncation():
    source, _ = make_source(endless_pages(), max_reviews=12)
    reviews = fetch_window(source)
    assert 12 <= len(reviews) <= 15
    assert source.stats.truncated is True and source.stats.reached_window_start is False


def test_max_pages_stops_collection_and_flags_truncation():
    source, _ = make_source(endless_pages(), max_pages=3)
    fetch_window(source)
    assert source.stats.pages == 3 and source.stats.truncated is True


# --- retries and failures ---


def test_empty_response_is_retried_from_the_same_cursor_then_succeeds():
    inner = ScriptedPages(recorded_pages())
    state = {"swallowed": False}

    def flaky(cursor):
        if cursor == "1" and not state["swallowed"]:
            state["swallowed"] = True  # what the library returns after swallowing an error
            return Page(items=[], next=None)
        return inner(cursor)

    source, sleeps = make_source(flaky)
    assert len(fetch_window(source)) == 6  # nothing was lost to the empty response
    assert source.stats.retries == 1
    assert inner.cursors.count("1") == 1  # the retry reused the same cursor
    assert 2.0 in sleeps  # and backed off before retrying


def test_backoff_is_exponential_and_bounded():
    def always_empty_after_first(cursor):
        if cursor is None:
            return Page(items=recorded_pages()[0], next="1")
        return Page(items=[], next=None)

    source, sleeps = make_source(always_empty_after_first, max_retries=3, delay_s=0)
    fetch_window(source)  # the stream is accepted as ended after retries are spent
    assert sleeps[1:] == [2.0, 4.0, 8.0]  # after the single inter-page pause of delay_s


def test_exceptions_are_retried_and_recovered():
    inner = ScriptedPages(recorded_pages())
    state = {"failed": False}

    def fetch(cursor):
        if cursor == "1" and not state["failed"]:
            state["failed"] = True
            raise ConnectionError("reset by peer")
        return inner(cursor)

    source, _ = make_source(fetch)
    assert len(fetch_window(source)) == 6 and source.stats.retries == 1


def test_persistent_exception_on_a_later_page_fails_the_fetch():
    def fetch(cursor):
        if cursor is None:
            return Page(items=recorded_pages()[0], next="1")
        raise TimeoutError("slow")

    source, _ = make_source(fetch, max_retries=2)
    with pytest.raises(PlayFetchError, match="page 2 failed after 2 retries"):
        fetch_window(source)


def test_no_reviews_at_all_is_an_error_that_points_to_the_csv_fallback():
    source, _ = make_source(lambda cursor: Page(items=[], next=None))
    with pytest.raises(PlayFetchError, match="--source csv"):
        fetch_window(source)


def test_unknown_app_is_fatal_and_not_retried():
    calls = []

    def fetch(cursor):
        calls.append(cursor)
        raise PlayAppNotFound("nope")

    source, _ = make_source(fetch)
    with pytest.raises(PlayAppNotFound):
        fetch_window(source)
    assert len(calls) == 1


def test_a_failed_fetch_is_a_source_unavailable_error():
    assert issubclass(PlayFetchError, SourceUnavailable)


# --- the library seam (the library itself is stubbed) ---


@pytest.fixture
def fake_library(monkeypatch):
    calls: list[dict] = []
    token = types.SimpleNamespace(token="abc")

    def reviews(app_id, **kwargs):
        calls.append({"app_id": app_id, **kwargs})
        return [{"reviewId": "x"}], token if kwargs.get(
            "continuation_token"
        ) is None else types.SimpleNamespace(token=None)

    module = types.ModuleType("google_play_scraper")
    module.Sort = types.SimpleNamespace(NEWEST="NEWEST")
    module.reviews = reviews
    exceptions = types.ModuleType("google_play_scraper.exceptions")

    class NotFoundError(Exception):
        pass

    exceptions.NotFoundError = NotFoundError
    monkeypatch.setitem(sys.modules, "google_play_scraper", module)
    monkeypatch.setitem(sys.modules, "google_play_scraper.exceptions", exceptions)
    return calls, NotFoundError, module


def test_default_fetcher_asks_for_newest_first_in_the_configured_locale(fake_library):
    calls, _, _ = fake_library
    fetch = google_scraper_fetcher("com.example.app", "en", "in", 200)
    first = fetch(None)
    second = fetch(first.next)
    assert calls[0] == {
        "app_id": "com.example.app",
        "lang": "en",
        "country": "in",
        "sort": "NEWEST",
        "count": 200,
        "continuation_token": None,
    }
    assert calls[1]["continuation_token"] is first.next
    assert first.next is not None and second.next is None  # an exhausted token ends the stream


def test_default_fetcher_maps_not_found_to_a_fatal_error(fake_library, monkeypatch):
    _, not_found, module = fake_library

    def missing(app_id, **kwargs):
        raise not_found("404")

    monkeypatch.setattr(module, "reviews", missing)
    with pytest.raises(PlayAppNotFound):
        google_scraper_fetcher("com.example.app", "en", "in", 200)(None)


def test_importing_the_library_does_not_leave_tls_verification_off(monkeypatch):
    """The real library disables certificate checks at import; the fetcher must undo that."""
    monkeypatch.delitem(sys.modules, "google_play_scraper", raising=False)
    monkeypatch.delitem(sys.modules, "google_play_scraper.exceptions", raising=False)
    monkeypatch.setattr(ssl, "_create_default_https_context", ssl.create_default_context)

    google_scraper_fetcher("com.example.app", "en", "in", 200)  # imports the real library
    assert ssl._create_default_https_context is ssl.create_default_context


# --- raw cache ---


def test_raw_cache_is_minimized_and_excludes_store_fields(tmp_path):
    source, _ = make_source(ScriptedPages(recorded_pages()))
    path = write_raw_cache(fetch_window(source), tmp_path / "raw" / "run1")
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert len(rows) == 6
    assert set(rows[0]) == {
        "store_review_id",
        "rating",
        "text",
        "date",
        "app_version",
        "author_name",
    }
    blob = path.read_text(encoding="utf-8")
    assert "avatar" not in blob and "Thanks for the feedback" not in blob and "thumbs" not in blob


# --- fallback ---


class FailingSource:
    def fetch(self, since, until):
        raise PlayFetchError("blocked")


class StaticSource:
    stats = None

    def __init__(self, reviews):
        self._reviews = reviews

    def fetch(self, since, until):
        return self._reviews


def test_fallback_uses_the_export_when_the_live_fetch_fails():
    export = [RawReview("play", "csv-1", 3, "", "from the export", date(2026, 9, 1))]
    source = FallbackSource(FailingSource(), StaticSource(export))
    assert source.fetch(SINCE, UNTIL) == export
    assert source.used_fallback and source.primary_error == "blocked"
    assert source.stats is None


def test_fallback_is_not_used_when_the_live_fetch_works():
    live = [RawReview("play", "g-1", 3, "", "live", date(2026, 9, 1))]
    source = FallbackSource(StaticSource(live), StaticSource([]))
    assert source.fetch(SINCE, UNTIL) == live and not source.used_fallback


def test_fallback_does_not_hide_non_source_errors():
    class Broken:
        def fetch(self, since, until):
            raise ValueError("bug")

    with pytest.raises(ValueError):
        FallbackSource(Broken(), StaticSource([])).fetch(SINCE, UNTIL)
