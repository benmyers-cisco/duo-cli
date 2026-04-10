#!/bin/bash
# Telegram-based approval for Claude Code permission requests.
# Sends a message with inline Approve/Deny buttons, then polls for the response.
#
# Usage: ./telegram-approval.sh "description of request"
# Exit code: 0 = approved, 1 = denied, 2 = timeout/error
# Also writes /tmp/claude-approve or /tmp/claude-deny

PYTHON="/opt/homebrew/opt/python@3.12/bin/python3.12"

# Load Telegram credentials
ENV_FILE="${TELEGRAM_ENV:-/Users/benmyers/Projects/telegram-notify/.env}"
if [[ -f "$ENV_FILE" ]]; then
  source "$ENV_FILE"
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  echo "Telegram not configured" >&2
  exit 2
fi

APPROVE_FILE="/tmp/claude-approve"
DENY_FILE="/tmp/claude-deny"
POLL_TIMEOUT=180  # 3 minutes
OFFSET_FILE="/tmp/telegram-bot-offset"

REASON="${1:-unknown}"

# Send message with inline keyboard
BODY=$("$PYTHON" -c "
import json, sys
print(json.dumps({
    'chat_id': sys.argv[1],
    'text': '\U0001f510 Claude Code Permission Request\n\n' + sys.argv[2],
    'reply_markup': {'inline_keyboard':[[
        {'text':'\u2705 Approve','callback_data':'approve'},
        {'text':'\u274c Deny','callback_data':'deny'}
    ]]}
}))
" "$TELEGRAM_CHAT_ID" "$REASON" 2>/dev/null) || { echo "Failed to build JSON" >&2; exit 2; }

RESPONSE=$(curl -s --max-time 10 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "$BODY" 2>/dev/null) || { echo "Failed to send message" >&2; exit 2; }

MSG_ID=$("$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['result']['message_id'])" <<< "$RESPONSE" 2>/dev/null) || { echo "Failed to get message ID" >&2; exit 2; }

# Get current update offset
OFFSET=0
if [[ -f "$OFFSET_FILE" ]]; then
  OFFSET=$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)
fi

# Helper to update the Telegram message text
update_msg() {
  curl -s --max-time 5 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/editMessageText" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d message_id="$MSG_ID" \
    -d text="$1" > /dev/null 2>&1 || true
}

# Poll loop — check local files AND Telegram callbacks
START=$(date +%s)
while true; do
  NOW=$(date +%s)
  if (( NOW - START >= POLL_TIMEOUT )); then
    update_msg "⏰ Timed out: $REASON"
    exit 2
  fi

  # Check local files first (fast path)
  if [[ -f "$APPROVE_FILE" ]]; then
    update_msg "✅ Approved (locally)"
    exit 0
  fi
  if [[ -f "$DENY_FILE" ]]; then
    update_msg "❌ Denied (locally)"
    exit 1
  fi

  # Poll Telegram for button callbacks (short timeout)
  UPDATES=$(curl -s --max-time 3 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates?offset=${OFFSET}&timeout=1&allowed_updates=%5B%22callback_query%22%5D" 2>/dev/null) || UPDATES=""

  if [[ -n "$UPDATES" ]]; then
    # Parse the callback
    DECISION=$("$PYTHON" -c "
import sys, json
try:
    data = json.load(sys.stdin)
except:
    sys.exit(0)
for update in data.get('result', []):
    offset = update['update_id'] + 1
    with open('$OFFSET_FILE', 'w') as f:
        f.write(str(offset))
    cb = update.get('callback_query', {})
    if cb.get('message', {}).get('message_id') == $MSG_ID:
        # Answer the callback to remove spinner
        import urllib.request
        try:
            urllib.request.urlopen(urllib.request.Request(
                'https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/answerCallbackQuery',
                data=('callback_query_id=' + cb['id']).encode()
            ))
        except:
            pass
        print(cb.get('data', ''))
        sys.exit(0)
" <<< "$UPDATES" 2>/dev/null) || DECISION=""

    if [[ "$DECISION" == "approve" ]]; then
      update_msg "✅ Approved: $REASON"
      touch "$APPROVE_FILE"
      exit 0
    elif [[ "$DECISION" == "deny" ]]; then
      update_msg "❌ Denied: $REASON"
      touch "$DENY_FILE"
      exit 1
    fi
  fi

  sleep 1
done
