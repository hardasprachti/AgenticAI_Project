"""Tolerant JSON reading. Every read is UTF-8: reviews hold rupee signs, Hinglish and emoji."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> tuple[Any | None, str | None]:
    """Return (data, None), or (None, "missing" | "unreadable"). Never raises."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except (OSError, UnicodeDecodeError):
        return None, "unreadable"
    try:
        return json.loads(text), None
    except ValueError:
        return None, "unreadable"
