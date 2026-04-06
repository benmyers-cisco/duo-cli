"""Main CLI entrypoint for duo-cli."""

import click

from duo_cli import __version__
from duo_cli.commands.configure import configure
from duo_cli.commands.users import users
from duo_cli.commands.auth import auth
from duo_cli.commands.info import info


@click.group()
@click.version_option(version=__version__, prog_name="duo-cli")
@click.option("--output", "-o", type=click.Choice(["table", "json"]), default="table",
              help="Output format.")
@click.pass_context
def cli(ctx, output):
    """Duo Security CLI — manage Duo from your terminal or AI agent."""
    ctx.ensure_object(dict)
    ctx.obj["output"] = output


cli.add_command(configure)
cli.add_command(users)
cli.add_command(auth)
cli.add_command(info)


if __name__ == "__main__":
    cli()
