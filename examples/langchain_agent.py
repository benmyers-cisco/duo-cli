"""
LangChain agent with Duo Push approval gate.

Demonstrates an AI agent that must get human approval via Duo Push
before executing a privileged action.

Requirements:
    pip install langchain-openai langgraph

Usage (OpenRouter):
    export OPENROUTER_API_KEY=sk-or-...
    python3 examples/langchain_agent.py <duo-username>

Usage (OpenAI directly):
    export OPENAI_API_KEY=sk-...
    # Edit the llm= line below to use ChatOpenAI(model="gpt-4o-mini")
    python3 examples/langchain_agent.py <duo-username>
"""

import os
import subprocess
import sys

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent


# --- Duo CLI Tools ---

@tool
def duo_preauth(username: str) -> str:
    """Check if a user is enrolled in Duo and can authenticate.
    Use this first to verify the user exists before sending a push."""
    result = subprocess.run(
        ["duo-cli", "auth", "preauth", username.strip()],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return f"Preauth failed: {result.stderr.strip()}"
    return result.stdout.strip()


@tool
def duo_push(username: str, reason: str) -> str:
    """Send a Duo Push notification to a user for approval.
    Returns 'Push result: allow' if approved, 'Push result: deny' if denied.
    You MUST get 'allow' before executing any privileged action."""
    result = subprocess.run(
        ["duo-cli", "auth", "push", username.strip(), "--reason", reason],
        capture_output=True, text=True
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        return f"Duo Push failed: {result.stderr.strip() or output}"
    return output


@tool
def execute_privileged_action(action: str) -> str:
    """Execute a privileged action. Only call this AFTER getting Duo Push approval
    (duo_push returned 'allow'). If Duo Push was denied, do NOT call this."""
    return f"SUCCESS: Executed '{action}'"


# --- Build and run the agent ---

# Using OpenRouter (supports many models). Swap to ChatOpenAI(model="gpt-4o-mini")
# for direct OpenAI usage, or any other LangChain-compatible LLM.
api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("Set OPENROUTER_API_KEY or OPENAI_API_KEY environment variable.")
    sys.exit(1)

llm_kwargs = {"model": "google/gemini-2.0-flash-001", "openai_api_key": api_key, "temperature": 0}
if os.environ.get("OPENROUTER_API_KEY"):
    llm_kwargs["openai_api_base"] = "https://openrouter.ai/api/v1"

llm = ChatOpenAI(**llm_kwargs)
tools = [duo_preauth, duo_push, execute_privileged_action]
agent = create_react_agent(llm, tools)

if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else input("Duo username: ").strip()

    print("=" * 60)
    print("LangChain Agent with Duo Push Approval")
    print("=" * 60)
    print()

    response = agent.invoke({
        "messages": [{
            "role": "user",
            "content": (
                f"I need to deploy the latest release to production. "
                f"Please get approval from {username} via Duo Push before proceeding. "
                f"The reason should mention it's a production deployment."
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
