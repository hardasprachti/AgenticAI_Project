import pytest
from api.files import read_json
from api.safe_paths import RUN_ID_RE, RunNotFound, safe_run_dir


@pytest.mark.parametrize("run_id", ["20261022-121514", "20261022-121514-2"])
def test_run_id_regex_accepts(run_id):
    assert RUN_ID_RE.match(run_id)


@pytest.mark.parametrize(
    "run_id",
    [
        "..",
        "20261022-121514/..",
        "20261022-12151",
        "20261022-121514-",
        "2026-10-22",
        "20261022-121514\\..\\x",
    ],
)
def test_run_id_regex_rejects(run_id):
    assert not RUN_ID_RE.match(run_id)


@pytest.mark.parametrize(
    "run_id", ["..", "../..", "20261022-121514/..", "2026-10-22", "20261022-121514\n"]
)
def test_safe_run_dir_rejects_bad_ids(settings, run_id):
    with pytest.raises(RunNotFound):
        safe_run_dir(settings, run_id)


def test_safe_run_dir_stays_inside_runs(settings):
    path = safe_run_dir(settings, "20261022-121514")
    assert path.parent == (settings.data_dir / "runs").resolve()
    assert path.name == "20261022-121514"


def test_safe_run_dir_rejects_symlink_escape(settings, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = settings.data_dir / "runs" / "20261022-121514"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted on this machine")
    with pytest.raises(RunNotFound):
        safe_run_dir(settings, "20261022-121514")


def test_traversal_is_404(client):
    assert client.get("/api/runs/..%2f..%2fconfig.yaml").status_code == 404
    assert client.get("/api/runs/%2e%2e").status_code == 404


def test_read_json_missing_and_garbage(tmp_path):
    assert read_json(tmp_path / "absent.json") == (None, "missing")
    bad = tmp_path / "bad.json"
    bad.write_text('{"a":', encoding="utf-8")
    assert read_json(bad) == (None, "unreadable")


def test_read_json_is_utf8(tmp_path):
    path = tmp_path / "ok.json"
    path.write_bytes('{"t": "₹295 सही है 😀"}'.encode())
    assert read_json(path) == ({"t": "₹295 सही है 😀"}, None)
