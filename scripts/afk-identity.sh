#!/usr/bin/env bash
# afk-identity.sh — Bootstrap AFK agent identity via DeepSecure delegation_tokens
# Usage: afk-identity.sh [--verify] [--revoke]
#
# Requests a scoped, ephemeral delegation_token from the DeepSecure Control Plane.
# The token has TTL, scoped permissions, and an audit trail. This replaces static
# API keys — dog-fooding DeepSecure's own identity controls for AFK agents.
set -euo pipefail

ACTION="${1:-bootstrap}"
IDENTITY_FILE="${AFK_IDENTITY_FILE:-.afk/identity.json}"
CONTROL_URL="${DEEPSECURE_CONTROL_URL:-http://localhost:8000}"
TTL_SECONDS="${AFK_TOKEN_TTL:-14400}"
LOG_FILE="${AFK_LOG_DIR:-.hermes}/identity.log"

log() {
    local msg="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [identity] $1"
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
    echo "$msg"
}

notify() {
    scripts/notify.sh "$1" "$2" "${3:-info}" 2>/dev/null || true
}

usage() {
    echo "Usage: afk-identity.sh [--verify|--revoke|--status]"
    echo ""
    echo "Bootstraps AFK agent identity via DeepSecure delegation_tokens."
    echo ""
    echo "Actions:"
    echo "  (default)   Bootstrap new delegation_token"
    echo "  --verify    Verify current token validity"
    echo "  --revoke    Revoke current token"
    echo "  --status    Show current identity status"
    echo ""
    echo "Environment variables:"
    echo "  DEEPSECURE_AGENT_ID     Agent identifier (required)"
    echo "  DEEPSECURE_CONTROL_URL  Control Plane URL (default: http://localhost:8000)"
    echo "  USER_TOKEN              User token for authentication (required for bootstrap)"
    echo "  AFK_TOKEN_TTL           Token TTL in seconds (default: 14400 = 4h)"
    echo "  AFK_TOKEN_PERMISSIONS   Comma-separated permissions (default: repo:read,repo:write,ci:trigger)"
    echo "  AFK_IDENTITY_FILE       Path to identity file (default: .afk/identity.json)"
    exit 0
}

validate_env() {
    local missing=0

    if [ -z "${DEEPSECURE_AGENT_ID:-}" ]; then
        log "❌ DEEPSECURE_AGENT_ID not set"
        missing=1
    fi

    if [ "$ACTION" = "bootstrap" ] && [ -z "${USER_TOKEN:-}" ]; then
        log "❌ USER_TOKEN not set (required for bootstrap)"
        missing=1
    fi

    if [ "$missing" -eq 1 ]; then
        echo ""
        echo "Required environment variables:"
        echo "  export DEEPSECURE_AGENT_ID=<agent-id>"
        echo "  export USER_TOKEN=<user-token>"
        echo "  export DEEPSECURE_CONTROL_URL=<url>  (optional, default: http://localhost:8000)"
        exit 1
    fi
}

