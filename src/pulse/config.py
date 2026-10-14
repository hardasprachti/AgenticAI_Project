"""Load and validate config.yaml (architecture section 9)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config.yaml")

MIN_WINDOW_WEEKS = 8
MAX_WINDOW_WEEKS = 12
MAX_THEMES_CAP = 5


class ConfigError(ValueError):
    """Raised when config.yaml is missing, malformed, or violates a hard constraint."""


@dataclass(frozen=True)
class AppConfig:
    play_package: str
    play_lang: str
    play_country: str


@dataclass(frozen=True)
class RankingConfig:
    volume: float
    recency: float
    severity: float
    recency_window_weeks: int


@dataclass(frozen=True)
class McpServerConfig:
    command: str | None
    args: list[str]
    tools: dict[str, str | None]

    @property
    def is_configured(self) -> bool:
        return bool(self.command) and all(self.tools.values())


@dataclass(frozen=True)
class Config:
    app: AppConfig
    window_weeks: int
    max_themes: int
    taxonomy: list[str]
    ranking: RankingConfig
    max_words: int
    models: dict[str, str]
    mcp_docs: McpServerConfig
    mcp_gmail: McpServerConfig
    draft_to: str | None
    data_dir: Path
    prompts_dir: Path
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise ConfigError(f"Missing required config value: {where}{key}")
    return mapping[key]


def _mcp_server(raw: dict[str, Any], name: str) -> McpServerConfig:
    section = raw.get("mcp", {}).get(name, {})
    return McpServerConfig(
        command=section.get("command"),
        args=list(section.get("args") or []),
        tools=dict(section.get("tools") or {}),
    )


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    app = _require(raw, "app", "")
    window_weeks = int(_require(raw, "window_weeks", ""))
    max_themes = int(_require(raw, "max_themes", ""))

    if not MIN_WINDOW_WEEKS <= window_weeks <= MAX_WINDOW_WEEKS:
        raise ConfigError(
            f"window_weeks must be between {MIN_WINDOW_WEEKS} and {MAX_WINDOW_WEEKS}, "
            f"got {window_weeks}"
        )
    if not 1 <= max_themes <= MAX_THEMES_CAP:
        raise ConfigError(f"max_themes must be between 1 and {MAX_THEMES_CAP}, got {max_themes}")

    taxonomy = list(raw.get("taxonomy") or [])
    if len(taxonomy) > max_themes:
        raise ConfigError(
            f"taxonomy has {len(taxonomy)} entries, more than max_themes ({max_themes})"
        )

    ranking = _require(raw, "ranking", "")
    weights = _require(ranking, "weights", "ranking.")
    ranking_cfg = RankingConfig(
        volume=float(weights["volume"]),
        recency=float(weights["recency"]),
        severity=float(weights["severity"]),
        recency_window_weeks=int(ranking.get("recency_window_weeks", 2)),
    )

    paths = raw.get("paths") or {}
    return Config(
        app=AppConfig(
            play_package=_require(app, "play_package", "app."),
            play_lang=app.get("play_lang", "en"),
            play_country=app.get("play_country", "in"),
        ),
        window_weeks=window_weeks,
        max_themes=max_themes,
        taxonomy=taxonomy,
        ranking=ranking_cfg,
        max_words=int((raw.get("pulse") or {}).get("max_words", 250)),
        models=dict(raw.get("models") or {}),
        mcp_docs=_mcp_server(raw, "docs"),
        mcp_gmail=_mcp_server(raw, "gmail"),
        draft_to=raw.get("draft_to"),
        data_dir=Path(paths.get("data_dir", "data")),
        prompts_dir=Path(paths.get("prompts_dir", "prompts")),
        raw=raw,
    )
