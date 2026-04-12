#!/bin/bash
# Claude Code Stop hook — sends a Telegram notification when Claude finishes.

PYTHON="/opt/homebrew/opt/python@3.12/bin/python3.12"

# Load Telegram credentials
ENV_FILE="${TELEGRAM_ENV:-/Users/benmyers/Projects/telegram-notify/.env}"
if [[ -f "$ENV_FILE" ]]; then
  source "$ENV_FILE"
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  exit 0
fi

PROJECT=$(basename "$PWD")

BODY=$("$PYTHON" -c "
import json, sys
project = sys.argv[1]
print(json.dumps({
    'chat_id': sys.argv[2],
    'text': '\u2753 ' + project + ' — ready for next prompt'
}))
" "$PROJECT" "$TELEGRAM_CHAT_ID" 2>/dev/null) || exit 0

curl -s --max-time 5 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "$BODY" > /dev/null 2>&1

echo '{}'
