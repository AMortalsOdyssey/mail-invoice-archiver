from __future__ import annotations

import getpass
import sys
from pathlib import Path

from .auth import available_auth_methods, store_in_system_credentials
from .config import RuntimeConfig, default_config_path, write_config
from .system_credentials import system_store_spec


def run_setup(
    *,
    config_path: Path | None = None,
    provider: str | None = None,
    email: str | None = None,
    secret: str | None = None,
    service: str | None = None,
    env_email_var: str | None = None,
    env_secret_var: str | None = None,
    interactive: bool = True,
) -> dict[str, object]:
    path = config_path or default_config_path()
    existing = RuntimeConfig.load(path) if path.exists() else RuntimeConfig()

    chosen_provider = (provider or "").strip().lower() or None
    if chosen_provider is None:
        if not interactive or not sys.stdin.isatty():
            raise RuntimeError("Provider must be given in non-interactive setup")
        chosen_provider = _prompt_provider()

    cfg = existing
    cfg.auth_provider = chosen_provider
    cfg.email_address = email or cfg.email_address

    if chosen_provider == "system":
        cfg.keychain_service = service or cfg.keychain_service
        if not cfg.email_address and interactive:
            cfg.email_address = input("126 email address: ").strip()
        secret_value = secret
        if not secret_value and interactive:
            secret_value = getpass.getpass("126 authorization code: ").strip()
        if not cfg.email_address or not secret_value:
            raise RuntimeError("System credential setup requires email and authorization code")
        store_in_system_credentials(cfg.keychain_service, cfg.email_address, secret_value)
        cfg.auth_secret = ""
    elif chosen_provider == "env":
        cfg.env_email_var = env_email_var or cfg.env_email_var
        cfg.env_secret_var = env_secret_var or cfg.env_secret_var
        if not cfg.email_address and interactive:
            cfg.email_address = input("126 email address: ").strip()
        cfg.auth_secret = ""
    elif chosen_provider == "config":
        if not cfg.email_address and interactive:
            cfg.email_address = input("126 email address: ").strip()
        secret_value = secret
        if not secret_value and interactive:
            secret_value = getpass.getpass("126 authorization code: ").strip()
        if not cfg.email_address or not secret_value:
            raise RuntimeError("Config setup requires email and authorization code")
        cfg.auth_secret = secret_value
    elif chosen_provider == "prompt":
        if not cfg.email_address and interactive:
            cfg.email_address = input("126 email address: ").strip()
        if not cfg.email_address:
            raise RuntimeError("Prompt setup requires an email address")
        cfg.auth_secret = ""
    else:
        raise RuntimeError(f"Unknown setup provider: {chosen_provider}")

    written = write_config(cfg, path)
    return {
        "setup_complete": True,
        "config_path": str(written),
        "auth_provider": cfg.auth_provider,
        "email_address": cfg.email_address,
        "keychain_service": cfg.keychain_service,
        "env_email_var": cfg.env_email_var,
        "env_secret_var": cfg.env_secret_var,
        "post_setup_notes": _post_setup_notes(cfg),
    }


def _prompt_provider() -> str:
    methods = available_auth_methods()
    print("Choose credential storage:")
    valid: dict[str, str] = {}
    for index, method in enumerate(methods, start=1):
        status = []
        if method["recommended"]:
            status.append("recommended")
        if not method["available"]:
            status.append("unavailable")
        suffix = f" ({', '.join(status)})" if status else ""
        print(f"{index}. {method['label']}{suffix}")
        print(f"   {method['notes']}")
        valid[str(index)] = str(method["provider"])
    while True:
        choice = input("Select 1-4: ").strip()
        provider = valid.get(choice)
        if not provider:
            print("Please choose a valid option.")
            continue
        selected = next(item for item in methods if item["provider"] == provider)
        if not selected["available"]:
            print("That option is not available on this machine. Choose another one.")
            continue
        return provider


def _post_setup_notes(config: RuntimeConfig) -> list[str]:
    if config.auth_provider == "env":
        return [
            f"Set {config.env_email_var} to the 126 email address.",
            f"Set {config.env_secret_var} to the 126 authorization code.",
            "Run doctor again after exporting those variables.",
        ]
    if config.auth_provider == "prompt":
        return ["The runtime will ask for the authorization code every session."]
    if config.auth_provider == "config":
        return ["The config file now contains the authorization code in plain text; protect that file carefully."]
    spec = system_store_spec()
    return [f"The authorization code was stored in {spec['label']}."]
