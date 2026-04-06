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

Or from source:

```bash
git clone https://github.com/cmedfisch/duo-cli.git
cd duo-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Duo has separate **Admin API**, **Auth API**, and **Universal Prompt (Web SDK)** integrations — configure each one you need:

```bash
duo-cli configure --api admin
duo-cli configure --api auth
duo-cli configure --api universal
```

The interactive setup walks you through where to find credentials in the Duo Admin Panel.

Credentials are stored in `~/.duo-cli/config.json`. You can also use environment variables (useful for CI/agents):

```bash
# Admin API
export DUO_ADMIN_IKEY=DIXXXXXXXXXXXXXXXXXX
export DUO_ADMIN_SKEY=your-secret-key
export DUO_ADMIN_HOST=api-XXXXXXXX.duosecurity.com

# Auth API
export DUO_AUTH_IKEY=DIXXXXXXXXXXXXXXXXXX
export DUO_AUTH_SKEY=your-secret-key
export DUO_AUTH_HOST=api-XXXXXXXX.duosecurity.com

# Universal Prompt (Web SDK)
export DUO_UNIVERSAL_CLIENT_ID=DIXXXXXXXXXXXXXXXXXX
export DUO_UNIVERSAL_CLIENT_SECRET=your-client-secret
export DUO_UNIVERSAL_HOST=api-XXXXXXXX.duosecurity.com
```

## Quick Start

```bash
# Verify credentials
duo-cli auth check

# Check if a user is enrolled and see their devices
duo-cli auth preauth jsmith

# Send a Duo Push
duo-cli auth push jsmith --reason "Agent requesting elevated access"

# Send a push with custom info fields
duo-cli auth push jsmith -p "action=deploy" -p "target=prod-us-east"

# List users (requires Admin API)
duo-cli users list

# JSON output for piping / agent consumption
duo-cli -o json users list
```

## Commands

### Auth API

| Command | Description |
|---------|-------------|
| `duo-cli auth check` | Verify Auth API credentials |
| `duo-cli auth preauth <username>` | Check if a user can authenticate, list their devices |
| `duo-cli auth push <username>` | Send a Duo Push |
| `duo-cli auth sms <username>` | Send SMS passcodes to a user |
| `duo-cli auth passcode <username> <code>` | Authenticate with a passcode |
| `duo-cli auth status <txid>` | Check async auth transaction status |

#### Push Options

```bash
duo-cli auth push <username> [OPTIONS]

  -r, --reason TEXT          Reason shown in the push prompt
  -p, --pushinfo TEXT        Custom key=value pairs (repeatable)
  -d, --device TEXT          Device ID or "auto" (default: auto)
  --type TEXT                Label for Duo auth logs
  --display-username TEXT    Override displayed username
  --ipaddr TEXT              Client IP for Duo's risk engine
  --wait / --no-wait         Wait for response (default: wait)
```

### Universal Prompt (Web SDK)

| Command | Description |
|---------|-------------|
| `duo-cli universal check` | Verify Universal Prompt credentials |
| `duo-cli universal login <username>` | Authenticate via browser with full Duo policy enforcement |

The `universal login` command opens your browser to the Duo Universal Prompt, spins up a local callback server, and returns the full JWT result including auth context, device info, and user details.

This is the **policy-enforced** flow — trusted devices, allowed networks, remembered devices, and all other Duo policies apply. Unlike `auth push` which calls the Auth API directly, this goes through the same OIDC flow as your SSO apps.

```bash
# Browser-based auth with full policy enforcement
duo-cli universal login jsmith

# JSON output returns the full decoded JWT
duo-cli -o json universal login jsmith
```

### Admin API

| Command | Description |
|---------|-------------|
| `duo-cli users list` | List all Duo users |
| `duo-cli users get <username>` | Get user details |
| `duo-cli users status <username>` | View or change a user's status |
| `duo-cli info` | Show account summary |

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

### Example: Async approval flow

```bash
# Send push without waiting
duo-cli auth push jsmith --reason "Approve deploy" --no-wait
# Output: Push sent. Transaction ID: abc123

# Poll for result
duo-cli auth status abc123
# Output: Status: allow
```

### Example: LangChain Tool

```python
from langchain.tools import ShellTool

shell = ShellTool()

# Agent decides it needs approval before a destructive action
result = shell.run("duo-cli auth push jsmith --reason 'Delete staging environment'")
if "allow" in result.lower():
    # proceed with the action
    ...
```

## Output Formats

All commands support `--output json` for machine-readable output:

```bash
duo-cli -o json users list | jq '.[].username'
duo-cli -o json auth preauth jsmith | jq '.devices'
```

## Auth Modes Compared

| | `auth push` | `universal login` |
|---|---|---|
| **Method** | Direct Auth API call | Browser-based OIDC flow |
| **Duo Policy** | Not enforced | Fully enforced |
| **Trusted devices** | No | Yes |
| **Allowed networks** | No | Yes |
| **Remembered devices** | No | Yes |
| **User interaction** | Phone push only | Full Universal Prompt |
| **Return value** | allow/deny | Full JWT with auth context |
| **Best for** | Quick agent approvals | Compliance-sensitive flows |

## Built On

- [duo_client_python](https://github.com/duosecurity/duo_client_python) — the official Duo Python SDK
- [duo_universal_python](https://github.com/duosecurity/duo_universal_python) — Duo Universal Prompt SDK
- [Click](https://click.palletsprojects.com/) — CLI framework
- [Rich](https://rich.readthedocs.io/) — beautiful terminal output
