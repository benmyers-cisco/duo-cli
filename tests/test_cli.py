"""Tests for CLI commands using Click's test runner."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from duo_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    monkeypatch.setenv("DUO_CLI_CONFIG", str(tmp_path / "config.json"))
    for key in list(os.environ):
        if key.startswith("DUO_") and key != "DUO_CLI_CONFIG":
            monkeypatch.delenv(key, raising=False)


class TestTopLevel:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Duo Security CLI" in result.output

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "duo-cli" in result.output


class TestConfigure:
    def test_configure_auth_noninteractive(self, runner):
        result = runner.invoke(cli, [
            "configure", "--api", "auth",
            "--ikey", "DITEST123456789012",
            "--skey", "testsecret",
            "--host", "api-test.duosecurity.com",
        ])
        assert result.exit_code == 0
        assert "Auth API configuration saved" in result.output

    def test_configure_universal_noninteractive(self, runner):
        result = runner.invoke(cli, [
            "configure", "--api", "universal",
            "--client-id", "DITEST123456789012",
            "--client-secret", "testsecret",
            "--host", "api-test.duosecurity.com",
        ])
        assert result.exit_code == 0
        assert "Universal API configuration saved" in result.output

    def test_configure_auth_interactive(self, runner):
        result = runner.invoke(cli, ["configure"], input="auth\nDIKEY123\nsecret\napi-host.duo.com\n")
        assert result.exit_code == 0
        assert "Auth API configuration saved" in result.output

    def test_configure_universal_interactive(self, runner):
        result = runner.invoke(cli, ["configure"], input="universal\nCLIENTID12345678901\nsecret\napi-host.duo.com\n")
        assert result.exit_code == 0
        assert "Universal API configuration saved" in result.output

    def test_configure_shows_setup_help_auth(self, runner):
        result = runner.invoke(cli, ["configure", "--api", "auth"],
                               input="DIKEY123\nsecret\napi-host.duo.com\n")
        assert "Auth API" in result.output
        assert "Protect an Application" in result.output

    def test_configure_shows_setup_help_universal(self, runner):
        result = runner.invoke(cli, ["configure", "--api", "universal"],
                               input="CLIENT123\nsecret\napi-host.duo.com\n")
        assert "Web SDK" in result.output
        assert "Client ID" in result.output

    def test_configure_skips_help_when_noninteractive(self, runner):
        result = runner.invoke(cli, [
            "configure", "--api", "auth",
            "--ikey", "DI123", "--skey", "sk", "--host", "h",
        ])
        assert "Protect an Application" not in result.output


class TestAuthCommands:
    def _setup_auth_config(self, runner):
        runner.invoke(cli, [
            "configure", "--api", "auth",
            "--ikey", "DITEST", "--skey", "SKTEST", "--host", "api-test.duo.com",
        ])

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_check(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.check.return_value = {"time": 1234567890}
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, ["auth", "check"])
        assert result.exit_code == 0
        assert "1234567890" in result.output
        assert "credentials are valid" in result.output

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_preauth(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.preauth.return_value = {
            "result": "auth",
            "status_msg": "Account is active",
            "devices": [
                {
                    "display_name": "iPhone",
                    "type": "phone",
                    "number": "+1234567890",
                    "capabilities": ["push", "sms"],
                }
            ],
        }
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, ["auth", "preauth", "testuser"])
        assert result.exit_code == 0
        assert "auth" in result.output
        assert "Account is active" in result.output

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_push_allow(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.auth.return_value = {"result": "allow", "status_msg": "Success"}
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, ["auth", "push", "testuser", "--reason", "test"])
        assert result.exit_code == 0
        assert "allow" in result.output

        # Verify pushinfo was built correctly
        call_kwargs = mock_client.auth.call_args
        assert "reason=test" in call_kwargs.kwargs.get("pushinfo", call_kwargs[1].get("pushinfo", ""))

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_push_with_custom_pushinfo(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.auth.return_value = {"result": "allow", "status_msg": "ok"}
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, [
            "auth", "push", "testuser",
            "-p", "action=deploy",
            "-p", "target=prod",
        ])
        assert result.exit_code == 0
        call_kwargs = mock_client.auth.call_args
        pushinfo = call_kwargs.kwargs.get("pushinfo", call_kwargs[1].get("pushinfo", ""))
        assert "action=deploy" in pushinfo
        assert "target=prod" in pushinfo

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_push_deny(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.auth.return_value = {"result": "deny", "status_msg": "Login request denied"}
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, ["auth", "push", "testuser"])
        assert result.exit_code == 0
        assert "deny" in result.output

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_push_no_wait(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.auth.return_value = {"txid": "tx123abc"}
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, ["auth", "push", "testuser", "--no-wait"])
        assert result.exit_code == 0
        assert "tx123abc" in result.output

        call_kwargs = mock_client.auth.call_args
        assert call_kwargs.kwargs.get("async_txn", call_kwargs[1].get("async_txn")) is True

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_push_all_options(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.auth.return_value = {"result": "allow", "status_msg": "ok"}
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, [
            "auth", "push", "testuser",
            "--reason", "deploy",
            "--device", "DPXXXXXXXXX",
            "--type", "ci-deploy",
            "--display-username", "Test User",
            "--ipaddr", "10.0.0.1",
        ])
        assert result.exit_code == 0
        call_kwargs = mock_client.auth.call_args[1]
        assert call_kwargs["device"] == "DPXXXXXXXXX"
        assert call_kwargs["type"] == "ci-deploy"
        assert call_kwargs["display_username"] == "Test User"
        assert call_kwargs["ipaddr"] == "10.0.0.1"

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_sms(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.auth.return_value = {"status_msg": "Sent"}
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, ["auth", "sms", "testuser"])
        assert result.exit_code == 0
        assert "SMS sent" in result.output

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_passcode(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.auth.return_value = {"result": "allow", "status_msg": "ok"}
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, ["auth", "passcode", "testuser", "123456"])
        assert result.exit_code == 0
        assert "allow" in result.output
        call_kwargs = mock_client.auth.call_args[1]
        assert call_kwargs["passcode"] == "123456"

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_status(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.auth_status.return_value = {"result": "allow", "status_msg": "Approved"}
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status", "tx123"])
        assert result.exit_code == 0
        assert "allow" in result.output

    def test_auth_without_config_exits(self, runner):
        result = runner.invoke(cli, ["auth", "check"])
        assert result.exit_code != 0

    @patch("duo_cli.commands.auth.duo_client.Auth")
    def test_auth_api_error_shows_message(self, mock_auth_cls, runner):
        self._setup_auth_config(runner)
        mock_client = MagicMock()
        mock_client.auth.side_effect = RuntimeError("Received 400 Invalid request parameters")
        mock_auth_cls.return_value = mock_client

        result = runner.invoke(cli, ["auth", "push", "baduser"])
        assert result.exit_code != 0
