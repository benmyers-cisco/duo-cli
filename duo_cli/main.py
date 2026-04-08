"""Main CLI entrypoint for duo-cli."""

from pathlib import Path

import click

from duo_cli import __version__
from duo_cli.commands.configure import configure
from duo_cli.commands.auth import auth
from duo_cli.commands.universal import universal

FLAG_FILE = Path("/tmp/duo-approvals-active")


@click.group()
@click.version_option(version=__version__, prog_name="duo-cli")
@click.option("--output", "-o", type=click.Choice(["table", "json"]), default="table",
              help="Output format.")
@click.pass_context
def cli(ctx, output):
    """Duo Security CLI — manage Duo from your terminal or AI agent."""
    ctx.ensure_object(dict)
    ctx.obj["output"] = output


@cli.command("push-on")
def push_on():
    """Activate Duo Push approval for Claude Code tool calls."""
    FLAG_FILE.touch()
    click.echo("Duo Push approval is ON. Write operations will require push approval.")


@cli.command("push-off")
def push_off():
    """Deactivate Duo Push approval for Claude Code tool calls."""
    FLAG_FILE.unlink(missing_ok=True)
    click.echo("Duo Push approval is OFF.")


cli.add_command(configure)
cli.add_command(auth)
cli.add_command(universal)


def main():
    try:
        cli(standalone_mode=False)
    except click.exceptions.Abort:
        raise SystemExit(1)
    except click.ClickException as e:
        e.show()
        raise SystemExit(e.exit_code)
    except RuntimeError as e:
        # duo_client raises RuntimeError for API errors
        click.secho(f"Duo API error: {e}", fg="red", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
