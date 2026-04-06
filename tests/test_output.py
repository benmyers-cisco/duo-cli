"""Tests for output formatting."""

import json

from duo_cli.output import render
from rich.console import Console


def test_render_json(capsys):
    data = [{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]
    render(data, ["name", "age"], output_format="json")
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert len(parsed) == 2
    assert parsed[0]["name"] == "alice"


def test_render_table(capsys):
    data = [{"name": "alice", "role": "admin"}]
    render(data, ["name", "role"], output_format="table", title="Test")
    captured = capsys.readouterr()
    assert "alice" in captured.out
    assert "admin" in captured.out


def test_render_empty_data(capsys):
    render([], ["name"], output_format="table")
    captured = capsys.readouterr()
    # Should render a table header but no rows — no crash
    assert "name" in captured.out


def test_render_missing_keys(capsys):
    data = [{"name": "alice"}]  # missing "role"
    render(data, ["name", "role"], output_format="table")
    captured = capsys.readouterr()
    assert "alice" in captured.out
