"""Tests for config module."""

import json
from pathlib import Path

from duo_cli.config import load_config, save_config


def test_save_and_load(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setenv("DUO_CLI_CONFIG", str(config_file))

    save_config({"admin": {"ikey": "DI123", "skey": "abc", "host": "api-test.duosecurity.com"}})
    loaded = load_config()
    assert loaded["admin"]["ikey"] == "DI123"
    assert loaded["admin"]["host"] == "api-test.duosecurity.com"


def test_load_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DUO_CLI_CONFIG", str(tmp_path / "nope.json"))
    assert load_config() == {}
