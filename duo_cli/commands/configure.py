"""Configure duo-cli credentials."""

import click

from duo_cli.config import load_config, save_config

SETUP_HELP = {
    "admin": (
        "\n  To get Admin API credentials:\n"
        "  1. Log into the Duo Admin Panel (admin.duosecurity.com)\n"
        "  2. Go to Applications > Protect an Application\n"
        "  3. Search for \"Admin API\" in the application catalog\n"
        "  4. Click Protect to create the integration\n"
        "  5. Grant the appropriate permissions (e.g. Grant read resource)\n"
        "  6. Copy the Integration key, Secret key, and API hostname below\n"
    ),
    "auth": (
        "\n  To get Auth API credentials:\n"
        "  1. Log into the Duo Admin Panel (admin.duosecurity.com)\n"
        "  2. Go to Applications > Protect an Application\n"
        "  3. Search for \"Auth API\" in the application catalog\n"
        "  4. Click Protect to create the integration\n"
        "  5. Copy the Integration key, Secret key, and API hostname below\n"
    ),
}


@click.command()
@click.option("--api", type=click.Choice(["admin", "auth"]), default=None,
              help="Which Duo API to configure.")
@click.option("--ikey", default=None, help="Duo integration key.")
@click.option("--skey", default=None, help="Duo secret key.")
@click.option("--host", default=None, help="Duo API hostname.")
def configure(api, ikey, skey, host):
    """Set up Duo API credentials (admin and auth are separate)."""
    if not api:
        api = click.prompt("Which API?", type=click.Choice(["admin", "auth"]))

    # Show setup instructions before prompting for creds
    interactive = ikey is None
    if interactive:
        click.echo(SETUP_HELP[api])

    if ikey is None:
        ikey = click.prompt("Integration key (DIXXXXXXXXXXXXXXXXXX)")
    if skey is None:
        skey = click.prompt("Secret key", hide_input=True)
    if host is None:
        host = click.prompt("API hostname (e.g. api-XXXXXXXX.duosecurity.com)")

    config = load_config()
    config[api] = {"ikey": ikey, "skey": skey, "host": host}
    save_config(config)
    click.echo(f"\n{api.title()} API configuration saved to ~/.duo-cli/config.json")
