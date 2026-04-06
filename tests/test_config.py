"""Tests for config module."""

import json
import os
import pytest

from duo_cli.config import load_config, save_config, get_client_kwargs, get_universal_kwargs


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Point all config operations at a temp directory and clear env vars."""
    monkeypatch.setenv("DUO_CLI_CONFIG", str(tmp_path / "config.json"))
    # Clear any Duo env vars that might leak from the real environment
    for key in list(os.environ):
        if key.startswith("DUO_"):
            monkeypatch.delenv(key, raising=False)


class TestLoadSave:
    def test_save_and_load(self):
        save_config({"auth": {"ikey": "DI123", "skey": "abc", "host": "api-test.duosecurity.com"}})
        loaded = load_config()
        assert loaded["auth"]["ikey"] == "DI123"
        assert loaded["auth"]["skey"] == "abc"
        assert loaded["auth"]["host"] == "api-test.duosecurity.com"

    def test_load_missing_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DUO_CLI_CONFIG", str(tmp_path / "nope.json"))
        assert load_config() == {}

    def test_save_creates_parent_dirs(self, tmp_path, monkeypatch):
        nested = tmp_path / "a" / "b" / "config.json"
        monkeypatch.setenv("DUO_CLI_CONFIG", str(nested))
        save_config({"test": True})
        assert nested.exists()
        assert json.loads(nested.read_text()) == {"test": True}

    def test_save_overwrites_existing(self):
        save_config({"v": 1})
        save_config({"v": 2})
        assert load_config() == {"v": 2}

    def test_round_trip_all_api_sections(self):
        config = {
            "auth": {"ikey": "DI_AUTH", "skey": "sk_auth", "host": "api-auth.duo.com"},
            "universal": {
                "client_id": "DI_UNI",
                "client_secret": "cs_uni",
                "host": "api-uni.duo.com",
            },
        }
        save_config(config)
        loaded = load_config()
        assert loaded == config


class TestGetClientKwargs:
    def test_loads_from_config_file(self):
        save_config({
            "auth": {"ikey": "DI_A", "skey": "SK_A", "host": "api-a.duo.com"},
        })
        result = get_client_kwargs("auth")
        assert result == {"ikey": "DI_A", "skey": "SK_A", "host": "api-a.duo.com"}

    def test_env_vars_override_config(self, monkeypatch):
        save_config({
            "auth": {"ikey": "file_ikey", "skey": "file_skey", "host": "file_host"},
        })
        monkeypatch.setenv("DUO_AUTH_IKEY", "env_ikey")
        monkeypatch.setenv("DUO_AUTH_SKEY", "env_skey")
        monkeypatch.setenv("DUO_AUTH_HOST", "env_host")
        result = get_client_kwargs("auth")
        assert result == {"ikey": "env_ikey", "skey": "env_skey", "host": "env_host"}

    def test_env_vars_partial_override(self, monkeypatch):
        save_config({
            "auth": {"ikey": "file_ikey", "skey": "file_skey", "host": "file_host"},
        })
        monkeypatch.setenv("DUO_AUTH_IKEY", "env_ikey")
        # skey and host fall back to config file
        result = get_client_kwargs("auth")
        assert result["ikey"] == "env_ikey"
        assert result["skey"] == "file_skey"
        assert result["host"] == "file_host"

    def test_env_vars_only_no_config(self, monkeypatch):
        monkeypatch.setenv("DUO_AUTH_IKEY", "env_ikey")
        monkeypatch.setenv("DUO_AUTH_SKEY", "env_skey")
        monkeypatch.setenv("DUO_AUTH_HOST", "env_host")
        result = get_client_kwargs("auth")
        assert result == {"ikey": "env_ikey", "skey": "env_skey", "host": "env_host"}

    def test_missing_config_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DUO_CLI_CONFIG", str(tmp_path / "empty" / "config.json"))
        monkeypatch.delenv("DUO_AUTH_IKEY", raising=False)
        monkeypatch.delenv("DUO_AUTH_SKEY", raising=False)
        monkeypatch.delenv("DUO_AUTH_HOST", raising=False)
        with pytest.raises(SystemExit, match="duo-cli configure --api auth"):
            get_client_kwargs("auth")

    def test_partial_config_exits(self):
        save_config({"auth": {"ikey": "DI_A", "skey": "SK_A"}})  # missing host
        with pytest.raises(SystemExit, match="duo-cli configure --api auth"):
            get_client_kwargs("auth")

    def test_empty_string_values_treated_as_missing(self):
        save_config({"auth": {"ikey": "", "skey": "SK", "host": "h"}})
        with pytest.raises(SystemExit):
            get_client_kwargs("auth")


class TestGetUniversalKwargs:
    def test_loads_from_config_file(self):
        save_config({
            "universal": {
                "client_id": "DI_UNI",
                "client_secret": "CS_UNI",
                "host": "api-uni.duo.com",
            },
        })
        result = get_universal_kwargs()
        assert result == {
            "client_id": "DI_UNI",
            "client_secret": "CS_UNI",
            "host": "api-uni.duo.com",
        }

    def test_env_vars_override(self, monkeypatch):
        save_config({
            "universal": {
                "client_id": "file_id",
                "client_secret": "file_secret",
                "host": "file_host",
            },
        })
        monkeypatch.setenv("DUO_UNIVERSAL_CLIENT_ID", "env_id")
        monkeypatch.setenv("DUO_UNIVERSAL_CLIENT_SECRET", "env_secret")
        monkeypatch.setenv("DUO_UNIVERSAL_HOST", "env_host")
        result = get_universal_kwargs()
        assert result == {
            "client_id": "env_id",
            "client_secret": "env_secret",
            "host": "env_host",
        }

    def test_missing_config_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DUO_CLI_CONFIG", str(tmp_path / "empty" / "config.json"))
        monkeypatch.delenv("DUO_UNIVERSAL_CLIENT_ID", raising=False)
        monkeypatch.delenv("DUO_UNIVERSAL_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("DUO_UNIVERSAL_HOST", raising=False)
        with pytest.raises(SystemExit, match="duo-cli configure --api universal"):
            get_universal_kwargs()

    def test_partial_config_exits(self):
        save_config({"universal": {"client_id": "DI", "host": "h"}})  # missing secret
        with pytest.raises(SystemExit):
            get_universal_kwargs()
