#!/usr/bin/env bash
# notify.sh — Multi-channel notification for AFK events
# Usage: notify.sh <title> <message> <level>
# Level: info | warning | error | success
# Channels: Claude App push (primary), Slack DM (secondary), Telegram (tertiary), macOS (fallback)
set -euo pipefail

TITLE="${1:?"Usage: notify.sh <title> <message> <level>"}"
MESSAGE="${2:?"Usage: notify.sh <title> <message> <level>"}"
LEVEL="${3:-info}"

SLACK_WEBHOOK_URL="${AFK_SLACK_WEBHOOK:-}"
TELEGRAM_BOT_TOKEN="${AFK_TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${AFK_TELEGRAM_CHAT_ID:-}"
CLOUD_ENV="${AFK_CLOUD_ENV:-}"

case "$LEVEL" in
    success) EMOJI="✅" ;;
    warning) EMOJI="⚠️" ;;
    error)   EMOJI="❌" ;;
    *)       EMOJI="ℹ️" ;;
esac

SENT=0

# ── Slack (secondary) ────────────────────────────────────────────────────────
if [ -n "$SLACK_WEBHOOK_URL" ]; then
    PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
    'text': f'$EMOJI *{sys.argv[1]}*\n{sys.argv[2]}',
    'unfurl_links': False
}))
" "$TITLE" "$MESSAGE" 2>/dev/null || echo '{}')

    if [ "$PAYLOAD" != '{}' ]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST "$SLACK_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "$PAYLOAD" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            SENT=$((SENT + 1))
        fi
    fi
fi

# ── Telegram (tertiary) ──────────────────────────────────────────────────────
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    TELEGRAM_MSG="$EMOJI *$TITLE*%0A$MESSAGE"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}&text=${TELEGRAM_MSG}&parse_mode=Markdown" \
        2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        SENT=$((SENT + 1))
    fi
fi

# ── Cloud logging (when running in cloud container) ──────────────────────────
if [ -n "$CLOUD_ENV" ]; then
    # Structured JSON log for Cloud Run / ECS log aggregation
    python3 -c "
import json, sys
print(json.dumps({
    'severity': sys.argv[1].upper(),
    'message': f'{sys.argv[2]}: {sys.argv[3]}',
    'labels': {'source': 'afk-notify', 'cloud_env': sys.argv[4]}
}))
" "$LEVEL" "$TITLE" "$MESSAGE" "$CLOUD_ENV" 2>/dev/null
    SENT=$((SENT + 1))
fi

# ── macOS notification (fallback, skip in cloud) ─────────────────────────────
if [ -z "$CLOUD_ENV" ] && command -v osascript &>/dev/null; then
    osascript -e "display notification \"$MESSAGE\" with title \"DeepSecure AFK\" subtitle \"$TITLE\" sound name \"Glass\"" 2>/dev/null &
    SENT=$((SENT + 1))
fi

if [ "$SENT" -eq 0 ]; then
    echo "[notify] No channels configured — message logged only: $EMOJI $TITLE: $MESSAGE" >&2
fi

exit 0
