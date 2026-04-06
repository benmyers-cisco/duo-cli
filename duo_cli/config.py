"""Configuration management for duo-cli."""

import json
import os
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".duo-cli"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"


def get_config_path() -> Path:
    """Return the config file path, respecting DUO_CLI_CONFIG env var."""
    env_path = os.environ.get("DUO_CLI_CONFIG")
    if env_path:
        return Path(env_path)
    return DEFAULT_CONFIG_FILE


def load_config() -> dict:
    """Load config from disk. Returns empty dict if not found."""
    path = get_config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_config(config: dict) -> None:
    """Save config to disk."""
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")


def get_client_kwargs() -> dict:
    """Return kwargs suitable for duo_client constructors."""
    config = load_config()
    if not config.get("ikey") or not config.get("skey") or not config.get("host"):
        raise SystemExit(
            "duo-cli is not configured. Run: duo-cli configure"
        )
    return {
        "ikey": config["ikey"],
        "skey": config["skey"],
        "host": config["host"],
    }
