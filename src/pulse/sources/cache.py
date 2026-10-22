"""Cache of the raw fetch, kept for audit and debugging (architecture section 4.1).

Written once per run under `data/raw/<run_id>/` and never read by any later stage: everything
downstream works from the sanitized reviews only. It is minimized to the fields the pipeline uses.
The reviewer's display name is kept because sanitizing needs it to scrub the name from review
text; that makes this the one place reviewer identity touches disk, so it lives under `data/`,
which is git-ignored. Avatars, replies and other store fields are not stored.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pulse.models import RawReview


def write_raw_cache(reviews: Sequence[RawReview], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "reviews.json"
    rows = [
        {
            "store_review_id": r.store_review_id,
            "rating": r.rating,
            "text": r.text,
            "date": r.date.isoformat(),
            "app_version": r.app_version,
            "author_name": r.author_name,
        }
        for r in reviews
    ]
    path.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    return path
