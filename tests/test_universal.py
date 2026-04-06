"""Tests for Universal Prompt commands."""

import json
import os
import threading
import urllib.request
import pytest
from unittest.mock import patch, MagicMock
from http.server import HTTPServer

from click.testing import CliRunner

from duo_cli.main import cli
from duo_cli.commands.universal import (
    CallbackResult,
    _make_callback_handler,
    REDIRECT_PATH,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    monkeypatch.setenv("DUO_CLI_CONFIG", str(tmp_path / "config.json"))
    for key in list(os.environ):
        if key.startswith("DUO_") and key != "DUO_CLI_CONFIG":
            monkeypatch.delenv(key, raising=False)


def _setup_universal_config(runner):
    runner.invoke(cli, [
        "configure", "--api", "universal",
        "--client-id", "DIXXXXXXXXXXXXXXXXXX",
        "--client-secret", "a" * 40,
        "--host", "api-test.duosecurity.com",
    ])


class TestCallbackResult:
    def test_initial_state(self):
        cb = CallbackResult()
        assert cb.duo_code is None
        assert cb.state is None
        assert cb.error is None

    def test_separate_instances(self):
        cb1 = CallbackResult()
        cb2 = CallbackResult()
        cb1.duo_code = "code1"
        assert cb2.duo_code is None


class TestCallbackHandler:
    def _start_server(self, result):
        handler = _make_callback_handler(result)
        server = HTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        return server, port, thread

    def test_successful_callback(self):
        cb = CallbackResult()
        server, port, thread = self._start_server(cb)
        try:
            url = f"http://localhost:{port}{REDIRECT_PATH}?duo_code=TESTCODE&state=TESTSTATE"
            resp = urllib.request.urlopen(url)
            assert resp.status == 200
            thread.join(timeout=5)
            assert cb.duo_code == "TESTCODE"
            assert cb.state == "TESTSTATE"
            assert cb.error is None
        finally:
            server.server_close()

    def test_error_callback(self):
        cb = CallbackResult()
        server, port, thread = self._start_server(cb)
        try:
            url = f"http://localhost:{port}{REDIRECT_PATH}?error=access_denied&error_description=User+denied"
            resp = urllib.request.urlopen(url)
            assert resp.status == 200
            thread.join(timeout=5)
            assert cb.error == "access_denied"
            assert cb.duo_code is None
        finally:
            server.server_close()

    def test_missing_duo_code(self):
        cb = CallbackResult()
        server, port, thread = self._start_server(cb)
        try:
            url = f"http://localhost:{port}{REDIRECT_PATH}?state=TESTSTATE"
            resp = urllib.request.urlopen(url)
            thread.join(timeout=5)
            assert cb.error == "No duo_code in callback"
        finally:
            server.server_close()

    def test_wrong_path_returns_404(self):
        cb = CallbackResult()
        server, port, thread = self._start_server(cb)
        try:
            url = f"http://localhost:{port}/wrong-path"
            try:
                urllib.request.urlopen(url)
            except urllib.error.HTTPError as e:
                assert e.code == 404
            thread.join(timeout=5)
            assert cb.duo_code is None
            assert cb.error is None
        finally:
            server.server_close()


class TestUniversalCheck:
    @patch("duo_cli.commands.universal.duo_universal.Client")
    def test_check_success(self, mock_client_cls, runner):
        _setup_universal_config(runner)
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        result = runner.invoke(cli, ["universal", "check"])
        assert result.exit_code == 0
        assert "credentials are valid" in result.output

    @patch("duo_cli.commands.universal.duo_universal.Client")
    def test_check_failure(self, mock_client_cls, runner):
        _setup_universal_config(runner)
        mock_client = MagicMock()
        mock_client.health_check.side_effect = Exception("Connection refused")
        mock_client_cls.return_value = mock_client

        result = runner.invoke(cli, ["universal", "check"])
        assert result.exit_code != 0

    def test_check_without_config(self, runner):
        result = runner.invoke(cli, ["universal", "check"])
        assert result.exit_code != 0


class TestUniversalLogin:
    @patch("duo_cli.commands.universal.webbrowser.open")
    @patch("duo_cli.commands.universal.duo_universal.Client")
    def test_login_success(self, mock_client_cls, mock_browser, runner):
        _setup_universal_config(runner)

        mock_client = MagicMock()
        mock_client.generate_state.return_value = "STATE123"
        mock_client.create_auth_url.return_value = "https://duo.example.com/auth"
        mock_client.exchange_authorization_code_for_2fa_result.return_value = {
            "preferred_username": "testuser",
            "iss": "https://api-test.duosecurity.com/oauth/v1/token",
            "aud": "DIXXXXXXXXXXXXXXXXXX",
            "iat": 1700000000,
            "exp": 1700000300,
            "auth_time": 1700000000,
            "auth_result": {"result": "allow", "status": "allow", "status_msg": "Approved"},
            "auth_context": {
                "factor": "duo_push",
                "event_type": "authentication",
                "txid": "tx123",
                "timestamp": 1700000000,
            },
        }
        mock_client_cls.return_value = mock_client

        # Simulate the browser callback by hitting the server
        original_open = mock_browser.side_effect

        def fake_browser(url):
            import time
            time.sleep(0.1)
            urllib.request.urlopen(
                f"http://localhost:8987{REDIRECT_PATH}?duo_code=DUOCODE&state=STATE123"
            )

        mock_browser.side_effect = fake_browser

        # Run in a thread since it blocks waiting for callback
        result = runner.invoke(cli, ["universal", "login", "testuser"])

        assert result.exit_code == 0
        assert "Authentication successful" in result.output
        assert "testuser" in result.output
        mock_client.exchange_authorization_code_for_2fa_result.assert_called_once_with(
            "DUOCODE", "testuser"
        )

    @patch("duo_cli.commands.universal.webbrowser.open")
    @patch("duo_cli.commands.universal.duo_universal.Client")
    def test_login_json_output(self, mock_client_cls, mock_browser, runner):
        _setup_universal_config(runner)

        mock_client = MagicMock()
        mock_client.generate_state.return_value = "STATE123"
        mock_client.create_auth_url.return_value = "https://duo.example.com/auth"
        mock_client.exchange_authorization_code_for_2fa_result.return_value = {
            "preferred_username": "testuser",
            "iss": "https://test",
            "aud": "DI123",
            "auth_result": {"result": "allow"},
        }
        mock_client_cls.return_value = mock_client

        def fake_browser(url):
            import time
            time.sleep(0.1)
            urllib.request.urlopen(
                f"http://localhost:8987{REDIRECT_PATH}?duo_code=DUOCODE&state=STATE123"
            )

        mock_browser.side_effect = fake_browser

        result = runner.invoke(cli, ["-o", "json", "universal", "login", "testuser"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip().split("\n")[-1])
        assert data["preferred_username"] == "testuser"

    @patch("duo_cli.commands.universal.duo_universal.Client")
    def test_login_health_check_fails(self, mock_client_cls, runner):
        _setup_universal_config(runner)
        mock_client = MagicMock()
        mock_client.health_check.side_effect = Exception("API down")
        mock_client_cls.return_value = mock_client

        result = runner.invoke(cli, ["universal", "login", "testuser"])
        assert result.exit_code != 0
        assert "health check failed" in result.output
