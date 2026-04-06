# duo-cli

A Python CLI wrapper for [Duo Security](https://duo.com) APIs — built for operators and AI agent integration.

## Why?

[duo_client_python](https://github.com/duosecurity/duo_client_python) is a great library for building Duo integrations in Python. But there's no CLI you can use directly from a terminal, a shell script, or an AI agent.

`duo-cli` fills that gap:

- **Terminal-first** — `duo-cli users list`, `duo-cli auth push jsmith`
- **AI-agent ready** — any agent that can call shell commands can use Duo (MCP, LangChain, etc.)
- **Human-in-the-loop** — use `duo-cli auth push` to gate privileged agent actions behind real Duo approval

## Install

```bash
pip install duo-cli
```

## Quick Start

```bash
# Configure credentials
duo-cli configure

# List users
duo-cli users list

# Get a specific user
duo-cli users get jsmith

# Send a Duo Push (great for agent approval workflows)
duo-cli auth push jsmith --reason "Agent requesting elevated access"

# JSON output for piping / agent consumption
duo-cli -o json users list
```

## AI Agent Integration

The killer feature: any AI agent can request human approval via Duo Push before taking a privileged action.

### Example: Claude / MCP Tool

```python
# As an MCP tool, an agent can call:
#   duo-cli auth push jsmith --reason "Deploy to production"
#
# The user gets a Duo Push on their phone.
# If they approve, the agent proceeds. If they deny, the agent stops.
```

### Example: LangChain Tool

```python
from langchain.tools import ShellTool

shell = ShellTool()

# Agent decides it needs approval before a destructive action
result = shell.run("duo-cli auth push jsmith --reason 'Delete staging environment' --wait")
if "allow" in result.lower():
    # proceed with the action
    ...
```

## Commands

| Command | Description |
|---------|-------------|
| `duo-cli configure` | Set up API credentials |
| `duo-cli users list` | List all Duo users |
| `duo-cli users get <username>` | Get user details |
| `duo-cli users status <username>` | View/change user status |
| `duo-cli auth check` | Verify API credentials |
| `duo-cli auth push <username>` | Send a Duo Push |
| `duo-cli auth status <txid>` | Check async auth status |
| `duo-cli info` | Show account summary |

## Output Formats

All commands support `--output json` for machine-readable output:

```bash
duo-cli -o json users list | jq '.[].username'
```

## Built On

- [duo_client_python](https://github.com/duosecurity/duo_client_python) — the official Duo Python SDK
- [Click](https://click.palletsprojects.com/) — CLI framework
- [Rich](https://rich.readthedocs.io/) — beautiful terminal output
