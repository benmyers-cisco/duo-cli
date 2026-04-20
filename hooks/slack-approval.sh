#!/bin/bash
# Slack-based approval for Claude Code permission requests.
# Sends a message with Approve/Deny buttons, then polls temp files for the response.
# The Slack bot (claude-remote-slack) handles button clicks and writes the temp files.
#
# Usage: ./slack-approval.sh "description of request" "project-name"
# Exit code: 0 = approved, 1 = denied, 2 = timeout/error

# Load Slack credentials
ENV_FILE="${SLACK_ENV:-/Users/benmyers/projects/claude-remote-slack/.env}"
if [[ -f "$ENV_FILE" ]]; then
  source "$ENV_FILE"
fi

if [[ -z "${SLACK_BOT_TOKEN:-}" ]]; then
  echo "Slack not configured" >&2
  exit 2
fi

APPROVE_FILE="/tmp/claude-approve"
DENY_FILE="/tmp/claude-deny"
TIMEOUT_FILE="/tmp/approval-timeout"

# Read custom timeout (in minutes) or default to 10 minutes
if [[ -f "$TIMEOUT_FILE" ]]; then
  TIMEOUT_MINUTES=$(cat "$TIMEOUT_FILE" 2>/dev/null)
  POLL_TIMEOUT=$(( TIMEOUT_MINUTES * 60 ))
else
  POLL_TIMEOUT=600  # 10 minutes default
fi
APPROVAL_CHANNEL="C0ATR9D5VPX"  # #claude-validation channel

REASON="${1:-unknown}"
PROJECT="${2:-unknown}"

# Generate a unique action ID for this request
ACTION_ID="approval_$(date +%s)_$$"

# Send message with interactive buttons using Block Kit
BLOCKS=$(python3 -c "
import json, sys
reason = sys.argv[1]
project = sys.argv[2]
action_id = sys.argv[3]
blocks = [
    {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': '*' + project + '*\n\n' + reason
        }
    },
    {
        'type': 'actions',
        'block_id': action_id,
        'elements': [
            {
                'type': 'button',
                'text': {'type': 'plain_text', 'text': 'Approve'},
                'style': 'primary',
                'action_id': 'approval_approve',
                'value': action_id
            },
            {
                'type': 'button',
                'text': {'type': 'plain_text', 'text': 'Deny'},
                'style': 'danger',
                'action_id': 'approval_deny',
                'value': action_id
            }
        ]
    }
]
print(json.dumps(blocks))
" "$REASON" "$PROJECT" "$ACTION_ID" 2>/dev/null) || { echo "Failed to build blocks JSON" >&2; exit 2; }

BODY=$(python3 -c "
import json, sys
blocks = json.loads(sys.argv[1])
print(json.dumps({
    'channel': sys.argv[2],
    'text': sys.argv[3] + ': ' + sys.argv[4],
    'blocks': blocks
}))
" "$BLOCKS" "$APPROVAL_CHANNEL" "$PROJECT" "$REASON" 2>/dev/null) || { echo "Failed to build body JSON" >&2; exit 2; }

RESPONSE=$(curl -s --max-time 10 -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$BODY" 2>/dev/null) || { echo "Failed to send message" >&2; exit 2; }

MSG_TS=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d['ts'])" <<< "$RESPONSE" 2>/dev/null) || { echo "Failed to get message ts: $RESPONSE" >&2; exit 2; }

# Helper to update the Slack message
update_msg() {
  local UPDATE_BODY
  UPDATE_BODY=$(python3 -c "
import json, sys
print(json.dumps({
    'channel': sys.argv[1],
    'ts': sys.argv[2],
    'text': sys.argv[3],
    'blocks': []
}))
" "$APPROVAL_CHANNEL" "$MSG_TS" "$1" 2>/dev/null) || return
  curl -s --max-time 5 -X POST "https://slack.com/api/chat.update" \
    -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$UPDATE_BODY" > /dev/null 2>&1 || true
}

# Poll loop — check temp files for response from bot
START=$(date +%s)
while true; do
  NOW=$(date +%s)
  if (( NOW - START >= POLL_TIMEOUT )); then
    update_msg "Timed out: $REASON"
    exit 2
  fi

  if [[ -f "$APPROVE_FILE" ]]; then
    update_msg "Approved: $REASON"
    exit 0
  fi
  if [[ -f "$DENY_FILE" ]]; then
    update_msg "Denied: $REASON"
    exit 1
  fi

  sleep 1
done
