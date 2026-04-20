#!/bin/bash
# Pause approval flow for a given duration.
# Usage: approval-pause.sh <minutes>
#        approval-pause.sh off        (resume immediately)
#
# While paused, all Claude Code sessions fall back to terminal prompts.

PAUSE_FILE="/tmp/telegram-pause-until"

if [ "$1" = "off" ] || [ "$1" = "stop" ]; then
  rm -f "$PAUSE_FILE"
  echo "Approvals resumed."
  exit 0
fi

MINUTES="${1:-30}"

if ! [[ "$MINUTES" =~ ^[0-9]+$ ]]; then
  echo "Usage: approval-pause.sh <minutes>  or  approval-pause.sh off"
  exit 1
fi

date -v+"${MINUTES}M" +%s > "$PAUSE_FILE"
UNTIL=$(date -v+"${MINUTES}M" '+%H:%M')
echo "Approvals paused for ${MINUTES} minutes (until ${UNTIL})."
