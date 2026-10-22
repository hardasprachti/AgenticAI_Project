"""CSV review source: test fixtures and Play Console exports (architecture section 4.1).

Columns are matched case-insensitively. Our own column names are tried first, then the names a
Play Console export uses, so an exported file works without editing.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from pulse.models import RawReview

STORE = "play"

# canonical field -> accepted header names (lowercase)
_COLUMNS: dict[str, tuple[str, ...]] = {
    "id": ("review_id", "review id"),
    "date": ("date", "review submit date and time", "review last update date and time"),
    "rating": ("rating", "star rating"),
    "title": ("title", "review title"),
    "text": ("text", "review text"),
    "author_name": ("author_name", "author", "reviewer name"),
    "author_id": ("author_id",),
    "app_version": ("app_version", "app version name"),
}


class CsvSourceError(ValueError):
    """The file is missing or lacks the columns a review needs."""


def _parse_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value[:10] if fmt != "%b %d, %Y" else value, fmt).date()
        except ValueError:
            continue
    return None


class CsvSource:
    """Reads reviews from a CSV file. Rows that cannot be parsed are counted, not fatal."""

    def __init__(self, path: str | Path, store: str = STORE) -> None:
        self.path = Path(path)
        self.store = store
        self.rows_read = 0
        self.rows_skipped = 0

    def fetch(self, since: date, until: date) -> list[RawReview]:
        if not self.path.is_file():
            raise CsvSourceError(f"Review file not found: {self.path}")

        reviews: list[RawReview] = []
        self.rows_read = self.rows_skipped = 0
        with self.path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = {name.strip().lower(): name for name in (reader.fieldnames or [])}
            columns = {
                field: next((headers[n] for n in names if n in headers), None)
                for field, names in _COLUMNS.items()
            }
            missing = [f for f in ("date", "rating", "text") if columns[f] is None]
            if missing:
                raise CsvSourceError(f"{self.path.name} is missing required column(s): {missing}")

            for number, row in enumerate(reader, start=1):
                self.rows_read += 1
                review = self._row_to_review(row, columns, number)
                if review is None:
                    self.rows_skipped += 1
                elif since <= review.date <= until:
                    reviews.append(review)
        return reviews

    def _row_to_review(
        self, row: dict[str, str], columns: dict[str, str | None], number: int
    ) -> RawReview | None:
        def get(field: str) -> str:
            column = columns[field]
            return (row.get(column) or "").strip() if column else ""

        review_date = _parse_date(get("date"))
        try:
            rating = int(float(get("rating")))
        except ValueError:
            return None
        if review_date is None:
            return None

        return RawReview(
            store=self.store,
            store_review_id=get("id") or f"row-{number}",
            rating=rating,
            title=get("title"),
            text=get("text"),
            date=review_date,
            app_version=get("app_version") or None,
            author_name=get("author_name") or None,
            author_id=get("author_id") or None,
        )
