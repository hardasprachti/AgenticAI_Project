import inspect
import os
import sys
import threading
import time
from datetime import date, timedelta

import pytest
from api.controller import RunController, default_spawn, exit_message
from api.main import create_app
from api.runs import RUNNING_STALE_AFTER_S
from api.schemas import StartRequest
from fastapi.testclient import TestClient

NEW_RUN = "20261022-160000"


class FakeProcess:
    """Stands in for subprocess.Popen: emits `lines`, then holds until released, then exits."""

    def __init__(self, lines=(), code=0, hold=False, pid=4242):
        self.pid = pid
        self.release = threading.Event()
        if not hold:
            self.release.set()
        self._lines, self._code = lines, code
        self.stdout = self._emit()

    def _emit(self):
        for line in self._lines:
            yield line + "\n"
        assert self.release.wait(10), "test forgot to release the fake process"

    def wait(self):
        return self._code


class Spawner:
    def __init__(self, settings, make=None, creates_folder=None):
        self.settings = settings
        self.make = make or (lambda: FakeProcess())
        self.creates_folder = creates_folder
        self.calls = []
        self.processes = []

    def __call__(self, argv, cwd):
        self.calls.append((argv, cwd))
        if self.creates_folder:
            (self.settings.data_dir / "runs" / self.creates_folder).mkdir(parents=True)
        process = self.make()
        self.processes.append(process)
        return process


def make_client(settings, spawner):
    app = create_app(settings)
    app.state.controller = RunController(settings, spawn=spawner)
    return TestClient(app), app.state.controller


