#!/bin/bash
# Claude Code PreToolUse approval hook
#
# Flow:
#   1. Skip read-only and harmless tools
#   2. Send Telegram message with Approve/Deny buttons
#   3. If approved/denied via Telegram, return result
#   4. If Telegram times out (3 min), defer to terminal prompt
#
# State files:
#   /tmp/claude-approve  — written by Telegram script on approve
#   /tmp/claude-deny     — written by Telegram script on deny
#   /tmp/duo-bg-push.log — debug log
LOG="/tmp/duo-bg-push.log"

PENDING_FILE="/tmp/claude-pending-approval"
APPROVE_FILE="/tmp/claude-approve"
DENY_FILE="/tmp/claude-deny"
allow() {
  rm -f "$PENDING_FILE" "$APPROVE_FILE" "$DENY_FILE"
  echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "'"$1"'"}}'
  exit 0
}

deny() {
  rm -f "$PENDING_FILE" "$APPROVE_FILE" "$DENY_FILE"
  echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "'"$1"'"}}'
  exit 0
}

defer() {
  rm -f "$PENDING_FILE" "$APPROVE_FILE" "$DENY_FILE"
  echo '{}'
  exit 0
}

# Read JSON payload from stdin
PAYLOAD=$(cat)

# Extract tool name
TOOL_NAME=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)

# Skip read-only operations
case "$TOOL_NAME" in
  Read|Glob|Grep|ToolSearch|TaskCreate|TaskUpdate|TaskGet|TaskList|TaskOutput|AskUserQuestion|EnterPlanMode|ExitPlanMode)
    allow "Read-only tool: $TOOL_NAME"
    ;;
esac

# Skip harmless Bash commands
if [ "$TOOL_NAME" = "Bash" ]; then
  BASH_CMD=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null)
  case "$BASH_CMD" in
    rm\ -f\ /tmp/*|cat\ /tmp/*|ls\ *|ps\ *|date\ *|pwd|whoami|which\ *)
      allow "Harmless command: $BASH_CMD"
      ;;
  esac
fi

# Build a human-readable description
case "$TOOL_NAME" in
  Bash)
    CMD=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command','unknown'))" 2>/dev/null)
    REASON="Bash: ${CMD:0:200}"
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

# Send Telegram approval request immediately
rm -f "$APPROVE_FILE" "$DENY_FILE"
TELEGRAM_SCRIPT="/Users/benmyers/duo-cli/hooks/telegram-approval.sh"
echo "$(date '+%H:%M:%S') Sending Telegram approval: $REASON" >> "$LOG"

PROJECT=$(basename "$PWD")
"$TELEGRAM_SCRIPT" "$REASON" "$PROJECT"
EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "$(date '+%H:%M:%S') Telegram approved" >> "$LOG"
  allow "Telegram approved"
elif [ "$EXIT_CODE" -eq 1 ]; then
  echo "$(date '+%H:%M:%S') Telegram denied" >> "$LOG"
  deny "Telegram denied"
else
  # Telegram timed out or unavailable — show terminal prompt
  echo "$(date '+%H:%M:%S') Telegram unavailable — deferring to terminal prompt" >> "$LOG"
  defer
fi
