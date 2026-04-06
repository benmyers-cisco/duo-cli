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


def get_client_kwargs(api: str) -> dict:
    """Return kwargs for a duo_client constructor.

    Args:
        api: "admin" or "auth"
    """
    config = load_config()
    section = config.get(api, {})

    # Also check env vars: DUO_ADMIN_IKEY / DUO_AUTH_IKEY, etc.
    prefix = f"DUO_{api.upper()}_"
    ikey = os.environ.get(f"{prefix}IKEY") or section.get("ikey")
    skey = os.environ.get(f"{prefix}SKEY") or section.get("skey")
    host = os.environ.get(f"{prefix}HOST") or section.get("host")

    if not ikey or not skey or not host:
        raise SystemExit(
            f"Duo {api.title()} API is not configured. Run: duo-cli configure --api {api}"
        )
    return {"ikey": ikey, "skey": skey, "host": host}


def get_universal_kwargs() -> dict:
    """Return kwargs for duo_universal.Client.

    Uses the 'universal' config section or DUO_UNIVERSAL_* env vars.
    The universal API uses client_id/client_secret instead of ikey/skey.
    """
    config = load_config()
    section = config.get("universal", {})

    client_id = os.environ.get("DUO_UNIVERSAL_CLIENT_ID") or section.get("client_id")
    client_secret = os.environ.get("DUO_UNIVERSAL_CLIENT_SECRET") or section.get("client_secret")
    host = os.environ.get("DUO_UNIVERSAL_HOST") or section.get("host")

    if not client_id or not client_secret or not host:
        raise SystemExit(
            "Duo Universal Prompt is not configured. Run: duo-cli configure --api universal"
        )
    return {"client_id": client_id, "client_secret": client_secret, "host": host}
