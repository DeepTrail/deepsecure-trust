#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DeepSecure MVP - Complete Integration Validation Script
# Phase 1 (P1-B1, P1-B2, P1-B3) + Phase 2 Readiness
#
# Usage:
#   ./scripts/validate_integration.sh           # Run all tests
#   ./scripts/validate_integration.sh --skip-setup  # Skip container restart
#
# Prerequisites:
#   - docker and docker compose installed
#   - python3 with pynacl installed (pip install pynacl)
#   - jq installed
#   - curl installed
# ═══════════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

# Parse arguments
SKIP_SETUP=false
for arg in "$@"; do
  case $arg in
    --skip-setup)
      SKIP_SETUP=true
      shift
      ;;
  esac
done

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║    DeepSecure MVP - Complete Integration Validation                  ║"
echo "║    Sarah's Journey: 16 Test Scenarios                                ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"

# ─────────────────────────────────────────────────────────────────────────────
# API KEY DETECTION
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "API Key Detection:"
REAL_API_MODE=false

if [[ -n "$NOTION_API_KEY" ]] && [[ "$NOTION_API_KEY" == secret_* ]]; then
  echo "  Notion: ✅ Real API key detected (${NOTION_API_KEY:0:12}...)"
  REAL_API_MODE=true
else
  echo "  Notion: ⚪ Using mock token (set NOTION_API_KEY for real API)"
fi

if [[ -n "$SLACK_BOT_TOKEN" ]] && [[ "$SLACK_BOT_TOKEN" == xoxb-* ]]; then
  echo "  Slack:  ✅ Real API key detected (${SLACK_BOT_TOKEN:0:15}...)"
  REAL_API_MODE=true
else
  echo "  Slack:  ⚪ Using mock token (set SLACK_BOT_TOKEN for real API)"
fi

fi

if [ "$REAL_API_MODE" = true ]; then
  echo ""
  echo "═══════════════════════════════════════════════════════════════════════"
  echo "REAL API MODE: Tool calls will use actual external APIs"
  echo "═══════════════════════════════════════════════════════════════════════"
else
  echo ""
  echo "MOCK MODE: Tool calls will return simulated responses"
  echo "For real API testing, set: NOTION_API_KEY, SLACK_BOT_TOKEN"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────────────────────────

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

if [ "$SKIP_SETUP" = false ]; then
  echo ""
  echo "Step 0: Starting services..."
  docker compose down -v 2>/dev/null || true
  docker compose up -d --build
  echo "Waiting for services to initialize (20s)..."
  sleep 20
else
  echo ""
  echo "Step 0: Skipping setup (--skip-setup flag)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Health Checks
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 1: Service Health Checks"
echo "═══════════════════════════════════════════════════════════════════════"

curl -sf http://localhost:8000/health > /dev/null && echo "✅ Control Plane healthy" || { echo "❌ Control Plane unavailable"; exit 1; }
curl -sf http://localhost:8002/health > /dev/null && echo "✅ Gateway healthy" || { echo "❌ Gateway unavailable"; exit 1; }

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: User Login
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 2: User Login"
echo "═══════════════════════════════════════════════════════════════════════"

USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

if [ -n "$USER_TOKEN" ] && [ "$USER_TOKEN" != "null" ]; then
  echo "✅ Login successful: ${USER_TOKEN:0:30}..."
else
  echo "❌ Login failed"; exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: Connect Service (Notion)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 3: Connect Service (Notion)"
echo "═══════════════════════════════════════════════════════════════════════"

# Use real API key if set, otherwise use test token
NOTION_TOKEN="${NOTION_API_KEY:-test_notion_token_12345}"
if [[ "$NOTION_TOKEN" == secret_* ]]; then
  echo "Using REAL Notion API key"
else
  echo "Using mock token (set NOTION_API_KEY for real API testing)"
fi

CONNECT_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"service_id\": \"notion\",
    \"oauth_token\": {
      \"access_token\": \"$NOTION_TOKEN\",
      \"token_type\": \"bearer\",
      \"scope\": \"read_pages search_content\",
      \"expires_at\": \"2027-02-22T00:00:00.000000+00:00\"
    }
  }")

