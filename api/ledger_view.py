"""Read-only view of data/ledger.json, the publishing ledger.

Only `Ledger.weeks()` is called. A ledger that cannot be read or does not have the expected shape
is reported as an error, never as an empty ledger: it is what prevents duplicate Doc sections and
drafts, so "nothing published" would be a claim the API cannot back.
"""

from __future__ import annotations

from typing import Any

from api.schemas import LedgerView, StepView, WeekView
from api.settings import Settings
from pulse.mcp.ledger import Ledger, LedgerError

LEDGER_UNREADABLE = "ledger_unreadable"
STEP_STATES = frozenset({"appended", "created", "pending"})
STEPS = ("doc", "draft")


def _step_view(entry: Any) -> StepView:
    if not isinstance(entry, dict) or entry.get("state") not in STEP_STATES:
        raise ValueError("malformed ledger step")
    # Field by field through the model: unknown keys in the file are dropped.
    return StepView.model_validate(entry)


def read_ledger(settings: Settings) -> LedgerView:
    try:
        raw_weeks = Ledger(settings.data_dir / "ledger.json").weeks()
        weeks = {}
        for week, steps in raw_weeks.items():
            if not isinstance(steps, dict):
                raise ValueError("malformed ledger week")
            weeks[week] = WeekView(
                **{step: _step_view(steps[step]) if step in steps else None for step in STEPS}
            )
    except (LedgerError, ValueError):
        return LedgerView(weeks={}, error=LEDGER_UNREADABLE)
    return LedgerView(weeks=weeks, error=None)
