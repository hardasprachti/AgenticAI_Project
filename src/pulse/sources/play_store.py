"""Live Google Play source (architecture section 4.1): public reviews only, no login.

Reviews are fetched newest first, page by page, until a whole page is older than the window.
Everything is normalized to `RawReview` here, so store-specific fields (avatar URLs, reply text,
thumbs-up counts) never leave this module.

Fetching goes through a small `PageFetcher` seam. The default one wraps the third-party
`google-play-scraper` library; tests and fallbacks substitute their own.

Two properties of that library shape this module:
- Its `reviews()` call swallows every error and returns an empty page with no continuation token,
  which looks exactly like "no more reviews". So an empty page is never trusted at face value:
  it is retried from the previous cursor, and the run records whether the start of the window was
  actually reached.
- It switches off TLS certificate verification process-wide when imported. We restore the original
  setting straight after the import so that nothing else in the process loses verification.
"""

from __future__ import annotations

import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pulse.models import RawReview
from pulse.sources.base import SourceUnavailable

STORE = "play"
_MAX_BACKOFF_S = 30.0


class PlayFetchError(SourceUnavailable):
    """Reviews could not be fetched. The caller can fall back to a Play Console export."""


class PlayAppNotFound(PlayFetchError):
    """The package id does not exist on Google Play (permanent, so never retried)."""


@dataclass
class Page:
    items: list[dict[str, Any]]
    next: Any | None  # opaque cursor for the following page; None means the stream ended


PageFetcher = Callable[[Any | None], Page]


@dataclass
class PlayStats:
    pages: int = 0
    items_seen: int = 0
    kept: int = 0
    outside_window: int = 0
    duplicates: int = 0
    invalid: int = 0  # missing id, rating or date
    retries: int = 0
    truncated: bool = False  # stopped at max_pages / max_reviews before the window start
    reached_window_start: bool = False  # saw reviews older than the window, so coverage is complete

    def as_counts(self) -> dict[str, int]:
        return {
            "pages": self.pages,
            "items_seen": self.items_seen,
            "kept": self.kept,
            "outside_window": self.outside_window,
            "duplicates": self.duplicates,
            "invalid": self.invalid,
            "retries": self.retries,
            "truncated": int(self.truncated),
            "window_start_reached": int(self.reached_window_start),
        }


def google_scraper_fetcher(package: str, lang: str, country: str, page_size: int) -> PageFetcher:
    """A `PageFetcher` backed by google-play-scraper, newest reviews first."""
    original_context = ssl._create_default_https_context
    try:
        from google_play_scraper import Sort, reviews
        from google_play_scraper.exceptions import NotFoundError
    finally:
        # The library replaces the default HTTPS context with an unverified one at import time.
        ssl._create_default_https_context = original_context

    def fetch(cursor: Any | None) -> Page:
        try:
            items, token = reviews(
                package,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=page_size,
                continuation_token=cursor,
            )
        except NotFoundError as exc:
            raise PlayAppNotFound(f"'{package}' was not found on Google Play") from exc
        has_more = token is not None and getattr(token, "token", None) is not None
        return Page(items=items, next=token if has_more else None)

    return fetch


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


class PlayStoreSource:
    """Fetches public Play reviews dated within the requested window."""

    def __init__(
        self,
        package: str,
        lang: str = "en",
        country: str = "in",
        *,
        fetch_page: PageFetcher | None = None,
        page_size: int = 200,
        delay_s: float = 1.0,
        max_retries: int = 3,
        max_pages: int = 400,
        max_reviews: int = 30000,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.package = package
        self._fetch_page = fetch_page or google_scraper_fetcher(package, lang, country, page_size)
        self._delay_s = delay_s
        self._max_retries = max_retries
        self._max_pages = max_pages
        self._max_reviews = max_reviews
        self._sleep = sleep
        self.stats = PlayStats()

    def fetch(self, since: date, until: date) -> list[RawReview]:
        self.stats = stats = PlayStats()
        kept: dict[str, RawReview] = {}
        cursor: Any | None = None

        while True:
            page = self._get_page(cursor, first=stats.pages == 0)
            stats.pages += 1
            stats.items_seen += len(page.items)

            oldest_on_page: date | None = None
            for item in page.items:
                review = self._normalize(item)
                if review is None:
                    stats.invalid += 1
                    continue
                if oldest_on_page is None or review.date < oldest_on_page:
                    oldest_on_page = review.date
                if not since <= review.date <= until:
                    stats.outside_window += 1
                elif review.store_review_id in kept:
                    stats.duplicates += 1
                else:
                    kept[review.store_review_id] = review

            # Results are newest first, so a review older than the window means everything after
            # it is older too: this page is the last one needed.
            if oldest_on_page is not None and oldest_on_page < since:
                stats.reached_window_start = True
                break
            if page.next is None:
                break
            if len(kept) >= self._max_reviews or stats.pages >= self._max_pages:
                stats.truncated = True
                break

            cursor = page.next
            self._sleep(self._delay_s)

        stats.kept = len(kept)
        return list(kept.values())

    # --- internals ---

    def _get_page(self, cursor: Any | None, *, first: bool) -> Page:
        """One page, retried from the same cursor when the response is empty or fails.

        An empty page with no next cursor is what the library returns for both "end of reviews"
        and "swallowed an error", so it is retried before being believed.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt:
                self.stats.retries += 1
                self._sleep(min(2.0 * 2 ** (attempt - 1), _MAX_BACKOFF_S))
            try:
                page = self._fetch_page(cursor)
            except PlayAppNotFound:
                raise
            except Exception as exc:  # transient: network, HTTP, parsing
                last_error = exc
                continue
            if page.items or page.next is not None:
                return page
            last_error = None

        if first:
            reason = f" ({type(last_error).__name__})" if last_error else ""
            raise PlayFetchError(
                f"Google Play returned no reviews for '{self.package}'{reason}. It may be "
                "blocking automated requests; use a Play Console export (--source csv) instead."
            )
        if last_error is not None:
            raise PlayFetchError(
                f"Fetching page {self.stats.pages + 1} failed after {self._max_retries} retries "
                f"({type(last_error).__name__})."
            ) from last_error
        return Page(items=[], next=None)  # an empty page, retried, is the end of the stream

    @staticmethod
    def _normalize(item: dict[str, Any]) -> RawReview | None:
        """Map a store item to `RawReview`, keeping only what the pipeline needs.

        Deliberately not copied: avatar URL, reply text, thumbs-up count. `author_id` stays unset
        because Play does not expose one.
        """
        review_id = item.get("reviewId")
        review_date = _to_date(item.get("at"))
        try:
            rating = int(item.get("score"))
        except (TypeError, ValueError):
            return None
        if not review_id or review_date is None or not 1 <= rating <= 5:
            return None
        return RawReview(
            store=STORE,
            store_review_id=str(review_id),
            rating=rating,
            title="",  # Play reviews have no title
            text=(item.get("content") or "").strip(),
            date=review_date,
            app_version=item.get("reviewCreatedVersion") or item.get("appVersion") or None,
            author_name=item.get("userName") or None,
            author_id=None,
        )
