from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CANDIDATE_EXTENSIONS = ["pdf", "png", "jpg", "jpeg", "xml", "ofd", "zip"]
DEFAULT_KEYWORDS = [
    "发票",
    "电子发票",
    "invoice",
    "票据",
    "专票",
    "普票",
]


def _home() -> Path:
    return Path.home()


def default_archive_root() -> Path:
    return _home() / "Documents" / "invoice-archive"


def default_config_path() -> Path:
    return _home() / ".config" / "mail-invoice-archiver" / "config.toml"


@dataclass(slots=True)
class RuntimeConfig:
    archive_root: Path = field(default_factory=default_archive_root)
    candidate_extensions: list[str] = field(default_factory=lambda: list(DEFAULT_CANDIDATE_EXTENSIONS))
    keyword_allowlist: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    keyword_denylist: list[str] = field(default_factory=list)
    high_value_threshold: int = 1000
    chat_delivery_channel: str = "current-chat"
    timezone: str = "Asia/Shanghai"

    @property
    def state_dir(self) -> Path:
        return self.archive_root / ".state"

    @property
    def database_path(self) -> Path:
        return self.state_dir / "index.sqlite3"

    @classmethod
    def load(cls, config_path: Path | None = None) -> "RuntimeConfig":
        path = config_path or default_config_path()
        data: dict[str, object] = {}
        if path.exists():
            with path.open("rb") as fh:
                data = tomllib.load(fh)

        cfg = cls()
        for key in [
            "candidate_extensions",
            "keyword_allowlist",
            "keyword_denylist",
            "high_value_threshold",
            "chat_delivery_channel",
            "timezone",
        ]:
            if key in data:
                setattr(cfg, key, data[key])

        archive_root = data.get("archive_root")
        if archive_root:
            cfg.archive_root = Path(str(archive_root)).expanduser()

        env_root = os.getenv("MAIL_INVOICE_ARCHIVER_ARCHIVE_ROOT")
        if env_root:
            cfg.archive_root = Path(env_root).expanduser()

        return cfg

    def public_dict(self) -> dict[str, object]:
        return {
            "archive_root": str(self.archive_root),
            "candidate_extensions": self.candidate_extensions,
            "keyword_allowlist": self.keyword_allowlist,
            "keyword_denylist": self.keyword_denylist,
            "high_value_threshold": self.high_value_threshold,
            "chat_delivery_channel": self.chat_delivery_channel,
            "timezone": self.timezone,
        }
