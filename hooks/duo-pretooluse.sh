#!/bin/bash
# Duo Push approval hook for Claude Code PreToolUse events
# Checks a flag file, then sends a Duo Push for non-read-only tool calls.
#
# State files:
#   /tmp/duo-approvals-active  — flag to enable Duo approval mode
#   /tmp/duo-last-deny         — epoch timestamp of last deny/timeout
#   /tmp/duo-fail-count        — consecutive failed push count

DUO_CLI="/Users/benmyers/duo-cli/.venv/bin/duo-cli"
DUO_USER="ben@benmyers.io"
FLAG_FILE="/tmp/duo-approvals-active"
LAST_DENY_FILE="/tmp/duo-last-deny"
FAIL_COUNT_FILE="/tmp/duo-fail-count"
COOLDOWN_SECONDS=120
MAX_CONSECUTIVE_FAILURES=5

allow() {
  echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "'"$1"'"}}'
  exit 0
}

deny() {
  echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "'"$1"'"}}'
  exit 0
}

# Return no opinion — defers to Claude Code's native permission prompt
defer() {
  echo '{}'
  exit 0
}

# Read JSON payload from stdin
PAYLOAD=$(cat)

# If Duo mode is not active, pass through (no opinion)
if [ ! -f "$FLAG_FILE" ]; then
  allow "Duo approval mode not active"
fi

# Extract tool name
TOOL_NAME=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)

# Skip read-only operations — no point buzzing your phone for a grep
case "$TOOL_NAME" in
  Read|Glob|Grep|ToolSearch|TaskCreate|TaskUpdate|TaskGet|TaskList|TaskOutput|AskUserQuestion|EnterPlanMode|ExitPlanMode)
    allow "Read-only tool: $TOOL_NAME"
    ;;
esac

# Check cooldown — don't send a push if one was denied/timed out in the last 120s
if [ -f "$LAST_DENY_FILE" ]; then
  LAST_DENY=$(cat "$LAST_DENY_FILE" 2>/dev/null || echo 0)
  NOW=$(date +%s)
  ELAPSED=$(( NOW - LAST_DENY ))
  if [ "$ELAPSED" -lt "$COOLDOWN_SECONDS" ]; then
    REMAINING=$(( COOLDOWN_SECONDS - ELAPSED ))
    defer  # fall back to Claude Code's native prompt
  fi
fi

# Check consecutive failure count — fall back after too many failures
FAIL_COUNT=0
if [ -f "$FAIL_COUNT_FILE" ]; then
  FAIL_COUNT=$(cat "$FAIL_COUNT_FILE" 2>/dev/null || echo 0)
fi
if [ "$FAIL_COUNT" -ge "$MAX_CONSECUTIVE_FAILURES" ]; then
  defer  # fall back to Claude Code's native prompt
fi

# Build a human-readable reason from the tool call
case "$TOOL_NAME" in
  Bash)
    CMD=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command','unknown'))" 2>/dev/null)
    REASON="Bash: $CMD"
    ;;
  Edit)
    FILE=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path','unknown'))" 2>/dev/null)
    REASON="Edit: $FILE"
    ;;
  Write)
    FILE=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path','unknown'))" 2>/dev/null)
    REASON="Write: $FILE"
    ;;
  WebFetch)
    URL=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('url','unknown'))" 2>/dev/null)
    REASON="WebFetch: $URL"
    ;;
  *)
    REASON="$TOOL_NAME"
    ;;
esac

# Truncate reason if too long
REASON="${REASON:0:200}"

# Send Duo Push
RESULT=$($DUO_CLI auth push "$DUO_USER" --reason "$REASON" --wait 2>&1)

if echo "$RESULT" | grep -qi "allow\|success\|approved"; then
  # Reset failure tracking on success
  rm -f "$LAST_DENY_FILE" "$FAIL_COUNT_FILE"
  allow "Duo Push approved"
else
  # Record the failure
  date +%s > "$LAST_DENY_FILE"
  FAIL_COUNT=$(( FAIL_COUNT + 1 ))
  echo "$FAIL_COUNT" > "$FAIL_COUNT_FILE"
  deny "Duo Push denied or timed out ($FAIL_COUNT consecutive failure(s))"
fi
