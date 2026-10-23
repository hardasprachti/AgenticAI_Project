"""Fixtures for the dashboard API tests: a throwaway data dir and a TestClient."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from api.main import create_app
from api.settings import Settings
from fastapi.testclient import TestClient

from pulse.config import DEFAULT_CONFIG_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_data_dir(tmp_path: Path) -> Settings:
    """Settings for the repo's real config.yaml, with data_dir pointing at an empty tmp tree."""
    data_dir = tmp_path / "data"
    (data_dir / "runs").mkdir(parents=True)
    settings = Settings.load(REPO_ROOT / DEFAULT_CONFIG_PATH)
    return Settings(config=settings.config, data_dir=data_dir, repo_root=REPO_ROOT)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_data_dir(tmp_path)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def completed_run_json():
    """Factory: the shape of a real dry-run record (values from data/runs/20261022-121514)."""

    def make(run_id: str = "20261022-121514") -> dict:
        return {
            "run_id": run_id,
            "week_label": "2026-W43",
            "status": "completed",
            "started_at": "2026-10-22T12:15:14.967424+00:00",
            "stages": [
                {
                    "name": "ingest",
                    "duration_s": 79.672,
                    "counts": {
                        "fetched": 10332,
                        "pages": 52,
                        "items_seen": 10400,
                        "kept": 10332,
                        "outside_window": 68,
                    },
                    "notes": ["raw cache: data\\raw\\" + run_id + "\\reviews.json"],
                },
                {
                    "name": "sanitize",
                    "duration_s": 1.213,
                    "counts": {"fetched": 10332, "kept": 3029, "clean": 3029, "analysed": 500},
                    "notes": ["analysing a sample of 500 of 3029 reviews"],
                },
                {"name": "theme", "duration_s": 335.988, "counts": {"themes": 6}, "notes": []},
                {"name": "rank", "duration_s": 0.006, "counts": {"ranked": 6}, "notes": []},
                {"name": "compose", "duration_s": 18.931, "counts": {"attempts": 1}, "notes": []},
                {"name": "render", "duration_s": 0.0, "counts": {"words": 192}, "notes": []},
            ],
            "theme_scores": {},
            "retries": 0,
            "violations": [],
            "word_count": 192,
            "doc_id": None,
            "doc_url": None,
            "doc_revision_id": None,
            "draft_id": None,
        }

    return make


@pytest.fixture
def failed_run_json():
    """Factory: a run that died in the theme stage (values from data/runs/20261022-151338)."""

    def make(run_id: str = "20261022-151338") -> dict:
        return {
            "run_id": run_id,
            "week_label": "2026-W43",
            "status": "failed",
            "started_at": "2026-10-22T15:13:38.804812+00:00",
            "stages": [
                {
                    "name": "ingest",
                    "duration_s": 70.457,
                    "counts": {"fetched": 10366, "pages": 52, "items_seen": 10400},
                    "notes": [],
                },
                {
                    "name": "sanitize",
                    "duration_s": 1.604,
                    "counts": {"fetched": 10366, "kept": 3038, "clean": 3038, "analysed": 500},
                    "notes": [],
                },
                {"name": "theme", "duration_s": 0.0, "counts": {}, "notes": []},
            ],
            "theme_scores": {},
            "retries": 0,
            "violations": ["LLMError: Groq tokens-per-day limit reached"],
            "word_count": 0,
            "doc_id": None,
            "doc_url": None,
            "doc_revision_id": None,
            "draft_id": None,
        }

    return make


@pytest.fixture
def write_run(settings: Settings):
    """Create <data_dir>/runs/<run_id>/ with the given files (dicts as JSON, str as text)."""

    def write(run_id: str, **files) -> Path:
        folder = settings.data_dir / "runs" / run_id
        folder.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            filename = "note.txt" if name == "note" else f"{name}.json"
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            (folder / filename).write_text(text, encoding="utf-8")
        return folder

    return write
