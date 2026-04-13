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

ask() {
  rm -f "$PENDING_FILE" "$APPROVE_FILE" "$DENY_FILE"
  echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "'"$1"'"}}'
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

# Check if the tool call matches any allowed permission in settings files
ALLOWED=$(echo "$PAYLOAD" | python3 -c "
import sys, json, os, re, fnmatch

payload = json.load(sys.stdin)
tool = payload.get('tool_name', '')
tool_input = payload.get('tool_input', {})

# Load allow lists from both settings files
allow_patterns = []
for path in [
    os.path.expanduser('~/.claude/settings.json'),
    os.path.expanduser('~/.claude/settings.local.json'),
]:
    try:
        with open(path) as f:
            data = json.load(f)
        allow_patterns.extend(data.get('permissions', {}).get('allow', []))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

def matches(pattern):
    # Exact tool name match (e.g. 'Agent', 'WebFetch')
    if pattern == tool:
        return True

    # Pattern with qualifier: ToolName(qualifier)
    m = re.match(r'^(\w+)\((.+)\)$', pattern)
    if not m:
        return False
    pat_tool, qualifier = m.group(1), m.group(2)
    if pat_tool != tool:
        return False

    if tool == 'Bash':
        cmd = tool_input.get('command', '')
        if qualifier.endswith(':*'):
            prefix = qualifier[:-2]
            if cmd == prefix or cmd.startswith(prefix + ' ') or cmd.startswith(prefix + '\n'):
                return True
        else:
            if cmd == qualifier:
                return True
    elif tool == 'WebFetch':
        url = tool_input.get('url', '')
        if qualifier.startswith('domain:'):
            domain = qualifier[7:]
            if domain in url:
                return True
        elif url == qualifier:
            return True
    elif tool == 'Read':
        file_path = tool_input.get('file_path', '')
        # Convert permission glob (e.g. //tmp/**) to fnmatch pattern
        pat = qualifier.lstrip('/')
        if fnmatch.fnmatch(file_path, '/' + pat):
            return True
    elif tool == 'Skill':
        skill = tool_input.get('skillName', '')
        if qualifier == skill:
            return True
    else:
        # Generic qualifier match for other tools (e.g. mcp tools)
        return False
    return False

print('yes' if any(matches(p) for p in allow_patterns) else 'no')
" 2>/dev/null)

if [ "$ALLOWED" = "yes" ]; then
  allow "Matched settings allow pattern"
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
  echo "$(date '+%H:%M:%S') Telegram unavailable — asking via terminal prompt" >> "$LOG"
  ask "Telegram timed out"
fi
