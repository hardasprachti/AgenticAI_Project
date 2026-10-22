"""Source adapter interface (architecture section 4.1).

Every source returns the same `RawReview` shape, so the rest of the pipeline never knows where
reviews came from. Adding a store means adding an adapter, not touching downstream stages.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from pulse.models import RawReview


class SourceUnavailable(RuntimeError):
    """A live source could not deliver reviews. Callers may fall back to an exported file."""


class ReviewSource(Protocol):
    def fetch(self, since: date, until: date) -> list[RawReview]:
        """Reviews dated within [since, until], both inclusive."""
        ...