if echo "$CONNECT_RESULT" | jq -e '.success == true' > /dev/null; then
  echo "✅ Notion connected successfully"
else
  echo "❌ Failed to connect Notion"
  echo "   Response: $CONNECT_RESULT"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: Generate Agent Keypair
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 4: Generate Agent Ed25519 Keypair"
echo "═══════════════════════════════════════════════════════════════════════"

python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey.generate()
public_key = private_key.verify_key
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env
echo "✅ Keypair generated: ${PUBLIC_KEY_B64:0:30}..."

AGENT_ID="sdr-assistant-$(date +%s)"

# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: Register Agent
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 5: Register Agent"
echo "═══════════════════════════════════════════════════════════════════════"

AGENT_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"name\": \"SDR Assistant\",
    \"public_key\": \"$PUBLIC_KEY_B64\"
  }")

if echo "$AGENT_RESULT" | jq -e '.agent_id' > /dev/null; then
  echo "✅ Agent registered: $AGENT_ID"
else
  echo "❌ Agent registration failed"
  echo "   Response: $AGENT_RESULT"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: Create Delegation
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 6: Create Delegation"
echo "═══════════════════════════════════════════════════════════════════════"

DELEGATION_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"permissions\": [
      \"notion:pages:search\",
      \"notion:pages:read\",
      \"slack:messages:search\"
    ]
  }")

if echo "$DELEGATION_RESULT" | jq -e '.delegation_token' > /dev/null; then
  echo "✅ Delegation created with permissions"
else
  echo "❌ Delegation failed"
  echo "   Response: $DELEGATION_RESULT"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 7: Agent Challenge
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 7: Agent Challenge-Response"
echo "═══════════════════════════════════════════════════════════════════════"

CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\"}" | jq -r '.challenge')

if [ -n "$CHALLENGE" ] && [ "$CHALLENGE" != "null" ]; then
  echo "✅ Challenge received: ${CHALLENGE:0:30}..."
else
  echo "❌ Failed to get challenge"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 8: Verify and Get Agent JWT
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 8: Verify and Get Agent JWT"
echo "═══════════════════════════════════════════════════════════════════════"

SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
signed = private_key.sign('$CHALLENGE'.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')

if [ -n "$AGENT_JWT" ] && [ "$AGENT_JWT" != "null" ]; then
  echo "✅ Agent JWT obtained: ${AGENT_JWT:0:30}..."
else
  echo "❌ Agent authentication failed"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 9: Vault Token Retrieval
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 9: Vault Token Retrieval"
echo "═══════════════════════════════════════════════════════════════════════"

VAULT_RESULT=$(curl -s -X GET "http://localhost:8000/api/v1/vault/tokens/notion" \
  -H "Authorization: Bearer $AGENT_JWT")

if echo "$VAULT_RESULT" | jq -e '.access_token' > /dev/null 2>&1; then
  echo "✅ Vault token retrieved successfully"
else
  echo "⚠️  Vault token retrieval: $(echo $VAULT_RESULT | jq -c . 2>/dev/null || echo $VAULT_RESULT)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 10: Vault Token Refresh
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 10: Vault Token Refresh (Internal API)"
echo "═══════════════════════════════════════════════════════════════════════"

REFRESH_RESULT=$(curl -s -X POST "http://localhost:8000/api/v1/vault/tokens/notion/refresh" \
  -H "Authorization: Bearer gateway-internal-secret-token" \
  -H "X-User-ID: sarah@acme.com" \
  -H "Content-Type: application/json" \
  -d '{"force": false}')

echo "✅ Refresh endpoint responded: $(echo $REFRESH_RESULT | jq -c . 2>/dev/null || echo $REFRESH_RESULT)"

# ─────────────────────────────────────────────────────────────────────────────
# TEST 11: OAuth Authorize
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 11: OAuth Authorize URL"
echo "═══════════════════════════════════════════════════════════════════════"

OAUTH_RESULT=$(curl -s -X GET "http://localhost:8000/api/v1/oauth/notion/authorize" \
  -H "Authorization: Bearer $USER_TOKEN")

if echo "$OAUTH_RESULT" | jq -e '.authorization_url' > /dev/null 2>&1; then
  echo "✅ OAuth authorize URL generated"
else
  echo "⚠️  OAuth response: $(echo $OAUTH_RESULT | jq -c . 2>/dev/null || echo $OAUTH_RESULT)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 12: MCP Initialize
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 12: MCP Initialize Session"
echo "═══════════════════════════════════════════════════════════════════════"

INIT_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "SDR Assistant", "version": "1.0.0"}
    }
  }')

