"""Privacy audit: search everything a run wrote or would send for identities from the raw data."""

import csv
import dataclasses
import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from fake_mcp import FakeGoogleServer, make_config, no_sleep
from fakes import scripted_llm
from pulse.__main__ import main
from pulse.audit import Identities, audit_run, identities_from_csv, identities_from_raw_cache
from pulse.config import load_config
from pulse.mcp.client import McpClient
from pulse.orchestrator import run_week
from pulse.sources.csv_source import CsvSource

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "evals" / "fixtures" / "reviews.csv"
AS_OF = date(2026, 10, 19)


@pytest.fixture
def config(tmp_path):
    cfg = load_config(REPO_ROOT / "config.yaml")
    return dataclasses.replace(
        cfg,
        data_dir=tmp_path / "data",
        prompts_dir=REPO_ROOT / "prompts",
        mcp=make_config(),
        draft_to="me@example.com",
    )


@pytest.fixture
def published(config):
    fake = FakeGoogleServer()
    return run_week(
        source=CsvSource(FIXTURE),
        config=config,
        llm_factory=scripted_llm,
        client_factory=lambda: McpClient(make_config(), transport=fake.server, sleep=no_sleep),
        as_of=AS_OF,
    )


@pytest.fixture(scope="module")
def fixture_identities() -> Identities:
    return identities_from_csv(FIXTURE)


def test_identities_come_from_names_ids_and_pii_in_the_raw_text(fixture_identities):
    assert len(fixture_identities.names) > 20
    assert fixture_identities.store_ids
    assert fixture_identities.pii_strings  # the fixture seeds emails, phone numbers, URLs


def test_a_real_published_run_is_clean(config, published, fixture_identities):
    report = audit_run(published.run_dir, fixture_identities, data_dir=config.data_dir)

    assert report.findings == []
    scanned = " ".join(report.artifacts)
    assert "note.txt" in scanned and "run.json" in scanned
    assert "ledger.json" in scanned and "draft body" in scanned


def test_a_name_in_any_run_file_is_found_and_reported_without_the_name(
    config, published, fixture_identities
):
    name = sorted(fixture_identities.names)[0]
    (published.run_dir / "themes.json").write_text(f'{{"x": "thanks {name}"}}', encoding="utf-8")

    report = audit_run(published.run_dir, fixture_identities, data_dir=config.data_dir)

    assert [(f.artifact, f.kind) for f in report.findings] == [("themes.json", "reviewer name")]
    assert name not in report.render()  # the audit must not re-leak what it finds


def test_a_single_name_part_is_found_on_a_word_boundary_only(config, published):
    ids = Identities(names={"Priya Sharma"}, store_ids=set(), pii_strings=set())
    (published.run_dir / "a.txt").write_text("hello Sharma!", encoding="utf-8")
    (published.run_dir / "b.txt").write_text("Sharmaji and Priyanka", encoding="utf-8")

    found = {
        f.artifact for f in audit_run(published.run_dir, ids, data_dir=config.data_dir).findings
    }

    assert found == {"a.txt"}


def test_an_email_in_the_note_is_found_even_without_the_raw_data(config, published):
    note = (published.run_dir / "note.txt").read_text(encoding="utf-8")
    (published.run_dir / "note.txt").write_text(note + "\nwrite to someone@example.com", "utf-8")
    empty = Identities(names=set(), store_ids=set(), pii_strings=set())

    report = audit_run(published.run_dir, empty, data_dir=config.data_dir)

    assert any(f.artifact == "note.txt" and f.kind == "email" for f in report.findings)


def test_a_phone_number_from_the_raw_text_is_found_in_the_ledger_or_logs(config, published):
    ids = Identities(names=set(), store_ids=set(), pii_strings={"9876543210"})
    logs = config.data_dir / "logs"
    logs.mkdir()
    (logs / "weekly.log").write_text("user said call 9876543210", encoding="utf-8")

    report = audit_run(published.run_dir, ids, data_dir=config.data_dir)

    assert [(f.artifact, f.kind) for f in report.findings] == [
        ("logs/weekly.log", "personal data from the raw reviews")
    ]


def test_the_review_id_from_the_store_is_a_reviewer_identifier_too(config, published):
    ids = Identities(names=set(), store_ids={"gp-store-id-0042"}, pii_strings=set())
    (published.run_dir / "run.json").write_text("gp-store-id-0042", encoding="utf-8")

    report = audit_run(published.run_dir, ids, data_dir=config.data_dir)

    assert any(f.kind == "store review id" for f in report.findings)


def test_the_raw_cache_is_read_for_identities_and_is_not_itself_audited(config, tmp_path):
    cache = tmp_path / "reviews.json"
    cache.write_text(
        json.dumps(
            [
                {
                    "store_review_id": "sid-0001",
                    "text": "mail me a.b@example.com or 9123456780",
                    "author_name": "Rahul Verma",
                }
            ]
        ),
        encoding="utf-8",
    )

    ids = identities_from_raw_cache(cache)

    assert ids.names == {"Rahul Verma"} and ids.store_ids == {"sid-0001"}
    assert {"a.b@example.com", "9123456780"} <= ids.pii_strings


# --- the command ----------------------------------------------------------------------------


@pytest.fixture
def cli_config(tmp_path, config):
    raw = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))
    raw["paths"] = {"data_dir": str(config.data_dir), "prompts_dir": str(REPO_ROOT / "prompts")}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def test_audit_command_exits_zero_on_a_clean_run(cli_config, published, capsys):
    code = main(
        ["audit", published.run.run_id, "--raw-csv", str(FIXTURE), "--config", str(cli_config)]
    )

    assert code == 0
    assert "clean" in capsys.readouterr().out.lower()


def test_audit_command_exits_one_and_lists_findings_on_a_leak(
    cli_config, published, capsys, fixture_identities
):
    name = sorted(fixture_identities.names)[0]
    (published.run_dir / "sanitized.json").write_text(name, encoding="utf-8")

    code = main(
        ["audit", published.run.run_id, "--raw-csv", str(FIXTURE), "--config", str(cli_config)]
    )

    out = capsys.readouterr().out
    assert code == 1 and "sanitized.json" in out and "reviewer name" in out and name not in out


def test_audit_command_without_any_raw_source_explains_what_to_pass(cli_config, published, capsys):
    code = main(["audit", published.run.run_id, "--config", str(cli_config)])

    assert code == 2
    assert "--raw-csv" in capsys.readouterr().err


def test_audit_of_an_unknown_run_is_an_error(cli_config, capsys):
    assert main(["audit", "nope", "--raw-csv", str(FIXTURE), "--config", str(cli_config)]) == 2
    assert "nope" in capsys.readouterr().err


def test_fixture_has_the_columns_the_audit_reads():
    with FIXTURE.open(encoding="utf-8") as handle:
        assert {"author_name", "author_id", "text"} <= set(next(csv.reader(handle)))
