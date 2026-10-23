import json
import os
import time

import pytest
from api.runs import (
    RUNNING_STALE_AFTER_S,
    derive_status,
    get_run,
    has_live_foreign_run,
)
from api.safe_paths import RunNotFound

COMPLETED = "20261022-121514"
FAILED = "20261022-151338"


def age(folder, seconds):
    """Make a run folder and everything in it look `seconds` old."""
    stamp = time.time() - seconds
    for path in [*folder.iterdir(), folder]:
        os.utime(path, (stamp, stamp))


def test_list_newest_first_with_counts(client, write_run, completed_run_json, failed_run_json):
    write_run(COMPLETED, run=completed_run_json(), pulse={"week_label": "2026-W43"})
    write_run(FAILED, run=failed_run_json())
    rows = client.get("/api/runs").json()

    assert [r["run_id"] for r in rows] == [FAILED, COMPLETED]
    done = rows[1]
    assert done["status"] == "completed"
    assert done["week_label"] == "2026-W43"
    assert (done["fetched"], done["clean"], done["analysed"]) == (10332, 3029, 500)
    assert done["word_count"] == 192
    assert done["has_pulse"] is True
    assert done["is_dry_run"] is True
    assert done["duration_s"] == 435.81
    assert done["doc_url"] is None and done["draft_id"] is None
    assert set(done) == {
        "run_id",
        "week_label",
        "status",
        "started_at",
        "duration_s",
        "fetched",
        "clean",
        "analysed",
        "word_count",
        "has_pulse",
        "doc_url",
        "draft_id",
        "is_dry_run",
    }


def test_failed_run_keeps_funnel_counts(client, write_run, failed_run_json):
    write_run(FAILED, run=failed_run_json())
    (row,) = client.get("/api/runs").json()
    assert row["status"] == "failed"
    assert (row["fetched"], row["clean"], row["analysed"]) == (10366, 3038, 500)
    assert row["has_pulse"] is False
    assert row["is_dry_run"] is False


def test_published_run_is_not_dry_run(client, write_run, completed_run_json):
    run = completed_run_json() | {"doc_url": "https://docs.google.com/document/d/x/edit"}
    write_run(COMPLETED, run=run)
    (row,) = client.get("/api/runs").json()
    assert row["is_dry_run"] is False
    assert row["doc_url"].endswith("/edit")


def test_running_folder_without_run_json(client, write_run):
    write_run(COMPLETED, sanitized=[])
    (row,) = client.get("/api/runs").json()
    assert row["status"] == "running"
    assert row["week_label"] == "2026-W43"
    assert row["started_at"] == "2026-10-22T12:15:14+00:00"
    for key in ("duration_s", "fetched", "clean", "analysed", "word_count"):
        assert row[key] is None
    assert row["has_pulse"] is False


def test_stale_folder_is_interrupted(client, write_run):
    folder = write_run(COMPLETED, sanitized=[])
    age(folder, RUNNING_STALE_AFTER_S + 600)
    (row,) = client.get("/api/runs").json()
    assert row["status"] == "interrupted"


def test_recent_file_keeps_old_folder_running(client, write_run):
    folder = write_run(COMPLETED, sanitized=[])
    stamp = time.time() - 3 * RUNNING_STALE_AFTER_S
    os.utime(folder, (stamp, stamp))
    assert client.get("/api/runs").json()[0]["status"] == "running"


def test_derive_status_active_run_is_running_even_when_old(write_run):
    folder = write_run(COMPLETED, sanitized=[])
    age(folder, 10 * RUNNING_STALE_AFTER_S)
    now = time.time()
    assert derive_status(None, folder, now, None) == "interrupted"
    assert derive_status(None, folder, now, COMPLETED) == "running"
    assert derive_status(None, folder, now, "20990101-000000") == "interrupted"


