"""Output formatting helpers."""

import json

from rich.console import Console
from rich.table import Table

console = Console()


def render(data, columns: list[str], *, output_format: str = "table", title: str = ""):
    """Render a list of dicts as either a rich table or JSON.

    Args:
        data: list of dicts (rows)
        columns: list of keys to display
        output_format: "table" or "json"
        title: optional table title
    """
    if output_format == "json":
        console.print_json(json.dumps(data, default=str))
        return

    table = Table(title=title, show_lines=False)
    for col in columns:
        table.add_column(col, style="cyan" if col == columns[0] else "")
    for row in data:
        table.add_row(*(str(row.get(c, "")) for c in columns))
    console.print(table)
