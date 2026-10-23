"""Starts `python -m pulse run` as a child process, one at a time, and reports on it.

The CLI is the only writer. This module builds its argv as a list (no shell), never forwards a
path from a request, never reads `.env` (the CLI loads its own), and never lets a second run start
while one is in flight, whether that run came from here, a terminal or the scheduler.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from api.runs import has_live_foreign_run, run_ids
from api.schemas import ActiveRun, StartRequest, StartResponse
from api.settings import Settings

TAIL_LINES = 6

_EXIT_MESSAGES = {
    0: "Run finished",
    1: "Run failed, was partial, or failed validation. See the run record",
    2: "Bad arguments, or the run could not be resumed",
    3: (
        "Stopped: a ledger step is pending. Check the Doc or Drafts folder, "
        "then use the ledger commands"
    ),
}

_API_KEY = re.compile(r"\b(?:gsk_|sk-)[A-Za-z0-9_\-]{8,}")
_ABSOLUTE_PATH = re.compile(
    r"""[A-Za-z]:[\\/][^\s'"<>|]*|(?<![\w.])/(?:Users|home|var|tmp|opt|etc|root)/[^\s'"]*"""
)


class RunConflict(RuntimeError):
    """A run is already in progress."""


class RunStartError(RuntimeError):
    """The child process could not be started."""


class Process(Protocol):
    pid: int
    stdout: Iterable[str]

    def wait(self) -> int: ...


Spawn = Callable[[list[str], Path], Process]


def exit_message(code: int) -> str:
    return _EXIT_MESSAGES.get(code, f"Exited with code {code}")


def default_spawn(argv: list[str], cwd: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        argv,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )


class RunController:
    def __init__(self, settings: Settings, spawn: Spawn = default_spawn) -> None:
        self.settings = settings
        self.spawn = spawn
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False
        self._started_mono = 0.0
        self._finished_mono: float | None = None
        self._before: frozenset[str] = frozenset()
        self._own_folders: frozenset[str] = frozenset()
        self._reset_result()

    def _reset_result(self) -> None:
        self._has_run = False
        self._last_line: str | None = None
        self._tail: deque[str] = deque(maxlen=TAIL_LINES)
        self._exit_code: int | None = None
        self._new_run_id: str | None = None
        self._finished_mono = None

    # --- starting ----------------------------------------------------------------------------

    def start(self, request: StartRequest) -> StartResponse:
        argv = [sys.executable, "-m", "pulse", "run", "--source", request.source]
        if request.dry_run:
            argv.append("--dry-run")
        if request.as_of is not None:
            argv += ["--as-of", request.as_of.isoformat()]

        with self._lock:
            if self._running or has_live_foreign_run(self.settings, time.time(), self._own_folders):
                raise RunConflict("A run is already in progress")
            before = frozenset(run_ids(self.settings))
            try:
                process = self.spawn(argv, self.settings.repo_root)
            except OSError as exc:
                raise RunStartError("Could not start the run") from exc
            self._reset_result()
            self._has_run = True
            self._running = True
            self._started_mono = time.monotonic()
            self._before = before
            self._thread = threading.Thread(
                target=self._pump, args=(process,), name="pulse-run-output", daemon=True
            )
            self._thread.start()
        return StartResponse(pid=process.pid, started_at=datetime.now(UTC).isoformat())

    def _pump(self, process: Process) -> None:
        code = -1  # stays -1 only if reading the output itself failed
        try:
            for raw in process.stdout:
                line = self._redact(raw.strip())
                if line:
                    with self._lock:
                        self._last_line = line
                        self._tail.append(line)
            code = process.wait()
        finally:
            with self._lock:
                new = [name for name in run_ids(self.settings) if name not in self._before]
                self._own_folders = frozenset(new)
                self._new_run_id = new[0] if new else None
                self._exit_code = code
                self._finished_mono = time.monotonic()
                self._running = False

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    # --- reporting ---------------------------------------------------------------------------

    @property
    def active_run_id(self) -> str | None:
        """The folder the in-flight child created, so the run list can call it `running`."""
        with self._lock:
            if not self._running:
                return None
            new = [name for name in run_ids(self.settings) if name not in self._before]
            return new[0] if new else None

    def active(self) -> ActiveRun:
        with self._lock:
            running = self._running
            foreign = not running and has_live_foreign_run(
                self.settings, time.time(), self._own_folders
            )
            own = running or (self._has_run and not foreign)
            elapsed = None
            if own:
                end = time.monotonic() if running else self._finished_mono
                elapsed = round(max(0.0, (end or 0.0) - self._started_mono), 1)
            finished = self._has_run and not running
            code = self._exit_code if finished else None
            return ActiveRun(
                active=running or foreign,
                elapsed_s=elapsed,
                last_line=self._last_line if self._has_run else None,
                started_by_api=own,
                exit_code=code,
                exit_message=exit_message(code) if code is not None else None,
                new_run_id=self._new_run_id if finished else None,
                stderr_tail=list(self._tail) if finished and code != 0 else [],
            )

    # --- output hygiene ----------------------------------------------------------------------

    def _redact(self, line: str) -> str:
        """The CLI's output is shown in the browser: strip local paths and key-shaped strings."""
        roots = [self.settings.repo_root, self.settings.config.mcp.server_dir]
        for root in filter(None, roots):
            for form in {str(root), str(root).replace("\\", "/"), str(root).replace("/", "\\")}:
                line = re.sub(re.escape(form), "<repo>", line, flags=re.IGNORECASE)
        line = _ABSOLUTE_PATH.sub("<path>", line)
        line = _API_KEY.sub("[redacted]", line)
        secret: Any = os.environ.get("GROQ_API_KEY")
        return line.replace(secret, "[redacted]") if secret else line
