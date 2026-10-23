"""Run list and run detail, derived from the files under <data_dir>/runs/<run_id>/.

Nothing here raises for a missing or half-written file: a run that is still going, died early,
or has a corrupt record is reported as such, with whatever else exists.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.files import read_json
from api.safe_paths import RUN_ID_RE, RunNotFound, safe_run_dir
from api.schemas import RunDetail, RunSummary
from api.settings import Settings
from pulse.pipeline import week_label_for

RUNNING_STALE_AFTER_S = 1800

# The six statuses the backend writes to run.json. `interrupted` and `unreadable` are derived.
BACKEND_STATUSES = frozenset(
    {"running", "completed", "failed_validation", "partial", "failed", "already_published"}
)

# Stage notes can carry local paths (the ingest stage names its on-disk cache); never serve them.
_PATH_CHARS = re.compile(r"[\\/]")


def _num(value: Any) -> int | float | None:
    return value if isinstance(value, int | float) and not isinstance(value, bool) else None


def _stages(run: dict[str, Any]) -> list[dict[str, Any]]:
    stages = run.get("stages")
    return [s for s in stages if isinstance(s, dict)] if isinstance(stages, list) else []


def _stage_count(run: dict[str, Any], stage_name: str, key: str) -> int | float | None:
    for stage in _stages(run):
        if stage.get("name") == stage_name:
            counts = stage.get("counts")
            return _num(counts.get(key)) if isinstance(counts, dict) else None
    return None


def _duration(run: dict[str, Any]) -> float | None:
    durations = [d for s in _stages(run) if (d := _num(s.get("duration_s"))) is not None]
    return round(sum(durations), 3) if durations else None


def _run_id_time(run_id: str) -> datetime | None:
    """The UTC start time encoded in a run id (YYYYMMDD-HHMMSS[-n])."""
    try:
        return datetime.strptime(run_id[:15], "%Y%m%d-%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _run_id_sort_key(run_id: str) -> tuple[str, int]:
    suffix = run_id[16:]  # the "n" of YYYYMMDD-HHMMSS-n
    return run_id[:15], int(suffix) if suffix else 0


def _latest_mtime(folder: Path) -> float:
    """Newest modification time of the folder and the files directly inside it."""
    newest = 0.0
    try:
        newest = folder.stat().st_mtime
        for entry in folder.iterdir():
            newest = max(newest, entry.stat().st_mtime)
    except OSError:
        pass
    return newest


def _is_live(folder: Path, now: float, active_run_id: str | None) -> bool:
    if folder.name == active_run_id:
        return True
    return now - _latest_mtime(folder) <= RUNNING_STALE_AFTER_S


def derive_status(
    run_json: dict[str, Any] | None, folder: Path, now: float, active_run_id: str | None
) -> str:
    if run_json is not None:
        status = run_json.get("status")
        return status if status in BACKEND_STATUSES else "unreadable"
    if (folder / "run.json").exists():
        return "unreadable"
    return "running" if _is_live(folder, now, active_run_id) else "interrupted"


def _iter_run_dirs(settings: Settings) -> Iterator[Path]:
    """Run folders only: <data_dir>/runs/<valid run id>/. Nothing else under data/ is listed."""
    runs_root = settings.data_dir / "runs"
    try:
        names = [p.name for p in runs_root.iterdir() if RUN_ID_RE.fullmatch(p.name)]
    except OSError:
        return
    for name in sorted(names, key=_run_id_sort_key, reverse=True):
        try:
            folder = safe_run_dir(settings, name)
        except RunNotFound:
            continue
        if folder.is_dir():
            yield folder


def run_ids(settings: Settings) -> list[str]:
    """Every run folder name, newest first."""
    return [folder.name for folder in _iter_run_dirs(settings)]


def has_live_foreign_run(
    settings: Settings, now: float, exclude: frozenset[str] = frozenset()
) -> bool:
    """True if some run folder has no run.json and was touched recently (a run in flight).

    `exclude` names folders known to belong to a process that has already exited.
    """
    return any(
        folder.name not in exclude
        and not (folder / "run.json").exists()
        and now - _latest_mtime(folder) <= RUNNING_STALE_AFTER_S
        for folder in _iter_run_dirs(settings)
    )


def _load_run_json(folder: Path) -> tuple[dict[str, Any] | None, str | None]:
    data, error = read_json(folder / "run.json")
    if error is None and not isinstance(data, dict):
        return None, "unreadable"
    return data, error


def _summarize(folder: Path, run: dict[str, Any] | None, status: str) -> RunSummary:
    run_id = folder.name
    started = _run_id_time(run_id)
    week_label = week_label_for(started.date()) if started else None
    started_at = started.isoformat() if started else None
    summary: dict[str, Any] = {
        "run_id": run_id,
        "week_label": week_label,
        "status": status,
        "started_at": started_at,
        "has_pulse": (folder / "pulse.json").is_file(),
        "duration_s": None,
        "fetched": None,
        "clean": None,
        "analysed": None,
        "word_count": None,
        "doc_url": None,
        "draft_id": None,
        "is_dry_run": False,
    }
    if run is not None:
        doc_url = run.get("doc_url") if isinstance(run.get("doc_url"), str) else None
        draft_id = run.get("draft_id") if isinstance(run.get("draft_id"), str) else None
        summary.update(
            week_label=run["week_label"] if isinstance(run.get("week_label"), str) else week_label,
            started_at=run["started_at"] if isinstance(run.get("started_at"), str) else started_at,
            duration_s=_duration(run),
            fetched=_stage_count(run, "ingest", "fetched"),
            clean=_stage_count(run, "sanitize", "clean"),
            analysed=_stage_count(run, "sanitize", "analysed"),
            word_count=_num(run.get("word_count")),
            doc_url=doc_url,
            draft_id=draft_id,
            is_dry_run=status == "completed" and doc_url is None,
        )
    return RunSummary(**summary)


def list_runs(
    settings: Settings, active_run_id: str | None, now: float | None = None
) -> list[RunSummary]:
    now = time.time() if now is None else now
    rows = []
    for folder in _iter_run_dirs(settings):
        run, _ = _load_run_json(folder)
        rows.append(_summarize(folder, run, derive_status(run, folder, now, active_run_id)))
    return rows


def _scrub(run: dict[str, Any]) -> dict[str, Any]:
    """Drop stage notes that look like filesystem paths."""
    stages = run.get("stages")
    if not isinstance(stages, list):
        return run
    cleaned = []
    for stage in stages:
        notes = stage.get("notes") if isinstance(stage, dict) else None
        if isinstance(notes, list):
            kept = [n for n in notes if not (isinstance(n, str) and _PATH_CHARS.search(n))]
            stage = {**stage, "notes": kept}
        cleaned.append(stage)
    return {**run, "stages": cleaned}


def get_run(
    settings: Settings, run_id: str, active_run_id: str | None, now: float | None = None
) -> RunDetail:
    folder = safe_run_dir(settings, run_id)
    if not folder.is_dir():
        raise RunNotFound(run_id)
    now = time.time() if now is None else now

    errors: dict[str, str] = {}
    run, run_error = _load_run_json(folder)
    if run_error == "unreadable":
        errors["run"] = run_error

    loaded: dict[str, Any] = {}
    for key in ("pulse", "ranking", "themes"):
        data, error = read_json(folder / f"{key}.json")
        loaded[key] = data
        if error == "unreadable":
            errors[key] = error

    note = None
    try:
        note = (folder / "note.txt").read_text(encoding="utf-8")
    except FileNotFoundError:
        pass
    except (OSError, UnicodeDecodeError):
        errors["note"] = "unreadable"

    return RunDetail(
        run=_scrub(run) if run is not None else None,
        status=derive_status(run, folder, now, active_run_id),
        note=note,
        file_errors=errors,
        **loaded,
    )
