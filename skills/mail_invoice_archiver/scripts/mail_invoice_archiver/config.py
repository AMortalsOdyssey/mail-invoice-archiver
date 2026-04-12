from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_HOST_CANDIDATES = [
    "appleimap.126.com",
    "imap.126.com",
    "imap.163.com",
]

DEFAULT_CLIENT_ID = '("name" "Apple Mail" "version" "16.0" "vendor" "Apple Inc." "os" "macOS")'
DEFAULT_CANDIDATE_EXTENSIONS = ["pdf", "ofd", "xml", "png", "jpg", "jpeg", "zip"]
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
    email_address: str | None = None
    auth_provider: str = "system"
    keychain_service: str = "mail-invoice-archiver/126-auth"
    auth_secret: str | None = None
    env_email_var: str = "MAIL_INVOICE_ARCHIVER_EMAIL"
    env_secret_var: str = "MAIL_INVOICE_ARCHIVER_AUTH_CODE"
    imap_port: int = 993
    host_candidates: list[str] = field(default_factory=lambda: list(DEFAULT_HOST_CANDIDATES))
    archive_root: Path = field(default_factory=default_archive_root)
    folders: list[str] = field(default_factory=lambda: ["INBOX"])
    candidate_extensions: list[str] = field(default_factory=lambda: list(DEFAULT_CANDIDATE_EXTENSIONS))
    sender_allowlist: list[str] = field(default_factory=list)
    keyword_allowlist: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    keyword_denylist: list[str] = field(default_factory=list)
    high_value_threshold: int = 1000
    web_healthcheck_enabled: bool = True
    download_link_domains: list[str] = field(default_factory=list)
    chat_delivery_channel: str = "current-chat"
    timezone: str = "Asia/Shanghai"
    imap_client_id: str = DEFAULT_CLIENT_ID

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
        auth_data = data.get("auth", {}) if isinstance(data.get("auth"), dict) else {}
        for key in [
            "email_address",
            "auth_provider",
            "keychain_service",
            "imap_port",
            "host_candidates",
            "folders",
            "candidate_extensions",
            "sender_allowlist",
            "keyword_allowlist",
            "keyword_denylist",
            "high_value_threshold",
            "web_healthcheck_enabled",
            "download_link_domains",
            "chat_delivery_channel",
            "timezone",
            "imap_client_id",
        ]:
            if key in data:
                setattr(cfg, key, data[key])

        if auth_data:
            cfg.email_address = str(auth_data.get("email", cfg.email_address or "")) or cfg.email_address
            cfg.auth_provider = str(auth_data.get("provider", cfg.auth_provider))
            cfg.keychain_service = str(auth_data.get("service", cfg.keychain_service))
            secret = auth_data.get("secret")
            cfg.auth_secret = str(secret) if secret else cfg.auth_secret
            cfg.env_email_var = str(auth_data.get("env_email_var", cfg.env_email_var))
            cfg.env_secret_var = str(auth_data.get("env_secret_var", cfg.env_secret_var))

        archive_root = data.get("archive_root")
        if archive_root:
            cfg.archive_root = Path(str(archive_root)).expanduser()

        env_account = os.getenv("MAIL_INVOICE_ARCHIVER_EMAIL")
        env_service = os.getenv("MAIL_INVOICE_ARCHIVER_SYSTEM_SERVICE") or os.getenv(
            "MAIL_INVOICE_ARCHIVER_KEYCHAIN_SERVICE"
        )
        env_root = os.getenv("MAIL_INVOICE_ARCHIVER_ARCHIVE_ROOT")
        env_hosts = os.getenv("MAIL_INVOICE_ARCHIVER_HOST_CANDIDATES")
        env_provider = os.getenv("MAIL_INVOICE_ARCHIVER_AUTH_PROVIDER")

        if env_account:
            cfg.email_address = env_account
        if env_service:
            cfg.keychain_service = env_service
        if env_root:
            cfg.archive_root = Path(env_root).expanduser()
        if env_hosts:
            cfg.host_candidates = [item.strip() for item in env_hosts.split(",") if item.strip()]
        if env_provider:
            cfg.auth_provider = env_provider

        return cfg

    def public_dict(self) -> dict[str, object]:
        return {
            "email_address": self.email_address,
            "auth_provider": self.auth_provider,
            "keychain_service": self.keychain_service,
            "env_email_var": self.env_email_var,
            "env_secret_var": self.env_secret_var,
            "imap_port": self.imap_port,
            "host_candidates": self.host_candidates,
            "archive_root": str(self.archive_root),
            "folders": self.folders,
            "candidate_extensions": self.candidate_extensions,
            "sender_allowlist": self.sender_allowlist,
            "keyword_allowlist": self.keyword_allowlist,
            "keyword_denylist": self.keyword_denylist,
            "high_value_threshold": self.high_value_threshold,
            "web_healthcheck_enabled": self.web_healthcheck_enabled,
            "download_link_domains": self.download_link_domains,
            "chat_delivery_channel": self.chat_delivery_channel,
            "timezone": self.timezone,
        }


def write_config(config: RuntimeConfig, config_path: Path | None = None) -> Path:
    path = config_path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "archive_root = " + _toml_string(str(config.archive_root)),
            "imap_port = " + str(config.imap_port),
            "host_candidates = " + _toml_list(config.host_candidates),
            "folders = " + _toml_list(config.folders),
            "candidate_extensions = " + _toml_list(config.candidate_extensions),
            "sender_allowlist = " + _toml_list(config.sender_allowlist),
            "keyword_allowlist = " + _toml_list(config.keyword_allowlist),
            "keyword_denylist = " + _toml_list(config.keyword_denylist),
            "high_value_threshold = " + str(config.high_value_threshold),
            "web_healthcheck_enabled = " + _toml_bool(config.web_healthcheck_enabled),
            "download_link_domains = " + _toml_list(config.download_link_domains),
            "chat_delivery_channel = " + _toml_string(config.chat_delivery_channel),
            "timezone = " + _toml_string(config.timezone),
            "imap_client_id = " + _toml_string(config.imap_client_id),
            "",
            "[auth]",
            "provider = " + _toml_string(config.auth_provider),
            "email = " + _toml_string(config.email_address or ""),
            "service = " + _toml_string(config.keychain_service),
            "env_email_var = " + _toml_string(config.env_email_var),
            "env_secret_var = " + _toml_string(config.env_secret_var),
            "secret = " + _toml_string(config.auth_secret or ""),
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    return path


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_list(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"
