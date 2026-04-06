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
    "universal": (
        "\n  To get Universal Prompt (Web SDK) credentials:\n"
        "  1. Log into the Duo Admin Panel (admin.duosecurity.com)\n"
        "  2. Go to Applications > Protect an Application\n"
        "  3. Search for \"Web SDK\" in the application catalog\n"
        "  4. Click Protect to create the integration\n"
        "  5. Copy the Client ID, Client secret, and API hostname below\n"
        "\n"
        "  Note: The Universal Prompt uses Client ID / Client secret\n"
        "  (not Integration key / Secret key like the other APIs).\n"
    ),
}

API_CHOICES = click.Choice(["admin", "auth", "universal"])


@click.command()
@click.option("--api", type=API_CHOICES, default=None,
              help="Which Duo API to configure.")
@click.option("--ikey", default=None, help="Integration key (admin/auth APIs).")
@click.option("--skey", default=None, help="Secret key (admin/auth APIs).")
@click.option("--client-id", default=None, help="Client ID (universal API).")
@click.option("--client-secret", default=None, help="Client secret (universal API).")
@click.option("--host", default=None, help="Duo API hostname.")
def configure(api, ikey, skey, client_id, client_secret, host):
    """Set up Duo API credentials (admin, auth, and universal are separate)."""
    if not api:
        api = click.prompt("Which API?", type=API_CHOICES)

    is_universal = api == "universal"

    # Show setup instructions before prompting for creds
    interactive = (client_id if is_universal else ikey) is None
    if interactive:
        click.echo(SETUP_HELP[api])

    if is_universal:
        if client_id is None:
            client_id = click.prompt("Client ID (DIXXXXXXXXXXXXXXXXXX)")
        if client_secret is None:
            client_secret = click.prompt("Client secret", hide_input=True)
    else:
        if ikey is None:
            ikey = click.prompt("Integration key (DIXXXXXXXXXXXXXXXXXX)")
        if skey is None:
            skey = click.prompt("Secret key", hide_input=True)

    if host is None:
        host = click.prompt("API hostname (e.g. api-XXXXXXXX.duosecurity.com)")

    config = load_config()
    if is_universal:
        config[api] = {"client_id": client_id, "client_secret": client_secret, "host": host}
    else:
        config[api] = {"ikey": ikey, "skey": skey, "host": host}
    save_config(config)
    click.echo(f"\n{api.title()} API configuration saved to ~/.duo-cli/config.json")
