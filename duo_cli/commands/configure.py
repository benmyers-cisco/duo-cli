"""Configure duo-cli credentials."""

import click

from duo_cli.config import load_config, save_config


@click.command()
@click.option("--ikey", prompt="Integration key (DIXXXXXXXXXXXXXXXXXX)",
              help="Duo Admin API integration key.")
@click.option("--skey", prompt="Secret key", hide_input=True,
              help="Duo Admin API secret key.")
@click.option("--host", prompt="API hostname (e.g. api-XXXXXXXX.duosecurity.com)",
              help="Duo API hostname.")
def configure(ikey, skey, host):
    """Set up Duo API credentials."""
    config = load_config()
    config.update({"ikey": ikey, "skey": skey, "host": host})
    save_config(config)
    click.echo("Configuration saved to ~/.duo-cli/config.json")
