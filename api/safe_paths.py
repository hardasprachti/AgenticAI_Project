"""Run-id validation and path containment: no request string ever reaches the filesystem raw."""

from __future__ import annotations

import re
from pathlib import Path

from api.settings import Settings

RUN_ID_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?$")


class RunNotFound(LookupError):
    """The run id is malformed, escapes data/runs/, or names no folder."""


def safe_run_dir(settings: Settings, run_id: str) -> Path:
    """Resolve a run folder, guaranteeing it sits directly inside <data_dir>/runs/."""
    if not RUN_ID_RE.fullmatch(run_id):
        raise RunNotFound(run_id)
    runs_root = (settings.data_dir / "runs").resolve()
    candidate = (runs_root / run_id).resolve()
    if candidate.parent != runs_root:
        raise RunNotFound(run_id)
    return candidate
