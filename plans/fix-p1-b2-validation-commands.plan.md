# Fix P1-B2 Integration Test Commands

## Context

**Problem:** The current integration test commands in `BATCH_EXECUTION_PLAN.md` return 401/400 errors because they use incorrect authentication:

| Endpoint | Current Auth | Result | Required Auth |
|----------|--------------|--------|---------------|
| Vault Token Retrieval (E2) | User JWT | 401 "missing user identity" | **Agent JWT** with `owner` claim |
| Vault Token Refresh (E3) | User JWT | 401 "Invalid internal token" | **Internal API Token** + `X-User-ID` header |
| OAuth Authorize (F3) | User JWT | 400 "Missing env vars" | User JWT + **OAuth env vars** |

**Goal:** Update the validation commands to use correct tokens/config so they return 200.

---

## Fix 1: Vault Token Retrieval (E2) - Requires Agent JWT

### The Problem

The endpoint `/api/v1/vault/tokens/{service_id}` requires an **Agent JWT** (not a user JWT). Agent JWTs contain:
- `owner` claim: The user who delegated permissions (e.g., "sarah@acme.com")
- `delegated_permissions` claim: Array of service permissions

### Solution: Full Agent Authentication Flow

To get an Agent JWT, we need to complete the full agent auth flow:

```bash
# ═══════════════════════════════════════════════════════════════
# STEP 1: Generate Ed25519 keypair (one-time)
# ═══════════════════════════════════════════════════════════════
python3 -c "
from nacl.signing import SigningKey
import base64

# Generate keypair
private_key = SigningKey.generate()
public_key = private_key.verify_key

# Export for use
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env

# ═══════════════════════════════════════════════════════════════
# STEP 2: Login as user
# ═══════════════════════════════════════════════════════════════
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# ═══════════════════════════════════════════════════════════════
# STEP 3: Register agent with public key
# ═══════════════════════════════════════════════════════════════
curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"test-agent-001\",
    \"name\": \"Test Agent\",
    \"public_key\": \"$PUBLIC_KEY_B64\"
  }" | jq .

# ═══════════════════════════════════════════════════════════════
# STEP 4: Create delegation (grant permissions)
# ═══════════════════════════════════════════════════════════════
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent-001",
    "permissions": ["notion:pages:search", "notion:pages:read", "slack:channels:list"]
  }' | jq .

# ═══════════════════════════════════════════════════════════════
# STEP 5: Request challenge (no auth required)
# ═══════════════════════════════════════════════════════════════
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent-001"}' | jq -r '.challenge')
echo "Challenge: $CHALLENGE"

# ═══════════════════════════════════════════════════════════════
# STEP 6: Sign challenge with Ed25519 private key
# ═══════════════════════════════════════════════════════════════
SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64

private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
challenge = '$CHALLENGE'
signed = private_key.sign(challenge.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

# ═══════════════════════════════════════════════════════════════
# STEP 7: Verify and get Agent JWT
# ═══════════════════════════════════════════════════════════════
AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"test-agent-001\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')
echo "Agent JWT: ${AGENT_JWT:0:50}..."

# ═══════════════════════════════════════════════════════════════
# STEP 8: NOW test vault token retrieval with Agent JWT
# ═══════════════════════════════════════════════════════════════
curl -s -X GET "http://localhost:8000/api/v1/vault/tokens/notion" \
  -H "Authorization: Bearer $AGENT_JWT" | jq .
# Expected: 200 with token data (or 404 if no token stored)
```

### Key Files

| File | Purpose |
|------|---------|
| `deeptrail-control/app/api/v1/endpoints/vault.py` | Token retrieval endpoint |
| `deeptrail-control/app/api/v1/endpoints/agent_auth.py` | Challenge/verify endpoints |
| `deeptrail-control/app/services/agent_session_service.py` | JWT creation with `owner` claim |

---

## Fix 2: Vault Token Refresh (E3) - Requires Internal API Token

### The Problem

