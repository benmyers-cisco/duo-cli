"""Authentication commands — trigger and check Duo auth."""

import click
import duo_client

from duo_cli.config import get_client_kwargs
from duo_cli.output import render


def _auth_client() -> duo_client.Auth:
    kwargs = get_client_kwargs()
    return duo_client.Auth(**kwargs)


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


@auth.command("push")
@click.argument("username")
@click.option("--reason", "-r", default=None, help="Reason for the auth request (shown to user).")
@click.option("--wait/--no-wait", default=True, help="Wait for user response.")
def auth_push(username, reason, wait):
    """Send a Duo Push to a user and return the result.

    This is the key command for AI agent integration — an agent can request
    approval from a human via Duo Push before taking a privileged action.
    """
    client = _auth_client()

    kwargs = {
        "username": username,
        "factor": "push",
        "device": "auto",
    }
    if reason:
        kwargs["pushinfo"] = f"reason={reason}"
    if not wait:
        kwargs["async_txn"] = "1"

    result = client.auth(**kwargs)

    if not wait:
        txid = result.get("txid", "")
        click.echo(f"Push sent. Transaction ID: {txid}")
        return

    status = result.get("result", "unknown")
    click.echo(f"Push result: {status}")
    if result.get("status_msg"):
        click.echo(f"Message: {result['status_msg']}")


@auth.command("status")
@click.argument("txid")
def auth_status(txid):
    """Check the status of an async auth transaction."""
    client = _auth_client()
    result = client.auth_status(txid)
    click.echo(f"Status: {result.get('result', 'waiting')}")
    if result.get("status_msg"):
        click.echo(f"Message: {result['status_msg']}")