def wait_until_idle(client, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get("/api/runs/active").json()
        if not body["active"]:
            return body
        time.sleep(0.01)
    raise AssertionError("run never finished")


def post(client, **body):
    return client.post("/api/runs", json=body)


def test_defaults_to_dry_run(settings):
    spawner = Spawner(settings)
    client, _ = make_client(settings, spawner)
    response = post(client, source="csv")
    assert response.status_code == 200
    assert set(response.json()) == {"pid", "started_at"}
    ((argv, cwd),) = spawner.calls
    assert argv == [sys.executable, "-m", "pulse", "run", "--source", "csv", "--dry-run"]
    assert cwd == settings.repo_root


def test_as_of_is_passed_as_a_separate_argument(settings):
    spawner = Spawner(settings)
    client, _ = make_client(settings, spawner)
    assert post(client, source="play", as_of="2026-10-01").status_code == 200
    argv = spawner.calls[0][0]
    assert argv[-3:] == ["--dry-run", "--as-of", "2026-10-01"]


def test_publish_requires_confirm(settings):
    spawner = Spawner(settings)
    client, _ = make_client(settings, spawner)
    assert post(client, source="csv", dry_run=False).status_code == 422
    assert post(client, source="csv", dry_run=False, confirm="yes").status_code == 422
    assert post(client, source="csv", dry_run=False, confirm="PUBLISH").status_code == 422
    assert spawner.calls == []

    assert post(client, source="csv", dry_run=False, confirm="publish").status_code == 200
    assert "--dry-run" not in spawner.calls[0][0]


@pytest.mark.parametrize(
    "body",
    [
        {"source": "x"},
        {},
        {"source": "csv", "as_of": "2026-13-40"},
        {"source": "csv", "as_of": (date.today() + timedelta(days=1)).isoformat()},
        {"source": "csv", "path": "C:/secrets.csv"},
        {"source": "csv", "fallback_csv": "x.csv"},
        {"source": "csv", "dry_run": "maybe"},
    ],
)
def test_rejects_bad_input(settings, body):
    spawner = Spawner(settings)
    client, _ = make_client(settings, spawner)
    assert post(client, **body).status_code == 422
    assert spawner.calls == []


def test_today_is_a_valid_as_of(settings):
    client, _ = make_client(settings, Spawner(settings))
    assert post(client, source="csv", as_of=date.today().isoformat()).status_code == 200


def test_second_start_is_409(settings):
    spawner = Spawner(settings, make=lambda: FakeProcess(hold=True))
    client, _ = make_client(settings, spawner)
    assert post(client, source="csv").status_code == 200
    second = post(client, source="csv")
    assert second.status_code == 409
    assert len(spawner.calls) == 1
    spawner.processes[0].release.set()
    wait_until_idle(client)
    spawner.make = lambda: FakeProcess()
    assert post(client, source="csv").status_code == 200
    wait_until_idle(client)


def test_double_submit_starts_once(settings):
    # Review Focus 5: many simultaneous POSTs, exactly one process.
    spawner = Spawner(settings, make=lambda: FakeProcess(hold=True))
    client, _ = make_client(settings, spawner)
    statuses = []
    barrier = threading.Barrier(8)

    def submit():
        barrier.wait()
        statuses.append(post(client, source="csv").status_code)

    threads = [threading.Thread(target=submit) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(statuses) == [200] + [409] * 7
    assert len(spawner.calls) == 1
    spawner.processes[0].release.set()
    wait_until_idle(client)


def test_foreign_live_run_blocks_start(settings, write_run):
    write_run("20261022-150000", sanitized=[])
    spawner = Spawner(settings)
    client, _ = make_client(settings, spawner)
    assert post(client, source="csv").status_code == 409
    assert spawner.calls == []
    active = client.get("/api/runs/active").json()
    assert active["active"] is True and active["started_by_api"] is False


def test_stale_folder_does_not_block(settings, write_run):
    # Review Focus 2: a run that died long ago must not lock the button forever.
    folder = write_run("20261022-150000", sanitized=[])
    old = time.time() - RUNNING_STALE_AFTER_S - 600
    for path in [*folder.iterdir(), folder]:
        os.utime(path, (old, old))
    client, _ = make_client(settings, Spawner(settings))
    assert client.get("/api/runs/active").json()["active"] is False
    assert post(client, source="csv").status_code == 200


def test_idle_active_state(settings):
    client, _ = make_client(settings, Spawner(settings))
    assert client.get("/api/runs/active").json() == {
        "active": False,
        "elapsed_s": None,
        "last_line": None,
        "started_by_api": False,
        "exit_code": None,
        "exit_message": None,
        "new_run_id": None,
        "stderr_tail": [],
    }


def test_active_reports_elapsed_last_line_and_exit(settings):
    process_lines = ["starting", "", "fetching page 3", "   "]
    spawner = Spawner(
        settings,
        make=lambda: FakeProcess(lines=process_lines, code=3, hold=True),
        creates_folder=NEW_RUN,
    )
    client, controller = make_client(settings, spawner)
    post(client, source="csv")

    deadline = time.time() + 5
    while client.get("/api/runs/active").json()["last_line"] != "fetching page 3":
        assert time.time() < deadline
        time.sleep(0.01)
    running = client.get("/api/runs/active").json()
    assert running["active"] is True
    assert running["started_by_api"] is True
    assert running["elapsed_s"] >= 0
    assert running["exit_code"] is None
    assert controller.active_run_id == NEW_RUN

    spawner.processes[0].release.set()
    done = wait_until_idle(client)
    assert done["last_line"] == "fetching page 3"
    assert done["exit_code"] == 3
    assert done["exit_message"].startswith("Stopped: a ledger step is pending")
    assert done["new_run_id"] == NEW_RUN
    assert done["started_by_api"] is True
    assert controller.active_run_id is None


def test_stderr_tail_keeps_last_six_non_empty_lines(settings):
    lines = [f"line {n}" for n in range(10)]
    spawner = Spawner(settings, make=lambda: FakeProcess(lines=lines, code=1))
    client, _ = make_client(settings, spawner)
    post(client, source="csv")
    done = wait_until_idle(client)
    assert done["stderr_tail"] == [f"line {n}" for n in range(4, 10)]
    assert done["exit_code"] == 1


def test_successful_run_has_no_stderr_tail(settings):
    spawner = Spawner(settings, make=lambda: FakeProcess(lines=["ok"], code=0))
    client, _ = make_client(settings, spawner)
    post(client, source="csv")
    done = wait_until_idle(client)
    assert done["exit_message"] == "Run finished"
    assert done["stderr_tail"] == []


def test_output_is_redacted(settings):
    secret = f"gsk_{'a1B2' * 8}"
    lines = [
        f"cannot read {settings.repo_root}/data/ledger.json",
        r"opened C:\Users\someone\AppData\x.txt with key " + secret,
    ]
    spawner = Spawner(settings, make=lambda: FakeProcess(lines=lines, code=1))
    client, _ = make_client(settings, spawner)
    post(client, source="csv")
    done = wait_until_idle(client)
    text = str(done)
    assert secret not in text
    assert str(settings.repo_root) not in text
    assert "someone" not in text
    assert "ledger.json" in done["stderr_tail"][0]


def test_finished_runs_own_folder_does_not_block_restart(settings):
    # The process exited, so its folder (even without run.json) is not a run in flight.
    spawner = Spawner(settings, make=lambda: FakeProcess(code=1), creates_folder=NEW_RUN)
    client, _ = make_client(settings, spawner)
    post(client, source="csv")
    wait_until_idle(client)
    spawner.creates_folder = None
    assert post(client, source="csv").status_code == 200


def test_a_new_start_clears_the_previous_result(settings):
    spawner = Spawner(settings, make=lambda: FakeProcess(lines=["boom"], code=1))
    client, _ = make_client(settings, spawner)
    post(client, source="csv")
    assert wait_until_idle(client)["exit_code"] == 1
    spawner.make = lambda: FakeProcess(hold=True)
    post(client, source="csv")
    now = client.get("/api/runs/active").json()
    assert now["active"] is True and now["exit_code"] is None and now["stderr_tail"] == []
    spawner.processes[-1].release.set()
    wait_until_idle(client)


def test_spawn_failure_is_500_and_does_not_lock(settings):
    def broken(argv, cwd):
        raise OSError("no such interpreter")

    client, controller = make_client(settings, broken)
    assert post(client, source="csv").status_code == 500
    spawner = Spawner(settings)
    controller.spawn = spawner
    assert post(client, source="csv").status_code == 200


def test_active_route_is_not_shadowed_by_run_id(settings):
    client, _ = make_client(settings, Spawner(settings))
    assert client.get("/api/runs/active").status_code == 200


def test_exit_messages():
    assert exit_message(0) == "Run finished"
    assert exit_message(1) == ("Run failed, was partial, or failed validation. See the run record")
    assert exit_message(2) == "Bad arguments, or the run could not be resumed"
    assert exit_message(3) == (
        "Stopped: a ledger step is pending. Check the Doc or Drafts folder, "
        "then use the ledger commands"
    )
    assert exit_message(7) == "Exited with code 7"
    assert exit_message(-9) == "Exited with code -9"


def test_argv_is_a_list_with_no_shell(settings):
    spawner = Spawner(settings)
    client, _ = make_client(settings, spawner)
    post(client, source="play", as_of="2026-10-01")
    argv, cwd = spawner.calls[0]
    assert isinstance(argv, list) and all(isinstance(a, str) for a in argv)
    assert argv.count("--as-of") == 1 and "2026-10-01" in argv
    assert all(" " not in a for a in argv[1:])  # no request string glued into one element
    assert "--path" not in argv and "--fallback-csv" not in argv
    source = inspect.getsource(default_spawn)
    assert "shell" not in source
    assert 'encoding="utf-8"' in source and 'errors="replace"' in source


def test_api_does_not_read_dotenv():
    import api.controller as module

    assert "dotenv" not in inspect.getsource(module)


def test_default_spawn_round_trips_utf8_and_exit_code(settings):
    # A real child process, but not the pulse CLI: it only prints non-ASCII text and exits 3.
    code = "import sys; print('₹295 सही है'); sys.exit(3)"
    controller = RunController(
        settings, spawn=lambda argv, cwd: default_spawn([sys.executable, "-c", code], cwd)
    )
    controller.start(StartRequest(source="csv"))
    controller.join(10)
    state = controller.active()
    assert state.last_line == "₹295 सही है"
    assert state.exit_code == 3