The endpoint `/api/v1/vault/tokens/{service_id}/refresh` is for **Gateway-to-Control** communication only. It requires:
- `Authorization: Bearer <INTERNAL_TOKEN>` - Static shared secret
- `X-User-ID` header - Identifies which user's token to refresh

### Solution: Use the Internal API Token

The internal token is configured via environment variable `GATEWAY_INTERNAL_API_TOKEN`.

**Default dev value:** `insecure_default_gateway_token_for_dev`

```bash
# ═══════════════════════════════════════════════════════════════
# Test vault token refresh with internal API token
# ═══════════════════════════════════════════════════════════════

# Internal token (from Control Plane config)
INTERNAL_TOKEN="insecure_default_gateway_token_for_dev"

# Call refresh endpoint
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST "http://localhost:8000/api/v1/vault/tokens/notion/refresh" \
  -H "Authorization: Bearer $INTERNAL_TOKEN" \
  -H "X-User-ID: sarah@acme.com" \
  -H "Content-Type: application/json" \
  -d '{"force": false}'

# Expected: 200 with refresh result (or 404 if no token/400 if no refresh_token)
```

### Key Configuration

| Service | Environment Variable | Default (Dev) |
|---------|---------------------|---------------|
| Control Plane | `GATEWAY_INTERNAL_API_TOKEN` | `insecure_default_gateway_token_for_dev` |
| Gateway | Same (shared secret) | Same |

### Key Files

| File | Purpose |
|------|---------|
| `deeptrail-control/app/core/config.py:47-49` | Token configuration |
| `deeptrail-control/app/api/deps.py:193-240` | `verify_internal_token` dependency |
| `deeptrail-control/app/api/v1/endpoints/vault.py:202-240` | Refresh endpoint |

---

## Fix 3: OAuth Authorize (F3) - Requires Environment Variables

### The Problem

The endpoint `/api/v1/oauth/{service_id}/authorize` requires OAuth provider credentials to be configured via environment variables.

### Solution: Set OAuth Environment Variables

**Option A: Set in docker-compose.yml (persistent)**

Add to `deeptrail-control` service in `docker-compose.yml`:

```yaml
environment:
  # OAuth Global
  - OAUTH_REDIRECT_BASE_URL=http://localhost:8000

  # Notion OAuth (test values - won't work with real Notion but allows endpoint testing)
  - NOTION_OAUTH_CLIENT_ID=test-notion-client-id
  - NOTION_OAUTH_CLIENT_SECRET=test-notion-client-secret

  # Slack OAuth
  - SLACK_OAUTH_CLIENT_ID=test-slack-client-id
  - SLACK_OAUTH_CLIENT_SECRET=test-slack-client-secret

  # HubSpot OAuth
  - HUBSPOT_OAUTH_CLIENT_ID=test-hubspot-client-id
  - HUBSPOT_OAUTH_CLIENT_SECRET=test-hubspot-client-secret
```

**Option B: Set via shell and restart container**

```bash
# Export env vars and restart container
docker compose stop deeptrail-control

docker compose run -e OAUTH_REDIRECT_BASE_URL=http://localhost:8000 \
  -e NOTION_OAUTH_CLIENT_ID=test-notion-client-id \
  -e NOTION_OAUTH_CLIENT_SECRET=test-notion-client-secret \
  -e SLACK_OAUTH_CLIENT_ID=test-slack-client-id \
  -e SLACK_OAUTH_CLIENT_SECRET=test-slack-client-secret \
  -e HUBSPOT_OAUTH_CLIENT_ID=test-hubspot-client-id \
  -e HUBSPOT_OAUTH_CLIENT_SECRET=test-hubspot-client-secret \
  deeptrail-control
```

**After setting env vars, test:**

```bash
# Get user token
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# Test OAuth authorize endpoint
curl -s -X GET "http://localhost:8000/api/v1/oauth/notion/authorize" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .

# Expected: 200 with {"authorization_url": "https://api.notion.com/v1/oauth/authorize?...", "state": "..."}
```

### Required Environment Variables

