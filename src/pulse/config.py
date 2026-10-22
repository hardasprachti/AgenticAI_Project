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
class LlmConfig:
    batch_size: int
    max_retries: int
    timeout_s: float
    max_output_tokens: int
    reasoning_effort: str | None = None
    max_rate_limit_retries: int = 8
    max_rate_limit_wait_s: float = 120.0


@dataclass(frozen=True)
class ComposeConfig:
    candidates_per_theme: int
    max_retries: int


@dataclass(frozen=True)
class PlayConfig:
    page_size: int
    delay_s: float
    max_retries: int
    max_pages: int
    max_reviews: int


@dataclass(frozen=True)
class McpConfig:
    """The single Google Workspace MCP server that serves Docs and Gmail."""

    server_dir: Path | None
    command: str
    entrypoint: str
    document_id: str | None
    tools: dict[str, str]
    timeout_s: float = 60.0
    max_retries: int = 3  # for rate limits only; other write failures are never retried blindly
    retry_base_s: float = 2.0
    max_email_body_bytes: int = 1_048_576  # the server's MAX_EMAIL_BODY_BYTES default

    @property
    def allowed_tools(self) -> frozenset[str]:
        """The allowlist: the client may call only these server tools."""
        return frozenset(self.tools.values())

    @property
    def is_configured(self) -> bool:
        return self.server_dir is not None and bool(self.document_id)


@dataclass(frozen=True)
class Config:
    app: AppConfig
    window_weeks: int
    max_themes: int
    taxonomy: list[str]
    ranking: RankingConfig
    max_words: int
    min_reviews: int
    min_words: int
    max_analysed: int
    play: PlayConfig
    models: dict[str, str]
    llm: LlmConfig
    compose: ComposeConfig
    mcp: McpConfig
    draft_to: str | None
    data_dir: Path
    prompts_dir: Path
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise ConfigError(f"Missing required config value: {where}{key}")
    return mapping[key]


def _mcp_config(raw: dict[str, Any]) -> McpConfig:
    section = raw.get("mcp") or {}
    tools = {k: v for k, v in (section.get("tools") or {}).items() if v}
    server_dir = section.get("server_dir")
    return McpConfig(
        server_dir=Path(server_dir) if server_dir else None,
        command=section.get("command") or "node",
        entrypoint=section.get("entrypoint") or "dist/index.js",
        document_id=section.get("document_id"),
        tools=tools,
        timeout_s=float(section.get("timeout_s", 60)),
        max_retries=int(section.get("max_retries", 3)),
        retry_base_s=float(section.get("retry_base_s", 2)),
        max_email_body_bytes=int(section.get("max_email_body_bytes", 1_048_576)),
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
    llm = raw.get("llm") or {}
    compose = raw.get("compose") or {}
    play = raw.get("play") or {}
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
        min_reviews=int((raw.get("pulse") or {}).get("min_reviews", 20)),
        min_words=int((raw.get("pulse") or {}).get("min_words", 4)),
        max_analysed=int((raw.get("pulse") or {}).get("max_analysed", 500)),
        play=PlayConfig(
            page_size=int(play.get("page_size", 200)),
            delay_s=float(play.get("delay_s", 1.0)),
            max_retries=int(play.get("max_retries", 3)),
            max_pages=int(play.get("max_pages", 400)),
            max_reviews=int(play.get("max_reviews", 30000)),
        ),
        models=dict(raw.get("models") or {}),
        llm=LlmConfig(
            batch_size=int(llm.get("batch_size", 40)),
            max_retries=int(llm.get("max_retries", 3)),
            timeout_s=float(llm.get("timeout_s", 60)),
            max_output_tokens=int(llm.get("max_output_tokens", 4096)),
            reasoning_effort=llm.get("reasoning_effort"),
            max_rate_limit_retries=int(llm.get("max_rate_limit_retries", 8)),
            max_rate_limit_wait_s=float(llm.get("max_rate_limit_wait_s", 120)),
        ),
        compose=ComposeConfig(
            candidates_per_theme=int(compose.get("candidates_per_theme", 5)),
            max_retries=int(compose.get("max_retries", 2)),
        ),
        mcp=_mcp_config(raw),
        draft_to=raw.get("draft_to"),
        data_dir=Path(paths.get("data_dir", "data")),
        prompts_dir=Path(paths.get("prompts_dir", "prompts")),
        raw=raw,
    )
