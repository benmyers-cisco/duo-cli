"""Universal Prompt commands — browser-based auth with full Duo policy enforcement."""

import json
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import click
import duo_universal

from duo_cli.config import get_universal_kwargs


DEFAULT_PORT = 8987
REDIRECT_PATH = "/callback"


class CallbackResult:
    """Thread-safe container for the OAuth callback result."""

    def __init__(self):
        self.duo_code = None
        self.state = None
        self.error = None


def _make_callback_handler(result: CallbackResult):
    """Create a request handler class that writes to the given result container."""

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != REDIRECT_PATH:
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)

            if "error" in params:
                result.error = params["error"][0]
                msg = params.get("error_description", [result.error])[0]
                self._respond(f"Authentication failed: {msg}")
                return

            result.duo_code = params.get("duo_code", [None])[0]
            result.state = params.get("state", [None])[0]

            if result.duo_code:
                self._respond(
                    "Duo authentication successful! You can close this tab."
                )
            else:
                result.error = "No duo_code in callback"
                self._respond("Authentication failed: no authorization code received.")

        def _respond(self, message):
            html = (
                "<html><body style='font-family: sans-serif; text-align: center; "
                "padding: 50px;'>"
                f"<h2>{message}</h2>"
                "</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

        def log_message(self, format, *args):
            pass

    return _CallbackHandler


def _build_client(port):
    """Build a duo_universal.Client with a localhost redirect URI."""
    kwargs = get_universal_kwargs()
    redirect_uri = f"http://localhost:{port}{REDIRECT_PATH}"
    return duo_universal.Client(
        client_id=kwargs["client_id"],
        client_secret=kwargs["client_secret"],
        host=kwargs["host"],
        redirect_uri=redirect_uri,
    )


@click.group()
def universal():
    """Browser-based auth with Duo Universal Prompt (full policy enforcement)."""
    pass


@universal.command("check")
def universal_check():
    """Verify that the Universal Prompt credentials are valid."""
    client = _build_client(DEFAULT_PORT)
    client.health_check()
    click.echo("Universal Prompt credentials are valid.")


@universal.command("login")
@click.argument("username")
@click.option("--port", "-p", default=DEFAULT_PORT, show_default=True,
              help="Local port for the OAuth callback server.")
@click.pass_context
def universal_login(ctx, username, port):
    """Authenticate a user via the Duo Universal Prompt in a browser.

    Opens your browser to the Duo Universal Prompt where full Duo policy
    is enforced (trusted devices, allowed networks, remembered devices, etc.).

    \b
    Examples:
      duo-cli universal login medfisch
      duo-cli universal login medfisch --port 9090
    """
    client = _build_client(port)

    # Health check first
    try:
        client.health_check()
    except Exception as e:
        raise click.ClickException(f"Duo health check failed: {e}")

    # Generate state and create auth URL
    state = client.generate_state()
    auth_url = client.create_auth_url(username, state)

    # Start local callback server
    cb = CallbackResult()
    handler_class = _make_callback_handler(cb)
    server = HTTPServer(("127.0.0.1", port), handler_class)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    click.echo("Opening browser for Duo authentication...")
    click.echo(f"Callback listening on http://localhost:{port}{REDIRECT_PATH}")
    click.echo("Waiting for approval...")

    webbrowser.open(auth_url)

    # Wait for the callback
    server_thread.join(timeout=120)
    server.server_close()

    if cb.error:
        raise click.ClickException(f"Authentication failed: {cb.error}")

    if not cb.duo_code:
        raise click.ClickException("Timed out waiting for Duo callback (120s).")

    if cb.state != state:
        raise click.ClickException("State mismatch — possible CSRF. Authentication rejected.")

    # Exchange the code for the auth result
    try:
        result = client.exchange_authorization_code_for_2fa_result(
            cb.duo_code, username
        )
    except Exception as e:
        raise click.ClickException(f"Token exchange failed: {e}")

    output_format = ctx.obj.get("output", "table")
    if output_format == "json":
        click.echo(json.dumps(result, default=str))
    else:
        click.echo(f"\nAuthentication successful!")
        click.echo(f"  User:     {result.get('preferred_username', username)}")
        click.echo(f"  Issuer:   {result.get('iss', '')}")
        click.echo(f"  Audience: {result.get('aud', '')}")

        # Timestamps
        for field, label in [("iat", "Issued at"), ("exp", "Expires"), ("auth_time", "Auth time")]:
            ts = result.get(field)
            if ts:
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                click.echo(f"  {label + ':':<12}{dt}")

        # Auth result details
        auth_result = result.get("auth_result", {})
        if auth_result:
            click.echo(f"\n  Auth Result:")
            click.echo(f"    Result:      {auth_result.get('result', '')}")
            click.echo(f"    Status:      {auth_result.get('status', '')}")
            click.echo(f"    Status msg:  {auth_result.get('status_msg', '')}")

        # Auth context (device, access device, factor, etc.)
        auth_context = result.get("auth_context", {})
        if auth_context:
            click.echo(f"\n  Auth Context:")
            click.echo(f"    Factor:      {auth_context.get('factor', '')}")
            click.echo(f"    Event type:  {auth_context.get('event_type', '')}")
            click.echo(f"    Txid:        {auth_context.get('txid', '')}")
            click.echo(f"    Timestamp:   {auth_context.get('timestamp', '')}")

            access_device = auth_context.get("access_device", {})
            if access_device:
                click.echo(f"    Access Device:")
                for k, v in access_device.items():
                    click.echo(f"      {k}: {v}")

            auth_device = auth_context.get("auth_device", {})
            if auth_device:
                click.echo(f"    Auth Device:")
                for k, v in auth_device.items():
                    click.echo(f"      {k}: {v}")

            user = auth_context.get("user", {})
            if user:
                click.echo(f"    User:")
                for k, v in user.items():
                    click.echo(f"      {k}: {v}")

        # Any other top-level claims
        known_keys = {
            "preferred_username", "iss", "aud", "iat", "exp", "auth_time",
            "auth_result", "auth_context", "sub", "nonce",
        }
        extras = {k: v for k, v in result.items() if k not in known_keys}
        if extras:
            click.echo(f"\n  Additional claims:")
            for k, v in extras.items():
                click.echo(f"    {k}: {v}")