| Variable | Required | Example Value |
|----------|----------|---------------|
| `OAUTH_REDIRECT_BASE_URL` | Yes | `http://localhost:8000` |
| `NOTION_OAUTH_CLIENT_ID` | For Notion | `test-notion-client-id` |
| `NOTION_OAUTH_CLIENT_SECRET` | For Notion | `test-notion-client-secret` |
| `SLACK_OAUTH_CLIENT_ID` | For Slack | `test-slack-client-id` |
| `SLACK_OAUTH_CLIENT_SECRET` | For Slack | `test-slack-client-secret` |
| `HUBSPOT_OAUTH_CLIENT_ID` | For HubSpot | `test-hubspot-client-id` |
| `HUBSPOT_OAUTH_CLIENT_SECRET` | For HubSpot | `test-hubspot-client-secret` |

### Key Files

| File | Purpose |
|------|---------|
| `deeptrail-control/app/core/oauth_config.py` | OAuth configuration classes |
| `deeptrail-control/app/services/oauth_service.py:182-232` | Env var validation in `get_provider_config()` |
| `deeptrail-control/app/api/v1/endpoints/oauth.py` | OAuth endpoints |

---

## Implementation Plan

### What Changes

**File to modify:** `docs/workstreams/mvp-production-readiness/BATCH_EXECUTION_PLAN.md`

**Section:** Post-Merge Validation (Integration Tests) - lines 749-817

### Changes Required

1. **Replace simple curl commands with full flow scripts** for each endpoint
2. **Add prerequisite setup** for OAuth env vars (via docker-compose.yml)
3. **Document expected responses** for each test case

### Updated Validation Commands

The new validation section should include:

```bash
# ═══════════════════════════════════════════════════════════════
# P1-B2 COMPLETE VALIDATION (All endpoints return 200)
# ═══════════════════════════════════════════════════════════════

# --- PREREQUISITE: Add OAuth env vars to docker-compose.yml first ---
# See Fix 3 above for the environment block to add

# 0. Rebuild and restart with OAuth config
docker compose build deeptrail-control
docker compose up -d db redis deeptrail-control deeptrail-gateway
sleep 15

# 1. Verify health
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy"

# 2. Setup: Login and connect service (unchanged from before)
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "test_notion_token_123",
      "token_type": "bearer",
      "scope": "read_pages",
      "expires_in": 3600
    }
  }' | jq .

# 3. Test E2: Vault token retrieval (requires Agent JWT)
# [Full agent auth flow from Fix 1 above]

# 4. Test E3: Vault token refresh (requires internal token)
INTERNAL_TOKEN="insecure_default_gateway_token_for_dev"
curl -s -X POST "http://localhost:8000/api/v1/vault/tokens/notion/refresh" \
  -H "Authorization: Bearer $INTERNAL_TOKEN" \
  -H "X-User-ID: sarah@acme.com" \
  -H "Content-Type: application/json" \
  -d '{"force": false}' | jq .

# 5. Test F3: OAuth authorize (requires OAuth env vars)
curl -s -X GET "http://localhost:8000/api/v1/oauth/notion/authorize" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

---

## Verification

After implementing these changes, run the full validation script and verify:

| Test | Expected Response |
|------|-------------------|
| Service Connect | `{"success": true, "connection": {...}}` |
| Vault Retrieval (with Agent JWT) | `{"service_id": "notion", "access_token": "...", ...}` or 404 if no token |
| Vault Refresh (with Internal Token) | `{"refreshed": true/false, ...}` or 404 if no token |
| OAuth Authorize (with env vars) | `{"authorization_url": "https://...", "state": "..."}` |

---

## Summary

| Endpoint | Current Issue | Fix |
|----------|---------------|-----|
| E2 Vault Retrieval | 401 - needs Agent JWT | Add full agent auth flow (7 steps) |
| E3 Vault Refresh | 401 - needs internal token | Use `insecure_default_gateway_token_for_dev` + `X-User-ID` header |
| F3 OAuth Authorize | 400 - missing env vars | Add OAuth env vars to docker-compose.yml |
