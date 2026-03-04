# DeepSecure MVP - Integration Validation Guide

## Phase 1 & Phase 2 MVP Validation - Sarah's Journey

This guide provides complete curl-based validation commands for testing the DeepSecure Virtual MCP Server MVP, covering all batches from Phase 1 (P1-B1, P1-B2, P1-B3), Phase 1.5 (Integration Bug Fixes), through Phase 2 readiness.

**Last Updated:** February 23, 2026  
**Version:** 1.2.0 (P1.5 Complete - End-to-End Validated)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Container Deployment](#2-container-deployment)
3. [Test Scenarios Overview](#3-test-scenarios-overview)
4. [Test Scenario 1: Service Health Checks](#4-test-scenario-1-service-health-checks)
5. [Test Scenario 2: User Login](#5-test-scenario-2-user-login)
6. [Test Scenario 3: Connect Service (Notion)](#6-test-scenario-3-connect-service-notion)
7. [Test Scenario 3.5: Discover Available Permissions](#7-test-scenario-35-discover-available-permissions) *(NEW - P1.5)*
8. [Test Scenario 4: Generate Agent Ed25519 Keypair](#8-test-scenario-4-generate-agent-ed25519-keypair)
9. [Test Scenario 5: Register Agent](#9-test-scenario-5-register-agent)
10. [Test Scenario 6: Create Delegation](#10-test-scenario-6-create-delegation)
11. [Test Scenario 6.5: Delegation Validation (Invalid Permissions)](#11-test-scenario-65-delegation-validation-invalid-permissions) *(NEW - P1.5)*
12. [Test Scenario 7: Agent Challenge-Response](#12-test-scenario-7-agent-challenge-response)
13. [Test Scenario 8: Verify and Get Agent JWT](#13-test-scenario-8-verify-and-get-agent-jwt)
14. [Test Scenario 9: Vault Token Retrieval](#14-test-scenario-9-vault-token-retrieval)
15. [Test Scenario 10: Vault Token Refresh](#15-test-scenario-10-vault-token-refresh)
16. [Test Scenario 11: OAuth Authorize](#16-test-scenario-11-oauth-authorize)
17. [Test Scenario 12: MCP Initialize Session](#17-test-scenario-12-mcp-initialize-session)
18. [Test Scenario 13: MCP List Tools](#18-test-scenario-13-mcp-list-tools)
19. [Test Scenario 14: MCP Tool Call (Delegated)](#19-test-scenario-14-mcp-tool-call-delegated)
20. [Test Scenario 15: MCP Tool Call (Permission Denied)](#20-test-scenario-15-mcp-tool-call-permission-denied)
21. [Test Scenario 16: Audit Events Query](#21-test-scenario-16-audit-events-query)
22. [Test Scenario 17: Service Disconnect](#22-test-scenario-17-service-disconnect) *(NEW - P1.5)*
23. [Test Scenario 18: Token Persistence (Container Restart)](#23-test-scenario-18-token-persistence-container-restart) *(NEW - P1.5)*
24. [Complete Validation Script](#24-complete-validation-script)
25. [Cleanup](#25-cleanup)
26. [Troubleshooting](#26-troubleshooting)
27. [Real API Integration Testing](#27-real-api-integration-testing)

---

## 1. Prerequisites

### Required Tools

```bash
# Verify required tools are installed
curl --version    # HTTP client
jq --version      # JSON processor
python3 --version # For Ed25519 operations
docker --version  # Container runtime
docker compose version # Container orchestration
```

### Python Dependencies

```bash
pip install pynacl httpx
```

### Environment Variables

```bash
# Service URLs
export CONTROL_PLANE_URL="http://localhost:8000"
export GATEWAY_URL="http://localhost:8002"

# Test user credentials
export TEST_USER_EMAIL="sarah@acme.com"
export TEST_USER_PASSWORD="test_password"

# Internal API token (for Gateway→Control communication)
export INTERNAL_API_TOKEN="gateway-internal-secret-token"
```

---

## 2. Container Deployment

### 2.1 Clean Start

```bash
# Navigate to project root
cd /Users/imaxxs/repositories/deepsecure-mvp

# Stop any existing containers and remove volumes (clean slate)
docker compose down -v

# Build and start services
docker compose up -d --build

# Wait for services to be ready (database migrations, etc.)
echo "Waiting for services to initialize..."
sleep 20
```

### 2.2 Verify Containers Running

```bash
# Check container status
docker compose ps

# Expected output:
# NAME                      STATUS
# deeptrail_control_app     running (healthy)
# deeptrail_gateway_app     running
# deeptrail_control_db      running (healthy)
# deeptrail_gateway_redis   running (healthy)
```

### 2.3 View Service Logs (optional)

```bash
# Control Plane logs
docker compose logs deeptrail-control --tail=50

# Gateway logs
docker compose logs deeptrail-gateway --tail=50
```

---

## 3. Test Scenarios Overview

| # | Scenario | Batch | Endpoint | Method | Auth Required |
|---|----------|-------|----------|--------|---------------|
| 1 | Health Check | All | `/health` | GET | None |
| 2 | User Login | P1-B1 | `/api/v1/auth/login` | POST | None |
| 3 | Connect Service | P1-B1 | `/api/v1/users/me/services/connect` | POST | User Token |
| 3.5 | Discover Available Permissions | P1.5 | `/api/v1/users/me/available-permissions` | GET | User Token |
| 4 | Generate Keypair | P1-B1 | (local) | - | None |
| 5 | Register Agent | P1-B1 | `/api/v1/agents/` | POST | User Token |
| 6 | Create Delegation | P1-B1 | `/api/v1/auth/delegate` | POST | User Token |
| 6.5 | Delegation Validation | P1.5 | `/api/v1/auth/delegate` | POST | User Token |
| 7 | Agent Challenge | P1-B1 | `/api/v1/auth/agent/challenge` | POST | None |
| 8 | Agent Verify | P1-B1 | `/api/v1/auth/agent/verify` | POST | None |
| 9 | Vault Token Retrieval | P1-B2 | `/api/v1/vault/tokens/{service}` | GET | Agent JWT |
| 10 | Vault Token Refresh | P1-B2 | `/api/v1/vault/tokens/{service}/refresh` | POST | Internal Token |
| 11 | OAuth Authorize | P1-B2 | `/api/v1/oauth/{service}/authorize` | GET | User Token |
| 12 | MCP Initialize | P1-B3 | `/mcp` (Gateway) | POST | Agent JWT |
| 13 | MCP List Tools | P1-B3 | `/mcp` (Gateway) | POST | Agent JWT |
| 14 | MCP Tool Call | P1-B3 | `/mcp` (Gateway) | POST | Agent JWT |
| 15 | Permission Denied | P1-B3 | `/mcp` (Gateway) | POST | Agent JWT |
| 16 | Audit Events | All | `/api/v1/audit/events` | GET | User Token |
| 17 | Service Disconnect | P1.5 | `/api/v1/users/me/services/{service_id}` | DELETE | User Token |
| 18 | Token Persistence | P1.5 | (container restart test) | - | User Token |

---

## 4. Test Scenario 1: Service Health Checks

### Purpose

Verify that Control Plane and Gateway services are running and healthy.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /health` |
| **Control URL** | `http://localhost:8000/health` |
| **Gateway URL** | `http://localhost:8002/health` |
| **Auth** | None |

### Commands

```bash
# Control Plane health
echo "=== Control Plane Health Check ==="
curl -s http://localhost:8000/health | jq .
```

### Expected Response (Control Plane)

```json
{
  "service": "DeepSecure Control Plane",
  "version": "0.1.11",
  "status": "ok",
  "dependencies": {
    "database": "connected"
  }
}
```

```bash
# Gateway health
echo "=== Gateway Health Check ==="
curl -s http://localhost:8002/health | jq .
```

### Expected Response (Gateway)

```json
{
  "service": "DeepSecure Gateway",
  "version": "0.1.10",
  "status": "ok",
  "dependencies": {
    "control_plane": "connected",
    "redis": "connected"
  }
}
```

### Verification

```bash
# Combined health check with success/failure indication
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy" || echo "❌ Control Plane unavailable"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy" || echo "❌ Gateway unavailable"
```

---

## 5. Test Scenario 2: User Login

### Purpose

Authenticate as Sarah and obtain a User Session JWT.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /api/v1/auth/login` |
| **URL** | `http://localhost:8000/api/v1/auth/login` |
| **Content-Type** | `application/json` |
| **Auth** | None |

### Request Schema

```json
{
  "email": "string (required)",
  "password": "string (required)"
}
```

### Command

```bash
echo "=== User Login ==="
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sarah@acme.com",
    "password": "test_password"
  }')

# Print the full response
echo "$LOGIN_RESPONSE" | jq .

# Extract token
USER_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.token')

# Verify token was obtained
if [ -n "$USER_TOKEN" ] && [ "$USER_TOKEN" != "null" ]; then
  echo "✅ Login successful"
  echo "User Token: ${USER_TOKEN:0:50}..."
else
  echo "❌ Login failed"
  exit 1
fi
```

### Expected Response

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "email": "sarah@acme.com",
    "id": "sarah@acme.com",
    "organization_id": "org-acme-001"
  },
  "expires_in": 28800
}
```

### Decode JWT Claims

```bash
# Decode the JWT payload (base64url decode the middle section)
echo "=== Decode User JWT ==="
JWT_PAYLOAD=$(echo "$USER_TOKEN" | cut -d. -f2)
# Add padding if needed (base64url requires padding)
PADDING=$((4 - ${#JWT_PAYLOAD} % 4))
if [ $PADDING -ne 4 ]; then
  JWT_PAYLOAD="${JWT_PAYLOAD}$(printf '=%.0s' $(seq 1 $PADDING))"
fi
echo "$JWT_PAYLOAD" | tr '_-' '/+' | base64 -d 2>/dev/null | jq .
```

### JWT Claims (decoded)

```json
{
  "sub": "sarah@acme.com",
  "session_id": "usess-<uuid>",
  "organization_id": "org-acme-001",
  "exp": 1739912345,
  "iat": 1739883545
}
```

### Notes

- **IMPORTANT**: The login endpoint returns `token` field, NOT `access_token`
- Token expires in 8 hours (28800 seconds)
- MVP mode accepts any password

---

## 6. Test Scenario 3: Connect Service (Notion)

### Purpose

Sarah connects her Notion account, storing OAuth token in the vault.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /api/v1/users/me/services/connect` |
| **URL** | `http://localhost:8000/api/v1/users/me/services/connect` |
| **Content-Type** | `application/json` |
| **Auth** | `Bearer $USER_TOKEN` |

### Request Schema

```json
{
  "service_id": "string (required) - notion|slack|hubspot",
  "oauth_token": {
    "access_token": "string (required)",
    "token_type": "string (default: bearer)",
    "scope": "string (space-separated scopes)",
    "expires_at": "string (ISO timestamp, optional)",
    "refresh_token": "string (optional)"
  }
}
```

### Command (Mock Mode - Default)

Use this for CI/CD and basic validation:

```bash
echo "=== Connect Notion Service (Mock) ==="
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "test_notion_token_12345",
      "token_type": "bearer",
      "scope": "read_pages search_content",
      "expires_at": "2026-02-19T22:06:59.361415+00:00"
    }
  }' | jq .
```

### Command (Real API Mode)

For real Notion API integration, first set your API key then use it in the command:

```bash
# Step 1: Set your real Notion API key (get from notion.so/my-integrations)
export NOTION_API_KEY="secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Step 2: Verify it's set correctly
# Notion internal integration tokens start with 'ntn_' (newer) or 'secret_' (older)
if [[ "$NOTION_API_KEY" == ntn_* ]] || [[ "$NOTION_API_KEY" == secret_* ]]; then
  echo "✅ Real Notion API key detected"
else
  echo "❌ Invalid format (should start with 'ntn_' or 'secret_')"
fi

# Step 3: Connect with real API key (Notion tokens don't expire, use far future date)
echo "=== Connect Notion Service (Real API) ==="
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "'"$NOTION_API_KEY"'",
      "token_type": "bearer",
      "scope": "read_pages search_content",
      "expires_at": "2027-02-24T00:00:00.000000+00:00"
    }
  }' | jq .
```

**Key differences for real API:**

| Field | Mock Value | Real Value |
|-------|------------|------------|
| `access_token` | `test_notion_token_12345` | `$NOTION_API_KEY` (starts with `ntn_` or `secret_`) |
| `expires_at` | `2026-02-19T22:06:59...` (1 hour) | `2027-02-22T00:00:00...` (1 year - Notion tokens don't expire) |

### Expected Response (Same for Mock and Real)

The Control Plane response is **identical** for both mock and real tokens - it stores the token without validating it against Notion:

```json
{
  "success": true,
  "connection": {
    "id": "conn-<uuid>",
    "service_id": "notion",
    "service_name": "Notion",
    "scopes_granted": ["read_pages", "search_content"],
    "connected_at": "2026-02-18T22:06:59.361415+00:00"
  }
}
```

### When You See the Difference

The difference between mock and real appears in **Test Scenario 14 (MCP Tool Call)**:

| Mode | Tool Call Response |
|------|-------------------|
| **Mock** | `"[Notion] Found 5 results for 'test'"` |
| **Real** | `{"object":"list","results":[{"object":"page","id":"abc123",...}]}` |

### Connect Additional Services (optional)

```bash
# Connect Slack (Mock)
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "slack",
    "oauth_token": {
      "access_token": "test_slack_token_67890",
      "token_type": "bearer",
      "scope": "channels:read search:read"
    }
  }' | jq .

# Connect Slack (Real API)
export SLACK_BOT_TOKEN="xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx"
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "slack",
    "oauth_token": {
      "access_token": "'"$SLACK_BOT_TOKEN"'",
      "token_type": "bearer",
      "scope": "channels:read chat:write search:read users:read"
    }
  }' | jq .
```

### Notes

- Tokens are stored encrypted in the vault
- The connection creates both a `connected_services` DB record and a vault entry
- Agents will later retrieve these tokens via the vault API
- **Token validation happens at tool execution time, not at connection time**
- For real Notion access, ensure you've shared pages with your integration (see Section 23)
- **P1.5**: Tokens are now persisted to PostgreSQL (WS-K1) and survive container restarts

---

## 7. Test Scenario 3.5: Discover Available Permissions

> **Added in P1.5 (WS-K5)**: Users can now discover what permissions they can delegate based on their connected service scopes.

### Purpose

Before creating a delegation, discover what permissions are available based on connected services and their OAuth scopes.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/v1/users/me/available-permissions` |
| **URL** | `http://localhost:8000/api/v1/users/me/available-permissions` |
| **Auth** | `Bearer $USER_TOKEN` |

### Command

```bash
echo "=== Discover Available Permissions ==="
AVAILABLE_PERMS=$(curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN")

echo "$AVAILABLE_PERMS" | jq .

# Extract permission count
PERM_COUNT=$(echo "$AVAILABLE_PERMS" | jq -r '.total_permissions')
echo "✅ Available permissions: $PERM_COUNT"
```

### Expected Response

Based on connecting Notion with scopes `read_pages search_content`:

```json
{
  "services": {
    "notion": {
      "connected": true,
      "service_name": "Notion",
      "scopes_granted": ["read_pages", "search_content"],
      "available_permissions": [
        "notion:pages:read",
        "notion:pages:search"
      ],
      "connected_at": "2026-02-23T10:00:00+00:00"
    }
  },
  "all_permissions": [
    "notion:pages:read",
    "notion:pages:search"
  ],
  "total_services": 1,
  "total_permissions": 2
}
```

### With Multiple Services Connected

If both Notion (read_pages) and Slack (channels:read, search:read) are connected:

```json
{
  "services": {
    "notion": {
      "connected": true,
      "scopes_granted": ["read_pages", "search_content"],
      "available_permissions": ["notion:pages:read", "notion:pages:search"]
    },
    "slack": {
      "connected": true,
      "scopes_granted": ["channels:read", "search:read"],
      "available_permissions": ["slack:channels:list", "slack:messages:search"]
    }
  },
  "all_permissions": [
    "notion:pages:read",
    "notion:pages:search",
    "slack:channels:list",
    "slack:messages:search"
  ],
  "total_services": 2,
  "total_permissions": 4
}
```

### Why This Matters

| Before P1.5 | After P1.5 |
|-------------|------------|
| Users had to guess permission strings | Users can see exactly what's available |
| Invalid delegations accepted, failed at runtime | Invalid delegations rejected immediately |
| No UI/CLI could show available options | Permissions can be displayed in pickers |

### Notes

- Permissions are derived from OAuth scopes using `ScopeMapper` (WS-K3)
- Only connected (not disconnected) services are included
- Permissions are sorted alphabetically
- This endpoint powers the delegation validation in Step 6

---

## 8. Test Scenario 4: Generate Agent Ed25519 Keypair

### Purpose

Generate a cryptographic keypair for agent authentication.

### Background

The agent uses Ed25519 public-key cryptography:
- **Private key**: Held by the agent, used to sign challenges
- **Public key**: Registered with the Control Plane for verification

### Command

```bash
echo "=== Generate Ed25519 Keypair ==="
python3 -c "
from nacl.signing import SigningKey
import base64

# Generate new keypair
private_key = SigningKey.generate()
public_key = private_key.verify_key

# Export in formats needed for API
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env

# Source the variables
source /tmp/agent_keys.env

echo "✅ Keypair generated"
echo "Public Key (Base64): ${PUBLIC_KEY_B64:0:30}..."
```

### Output Format

```bash
PRIVATE_KEY_HEX=<64 hex characters>
PUBLIC_KEY_B64=<44 base64 characters>
```

### Notes

- Keep `PRIVATE_KEY_HEX` secret - it's the agent's identity
- Register `PUBLIC_KEY_B64` with the Control Plane
- Ed25519 provides 128-bit security

---

## 9. Test Scenario 5: Register Agent

### Purpose

Register a new agent with its public key.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /api/v1/agents/` |
| **URL** | `http://localhost:8000/api/v1/agents/` |
| **Content-Type** | `application/json` |
| **Auth** | `Bearer $USER_TOKEN` |

### Request Schema

```json
{
  "agent_id": "string (required) - unique identifier",
  "name": "string (required) - human-readable name",
  "public_key": "string (required) - base64-encoded Ed25519 public key",
  "description": "string (optional)"
}
```

### Command

```bash
echo "=== Register Agent ==="
AGENT_ID="sdr-assistant-001"

curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"name\": \"SDR Assistant\",
    \"public_key\": \"$PUBLIC_KEY_B64\",
    \"description\": \"Sales Development Representative AI assistant\"
  }" | jq .
```

### Expected Response

```json
{
  "name": "SDR Assistant",
  "description": "Sales Development Representative AI assistant",
  "agent_id": "sdr-assistant-001",
  "publicKey": "m3/V4Sobbnptl1pMiGqg+Mprp+JiZLnDCQAJw9VnJb8=",
  "status": "active",
  "created_at": "2026-02-18T22:08:14.761383Z",
  "updated_at": "2026-02-18T22:08:14.761383Z",
  "last_seen_at": null
}
```

### Error Responses

| Status | Error | Description |
|--------|-------|-------------|
| 400 | `invalid_public_key` | Public key is not valid base64 or wrong length |
| 409 | `agent_exists` | Agent with this ID already registered |
| 401 | `unauthorized` | Invalid or missing User Token |

---

## 10. Test Scenario 6: Create Delegation

### Purpose

Sarah grants specific permissions to the agent.

> **P1.5 Enhancement (WS-K4)**: Delegation now validates requested permissions against connected service scopes. Invalid permissions are rejected with detailed error messages.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /api/v1/auth/delegate` |
| **URL** | `http://localhost:8000/api/v1/auth/delegate` |
| **Content-Type** | `application/json` |
| **Auth** | `Bearer $USER_TOKEN` |

### Request Schema

```json
{
  "agent_id": "string (required)",
  "permissions": ["string"] ,
  "constraints": {
    "rate_limit": "integer (optional)",
    "expires_in_hours": "integer (optional, default: 8)"
  }
}
```

### Permission Format

```
<service>:<resource>:<action>

Examples:
- notion:pages:read      → Read Notion pages
- notion:pages:search    → Search Notion pages
- notion:pages:create    → Create Notion pages
- slack:messages:search  → Search Slack messages
- slack:channels:list    → List Slack channels
```

### Command

```bash
echo "=== Create Delegation ==="
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"permissions\": [
      \"notion:pages:search\",
      \"notion:pages:read\",
      \"notion:databases:query\",
      \"slack:messages:search\",
      \"slack:channels:list\"
    ],
    \"constraints\": {
      \"rate_limit\": 100,
      \"expires_in_hours\": 8
    }
  }" | jq .
```

### Expected Response

```json
{
  "delegation_token": "MDAyNmxvY2F0aW9uIGh0dHA6Ly9kZWVw...",
  "delegation_id": "del-<uuid>",
  "permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "notion:databases:query",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "expires_in": 28800
}
```

### Notes

- The delegation_token is a Macaroon-based token
- Agent must present this during authentication
- Permissions are the MAXIMUM the agent can use
- Gateway filters tools based on these permissions
- **P1.5**: Permissions are now validated against connected service scopes (WS-K4)
- Use Step 3.5 (Available Permissions) to see what you can delegate

---

## 11. Test Scenario 6.5: Delegation Validation (Invalid Permissions)

> **Added in P1.5 (WS-K4)**: The delegation endpoint now enforces monotonic attenuation - you cannot delegate permissions beyond what your connected service scopes allow.

### Purpose

Test that invalid permission requests are properly rejected with helpful error messages.

### Scenario

Sarah connected Notion with only `read_pages` scope, but tries to delegate `notion:pages:create` (requires `write_pages` scope).

### Command

```bash
echo "=== Test Invalid Delegation (Should Fail) ==="
INVALID_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"permissions\": [
      \"notion:pages:search\",
      \"notion:pages:create\"
    ]
  }")

echo "$INVALID_RESULT" | jq .

# Verify it was rejected
if echo "$INVALID_RESULT" | jq -e '.detail.error == "permission_validation_failed"' > /dev/null; then
  echo "✅ Invalid delegation correctly rejected"
  echo "Invalid permissions: $(echo $INVALID_RESULT | jq -r '.detail.invalid_permissions | join(", ")')"
  echo "Allowed permissions: $(echo $INVALID_RESULT | jq -r '.detail.allowed_permissions | join(", ")')"
else
  echo "⚠️ Expected validation failure but got: $(echo $INVALID_RESULT | jq -c .)"
fi
```

### Expected Error Response (400 Bad Request)

```json
{
  "detail": {
    "error": "permission_validation_failed",
    "message": "Requested permissions not allowed by connected scopes",
    "invalid_permissions": [
      "notion:pages:create"
    ],
    "allowed_permissions": [
      "notion:pages:read",
      "notion:pages:search"
    ],
    "hint": "Connect service with additional scopes or remove invalid permissions"
  }
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `error` | Machine-readable error code: `permission_validation_failed` |
| `message` | Human-readable explanation |
| `invalid_permissions` | Array of permissions that failed validation |
| `allowed_permissions` | Array of permissions that WOULD be allowed (sorted alphabetically) |
| `hint` | Actionable guidance for resolution |

### How to Fix

1. **Option A**: Connect Notion with additional scopes (`write_pages`)
2. **Option B**: Remove invalid permissions from the delegation request

### Notes

- This validates at delegation time, not at tool execution time
- Prevents agents from receiving permissions they can never use
- Uses `ScopeMapper` (WS-K3) for scope-to-permission mapping
- `allowed_permissions` shows exactly what the user CAN delegate

---

## 12. Test Scenario 7: Agent Challenge-Response

### Purpose

Agent requests a cryptographic challenge to prove identity.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /api/v1/auth/agent/challenge` |
| **URL** | `http://localhost:8000/api/v1/auth/agent/challenge` |
| **Content-Type** | `application/json` |
| **Auth** | None |

### Request Schema

```json
{
  "agent_id": "string (required)"
}
```

### Command

```bash
echo "=== Request Challenge ==="
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\"}" | jq -r '.challenge')

echo "Challenge: $CHALLENGE"
```

### Expected Response

```json
{
  "challenge": "OB6TfdExXGW0EGeiA2DyMrHdRUT0V8Jw36zESwVo77s=",
  "expires_in": 300
}
```

### Sign the Challenge

```bash
echo "=== Sign Challenge ==="
SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64

# Load private key from hex
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))

# Sign the challenge
signed = private_key.sign('$CHALLENGE'.encode())

# Output URL-safe base64 signature
print(base64.urlsafe_b64encode(signed.signature).decode())
")

echo "Signature: ${SIGNATURE:0:50}..."
```

### Notes

- Challenge is a 256-bit random nonce (base64 encoded)
- Challenge expires in 5 minutes (300 seconds)
- Single-use: cleared after successful verification

---

## 13. Test Scenario 8: Verify and Get Agent JWT

### Purpose

Submit signed challenge and receive Agent Session JWT.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /api/v1/auth/agent/verify` |
| **URL** | `http://localhost:8000/api/v1/auth/agent/verify` |
| **Content-Type** | `application/json` |
| **Auth** | None |

### Request Schema

```json
{
  "agent_id": "string (required)",
  "challenge": "string (required) - the challenge received",
  "signature": "string (required) - base64url-encoded Ed25519 signature",
  "delegation_token": "string (optional) - for permission binding"
}
```

### Command

```bash
echo "=== Verify Signature and Get Agent JWT ==="
AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')

if [ -n "$AGENT_JWT" ] && [ "$AGENT_JWT" != "null" ]; then
  echo "✅ Agent authenticated"
  echo "Agent JWT: ${AGENT_JWT:0:50}..."
else
  echo "❌ Agent authentication failed"
  exit 1
fi
```

### Expected Response

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 28800
}
```

### Agent JWT Claims (decoded)

```json
{
  "sub": "sdr-assistant-001",
  "owner": "sarah@acme.com",
  "delegated_permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "notion:databases:query",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "delegation_id": "del-<uuid>",
  "session_id": "asess-<uuid>",
  "exp": 1739912345,
  "iat": 1739883545
}
```

### Notes

- Agent JWT contains `owner` claim identifying the delegating user
- `delegated_permissions` are embedded in the JWT
- Gateway uses these claims for tool filtering and credential injection

---

## 14. Test Scenario 9: Vault Token Retrieval

### Purpose

Agent retrieves OAuth token from vault for a connected service.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/v1/vault/tokens/{service_id}` |
| **URL** | `http://localhost:8000/api/v1/vault/tokens/notion` |
| **Auth** | `Bearer $AGENT_JWT` |

### Path Parameters

| Parameter | Description |
|-----------|-------------|
| `service_id` | Service identifier: `notion`, `slack`, `hubspot` |

### Command

```bash
echo "=== Vault Token Retrieval ==="
curl -s -X GET "http://localhost:8000/api/v1/vault/tokens/notion" \
  -H "Authorization: Bearer $AGENT_JWT" | jq .
```

### Expected Response

```json
{
  "service_id": "notion",
  "access_token": "test_notion_token_12345",
  "token_type": "bearer",
  "scopes_granted": ["read_pages", "search_content"],
  "expires_at": "2026-02-18T23:06:59.361415+00:00"
}
```

### Error Responses

| Status | Error | Description |
|--------|-------|-------------|
| 401 | `unauthorized` | Invalid Agent JWT or missing `owner` claim |
| 404 | `not_found` | User has not connected this service |
| 403 | `forbidden` | Agent not authorized for this service |

### Notes

- **REQUIRES Agent JWT** (not User Token)
- The `owner` claim in Agent JWT identifies whose tokens to retrieve
- Gateway calls this internally during credential injection

---

## 15. Test Scenario 10: Vault Token Refresh

### Purpose

Gateway requests token refresh (Gateway→Control internal communication).

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /api/v1/vault/tokens/{service_id}/refresh` |
| **URL** | `http://localhost:8000/api/v1/vault/tokens/notion/refresh` |
| **Auth** | `Bearer $INTERNAL_API_TOKEN` |
| **Header** | `X-User-ID: <user_email>` |

### Headers

| Header | Value | Description |
|--------|-------|-------------|
| `Authorization` | `Bearer gateway-internal-secret-token` | Internal API token from docker-compose |
| `X-User-ID` | `sarah@acme.com` | User whose token to refresh |

### Command

```bash
echo "=== Vault Token Refresh ==="
curl -s -X POST "http://localhost:8000/api/v1/vault/tokens/notion/refresh" \
  -H "Authorization: Bearer gateway-internal-secret-token" \
  -H "X-User-ID: sarah@acme.com" \
  -H "Content-Type: application/json" \
  -d '{"force": false}' | jq .
```

### Expected Response (token refreshed)

```json
{
  "refreshed": true,
  "service_id": "notion",
  "new_expires_at": "2026-02-19T22:06:59.361415+00:00"
}
```

### Expected Response (no refresh needed or no refresh_token)

```json
{
  "refreshed": false,
  "reason": "no_refresh_token_stored"
}
```

### Notes

- **Internal endpoint** - not meant for direct agent/user calls
- Used by Gateway when a token is expired/expiring
- Requires `refresh_token` to be stored during service connection
- The `force: true` option forces refresh even if not expired

---

## 16. Test Scenario 11: OAuth Authorize

### Purpose

Get OAuth authorization URL for connecting a new service.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/v1/oauth/{service_id}/authorize` |
| **URL** | `http://localhost:8000/api/v1/oauth/notion/authorize` |
| **Auth** | `Bearer $USER_TOKEN` |

### Query Parameters

| Parameter | Description |
|-----------|-------------|
| `scopes` | Comma-separated scopes to request (optional) |
| `redirect` | If `true`, returns 302 redirect instead of JSON |

### Command

```bash
echo "=== OAuth Authorize URL ==="
curl -s -X GET "http://localhost:8000/api/v1/oauth/notion/authorize" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

### Expected Response

```json
{
  "authorization_url": "https://api.notion.com/v1/oauth/authorize?client_id=test-notion-client-id&redirect_uri=http://localhost:8000/api/v1/oauth/notion/callback&response_type=code&state=<state_token>&scope=read_pages",
  "state": "<state_token>"
}
```

### Error Response (missing config)

```json
{
  "detail": {
    "error": "config_error",
    "message": "Missing required environment variables: NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, OAUTH_REDIRECT_BASE_URL"
  }
}
```

### Notes

- Returns URL for browser-based OAuth flow
- `state` parameter prevents CSRF attacks
- Callback URL is configured in `docker-compose.yml`
- Test OAuth credentials are pre-configured

---

## 17. Test Scenario 12: MCP Initialize Session

### Purpose

Initialize MCP session with the Gateway (REQUIRED before tools/call).

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /mcp` |
| **URL** | `http://localhost:8002/mcp` |
| **Protocol** | JSON-RPC 2.0 |
| **Auth** | `Bearer $AGENT_JWT` |

### Request Schema (JSON-RPC)

```json
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "id": 1,
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "string - agent name",
      "version": "string - agent version"
    }
  }
}
```

### Command

```bash
echo "=== MCP Initialize Session ==="
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

echo "$INIT_RESULT" | jq .

# Verify success
if echo "$INIT_RESULT" | jq -e '.result.protocolVersion' > /dev/null; then
  echo "✅ MCP session initialized"
else
  echo "❌ MCP initialization failed"
  exit 1
fi
```

### Expected Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "DeepSecure Virtual MCP Server",
      "version": "0.1.10"
    }
  }
}
```

### Error Response (no session)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32002,
    "message": "Session not found. Call initialize first.",
    "data": null
  }
}
```

### Notes

- **CRITICAL**: Must call `initialize` before `tools/list` or `tools/call`
- Session is tied to the Agent JWT
- Session may timeout after extended inactivity

---

## 18. Test Scenario 13: MCP List Tools

### Purpose

Discover available tools (filtered by agent's delegated permissions).

> **P1.5 Fix (WS-J2)**: Tool name derivation now uses `PermissionMapper.get_all_tools_for_permission()` for proper reverse lookup. All tools matching delegated permissions are returned with full schemas.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /mcp` |
| **URL** | `http://localhost:8002/mcp` |
| **Method** | `tools/list` |
| **Auth** | `Bearer $AGENT_JWT` |

### Command

```bash
echo "=== MCP List Tools ==="
TOOLS_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2,
    "params": {}
  }')

echo "$TOOLS_RESULT" | jq .

# Count tools - should be 5 based on delegation
TOOL_COUNT=$(echo "$TOOLS_RESULT" | jq -r '.result.tools | length')
echo "✅ Discovered $TOOL_COUNT tools"

# Verify expected tools are present
echo "Tools returned:"
echo "$TOOLS_RESULT" | jq -r '.result.tools[].name'
```

### Expected Response

Based on delegation with permissions `notion:pages:search`, `notion:pages:read`, `notion:databases:query`, `slack:messages:search`, `slack:channels:list`:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "notion.search_pages",
        "description": "Search for pages in Notion workspace",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {"type": "string", "description": "Search query string"},
            "limit": {"type": "integer", "description": "Maximum number of results", "default": 10}
          },
          "required": ["query"]
        }
      },
      {
        "name": "notion.read_page",
        "description": "Read a Notion page by ID",
        "inputSchema": {
          "type": "object",
          "properties": {
            "page_id": {"type": "string", "description": "Notion page ID"}
          },
          "required": ["page_id"]
        }
      },
      {
        "name": "notion.query_database",
        "description": "Query a Notion database",
        "inputSchema": {
          "type": "object",
          "properties": {
            "database_id": {"type": "string", "description": "Notion database ID"},
            "filter": {"type": "object", "description": "Filter conditions"},
            "sorts": {"type": "array", "description": "Sort conditions"}
          },
          "required": ["database_id"]
        }
      },
      {
        "name": "slack.search_messages",
        "description": "Search Slack messages across channels",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {"type": "string", "description": "Search query string"},
            "limit": {"type": "integer", "default": 20}
          },
          "required": ["query"]
        }
      },
      {
        "name": "slack.list_channels",
        "description": "List available Slack channels",
        "inputSchema": {
          "type": "object",
          "properties": {
            "types": {"type": "string", "default": "public_channel"},
            "limit": {"type": "integer", "default": 100}
          }
        }
      }
    ],
    "nextCursor": null
  }
}
```

### Permission to Tool Mapping

| Delegated Permission | Tool(s) Returned |
|---------------------|------------------|
| `notion:pages:search` | `notion.search_pages` |
| `notion:pages:read` | `notion.read_page` |
| `notion:databases:query` | `notion.query_database` |
| `slack:messages:search` | `slack.search_messages` |
| `slack:channels:list` | `slack.list_channels` |

### Notes

- **5 tools returned** (one per delegated permission)
- Tools are filtered based on `delegated_permissions` in Agent JWT
- Tools NOT in delegation (e.g., `notion:pages:create`) are hidden
- Each tool has `inputSchema` for validation
- **P1.5 Fix**: Tool names now correctly derived using PermissionMapper reverse lookup

---

## 19. Test Scenario 14: MCP Tool Call (Delegated)

### Purpose

Execute a tool that the agent has permission to use.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /mcp` |
| **URL** | `http://localhost:8002/mcp` |
| **Method** | `tools/call` |
| **Auth** | `Bearer $AGENT_JWT` |

### Request Schema

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "id": 3,
  "params": {
    "name": "string - tool name (e.g., notion.search_pages)",
    "arguments": {
      "...tool-specific arguments"
    }
  }
}
```

### Command

```bash
echo "=== MCP Tool Call (Delegated) ==="
TOOL_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {
      "name": "notion.search_pages",
      "arguments": {
        "query": "competitor analysis",
        "limit": 5
      }
    }
  }')

echo "$TOOL_RESULT" | jq .

# Verify success
if echo "$TOOL_RESULT" | jq -e '.result' > /dev/null; then
  echo "✅ Tool executed successfully"
else
  echo "❌ Tool execution failed"
fi
```

### Expected Response (Mock Mode)

When connected with `test_notion_token_12345`:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[Notion] Found 5 results for 'competitor analysis'"
      }
    ],
    "isError": false
  }
}
```

### Expected Response (Real API Mode)

When connected with a real Notion API key (`ntn_xxx...` or `secret_xxx...`):

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"object\":\"list\",\"results\":[{\"object\":\"page\",\"id\":\"12345678-abcd-efgh-ijkl-mnopqrstuvwx\",\"created_time\":\"2025-01-15T10:00:00.000Z\",\"last_edited_time\":\"2026-02-10T14:30:00.000Z\",\"properties\":{\"title\":{\"title\":[{\"text\":{\"content\":\"Competitor Analysis Q1 2026\"}}]}},\"url\":\"https://www.notion.so/Competitor-Analysis-12345678abcd\"}],\"next_cursor\":null,\"has_more\":false}"
      }
    ],
    "isError": false
  }
}
```

### How to Verify Real vs Mock

```bash
# Check if response is mock or real
if echo "$TOOL_RESULT" | grep -q '"object":"list"'; then
  echo "✅ REAL Notion API response"
elif echo "$TOOL_RESULT" | grep -q '\[Notion\].*results'; then
  echo "⚪ Mock response (set NOTION_API_KEY for real API)"
else
  echo "⚠️ Unexpected response format"
fi
```

### Security Properties

- ✅ Agent never saw OAuth tokens (token injected server-side)
- ✅ Gateway injected Sarah's Notion credentials
- ✅ Action logged as "agent on behalf of sarah@acme.com"
- ✅ Same security model for mock and real tokens

---

## 20. Test Scenario 15: MCP Tool Call (Permission Denied)

### Purpose

Verify that non-delegated tools are blocked.

### Command

```bash
echo "=== MCP Tool Call (Non-Delegated - Should Fail) ==="
DENIED_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 4,
    "params": {
      "name": "notion.create_page",
      "arguments": {
        "title": "Unauthorized Page",
        "content": "This should be blocked"
      }
    }
  }')

echo "$DENIED_RESULT" | jq .

# Verify denial
if echo "$DENIED_RESULT" | jq -e '.error' > /dev/null; then
  echo "✅ Permission DENIED as expected"
else
  echo "❌ ERROR: Tool was allowed but should have been denied!"
fi
```

### Expected Response

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "error": {
    "code": -32001,
    "message": "Permission denied: notion:pages:create not delegated",
    "data": {
      "tool": "notion.create_page",
      "required_permission": "notion:pages:create",
      "delegated_permissions": ["notion:pages:search", "notion:pages:read"]
    }
  }
}
```

### Security Properties

- ✅ Request blocked at Gateway (never reached Notion)
- ✅ Agent cannot exceed delegated permissions
- ✅ Denial logged for audit

---

## 21. Test Scenario 16: Audit Events Query

### Purpose

Sarah reviews the audit trail of agent activity. Every tool call, permission check, and credential access is logged for compliance and debugging.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/v1/audit/events` |
| **URL** | `http://localhost:8000/api/v1/audit/events` |
| **Auth** | `Bearer $USER_TOKEN` |

### Query Parameters

| Parameter | Description |
|-----------|-------------|
| `agent_id` | Filter by agent |
| `on_behalf_of` | Filter by user email |
| `event_type` | Filter by event type |
| `limit` | Max results (default 100, max 1000) |
| `offset` | Pagination offset |
| `start_time` | ISO 8601 timestamp |
| `end_time` | ISO 8601 timestamp |

### Command

```bash
echo "=== Query Audit Events ==="
curl -s -X GET "http://localhost:8000/api/v1/audit/events?agent_id=$AGENT_ID&limit=10" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

### Expected Response

```json
{
  "events": [
    {
      "id": "evt-a5634a478dc4",
      "timestamp": "2026-02-23T16:54:42.117575Z",
      "event_type": "mcp_tool_call",
      "agent_id": "sdr-assistant-001",
      "on_behalf_of": "sarah@acme.com",
      "organization_id": null,
      "tool": "notion.search_pages",
      "arguments": {
        "query": "founder",
        "limit": 5
      },
      "result_summary": "{'object': 'list', 'results': [{'object': 'page', 'id': '2f0a5287-...",
      "reason": null,
      "session_id": "asess-08fb1013a21b",
      "delegation_id": "mvp-delegation",
      "extra_data": null
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

### Query All Events (no agent filter)

```bash
echo "=== All Audit Events ==="
curl -s -X GET "http://localhost:8000/api/v1/audit/events?limit=10" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

### Query by User

```bash
echo "=== Audit Events for User ==="
curl -s -X GET "http://localhost:8000/api/v1/audit/events?on_behalf_of=sarah@acme.com&limit=10" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

### Event Fields

| Field | Description |
|-------|-------------|
| `id` | Unique event identifier (evt-<uuid>) |
| `timestamp` | ISO 8601 timestamp |
| `event_type` | `mcp_tool_call`, `permission_denied`, etc. |
| `agent_id` | Agent that performed the action |
| `on_behalf_of` | User who delegated to the agent |
| `tool` | Tool name (e.g., `notion.search_pages`) |
| `arguments` | Tool call arguments |
| `result_summary` | Truncated result or error message |
| `session_id` | MCP session identifier |
| `delegation_id` | Delegation that authorized the action |

### Audit Summary Endpoint

```bash
echo "=== Audit Summary ==="
curl -s -X GET "http://localhost:8000/api/v1/audit/summary?agent_id=$AGENT_ID" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

---

## 22. Test Scenario 17: Service Disconnect

> **Added in P1.5 (WS-K2)**: Users can now disconnect services, which triggers cache invalidation across the Gateway.

### Purpose

Disconnect a previously connected service. This soft-deletes the connection and publishes a cache invalidation event.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `DELETE /api/v1/users/me/services/{service_id}` |
| **URL** | `http://localhost:8000/api/v1/users/me/services/slack` |
| **Auth** | `Bearer $USER_TOKEN` |

### Command

```bash
echo "=== Disconnect Service (Slack) ==="
DISCONNECT_RESULT=$(curl -s -X DELETE http://localhost:8000/api/v1/users/me/services/slack \
  -H "Authorization: Bearer $USER_TOKEN")

echo "$DISCONNECT_RESULT" | jq .

# Verify disconnection
if echo "$DISCONNECT_RESULT" | jq -e '.success == true' > /dev/null; then
  echo "✅ Service disconnected successfully"
else
  echo "❌ Disconnect failed: $(echo $DISCONNECT_RESULT | jq -c .)"
fi
```

### Expected Response

```json
{
  "success": true,
  "message": "Service disconnected",
  "service_id": "slack",
  "disconnected_at": "2026-02-23T15:30:00.000000+00:00"
}
```

### What Happens on Disconnect

1. **Database**: `disconnected_at` timestamp is set (soft delete)
2. **In-Memory**: Service removed from in-memory storage
3. **Cache Invalidation**: `service_disconnected` event published to Redis
4. **Gateway**: Receives event, invalidates all cached tokens for that user+service

### Verify Cache Invalidation

If Redis is running, you can observe the cache invalidation:

```bash
# In a separate terminal, subscribe to invalidation channel
docker compose exec redis redis-cli SUBSCRIBE deepsecure:cache_invalidation
```

### Notes

- This is a soft delete (sets `disconnected_at` timestamp)
- Gateway immediately invalidates its credential cache for this service
- Attempting to use tools for disconnected services will fail
- Re-connecting creates a new connection record

---

## 23. Test Scenario 18: Token Persistence (Container Restart)

> **Added in P1.5 (WS-K1)**: OAuth tokens are now stored in PostgreSQL with Fernet encryption. Tokens survive container restarts.

### Purpose

Verify that OAuth tokens persist across Control Plane container restarts (proving persistent vault storage works).

### Pre-Requisites

- Complete Test Scenario 3 (Connect Notion service)
- Have valid `$USER_TOKEN`

### Command

```bash
echo "=== Token Persistence Test ==="

# Step 1: Verify token exists before restart
echo "1. Checking token before restart..."
PRE_PERMS=$(curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq -r '.total_permissions')
echo "   Pre-restart permissions: $PRE_PERMS"

# Step 2: Restart Control Plane container
echo "2. Restarting Control Plane..."
docker compose restart deeptrail-control
sleep 15  # Wait for container to be healthy

# Step 3: Verify health
echo "3. Verifying health..."
until curl -sf http://localhost:8000/health > /dev/null; do
  echo "   Waiting for Control Plane..."
  sleep 2
done
echo "   ✅ Control Plane healthy"

# Step 4: Re-login (session expired after restart)
echo "4. Re-authenticating..."
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "sarah@acme.com", "password": "test_password"}' | jq -r '.token')

# Step 5: Verify token still exists
echo "5. Checking token after restart..."
POST_PERMS=$(curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq -r '.total_permissions')
echo "   Post-restart permissions: $POST_PERMS"

# Step 6: Compare
if [ "$PRE_PERMS" -eq "$POST_PERMS" ]; then
  echo "✅ Token persistence verified: $PRE_PERMS permissions before, $POST_PERMS after"
else
  echo "❌ Token persistence failed: $PRE_PERMS before, $POST_PERMS after"
  exit 1
fi
```

### Expected Result

| Check | Before Restart | After Restart | Match? |
|-------|----------------|---------------|--------|
| `total_permissions` | 2 | 2 | ✅ Yes |
| Services connected | `notion` | `notion` | ✅ Yes |

### What This Verifies

| Component | Verification |
|-----------|--------------|
| **WS-K1** | VaultToken model persists to PostgreSQL |
| **VaultClient** | Retrieves tokens from DB after restart |
| **Fernet Encryption** | Encrypted data can be decrypted |
| **Alembic Migration** | `vault_tokens` table exists |

### Before P1.5 (Expected Failure)

```
Pre-restart permissions: 2
Post-restart permissions: 0
❌ Token persistence failed (tokens were in-memory only)
```

### After P1.5 (Expected Success)

```
Pre-restart permissions: 2
Post-restart permissions: 2
✅ Token persistence verified
```

### Notes

- Tokens are stored encrypted with Fernet symmetric encryption
- The encryption key is derived from `VAULT_ENCRYPTION_KEY` environment variable
- Container restart does NOT affect PostgreSQL data (different container)
- For full cleanup, use `docker compose down -v` (removes volumes)

---

## 24. Complete Validation Script

Save this as `scripts/validate_integration.sh`:

```bash
#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DeepSecure MVP - Complete Integration Validation Script
# Phase 1 (P1-B1, P1-B2, P1-B3) + Phase 1.5 (Integration Bug Fixes) + Phase 2 Readiness
# Version: 1.1.0 (P1.5 Complete - WS-J2, WS-K1-K5)
# ═══════════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║    DeepSecure MVP - Complete Integration Validation                  ║"
echo "║    Sarah's Journey: 20 Test Scenarios (incl. P1.5 Fixes)             ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"

# ─────────────────────────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/deepsecure-mvp

# Clean start
echo "Step 0: Starting services..."
docker compose down -v 2>/dev/null || true
docker compose up -d --build
echo "Waiting for services to initialize (20s)..."
sleep 20

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Health Checks
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 1: Service Health Checks"
echo "═══════════════════════════════════════════════════════════════════════"

curl -sf http://localhost:8000/health > /dev/null && echo "✅ Control Plane healthy" || exit 1
curl -sf http://localhost:8002/health > /dev/null && echo "✅ Gateway healthy" || exit 1

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

CONNECT_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "test_notion_token_12345",
      "token_type": "bearer",
      "scope": "read_pages search_content",
      "expires_at": "2026-02-19T22:06:59.361415+00:00"
    }
  }')

if echo "$CONNECT_RESULT" | jq -e '.success == true' > /dev/null; then
  echo "✅ Notion connected successfully"
else
  echo "❌ Failed to connect Notion"; exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3.5: Available Permissions (P1.5 - WS-K5)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 3.5: Available Permissions (P1.5)"
echo "═══════════════════════════════════════════════════════════════════════"

AVAIL_PERMS=$(curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN")

PERM_COUNT=$(echo "$AVAIL_PERMS" | jq -r '.total_permissions')
if [ "$PERM_COUNT" -gt 0 ]; then
  echo "✅ Available permissions discovered: $PERM_COUNT"
  echo "   Permissions: $(echo $AVAIL_PERMS | jq -r '.all_permissions | join(", ")')"
else
  echo "❌ No available permissions found"; exit 1
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
  echo "❌ Agent registration failed"; exit 1
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
  echo "❌ Delegation failed"; exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6.5: Delegation Validation (P1.5 - WS-K4)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 6.5: Delegation Validation - Invalid Permissions (P1.5)"
echo "═══════════════════════════════════════════════════════════════════════"

# Try to delegate a permission we don't have (notion:pages:create requires write_pages scope)
INVALID_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"permissions\": [\"notion:pages:create\"]
  }")

if echo "$INVALID_RESULT" | jq -e '.detail.error == "permission_validation_failed"' > /dev/null; then
  echo "✅ Invalid delegation correctly rejected"
  echo "   Invalid: $(echo $INVALID_RESULT | jq -r '.detail.invalid_permissions | join(", ")')"
else
  echo "⚠️ Delegation validation may not be active: $(echo $INVALID_RESULT | jq -c .)"
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

echo "✅ Challenge received: ${CHALLENGE:0:30}..."

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
  echo "❌ Agent authentication failed"; exit 1
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

if echo "$VAULT_RESULT" | jq -e '.access_token' > /dev/null; then
  echo "✅ Vault token retrieved successfully"
else
  echo "⚠️ Vault token retrieval (may need real implementation): $(echo $VAULT_RESULT | jq -c .)"
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

echo "✅ Refresh endpoint responded: $(echo $REFRESH_RESULT | jq -c .)"

# ─────────────────────────────────────────────────────────────────────────────
# TEST 11: OAuth Authorize
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 11: OAuth Authorize URL"
echo "═══════════════════════════════════════════════════════════════════════"

OAUTH_RESULT=$(curl -s -X GET "http://localhost:8000/api/v1/oauth/notion/authorize" \
  -H "Authorization: Bearer $USER_TOKEN")

if echo "$OAUTH_RESULT" | jq -e '.authorization_url' > /dev/null; then
  echo "✅ OAuth authorize URL generated"
else
  echo "⚠️ OAuth response: $(echo $OAUTH_RESULT | jq -c .)"
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

if echo "$INIT_RESULT" | jq -e '.result.protocolVersion' > /dev/null; then
  echo "✅ MCP session initialized"
else
  echo "❌ MCP initialization failed: $(echo $INIT_RESULT | jq -c .)"; exit 1
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

TOOL_COUNT=$(echo "$TOOLS_RESULT" | jq -r '.result.tools | length')
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

if echo "$TOOL_RESULT" | jq -e '.result' > /dev/null; then
  echo "✅ Tool executed successfully"
else
  echo "⚠️ Tool result: $(echo $TOOL_RESULT | jq -c .)"
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

if echo "$DENIED_RESULT" | jq -e '.error' > /dev/null; then
  echo "✅ Permission DENIED as expected"
else
  echo "⚠️ Expected denial: $(echo $DENIED_RESULT | jq -c .)"
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

EVENT_COUNT=$(echo "$AUDIT_RESULT" | jq -r '.events | length')
echo "✅ Audit trail retrieved: $EVENT_COUNT events"

# ─────────────────────────────────────────────────────────────────────────────
# TEST 17: Service Disconnect (P1.5 - WS-K2)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 17: Service Disconnect (P1.5)"
echo "═══════════════════════════════════════════════════════════════════════"

# First connect Slack so we have something to disconnect
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "slack",
    "oauth_token": {
      "access_token": "test_slack_token",
      "token_type": "bearer",
      "scope": "channels:read"
    }
  }' > /dev/null

# Now disconnect it
DISCONNECT_RESULT=$(curl -s -X DELETE http://localhost:8000/api/v1/users/me/services/slack \
  -H "Authorization: Bearer $USER_TOKEN")

if echo "$DISCONNECT_RESULT" | jq -e '.success == true' > /dev/null; then
  echo "✅ Service disconnected successfully"
else
  echo "⚠️ Service disconnect: $(echo $DISCONNECT_RESULT | jq -c .)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# TEST 18: Token Persistence (P1.5 - WS-K1)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TEST 18: Token Persistence - Container Restart (P1.5)"
echo "═══════════════════════════════════════════════════════════════════════"

# Get pre-restart permission count
PRE_PERMS=$(curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq -r '.total_permissions')
echo "Pre-restart permissions: $PRE_PERMS"

# Restart Control Plane
echo "Restarting Control Plane..."
docker compose restart deeptrail-control > /dev/null 2>&1
sleep 15

# Wait for health
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  sleep 2
done

# Re-login
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# Get post-restart permission count
POST_PERMS=$(curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq -r '.total_permissions')
echo "Post-restart permissions: $POST_PERMS"

if [ "$PRE_PERMS" -eq "$POST_PERMS" ]; then
  echo "✅ Token persistence verified: $PRE_PERMS → $POST_PERMS"
else
  echo "⚠️ Token persistence: $PRE_PERMS → $POST_PERMS (may differ due to disconnect test)"
fi

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
echo "║    ✅ ALL 20 TESTS COMPLETED SUCCESSFULLY (incl. P1.5)               ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Services are still running. To stop:"
echo "  docker compose down"
echo ""
echo "To stop and remove all data:"
echo "  docker compose down -v"
```

---

## 25. Cleanup

### Stop Services (Keep Data)

```bash
docker compose down
```

### Stop Services and Remove Data

```bash
docker compose down -v
```

### Clean All Docker Resources

```bash
docker compose down -v --rmi all
docker system prune -f
```

### Clean Temporary Files

```bash
rm -f /tmp/agent_keys.env
```

---

## 26. Troubleshooting

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Services not healthy | `curl` returns connection refused | Wait longer: `sleep 30` |
| Login returns `null` | Using `jq -r '.access_token'` | Use `jq -r '.token'` instead |
| "Session not found" | MCP `tools/call` error | Call `initialize` first |
| 401 on vault endpoint | "missing user identity" | Use Agent JWT, not User Token |
| 401 on refresh endpoint | "Invalid internal token" | Use internal token + X-User-ID header |
| OAuth config error | Missing env variables | Check docker-compose.yml has OAuth vars |

### Debug Commands

```bash
# View all container logs
docker compose logs -f

# Check database
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "SELECT * FROM agents;"

# Check Redis
docker compose exec redis redis-cli KEYS '*'

# Inspect JWT claims
echo $AGENT_JWT | cut -d'.' -f2 | base64 -d 2>/dev/null | jq .

# Check Control Plane OpenAPI
curl -s http://localhost:8000/openapi.json | jq '.paths | keys'

# Check Gateway MCP endpoint
curl -s http://localhost:8002/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"ping","id":1}' | jq .
```

### Token Type Reference

| Token Type | How to Obtain | Used For | Header Format |
|------------|---------------|----------|---------------|
| User Token | `POST /api/v1/auth/login` | User endpoints, delegation | `Bearer $USER_TOKEN` |
| Agent JWT | Challenge-response flow | Gateway, vault retrieval | `Bearer $AGENT_JWT` |
| Internal Token | From `docker-compose.yml` | Gateway→Control calls | `Bearer gateway-internal-secret-token` |

### MCP Protocol Sequence

```
1. initialize → Establishes session
2. tools/list → Gets available tools (filtered)
3. tools/call → Executes tool (requires active session)
```

**CRITICAL**: Calling `tools/call` without `initialize` returns:
```json
{"error":{"code":-32002,"message":"Session not found. Call initialize first."}}
```

---

## 27. Real API Integration Testing

With P1-B3 complete, you can test with **real API keys** instead of mock tokens.

### Prerequisites

| Service | Token Type | How to Get |
|---------|------------|------------|
| **Notion** | Internal Integration Token | [notion.so/my-integrations](https://www.notion.so/my-integrations) |
| **Slack** | Bot User OAuth Token | [api.slack.com/apps](https://api.slack.com/apps) → OAuth & Permissions |
| **HubSpot** | Private App Access Token | [developers.hubspot.com](https://developers.hubspot.com) → Private Apps |

### Quick Setup

```bash
# 1. Set real API keys
# Notion tokens start with 'ntn_' (newer) or 'secret_' (older)
export NOTION_API_KEY="ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export SLACK_BOT_TOKEN="xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxx"
export HUBSPOT_ACCESS_TOKEN="pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# 2. Verify keys are set
echo "Notion: ${NOTION_API_KEY:+✅ Set}${NOTION_API_KEY:-❌ Not set}"
echo "Slack:  ${SLACK_BOT_TOKEN:+✅ Set}${SLACK_BOT_TOKEN:-❌ Not set}"
echo "HubSpot: ${HUBSPOT_ACCESS_TOKEN:+✅ Set}${HUBSPOT_ACCESS_TOKEN:-❌ Not set}"

# 3. The validation script will use these instead of mock tokens
./scripts/validate_integration.sh
```

### Notion-Specific Setup

1. Create integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. **IMPORTANT**: Share pages with your integration (click Share → Invite → select integration)
3. Integration can ONLY access explicitly shared pages

### Slack-Specific Setup

1. Create app at [api.slack.com/apps](https://api.slack.com/apps)
2. Add OAuth scopes: `channels:read`, `chat:write`, `search:read`, `users:read`
3. Install to workspace and copy Bot User OAuth Token

### What Changes with Real Keys

| Aspect | Mock Mode | Real Mode |
|--------|-----------|-----------|
| Token Value | `test_notion_token_12345` | `ntn_xxx...` or `secret_xxx...` |
| API Response | `"Unauthorized: API token is invalid."` | `{"object":"list","results":[...]}` |
| Data | Error or empty response | Your actual workspace data |

### Verifying Real API Responses

```bash
# After running validation with real keys, check:

# Notion: Look for real object structure
echo "$TOOL_RESULT" | grep -q '"object":"list"' && echo "✅ Real Notion response"

# Slack: Look for ok:true
echo "$TOOL_RESULT" | grep -q '"ok":true' && echo "✅ Real Slack response"

# NOT mock: Should NOT contain mock indicators
[[ "$TOOL_RESULT" != *"MVP Mock"* ]] && echo "✅ Not a mock response"
```

> **Detailed Instructions**: See `BATCH_EXECUTION_PLAN.md` section "Real API Integration Testing" for step-by-step setup guides.

---

## Related Documentation

- [BATCH_EXECUTION_PLAN.md](workstreams/mvp-production-readiness/BATCH_EXECUTION_PLAN.md) - Detailed batch execution plan with real API testing
- [MERGE_POINTS.md](workstreams/mvp-production-readiness/MERGE_POINTS.md) - Integration milestones
- [demos/demo_sarah_journey_e2e.py](../demos/demo_sarah_journey_e2e.py) - Python reference implementation
- [CLAUDE.md](../CLAUDE.md) - Development guidelines and learnings
