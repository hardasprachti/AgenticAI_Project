"""The API serves the built web app from one origin, without widening what it can read."""

from __future__ import annotations

from pathlib import Path

import pytest
from api.main import create_app
from api.settings import Settings
from fastapi.testclient import TestClient


@pytest.fixture
def web_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Pulse</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("do-not-serve", encoding="utf-8")
    return dist


@pytest.fixture
def web_client(settings: Settings, web_dist: Path) -> TestClient:
    return TestClient(create_app(settings, web_dist=web_dist))


def test_root_serves_index(web_client):
    r = web_client.get("/")
    assert r.status_code == 200
    assert "<title>Pulse</title>" in r.text


@pytest.mark.parametrize("path", ["/runs", "/runs/20261022-121514", "/ledger", "/settings"])
def test_spa_routes_fall_back_to_index(web_client, path):
    r = web_client.get(path)
    assert r.status_code == 200
    assert "<title>Pulse</title>" in r.text


def test_assets_are_served(web_client):
    assert web_client.get("/assets/app.js").text == "console.log(1)"


def test_api_routes_win_over_fallback(web_client):
    assert web_client.get("/api/runs").json() == []
    assert "taxonomy" in web_client.get("/api/config").json()


def test_unknown_api_path_is_json_404_not_index(web_client):
    r = web_client.get("/api/nope")
    assert r.status_code == 404
    assert "<title>" not in r.text


@pytest.mark.parametrize(
    "path",
    [
        "/..%2fsecret.txt",
        "/assets/..%2fsecret.txt",
        "/%2e%2e/secret.txt",
        "/assets/../../secret.txt",
    ],
)
def test_traversal_never_leaks_files(web_client, path):
    assert "do-not-serve" not in web_client.get(path).text


def test_without_a_build_the_api_still_works(settings, tmp_path):
    client = TestClient(create_app(settings, web_dist=tmp_path / "missing"))
    assert client.get("/api/runs").status_code == 200
    assert client.get("/").status_code == 404


def test_fallback_is_not_in_openapi(web_client):
    assert not any(not p.startswith("/api") for p in web_client.app.openapi()["paths"])
