from pathlib import Path

import pytest
import yaml

from pulse.config import ConfigError, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(tmp_path: Path, **overrides) -> Path:
    base = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))
    base.update(overrides)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(base), encoding="utf-8")
    return path


def test_repo_config_loads():
    cfg = load_config(REPO_ROOT / "config.yaml")
    assert cfg.app.play_package == "com.nextbillion.groww"
    assert 8 <= cfg.window_weeks <= 12
    assert cfg.max_themes <= 5
    assert cfg.max_words == 250


def test_unset_integrations_are_reported_not_configured(tmp_path):
    cfg = load_config(_write(tmp_path, mcp={"server_dir": None, "document_id": None}))
    assert not cfg.mcp.is_configured


def test_mcp_allowlist_excludes_send():
    cfg = load_config(REPO_ROOT / "config.yaml")
    assert cfg.mcp.allowed_tools == {"google_docs_append_content", "gmail_create_draft"}
    assert "gmail_send_email" not in cfg.mcp.allowed_tools


def test_mcp_configured_once_dir_and_doc_set(tmp_path):
    mcp = {"server_dir": "C:/mcp-server-4", "document_id": "abc123"}
    cfg = load_config(_write(tmp_path, mcp=mcp))
    assert cfg.mcp.is_configured
    assert cfg.mcp.command == "node"
    assert not cfg.mcp.allowed_tools


@pytest.mark.parametrize("weeks", [7, 13])
def test_window_outside_range_rejected(tmp_path, weeks):
    with pytest.raises(ConfigError, match="window_weeks"):
        load_config(_write(tmp_path, window_weeks=weeks))


def test_more_than_five_themes_rejected(tmp_path):
    with pytest.raises(ConfigError, match="max_themes"):
        load_config(_write(tmp_path, max_themes=6))


def test_taxonomy_larger_than_cap_rejected(tmp_path):
    with pytest.raises(ConfigError, match="taxonomy"):
        load_config(_write(tmp_path, max_themes=2))


def test_missing_file_rejected(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_mcp_call_settings_default_and_can_be_overridden(tmp_path):
    cfg = load_config(REPO_ROOT / "config.yaml")
    assert cfg.mcp.timeout_s > 0 and cfg.mcp.max_retries >= 0
    assert cfg.mcp.max_email_body_bytes == 1_048_576

    custom = load_config(_write(tmp_path, mcp={"timeout_s": 5, "max_retries": 1}))
    assert (custom.mcp.timeout_s, custom.mcp.max_retries) == (5.0, 1)
