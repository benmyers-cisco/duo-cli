"""Account info commands."""

import click
import duo_client

from duo_cli.config import get_client_kwargs
from duo_cli.output import render


@click.command()
@click.pass_context
def info(ctx):
    """Show Duo account summary info."""
    admin = duo_client.Admin(**get_client_kwargs("admin"))
    info_data = admin.get_info_summary()
    data = [
        {"metric": k, "value": v}
        for k, v in info_data.items()
    ]
    render(data, ["metric", "value"],
           output_format=ctx.obj["output"], title="Account Summary")
