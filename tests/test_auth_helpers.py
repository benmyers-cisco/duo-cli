"""Tests for auth helper functions."""

import pytest
import click

from duo_cli.commands.auth import _build_pushinfo


class TestBuildPushinfo:
    def test_none_when_empty(self):
        assert _build_pushinfo() is None

    def test_reason_only(self):
        result = _build_pushinfo(reason="deploy to prod")
        assert "reason=deploy+to+prod" in result

    def test_extra_only(self):
        result = _build_pushinfo(extra=["action=deploy", "target=prod"])
        assert "action=deploy" in result
        assert "target=prod" in result

    def test_reason_and_extra(self):
        result = _build_pushinfo(reason="test", extra=["key=val"])
        assert "reason=test" in result
        assert "key=val" in result

    def test_special_characters_encoded(self):
        result = _build_pushinfo(reason="hello world & goodbye")
        assert "reason=hello+world+%26+goodbye" in result

    def test_extra_with_equals_in_value(self):
        result = _build_pushinfo(extra=["url=https://example.com?a=1"])
        assert "url=https" in result

    def test_invalid_extra_raises(self):
        with pytest.raises(click.BadParameter, match="pushinfo must be key=value"):
            _build_pushinfo(extra=["no_equals_here"])

    def test_empty_extra_list(self):
        assert _build_pushinfo(extra=[]) is None

    def test_reason_empty_string(self):
        # Empty reason should not add a key
        assert _build_pushinfo(reason="") is None
