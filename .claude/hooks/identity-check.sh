#!/usr/bin/env bash
# identity-check.sh — Pre-iteration hook: verify/refresh delegation_token
#
# Runs before each AFK iteration (called by ralph.sh or as a Claude Code hook).
# When DEEPSECURE_AGENT_ID is set, verifies the delegation_token is still valid.
# If expired, attempts refresh via afk-identity.sh. If revoked, blocks execution.
# When DEEPSECURE_AGENT_ID is unset, exits cleanly — no identity configured.
set -euo pipefail

IDENTITY_FILE="${AFK_IDENTITY_FILE:-.afk/identity.json}"
CONTROL_URL="${DEEPSECURE_CONTROL_URL:-http://localhost:8000}"
REFRESH_THRESHOLD="${AFK_REFRESH_THRESHOLD:-900}"
LOG_FILE="${AFK_LOG_DIR:-.hermes}/identity.log"

log() {
    local msg="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [identity-check] $1"
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
}

# No identity configured — skip check entirely
if [ -z "${DEEPSECURE_AGENT_ID:-}" ]; then
    exit 0
fi

# No identity file — agent should bootstrap first
if [ ! -f "$IDENTITY_FILE" ]; then
    log "⚠️  DEEPSECURE_AGENT_ID set but no identity file — bootstrapping"
    scripts/afk-identity.sh 2>/dev/null || {
        log "❌ Bootstrap failed"
        echo "❌ Identity bootstrap failed. Set USER_TOKEN and retry."
        exit 1
    }
    exit 0
fi

# Read token and expiry from identity file
eval "$(python3 -c "
import json, sys
from datetime import datetime, timezone

try:
    with open('$IDENTITY_FILE') as f:
        data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print('TOKEN_STATUS=missing')
    sys.exit(0)

token = data.get('delegation_token', '')
expires_at = data.get('expires_at', '')
agent_id = data.get('agent_id', '')

if not token:
    print('TOKEN_STATUS=missing')
    sys.exit(0)

print(f'STORED_TOKEN={token}')
print(f'STORED_AGENT_ID={agent_id}')

if not expires_at:
    print('TOKEN_STATUS=unknown')
    sys.exit(0)

try:
    exp = datetime.fromisoformat(expires_at)
    now = datetime.now(timezone.utc)
    remaining = int((exp - now).total_seconds())
    print(f'TOKEN_REMAINING={remaining}')
    if remaining <= 0:
        print('TOKEN_STATUS=expired')
    elif remaining <= $REFRESH_THRESHOLD:
        print('TOKEN_STATUS=expiring_soon')
    else:
        print('TOKEN_STATUS=valid')
except:
    print('TOKEN_STATUS=unknown')
" 2>/dev/null)" || TOKEN_STATUS="error"

case "${TOKEN_STATUS:-error}" in
    valid)
        log "✅ Token valid ($TOKEN_REMAINING seconds remaining)"
        exit 0
        ;;
    expiring_soon)
        log "⚠️  Token expiring soon ($TOKEN_REMAINING seconds) — refreshing"
        ;;
    expired)
        log "⚠️  Token expired — refreshing"
        ;;
    missing)
        log "⚠️  No token found — bootstrapping"
        scripts/afk-identity.sh 2>/dev/null || {
            log "❌ Bootstrap failed"
            exit 1
        }
        exit 0
        ;;
    *)
        log "⚠️  Cannot determine token status — verifying with Control Plane"
        ;;
esac

# Verify against Control Plane before refreshing
if [ -n "${STORED_TOKEN:-}" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        "$CONTROL_URL/api/v1/auth/verify" \
        -H "Authorization: Bearer $STORED_TOKEN" \
        --connect-timeout 5 --max-time 10 2>/dev/null) || HTTP_CODE="000"

    case "$HTTP_CODE" in
        200)
            # Token still valid on server — only refresh if expiring soon
            if [ "${TOKEN_STATUS:-}" = "expiring_soon" ]; then
                log "Token valid on server but expiring soon — preemptive refresh"
            else
                log "✅ Token valid on Control Plane"
                exit 0
            fi
            ;;
        401|403)
            log "❌ Token revoked by Control Plane (HTTP $HTTP_CODE)"
            scripts/notify.sh "AFK Identity" "Token REVOKED for $DEEPSECURE_AGENT_ID — stopping" error 2>/dev/null || true
            echo "❌ Delegation token revoked. Agent execution blocked."
            echo "   Agent: $DEEPSECURE_AGENT_ID"
            echo "   Action: Contact administrator or re-bootstrap with new USER_TOKEN"
            exit 1
            ;;
        000)
            log "⚠️  Control Plane unreachable — using local expiry"
            if [ "${TOKEN_STATUS:-}" = "expired" ]; then
                log "❌ Token expired and cannot reach Control Plane"
                exit 1
            fi
            exit 0
            ;;
    esac
fi

# Attempt refresh
log "Refreshing delegation_token..."
if scripts/afk-identity.sh 2>/dev/null; then
    log "✅ Token refreshed successfully"
    exit 0
else
    log "❌ Token refresh failed"
    scripts/notify.sh "AFK Identity" "Token refresh FAILED for $DEEPSECURE_AGENT_ID" error 2>/dev/null || true
    exit 1
fi
