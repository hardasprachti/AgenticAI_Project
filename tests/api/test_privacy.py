"""Privacy and safety regression suite for the dashboard API and web sources.

These guard the Global Constraints: the raw Play Store cache (reviewer names) is never read or
served, no Google/OAuth code lives in the dashboard, no endpoint can send email, CORS is limited
to the Vite dev origins, and no secret reaches a response.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from api.main import VITE_ORIGINS
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "api"
WEB_DIR = REPO_ROOT / "web"

RUN_ID = "20261022-121514"
SENTINEL_NAME = "Sentinel Reviewer"
SENTINEL_EMAIL = "sentinel@example.com"
SECRET = "sk-test-secret"

RAW_SEGMENT_RE = re.compile(r"(^|[\\/])raw($|[\\/])", re.IGNORECASE)


@pytest.fixture
def populated(settings, write_run, completed_run_json):
    """A run with every file the API serves, a ledger, and a raw cache holding sentinel identity."""
    reviews = [
        {
            "review_id": f"r{i:04d}abcdef0123",
            "store": "play",
            "rating": 1 + i % 5,
            "title": "Slow",
            "text": f"Withdrawal is slow {i}",
            "date": "2026-10-01",
            "app_version": "1.2.3",
        }
        for i in range(10)
    ]
    write_run(
        RUN_ID,
        **{
            "run": completed_run_json(RUN_ID),
            "sanitized": reviews,
            "themes": {"assignments": {r["review_id"]: "other" for r in reviews}},
            "pulse": {"themes": [], "quotes": [], "actions": []},
            "ranking": [],
            "note": "Weekly pulse note",
        },
    )
    raw_dir = settings.data_dir / "raw" / RUN_ID
    raw_dir.mkdir(parents=True)
    (raw_dir / "reviews.json").write_text(
        json.dumps([{"userName": SENTINEL_NAME, "email": SENTINEL_EMAIL, "content": "x"}]),
        encoding="utf-8",
    )
    (settings.data_dir / "ledger.json").write_text(
        json.dumps({"2026-W43": {"doc": {"state": "appended", "run_id": RUN_ID}}}),
        encoding="utf-8",
    )
    return RUN_ID


def get_endpoints(run_id: str) -> list[str]:
    return [
        "/api/config",
        "/api/runs",
        "/api/runs/active",
        f"/api/runs/{run_id}",
        f"/api/runs/{run_id}/reviews",
        f"/api/runs/{run_id}/reviews/summary",
        "/api/ledger",
    ]


def test_no_endpoint_leaks_raw_cache(client: TestClient, populated):
    for path in get_endpoints(populated):
        response = client.get(path)
        assert response.status_code == 200, path
        assert SENTINEL_NAME not in response.text, path
        assert SENTINEL_EMAIL not in response.text, path


def _python_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _raw_references(source: str) -> list[tuple[int, str]]:
    """String literals naming a `raw` path segment, and `.raw` attribute access (e.g. Config.raw).

    Comments and docstrings that merely mention the raw cache are not code paths and are skipped.
    """
    tree = ast.parse(source)
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            if node.value.lower() == "raw" or RAW_SEGMENT_RE.search(node.value):
                found.append((node.lineno, node.value))
        elif isinstance(node, ast.Attribute) and node.attr == "raw":
            found.append((node.lineno, f".{node.attr}"))
    return found


def test_raw_reference_scanner_catches_offenders():
    assert _raw_references('p = data_dir / "raw" / run_id')
    assert _raw_references('p = "data/raw/x"')
    assert _raw_references("p = cfg.raw")
    assert not _raw_references('"""The raw cache is never read."""\nx = 1')


def test_api_source_never_references_raw():
    offenders = {
        f"{path.relative_to(REPO_ROOT)}:{line}": text
        for path in _python_files(API_DIR)
        for line, text in _raw_references(path.read_text(encoding="utf-8"))
    }
    assert not offenders


def _web_files(*dirs: str) -> list[Path]:
    files: list[Path] = []
    for name in dirs:
        root = WEB_DIR / name
        if root.exists():
            files.extend(p for p in root.rglob("*") if p.is_file())
    return files


def test_web_source_never_references_raw():
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _web_files("src", "fixtures")
        if re.search(r"data[\\/]raw", path.read_text(encoding="utf-8", errors="ignore"))
        or "raw" in {part.lower() for part in path.relative_to(WEB_DIR).parts}
    ]
    assert not offenders


GOOGLE_RE = re.compile(r"googleapis|oauth|gmail_send|google\.auth", re.IGNORECASE)


def test_no_google_code():
    files = _python_files(API_DIR) + _web_files("src")
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in files
        if GOOGLE_RE.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert not offenders


def test_no_send_email_route(client: TestClient):
    schema = client.app.openapi()
    operations = {
        (method.upper(), path)
        for path, item in schema["paths"].items()
        for method in item
    }
    assert operations == {
        ("GET", "/api/config"),
        ("GET", "/api/runs"),
        ("POST", "/api/runs"),
        ("GET", "/api/runs/active"),
        ("GET", "/api/runs/{run_id}"),
        ("GET", "/api/runs/{run_id}/reviews"),
        ("GET", "/api/runs/{run_id}/reviews/summary"),
        ("GET", "/api/ledger"),
    }
    assert {(m, p) for m, p in operations if m != "GET"} == {("POST", "/api/runs")}


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/api/runs",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )


def test_cors_only_vite_origins(client: TestClient):
    assert "access-control-allow-origin" not in _preflight(client, "http://evil.example").headers
    for origin in VITE_ORIGINS:
        assert _preflight(client, origin).headers["access-control-allow-origin"] == origin


def test_no_secret_in_responses(client: TestClient, populated, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", SECRET)
    for path in get_endpoints(populated):
        assert SECRET not in client.get(path).text, path