bootstrap_token() {
    validate_env

    local permissions="${AFK_TOKEN_PERMISSIONS:-repo:read,repo:write,ci:trigger}"

    # Build permissions JSON array
    local perms_json
    perms_json=$(python3 -c "
import json, sys
perms = '$permissions'.split(',')
print(json.dumps([p.strip() for p in perms]))
" 2>/dev/null || echo '["repo:read","repo:write","ci:trigger"]')

    log "Requesting delegation_token for agent: $DEEPSECURE_AGENT_ID"
    log "  Control Plane: $CONTROL_URL"
    log "  TTL: ${TTL_SECONDS}s"
    log "  Permissions: $permissions"

    local response
    local http_code
    http_code=$(curl -s -o /tmp/afk-identity-response.json -w "%{http_code}" \
        -X POST "$CONTROL_URL/api/v1/auth/delegate" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"agent_id\": \"$DEEPSECURE_AGENT_ID\",
            \"permissions\": $perms_json,
            \"ttl_seconds\": $TTL_SECONDS
        }" 2>/dev/null) || http_code="000"

    response=$(cat /tmp/afk-identity-response.json 2>/dev/null || echo '{}')
    rm -f /tmp/afk-identity-response.json

    if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
        log "❌ Token request failed (HTTP $http_code)"
        log "  Response: $response"
        notify "AFK Identity" "Token bootstrap failed (HTTP $http_code)" error
        exit 1
    fi

    # Extract token from response
    local token
    token=$(echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('delegation_token', data.get('token', '')))
" 2>/dev/null || echo "")

    if [ -z "$token" ]; then
        log "❌ No delegation_token in response"
        log "  Response: $response"
        exit 1
    fi

    # Store identity state
    mkdir -p "$(dirname "$IDENTITY_FILE")"
    python3 -c "
import json, sys
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
expires = now + timedelta(seconds=$TTL_SECONDS)

identity = {
    'agent_id': '$DEEPSECURE_AGENT_ID',
    'delegation_token': '$token',
    'permissions': $perms_json,
    'ttl_seconds': $TTL_SECONDS,
    'issued_at': now.isoformat(),
    'expires_at': expires.isoformat(),
    'control_url': '$CONTROL_URL',
    'bootstrap_count': 1
}

# Increment bootstrap count if file exists
try:
    with open('$IDENTITY_FILE') as f:
        old = json.load(f)
    identity['bootstrap_count'] = old.get('bootstrap_count', 0) + 1
except (FileNotFoundError, json.JSONDecodeError):
    pass

with open('$IDENTITY_FILE', 'w') as f:
    json.dump(identity, f, indent=2)
" 2>/dev/null

    # Export for current session
    export DEEPSECURE_DELEGATION_TOKEN="$token"

    log "✅ Agent identity bootstrapped: $DEEPSECURE_AGENT_ID (TTL: $((TTL_SECONDS / 3600))h)"
    notify "AFK Identity" "Agent $DEEPSECURE_AGENT_ID bootstrapped (TTL: $((TTL_SECONDS / 3600))h)" success

    echo ""
    echo "✅ Delegation token obtained"
    echo "   Agent:   $DEEPSECURE_AGENT_ID"
    echo "   TTL:     $((TTL_SECONDS / 3600))h ($TTL_SECONDS seconds)"
    echo "   Perms:   $permissions"
    echo ""
    echo "To use in current shell:"
    echo "  export DEEPSECURE_DELEGATION_TOKEN=\"$token\""
}

verify_token() {
    if [ ! -f "$IDENTITY_FILE" ]; then
        log "❌ No identity file found: $IDENTITY_FILE"
        echo "No identity bootstrapped. Run: scripts/afk-identity.sh"
        exit 1
    fi

    local token
    token=$(python3 -c "
import json
with open('$IDENTITY_FILE') as f:
    print(json.load(f).get('delegation_token', ''))
" 2>/dev/null || echo "")

    if [ -z "$token" ]; then
        log "❌ No token in identity file"
        exit 1
    fi

    # Check expiry locally first
    local expired
    expired=$(python3 -c "
import json
from datetime import datetime, timezone

with open('$IDENTITY_FILE') as f:
    data = json.load(f)

expires_at = data.get('expires_at', '')
if not expires_at:
    print('unknown')
else:
    exp = datetime.fromisoformat(expires_at)
    now = datetime.now(timezone.utc)
    if now >= exp:
        print('expired')
    else:
        remaining = (exp - now).total_seconds()
        print(f'valid:{int(remaining)}')
" 2>/dev/null || echo "unknown")

    case "$expired" in
        expired)
            log "⚠️  Token expired locally"
            echo "❌ Token expired"
            exit 1
            ;;
        valid:*)
            local remaining=${expired#valid:}
            log "Token locally valid ($remaining seconds remaining)"
            ;;
    esac

    # Verify against Control Plane
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        "$CONTROL_URL/api/v1/auth/verify" \
        -H "Authorization: Bearer $token" 2>/dev/null) || http_code="000"

    if [ "$http_code" = "200" ]; then
        log "✅ Token verified by Control Plane"
        echo "✅ Token valid (${expired#valid:}s remaining)"
        exit 0
    elif [ "$http_code" = "401" ] || [ "$http_code" = "403" ]; then
        log "❌ Token rejected by Control Plane (HTTP $http_code)"
        echo "❌ Token revoked or expired (HTTP $http_code)"
        exit 1
    elif [ "$http_code" = "000" ]; then
        log "⚠️  Control Plane unreachable — using local expiry check"
        echo "⚠️  Control Plane unreachable — local check: $expired"
        # If locally valid, don't fail — allow offline operation
        [[ "$expired" == valid:* ]] && exit 0 || exit 1
    else
        log "⚠️  Unexpected verify response: HTTP $http_code"
        echo "⚠️  Verify returned HTTP $http_code"
        exit 1
    fi
}

revoke_token() {
    if [ ! -f "$IDENTITY_FILE" ]; then
        echo "No identity to revoke"
        exit 0
    fi

    local token agent_id
    token=$(python3 -c "import json; print(json.load(open('$IDENTITY_FILE')).get('delegation_token',''))" 2>/dev/null || echo "")
    agent_id=$(python3 -c "import json; print(json.load(open('$IDENTITY_FILE')).get('agent_id',''))" 2>/dev/null || echo "unknown")

    if [ -n "$token" ]; then
        local http_code
        http_code=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST "$CONTROL_URL/api/v1/auth/revoke" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json" 2>/dev/null) || http_code="000"

        if [ "$http_code" = "200" ] || [ "$http_code" = "204" ]; then
            log "✅ Token revoked for agent: $agent_id"
        else
            log "⚠️  Revoke request returned HTTP $http_code (token may already be expired)"
        fi
    fi

    rm -f "$IDENTITY_FILE"
    unset DEEPSECURE_DELEGATION_TOKEN 2>/dev/null || true

    log "Identity file removed: $IDENTITY_FILE"
    notify "AFK Identity" "Agent $agent_id identity revoked" warning
    echo "✅ Identity revoked and cleaned up"
}

show_status() {
    echo "=== AFK Identity Status ==="
    echo ""

    if [ ! -f "$IDENTITY_FILE" ]; then
        echo "Status:   Not bootstrapped"
        echo "File:     $IDENTITY_FILE (not found)"
        echo ""
        echo "Bootstrap with: scripts/afk-identity.sh"
        exit 0
    fi

    python3 -c "
import json
from datetime import datetime, timezone

with open('$IDENTITY_FILE') as f:
    data = json.load(f)

agent_id = data.get('agent_id', 'unknown')
issued = data.get('issued_at', 'unknown')
expires = data.get('expires_at', 'unknown')
perms = ', '.join(data.get('permissions', []))
count = data.get('bootstrap_count', 0)
token = data.get('delegation_token', '')

# Calculate remaining
try:
    exp = datetime.fromisoformat(expires)
    now = datetime.now(timezone.utc)
    if now >= exp:
        remaining = '❌ EXPIRED'
    else:
        secs = int((exp - now).total_seconds())
        hours = secs // 3600
        mins = (secs % 3600) // 60
        remaining = f'✅ {hours}h {mins}m remaining'
except:
    remaining = '? unknown'

print(f'Agent ID:     {agent_id}')
print(f'Status:       {remaining}')
print(f'Issued:       {issued}')
print(f'Expires:      {expires}')
print(f'Permissions:  {perms}')
print(f'Bootstraps:   {count}')
print(f'Token:        {token[:20]}...{token[-10:]}' if len(token) > 30 else f'Token:        {token}')
print(f'Identity:     $IDENTITY_FILE')
" 2>/dev/null || echo "Error reading identity file"
}

# Parse action
case "${1:-}" in
    --help|-h) usage ;;
    --verify)  ACTION="verify" ;;
    --revoke)  ACTION="revoke" ;;
    --status)  ACTION="status" ;;
    "")        ACTION="bootstrap" ;;
    *)
        echo "Unknown option: $1"
        usage
        ;;
esac

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

case "$ACTION" in
    bootstrap) bootstrap_token ;;
    verify)    verify_token ;;
    revoke)    revoke_token ;;
    status)    show_status ;;
esac