def test_half_written_run_json(client, write_run, completed_run_json):
    text = json.dumps(completed_run_json())
    write_run(COMPLETED, run=text[: len(text) // 2], sanitized=[])
    (row,) = client.get("/api/runs").json()
    assert row["status"] == "unreadable"
    assert row["fetched"] is None

    detail = client.get(f"/api/runs/{COMPLETED}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["run"] is None
    assert body["status"] == "unreadable"
    assert body["file_errors"] == {"run": "unreadable"}


@pytest.mark.parametrize("content", ["[1, 2]", '"text"', "null"])
def test_run_json_that_is_not_an_object_is_unreadable(client, write_run, content):
    write_run(COMPLETED, run=content)
    assert client.get("/api/runs").json()[0]["status"] == "unreadable"
    assert client.get(f"/api/runs/{COMPLETED}").json()["file_errors"] == {"run": "unreadable"}


def test_unknown_status_is_unreadable(client, write_run, completed_run_json):
    write_run(COMPLETED, run=completed_run_json() | {"status": "exploded"})
    assert client.get("/api/runs").json()[0]["status"] == "unreadable"


def test_odd_stage_shapes_do_not_crash(client, write_run, completed_run_json):
    run = completed_run_json() | {"stages": ["x", {"name": "sanitize", "counts": []}, None]}
    write_run(COMPLETED, run=run)
    (row,) = client.get("/api/runs").json()
    assert row["status"] == "completed"
    assert row["clean"] is None and row["duration_s"] is None


def test_detail_returns_what_exists(client, write_run, completed_run_json):
    write_run(COMPLETED, run=completed_run_json(), sanitized=[])
    body = client.get(f"/api/runs/{COMPLETED}").json()
    assert body["status"] == "completed"
    assert body["run"]["run_id"] == COMPLETED
    assert body["pulse"] is None
    assert body["note"] is None
    assert body["ranking"] is None
    assert body["themes"] is None
    assert body["file_errors"] == {}
    assert set(body) == {"run", "status", "pulse", "note", "ranking", "themes", "file_errors"}


def test_detail_garbage_pulse_does_not_hide_the_rest(client, write_run, completed_run_json):
    write_run(
        COMPLETED,
        run=completed_run_json(),
        pulse='{"themes": [',
        note="Weekly note",
        ranking={"selected": ["a"]},
        themes={"assignments": {}},
    )
    body = client.get(f"/api/runs/{COMPLETED}").json()
    assert body["file_errors"] == {"pulse": "unreadable"}
    assert body["pulse"] is None
    assert body["note"] == "Weekly note"
    assert body["ranking"] == {"selected": ["a"]}
    assert body["themes"] == {"assignments": {}}


def test_unknown_run_404(client, write_run, completed_run_json):
    write_run(COMPLETED, run=completed_run_json())
    assert client.get("/api/runs/20250101-000000").status_code == 404
    assert client.get("/api/runs/not-a-run").status_code == 404


def test_already_published_run(client, write_run):
    run = {
        "run_id": COMPLETED,
        "week_label": "2026-W43",
        "status": "already_published",
        "started_at": "2026-10-22T12:15:14+00:00",
        "stages": [],
        "doc_url": "https://docs.google.com/document/d/x/edit",
        "draft_id": "r-123",
    }
    write_run(COMPLETED, run=run)
    (row,) = client.get("/api/runs").json()
    assert row["status"] == "already_published"
    assert row["doc_url"].endswith("/edit")
    assert row["draft_id"] == "r-123"
    assert row["is_dry_run"] is False
    for key in ("fetched", "clean", "analysed", "duration_s"):
        assert row[key] is None


def test_note_read_as_utf8(client, write_run, completed_run_json):
    write_run(COMPLETED, run=completed_run_json(), note="Withdrawals took ₹295 सही है 😀")
    assert client.get(f"/api/runs/{COMPLETED}").json()["note"] == "Withdrawals took ₹295 सही है 😀"


def test_detail_hides_filesystem_paths(client, write_run, completed_run_json):
    write_run(COMPLETED, run=completed_run_json())
    response = client.get(f"/api/runs/{COMPLETED}")
    notes = [n for stage in response.json()["run"]["stages"] for n in stage["notes"]]
    assert notes == ["analysing a sample of 500 of 3029 reviews"]
    assert "reviews.json" not in response.text


def test_retry_suffix_sorts_after_original(client, write_run, completed_run_json):
    for run_id in (COMPLETED, COMPLETED + "-2", COMPLETED + "-10", "20261022-121513"):
        write_run(run_id, run=completed_run_json(run_id))
    ids = [r["run_id"] for r in client.get("/api/runs").json()]
    assert ids == [COMPLETED + "-10", COMPLETED + "-2", COMPLETED, "20261022-121513"]


def test_listing_ignores_strays(client, settings, write_run, completed_run_json):
    write_run(COMPLETED, run=completed_run_json())
    runs = settings.data_dir / "runs"
    (runs / "notes").mkdir()
    (runs / "20261022-999999.txt").write_text("x", encoding="utf-8")
    (runs / "20261022-121515").write_text("a file named like a run", encoding="utf-8")
    assert [r["run_id"] for r in client.get("/api/runs").json()] == [COMPLETED]


def test_missing_runs_dir_is_empty_list(client, settings):
    (settings.data_dir / "runs").rmdir()
    assert client.get("/api/runs").json() == []


def test_has_live_foreign_run(settings, write_run, completed_run_json):
    now = time.time()
    assert has_live_foreign_run(settings, now) is False
    write_run("20261022-100000", run=completed_run_json("20261022-100000"))
    assert has_live_foreign_run(settings, now) is False
    folder = write_run(COMPLETED, sanitized=[])
    assert has_live_foreign_run(settings, now) is True
    age(folder, RUNNING_STALE_AFTER_S + 600)
    assert has_live_foreign_run(settings, now) is False


def test_get_run_raises_for_missing_folder(settings):
    with pytest.raises(RunNotFound):
        get_run(settings, COMPLETED, None)
