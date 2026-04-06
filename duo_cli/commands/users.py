"""User management commands."""

import click
import duo_client

from duo_cli.config import get_client_kwargs
from duo_cli.output import render


def _admin_client() -> duo_client.Admin:
    return duo_client.Admin(**get_client_kwargs("admin"))


@click.group()
def users():
    """Manage Duo users."""
    pass


@users.command("list")
@click.option("--limit", "-n", default=100, help="Max users to return.")
@click.pass_context
def list_users(ctx, limit):
    """List all Duo users."""
    admin = _admin_client()
    result = admin.get_users()[:limit]
    data = [
        {
            "user_id": u.get("user_id", ""),
            "username": u.get("username", ""),
            "email": u.get("email", ""),
            "status": u.get("status", ""),
            "last_login": u.get("last_login", ""),
        }
        for u in result
    ]
    render(data, ["user_id", "username", "email", "status", "last_login"],
           output_format=ctx.obj["output"], title="Duo Users")


@users.command("get")
@click.argument("username")
@click.pass_context
def get_user(ctx, username):
    """Get details for a specific user by username."""
    admin = _admin_client()
    result = admin.get_users_by_name(username)
    if not result:
        raise click.ClickException(f"User '{username}' not found.")
    render(result, ["user_id", "username", "email", "status", "phones", "groups"],
           output_format=ctx.obj["output"], title=f"User: {username}")


@users.command("status")
@click.argument("username")
@click.option("--set", "new_status", type=click.Choice(["active", "disabled", "bypass"]),
              help="Set user status.")
@click.pass_context
def user_status(ctx, username, new_status):
    """View or change a user's status."""
    admin = _admin_client()
    matches = admin.get_users_by_name(username)
    if not matches:
        raise click.ClickException(f"User '{username}' not found.")
    user = matches[0]

    if new_status:
        admin.update_user(user["user_id"], status=new_status)
        click.echo(f"Updated {username} status to '{new_status}'.")
    else:
        click.echo(f"{username}: {user.get('status', 'unknown')}")
