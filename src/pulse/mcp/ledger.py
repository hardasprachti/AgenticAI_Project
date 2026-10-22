"""Per-week publishing ledger (architecture sections 4.7 and 4.8).

The MCP server can neither read a Doc nor update a draft, and neither of its write tools is
idempotent, so this file is the only thing standing between a rerun and a duplicate section or
draft. Protocol: `mark_pending` is written to disk *before* the MCP call and `mark_done` right
after it. A step found `pending` means the process died somewhere between the two, so whether the
write happened is unknown; the rerun stops and a person checks the Doc / Drafts folder.

If this file is lost, duplicate protection is lost with it. A corrupt file is an error rather than
an empty ledger for the same reason.
"""

from __future__ import annotations

import json
import os
from enum import StrEnum
from pathlib import Path
from typing import Any


class LedgerError(RuntimeError):
    pass


class Step(StrEnum):
    DOC = "doc"
    DRAFT = "draft"


class StepState(StrEnum):
    NONE = "none"  # never attempted
    PENDING = "pending"  # a call was started and its outcome was not recorded
    DONE = "done"


# What the file says for a finished step (the implementation plan's names).
_DONE_WORD = {Step.DOC: "appended", Step.DRAFT: "created"}


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def state(self, week: str, step: Step) -> StepState:
        entry = self.entry(week, step)
        if not entry:
            return StepState.NONE
        return StepState.DONE if entry["state"] == _DONE_WORD[step] else StepState.PENDING

    def entry(self, week: str, step: Step) -> dict[str, Any]:
        return dict(self._read().get(week, {}).get(step.value, {}))

    def mark_pending(self, week: str, step: Step, *, run_id: str) -> None:
        data = self._read()
        existing = data.get(week, {}).get(step.value, {}).get("state")
        if existing == _DONE_WORD[step]:
            raise LedgerError(f"{week} {step.value} is already recorded as done; not repeating it")
        if existing == "pending":
            # Another run (or a crashed one) holds this step; two writers would duplicate it.
            raise LedgerError(f"{week} {step.value} is already pending from another run")
        data.setdefault(week, {})[step.value] = {"state": "pending", "run_id": run_id}
        self._write(data)

    def mark_done(self, week: str, step: Step, **details: Any) -> None:
        data = self._read()
        entry = data.get(week, {}).get(step.value)
        if not entry or entry["state"] != "pending":
            raise LedgerError(f"{week} {step.value} was not marked pending before it was done")
        data[week][step.value] = {**entry, **details, "state": _DONE_WORD[step]}
        self._write(data)

    def clear(self, week: str, step: Step) -> None:
        data = self._read()
        if data.get(week, {}).pop(step.value, None) is None:
            return
        if not data[week]:
            del data[week]
        self._write(data)

    def weeks(self) -> dict[str, dict[str, Any]]:
        return self._read()

    # --- storage ---------------------------------------------------------------------------

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise LedgerError(
                f"The ledger {self.path} is not valid JSON ({exc}). It is what prevents duplicate "
                "Doc sections and drafts, so it is not being treated as empty. Fix or restore it."
            ) from exc
        if not isinstance(data, dict):
            raise LedgerError(f"The ledger {self.path} is not a JSON object.")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        # Write-then-rename so a crash never leaves a half-written ledger, and fsync so the
        # `pending` mark is really on disk before the MCP call it guards.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)