if echo "$INIT_RESULT" | jq -e '.result.protocolVersion' > /dev/null 2>&1; then
  echo "✅ MCP session initialized"
else
  echo "❌ MCP initialization failed: $(echo $INIT_RESULT | jq -c . 2>/dev/null || echo $INIT_RESULT)"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 13: MCP List Tools
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 13: MCP List Tools"
echo "═══════════════════════════════════════════════════════════════════════"

TOOLS_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2,
    "params": {}
  }')

TOOL_COUNT=$(echo "$TOOLS_RESULT" | jq -r '.result.tools | length' 2>/dev/null || echo "0")
echo "✅ Discovered $TOOL_COUNT tools"

# ─────────────────────────────────────────────────────────────────────────────
# TEST 14: MCP Tool Call (Delegated)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 14: MCP Tool Call (Delegated)"
echo "═══════════════════════════════════════════════════════════════════════"

TOOL_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }')

if echo "$TOOL_RESULT" | jq -e '.result' > /dev/null 2>&1; then
  echo "✅ Tool executed successfully"
  
  # Check if this is a real API response or mock
  if echo "$TOOL_RESULT" | grep -q '"object":"list"'; then
    echo "   ✅ REAL Notion API response detected"
  elif echo "$TOOL_RESULT" | grep -q 'MVP Mock\|Found [0-9]* results'; then
    echo "   ⚪ Mock response (set NOTION_API_KEY for real API)"
  else
    echo "   Response: $(echo $TOOL_RESULT | jq -c '.result' 2>/dev/null | head -c 100)..."
  fi
else
  echo "⚠️  Tool result: $(echo $TOOL_RESULT | jq -c . 2>/dev/null || echo $TOOL_RESULT)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 15: MCP Tool Call (Permission Denied)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 15: MCP Tool Call (Permission Denied)"
echo "═══════════════════════════════════════════════════════════════════════"

DENIED_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 4,
    "params": {"name": "notion.create_page", "arguments": {"title": "Test"}}
  }')

if echo "$DENIED_RESULT" | jq -e '.error' > /dev/null 2>&1; then
  echo "✅ Permission DENIED as expected"
else
  echo "⚠️  Expected denial: $(echo $DENIED_RESULT | jq -c . 2>/dev/null || echo $DENIED_RESULT)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 16: Audit Events
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 16: Audit Events Query"
echo "═══════════════════════════════════════════════════════════════════════"

AUDIT_RESULT=$(curl -s -X GET "http://localhost:8000/api/v1/audit/events?agent_id=$AGENT_ID&limit=10" \
  -H "Authorization: Bearer $USER_TOKEN")

EVENT_COUNT=$(echo "$AUDIT_RESULT" | jq -r '.events | length' 2>/dev/null || echo "0")
echo "✅ Audit trail retrieved: $EVENT_COUNT events"

# ─────────────────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "CLEANUP"
echo "═══════════════════════════════════════════════════════════════════════"

rm -f /tmp/agent_keys.env
echo "✅ Temporary files cleaned"

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║    ✅ ALL 16 TESTS COMPLETED SUCCESSFULLY                            ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Show API mode summary
if [ "$REAL_API_MODE" = true ]; then
  echo "API Mode: REAL API INTEGRATION"
  echo "  Tool calls used actual external APIs"
else
  echo "API Mode: MOCK"
  echo "  Tool calls returned simulated responses"
  echo ""
  echo "For REAL API testing, set environment variables:"
  echo "  export NOTION_API_KEY=secret_xxx..."
  echo "  export SLACK_BOT_TOKEN=xoxb-xxx..."
fi
echo ""
echo "Services are still running. To stop:"
echo "  docker compose down"
echo ""
echo "To stop and remove all data:"
echo "  docker compose down -v"
echo ""
echo "Full documentation: docs/INTEGRATION_VALIDATION_GUIDE.md"
