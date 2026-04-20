#!/bin/bash
# Claude Code Stop hook — sends a Slack notification when Claude finishes.

PAUSE_FILE="/tmp/telegram-pause-until"
if [ -f "$PAUSE_FILE" ]; then
  PAUSE_UNTIL=$(cat "$PAUSE_FILE" 2>/dev/null)
  NOW=$(date +%s)
  if [ "$NOW" -lt "$PAUSE_UNTIL" ] 2>/dev/null; then
    echo '{}'
    exit 0
  else
    rm -f "$PAUSE_FILE"
  fi
fi

PYTHON="/opt/homebrew/opt/python@3.12/bin/python3.12"

# Check if user is in a Webex meeting — suppress notification
WEBEX_CHECK="/Users/benmyers/Projects/telegram-notify/scripts/check_webex_meeting.py"
if [ -f "$WEBEX_CHECK" ] && "$PYTHON" "$WEBEX_CHECK" >/dev/null 2>&1; then
  echo '{}'
  exit 0
fi

# Load Slack credentials
ENV_FILE="${SLACK_ENV:-/Users/benmyers/projects/claude-remote-slack/.env}"
if [[ -f "$ENV_FILE" ]]; then
  source "$ENV_FILE"
fi

if [[ -z "${SLACK_BOT_TOKEN:-}" ]]; then
  exit 0
fi

APPROVAL_CHANNEL="C0ATR9D5VPX"  # #claude-validation channel
PROJECT=$(basename "$PWD")

curl -s --max-time 5 -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"channel\":\"${APPROVAL_CHANNEL}\",\"text\":\"${PROJECT} — ready for next prompt\"}" \
  > /dev/null 2>&1

echo '{}'
