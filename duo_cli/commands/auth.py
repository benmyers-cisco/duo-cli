"""Authentication commands — trigger and check Duo auth."""

from urllib.parse import urlencode

import click
import duo_client

from duo_cli.config import get_client_kwargs
from duo_cli.output import render


def _auth_client() -> duo_client.Auth:
    kwargs = get_client_kwargs("auth")
    return duo_client.Auth(**kwargs)


def _build_pushinfo(reason=None, extra=None):
    """Build a URL-encoded pushinfo string from reason and extra key=value pairs."""
    info = {}
    if reason:
        info["reason"] = reason
    if extra:
        for item in extra:
            if "=" not in item:
                raise click.BadParameter(f"pushinfo must be key=value, got: {item}")
            k, v = item.split("=", 1)
            info[k] = v
    return urlencode(info) if info else None


@click.group()
def auth():
    """Trigger and check Duo authentication."""
    pass


@auth.command("check")
def auth_check():
    """Verify that the Duo Auth API credentials are valid."""
    client = _auth_client()
    result = client.check()
    click.echo(f"API time: {result.get('time', 'unknown')}")
    click.echo("Auth API credentials are valid.")


@auth.command("preauth")
@click.argument("username")
@click.pass_context
def auth_preauth(ctx, username):
    """Check if a user can authenticate (and see their devices).

    \b
    Use this to verify the username and see what factors are available:
      duo-cli auth preauth medfisch
      duo-cli auth preauth medfisch@cisco.com
    """
    client = _auth_client()
    result = client.preauth(username=username)

    status = result.get("result", "unknown")
    click.echo(f"Status: {status}")
    if result.get("status_msg"):
        click.echo(f"Message: {result['status_msg']}")

    devices = result.get("devices", [])
    if devices:
        data = [
            {
                "device": d.get("display_name") or d.get("device", ""),
                "type": d.get("type", ""),
                "number": d.get("number", ""),
                "capabilities": ", ".join(d.get("capabilities", [])),
            }
            for d in devices
        ]
        render(data, ["device", "type", "number", "capabilities"],
               output_format=ctx.obj["output"], title="Devices")


@auth.command("push")
@click.argument("username")
@click.option("--reason", "-r", default=None,
              help="Reason shown to user in the Duo Push prompt.")
@click.option("--pushinfo", "-p", multiple=True,
              help="Extra key=value pairs for push notification (repeatable). "
                   "e.g. -p 'action=deploy' -p 'target=prod'")
@click.option("--device", "-d", default="auto",
              help="Device ID or 'auto' (default: auto).")
@click.option("--type", "auth_type", default=None,
              help="Label for this auth request (shows in Duo logs).")
@click.option("--display-username", default=None,
              help="Username shown in push notification (if different from username).")
@click.option("--ipaddr", default=None,
              help="Client IP address for Duo's risk engine.")
@click.option("--wait/--no-wait", default=True,
              help="Wait for user response (default: wait).")
def auth_push(username, reason, pushinfo, device, auth_type, display_username, ipaddr, wait):
    """Send a Duo Push to a user and return the result.

    This is the key command for AI agent integration — an agent can request
    approval from a human via Duo Push before taking a privileged action.

    \b
    Examples:
      duo-cli auth push jsmith
      duo-cli auth push jsmith --reason "Deploy to production"
      duo-cli auth push jsmith -p "action=deploy" -p "target=prod-us-east"
      duo-cli auth push jsmith --no-wait
    """
    client = _auth_client()

    info_str = _build_pushinfo(reason, pushinfo)

    kwargs = {
        "factor": "push",
        "username": username,
        "device": device,
    }
    if info_str:
        kwargs["pushinfo"] = info_str
    if auth_type:
        kwargs["type"] = auth_type
    if display_username:
        kwargs["display_username"] = display_username
    if ipaddr:
        kwargs["ipaddr"] = ipaddr
    if not wait:
        kwargs["async_txn"] = True

    result = client.auth(**kwargs)

    if not wait:
        txid = result.get("txid", "")
        click.echo(f"Push sent. Transaction ID: {txid}")
        return

    status = result.get("result", "unknown")
    click.echo(f"Push result: {status}")
    if result.get("status_msg"):
        click.echo(f"Message: {result['status_msg']}")


@auth.command("sms")
@click.argument("username")
@click.option("--device", "-d", default="auto", help="Device ID or 'auto'.")
def auth_sms(username, device):
    """Send SMS passcodes to a user's device."""
    client = _auth_client()
    result = client.auth(factor="sms", username=username, device=device)
    click.echo(f"SMS sent. Status: {result.get('status_msg', 'sent')}")


@auth.command("passcode")
@click.argument("username")
@click.argument("code")
@click.option("--ipaddr", default=None, help="Client IP address.")
def auth_passcode(username, code, ipaddr):
    """Authenticate a user with a passcode (from SMS, hardware token, or Duo Mobile).

    \b
    Examples:
      duo-cli auth passcode jsmith 123456
    """
    client = _auth_client()
    kwargs = {"factor": "passcode", "username": username, "passcode": code}
    if ipaddr:
        kwargs["ipaddr"] = ipaddr
    result = client.auth(**kwargs)
    status = result.get("result", "unknown")
    click.echo(f"Auth result: {status}")
    if result.get("status_msg"):
        click.echo(f"Message: {result['status_msg']}")


@auth.command("status")
@click.argument("txid")
def auth_status(txid):
    """Check the status of an async auth transaction.

    \b
    Use with --no-wait on push:
      duo-cli auth push jsmith --no-wait
      duo-cli auth status <txid>
    """
    client = _auth_client()
    result = client.auth_status(txid)
    click.echo(f"Status: {result.get('result', 'waiting')}")
    if result.get("status_msg"):
        click.echo(f"Message: {result['status_msg']}")
