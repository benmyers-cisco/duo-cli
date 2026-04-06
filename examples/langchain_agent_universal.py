"""
LangChain agent with Duo Universal Prompt approval gate.

Like langchain_agent.py but uses the browser-based Universal Prompt
which enforces full Duo policy (trusted devices, allowed networks, etc.).

Requirements:
    pip install langchain-openai langgraph

Usage (OpenRouter):
    export OPENROUTER_API_KEY=sk-or-...
    python3 examples/langchain_agent_universal.py <duo-username>
"""

import os
import subprocess
import sys

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent


# --- Duo CLI Tools ---

@tool
def duo_universal_login(username: str) -> str:
    """Authenticate a user via the Duo Universal Prompt in a browser.
    This opens a browser window where the user completes Duo authentication
    with full policy enforcement (trusted devices, allowed networks, etc.).
    Returns JSON with auth result, device info, and user details.
    You MUST get a successful auth before executing any privileged action."""
    result = subprocess.run(
        ["duo-cli", "-o", "json", "universal", "login", username.strip()],
        capture_output=True, text=True
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        return f"Duo Universal login failed: {result.stderr.strip() or output}"
    return output


@tool
def execute_privileged_action(action: str) -> str:
    """Execute a privileged action. Only call this AFTER getting successful
    Duo Universal authentication. If auth failed, do NOT call this."""
    return f"SUCCESS: Executed '{action}'"


# --- Build and run the agent ---

api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("Set OPENROUTER_API_KEY or OPENAI_API_KEY environment variable.")
    sys.exit(1)

llm_kwargs = {"model": "google/gemini-2.0-flash-001", "openai_api_key": api_key, "temperature": 0}
if os.environ.get("OPENROUTER_API_KEY"):
    llm_kwargs["openai_api_base"] = "https://openrouter.ai/api/v1"

llm = ChatOpenAI(**llm_kwargs)
tools = [duo_universal_login, execute_privileged_action]
agent = create_react_agent(llm, tools)

if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else input("Duo username: ").strip()

    print("=" * 60)
    print("LangChain Agent with Duo Universal Prompt Approval")
    print("=" * 60)
    print()
    print("A browser window will open for Duo authentication.")
    print()

    response = agent.invoke({
        "messages": [{
            "role": "user",
            "content": (
                f"I need to deploy the latest release to production. "
                f"Please authenticate {username} via the Duo Universal Prompt "
                f"before proceeding. This requires full policy-enforced auth."
            ),
        }]
    })

    # Print the conversation
    for msg in response["messages"]:
        role = msg.__class__.__name__
        if hasattr(msg, "content") and msg.content:
            print(f"\n[{role}] {msg.content}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"\n[Tool Call] {tc['name']}({tc['args']})")

    print()
    print("=" * 60)
