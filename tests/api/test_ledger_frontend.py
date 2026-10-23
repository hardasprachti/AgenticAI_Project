import json

import pytest

RUN = "20261022-121514"

DOC_DONE = {
    "state": "appended",
    "run_id": "20261022-121514",
    "document_id": "doc123",
    "revision_id": "rev456",
    "characters_appended": 1284,
}
DRAFT_DONE = {
    "state": "created",
    "run_id": "20261022-121514",
    "draft_id": "r-1",
    "thread_id": "t-1",
    "subject": "Groww Weekly Review Pulse 2026-W43",
}


@pytest.fixture
def ledger_path(settings):
    return settings.data_dir / "ledger.json"


def test_absent_ledger_is_empty(client):
    assert client.get("/api/ledger").json() == {"weeks": {}, "error": None}


def test_ledger_shape_and_pending(client, ledger_path):
    ledger = {
        "2026-W43": {"doc": DOC_DONE, "draft": DRAFT_DONE},
        "2026-W39": {
            "doc": {**DOC_DONE, "run_id": "20260928-090000"},
            "draft": {"state": "pending", "run_id": "20260928-090000"},
        },
    }
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    body = client.get("/api/ledger").json()

    assert body["error"] is None
    w43, w39 = body["weeks"]["2026-W43"], body["weeks"]["2026-W39"]
    for key, value in DOC_DONE.items():
        assert w43["doc"][key] == value
    for key, value in DRAFT_DONE.items():
        assert w43["draft"][key] == value
    assert w39["draft"]["state"] == "pending"
    assert w39["draft"]["run_id"] == "20260928-090000"
    assert w39["doc"]["state"] == "appended"


def test_week_with_only_a_doc_has_null_draft(client, ledger_path):
    ledger_path.write_text(json.dumps({"2026-W40": {"doc": DOC_DONE}}), encoding="utf-8")
    week = client.get("/api/ledger").json()["weeks"]["2026-W40"]
    assert week["draft"] is None
    assert week["doc"]["state"] == "appended"


def test_confirmed_by_hand_is_passed_through(client, ledger_path):
    draft = {**DRAFT_DONE, "confirmed_by_hand": True}
    ledger_path.write_text(json.dumps({"2026-W43": {"draft": draft}}), encoding="utf-8")
    week = client.get("/api/ledger").json()["weeks"]["2026-W43"]
    assert week["draft"]["confirmed_by_hand"] is True
    assert week["doc"] is None


def test_unknown_keys_are_not_passed_through(client, ledger_path):
    doc = {**DOC_DONE, "internal_path": "C:/secret"}
    ledger_path.write_text(json.dumps({"2026-W43": {"doc": doc}}), encoding="utf-8")
    response = client.get("/api/ledger")
    assert "internal_path" not in response.text and "secret" not in response.text


def test_corrupt_ledger_is_error_not_empty(client, ledger_path):
    # Review Focus 3: an unreadable ledger must not look like "nothing published".
    ledger_path.write_text('{"2026-W43":', encoding="utf-8")
    assert client.get("/api/ledger").json() == {"weeks": {}, "error": "ledger_unreadable"}


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        '"text"',
        "null",
        '{"2026-W43": []}',
        '{"2026-W43": {"doc": "appended"}}',
        '{"2026-W43": {"doc": {"state": "weird", "run_id": "x"}}}',
        '{"2026-W43": {"doc": {"run_id": "x"}}}',
    ],
)
def test_malformed_ledger_is_error_not_empty(client, ledger_path, content):
    ledger_path.write_text(content, encoding="utf-8")
    assert client.get("/api/ledger").json() == {"weeks": {}, "error": "ledger_unreadable"}


def test_ledger_read_as_utf8(client, ledger_path):
    draft = {**DRAFT_DONE, "subject": "Pulse ₹ सही है"}
    ledger_path.write_bytes(
        json.dumps({"2026-W43": {"draft": draft}}, ensure_ascii=False).encode("utf-8")
    )
    assert client.get("/api/ledger").json()["weeks"]["2026-W43"]["draft"]["subject"] == (
        "Pulse ₹ सही है"
    )


def test_get_never_writes_ledger(client, ledger_path, write_run, completed_run_json):
    write_run(RUN, run=completed_run_json(), sanitized=[], themes={})
    ledger_path.write_text(json.dumps({"2026-W43": {"doc": DOC_DONE}}), encoding="utf-8")
    before = (ledger_path.read_bytes(), ledger_path.stat().st_mtime_ns)

    for path in (
        "/api/config",
        "/api/runs",
        f"/api/runs/{RUN}",
        f"/api/runs/{RUN}/reviews",
        f"/api/runs/{RUN}/reviews/summary",
        "/api/ledger",
    ):
        assert client.get(path).status_code == 200, path

    assert (ledger_path.read_bytes(), ledger_path.stat().st_mtime_ns) == before
    assert not ledger_path.with_suffix(".tmp").exists()


def test_corrupt_ledger_is_left_untouched(client, ledger_path):
    ledger_path.write_text('{"broken"', encoding="utf-8")
    client.get("/api/ledger")
    assert ledger_path.read_text(encoding="utf-8") == '{"broken"'


def test_only_the_read_method_of_ledger_is_used():
    import inspect

    import api.ledger_view as module

    source = inspect.getsource(module)
    for forbidden in ("mark_pending", "mark_done", ".clear(", "_write"):
        assert forbidden not in source
