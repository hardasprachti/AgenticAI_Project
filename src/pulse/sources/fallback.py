"""Try a live source, and fall back to an exported file if it is unavailable (plan, Phase 4)."""

from __future__ import annotations

from datetime import date

from pulse.models import RawReview
from pulse.sources.base import ReviewSource, SourceUnavailable


class FallbackSource:
    def __init__(self, primary: ReviewSource, fallback: ReviewSource) -> None:
        self._primary = primary
        self._fallback = fallback
        self.used_fallback = False
        self.primary_error: str | None = None

    @property
    def stats(self):
        """The live source's fetch stats, or None if the fallback was used instead."""
        return None if self.used_fallback else getattr(self._primary, "stats", None)

    def fetch(self, since: date, until: date) -> list[RawReview]:
        self.used_fallback, self.primary_error = False, None
        try:
            return self._primary.fetch(since, until)
        except SourceUnavailable as exc:
            self.used_fallback, self.primary_error = True, str(exc)
            return self._fallback.fetch(since, until)
