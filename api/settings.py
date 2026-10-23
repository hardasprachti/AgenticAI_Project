"""Runtime settings: the pulse Config plus the resolved data directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pulse.config import DEFAULT_CONFIG_PATH, Config, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    config: Config
    data_dir: Path
    repo_root: Path

    @classmethod
    def load(cls, config_path: Path = DEFAULT_CONFIG_PATH) -> Settings:
        config_path = Path(config_path)
        if not config_path.is_absolute():
            config_path = REPO_ROOT / config_path
        config = load_config(config_path)
        data_dir = config.data_dir if config.data_dir.is_absolute() else REPO_ROOT / config.data_dir
        return cls(config=config, data_dir=data_dir, repo_root=REPO_ROOT)
