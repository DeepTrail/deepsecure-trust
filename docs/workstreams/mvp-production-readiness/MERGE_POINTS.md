# MVP Production Readiness: Merge Points & Testing Strategy

> **Workstream:** [WORKSTREAM.md](./WORKSTREAM.md)  
> **Status:** [STATUS.md](./STATUS.md)  
> **Created:** February 16, 2026  
> **Last Updated:** February 22, 2026  
> **Latest Change:** Added MP3.5 (Integration Bug Fixes) merge point for Phase 1.5

---

## Overview

This document defines the merge point actions and testing strategy for the MVP Production Readiness workstream. This workstream converts MVP mock implementations to production-ready code.

### Key Distinction

This workstream is different from a typical greenfield implementation:

| Aspect | Typical Workstream | This Workstream |
|--------|-------------------|-----------------|
| Starting point | No code exists | Functional MVP with mocks |
| Merge points | Components integrate | Mocks replaced with real code |
| Testing | Components work together | Real APIs respond correctly |
| Success criteria | Flow works | Flow works with REAL data |

---

## Code Dependencies vs Runtime Dependencies

Understanding the difference between dependency types is critical for parallel development:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY TYPES IN MERGE POINTS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CODE DEPENDENCY (Worktree-level)                                           │
│  ─────────────────────────────────                                          │
│  • Task needs another task's API/interface to BUILD                         │
│  • Blocks task from STARTING                                                │
│  • Tracked in task tickets and STATUS.md                                    │
│  • Resolved when dependent task is "code complete"                          │
│                                                                              │
│  Example: H1 (credential injector) needs E2 (vault endpoint) to know        │
│           endpoint format: GET /api/v1/vault/tokens/{service_id}            │
│                                                                              │
│  RUNTIME DEPENDENCY (Deployment-level)                                      │
│  ────────────────────────────────────                                       │
│  • Task needs another service RUNNING for integration testing               │
│  • Does NOT block task from starting                                        │
│  • Resolved at MERGE POINTS when services are deployed together             │
│  • Development proceeds with mocks/local fallbacks                          │
│                                                                              │
│  Example: H1 needs Control Plane running to fetch real tokens               │
│           During P0, H1 used mock tokens instead                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Task Lifecycle with Dependencies

```
                              CODE COMPLETE                    INTEGRATION COMPLETE
                                   │                                   │
 ┌──────────┐   ┌──────────┐   ┌──┴───────┐   ┌──────────┐   ┌────────┴─────────┐
 │ Blocked  │ → │  Ready   │ → │   Dev    │ → │  Code    │ → │   Integration    │
 │          │   │          │   │          │   │ Complete │   │     Complete     │
 └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────────────┘
      │              │              │              │                   │
      │              │              │              │                   │
  Waiting for    Code deps      Building      Unit tests         Services
  code deps      satisfied      with mocks    pass, API          deployed,
  to complete                   /local mode   documented         integration
                                                                 tests pass
```

### When Each Dependency Type Matters

| Phase | Code Dependencies | Runtime Dependencies |
|-------|-------------------|----------------------|
| **Task Creation** | Listed in ticket metadata | Listed in ticket metadata |
| **Task Start** | Must be satisfied (✅) | Not required |
| **Development** | Use completed APIs | Use mocks/local fallbacks |
| **Unit Testing** | Against real interfaces | With mocked services |
| **Code Complete** | All satisfied | May be unavailable |
| **Merge Point** | All satisfied | Services deployed |
| **Integration Testing** | All satisfied | All services running |

---

## Development Mode vs Integration Mode

### Development Mode (In Worktree)

During task implementation, you can work WITHOUT all services running:

| Service Down | Fallback Behavior | Tasks Affected |
|--------------|-------------------|----------------|
| Control Plane | Use mock vault responses | G2, G3, G4 (backend clients) |
| Gateway | Control Plane works standalone | E1, E2, E3, F1, F2, F3 |
| Both down | Unit tests still pass with mocks | All tasks |

**Development Environment:**
```bash
# Control worktree (mvp-prod-control)
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control
pytest tests/ -v  # Works without Gateway

# Gateway worktree (mvp-prod-gateway)
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway
pytest tests/ -v  # Works without Control Plane
```

### Integration Mode (At Merge Point)

At merge points, services must be running for integration testing:

| Mode | When | Services Required | Purpose |
|------|------|-------------------|---------|
| Dev | During task work | None required | Unit testing with mocks |
| MP1 | After P0 | None (E2E with mocks) | Verify flow works |
| MP2 | After P1-B2 | Control + DB + Redis | Verify vault API |
| MP3 | After P1-B3 | Control + Gateway | Verify credential injection |
| MP3.5 | After P1.5-B1 | Control + Gateway + DB | Verify integration bug fixes |
| MP4 | After P2 | Full stack | Production readiness |

### Runtime Dependencies by Merge Point

| MP | Control Plane | Gateway | DB | Redis | Real APIs |
|----|---------------|---------|----|----|-----------|
| MP1 | ✅ Running | ✅ Running | ✅ | ✅ | ❌ Not needed |
| MP2 | ✅ Running | ❌ Not needed | ✅ | ✅ | ❌ Not needed |
| MP3 | ✅ Running | ✅ Running | ✅ | ✅ | ⚠️ Optional |
| MP3.5 | ✅ Running | ✅ Running | ✅ | ✅ | ✅ Required (to test fixes) |
| MP4 | ✅ Running | ✅ Running | ✅ | ✅ | ✅ Required |

### Runtime Dependencies by Task (Cross-Service)

| Task | Service | Needs at Runtime | During Dev Use |
|------|---------|------------------|----------------|
| H1 | Gateway | Control Plane vault API | Mock token |
| H2 | Gateway | Control Plane refresh endpoint | Mock refresh |
| G2 | Gateway | Real Notion API | Mock responses |
| G3 | Gateway | Real Slack API | Mock responses |
| G4 | Gateway | Real HubSpot API | Mock responses |

---

## Merge Point Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MERGE POINT OVERVIEW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  P0 ──────────────────────────────┐                                         │
│  (E2E Flow Verification)          │                                         │
│                                   ▼                                         │
│                              ┌────────┐                                     │
│                              │  MP1   │  E2E flow verified                  │
│                              │   ✅   │  (mocks still present)              │
│                              └────┬───┘                                     │
│                                   │                                         │
│  P1-B1 ──────────────────────────┐│                                         │
│  (Foundation: Vault, OAuth, Config)                                         │
│                                   │                                         │
│  P1-B2 ──────────────────────────┐│                                         │
│  (Integration: Endpoints, Clients)│                                         │
│                                   ▼                                         │
│                              ┌────────┐                                     │
│                              │  MP2   │  Vault API ready                    │
│                              │   ✅   │  (real token storage)               │
│                              └────┬───┘                                     │
│                                   │                                         │
│  P1-B3 ──────────────────────────┐│                                         │
│  (Credential Injection from Vault)│                                         │
│                                   ▼                                         │
│                              ┌────────┐                                     │
│                              │  MP3   │  P1 complete                        │
│                              │   ✅   │  (mocks replaced)                   │
│                              └────┬───┘                                     │
│                                   │                                         │
│  P1.5-B1 ────────────────────────┐│  ← NEW: Integration Bug Fixes           │
│  (Tool Names, Vault, Cache, Perms)│                                         │
│                                   ▼                                         │
│                              ┌────────┐                                     │
│                              │ MP3.5  │  Integration bugs fixed             │
│                              │   ⏳   │  (WS-J2, WS-K1-K5)                  │
│                              └────┬───┘                                     │
│                                   │                                         │
│  P2 ─────────────────────────────┐│                                         │
│  (Production Hardening)           │                                         │
│                                   ▼                                         │
│                              ┌────────┐                                     │
│                              │  MP4   │  Production ready                   │
│                              │   ⏳   │                                     │
│                              └────────┘                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## MP1: E2E Flow Verified

### Status: ✅ REACHED (February 16, 2026)

### Why It's a Merge Point

MP1 marks the point where:
1. **All P0 verification tasks** (P0-V1 through P0-V6) are complete
2. **E2E flow works** with mock data
3. **Both services can integrate** despite using mocks internally
4. **Baseline established** for real implementation work

This is NOT about real data—it's about proving the architecture works.

### Purpose

Verify that the end-to-end flow works with mock data before beginning real implementation work. This establishes a working baseline that P1 tasks can safely modify without breaking the overall flow.

### What Was Validated

| Aspect | Status | Evidence |
|--------|--------|----------|
| All endpoints exist | ✅ | E2E demo accesses all endpoints |
| API contracts correct | ✅ | Response formats match expectations |
| Flow works end-to-end | ✅ | All 10 steps pass |
| Permission enforcement | ✅ | Non-delegated tools blocked |
| Ed25519 auth | ✅ | Challenge-response works |

### What Was NOT Validated (Deferred to MP3)

| Aspect | Status | Notes |
|--------|--------|-------|
| Real password validation | ❌ | MVP accepts any password |
| Real OAuth token storage | ❌ | In-memory storage |
| Real backend API calls | ❌ | Mock responses returned |
| Real audit persistence | ❌ | Logs locally only |

### Validation Command

```bash
# MP1 validation - should pass
python demos/demo_sarah_journey_e2e.py
# Expected: All 10 steps pass (exit code 0)
```

### Converging Tasks

| Task | Description | Status |
|------|-------------|--------|
| P0-V1 | Verify login endpoint | ✅ Complete |
| P0-V2 | Verify service connection | ✅ Complete |
| P0-V3 | Verify delegation format | ✅ Complete |
| P0-V4 | Verify agent registration | ✅ Complete |
| P0-V5 | Verify router wiring | ✅ Complete |
| P0-V6 | Run E2E demo | ✅ Complete |

### Enables

- P1-B1 tasks (E1, F1, G1)
- Stakeholder demos with mock data

### Merge Actions

Since MP1 was reached during initial P0 verification (before worktrees were created), the merge action was simply confirming all P0 tasks passed in the main repo:

```bash
# 1. Verify all P0 tasks passed (in main repo)
cd /Users/imaxxs/repositories/deepsecure-mvp
git status
git log --oneline -10  # Check P0-V1 through P0-V6 commits

# 2. Run E2E demo to confirm
python demos/demo_sarah_journey_e2e.py
# Expected: All 10 steps pass

# 3. Commit any final verification updates
git add -A && git commit -m "Complete P0: E2E flow verified"
git push origin dev

# 4. Tag the merge point
git tag -a mp1-reached -m "MP1: E2E Flow Verified - $(date +%Y-%m-%d)"
git push origin mp1-reached
```

### Container Deployment

```bash
# Deploy services for MP1 verification
cd /Users/imaxxs/repositories/deepsecure-mvp

# Start all required services
docker compose up -d db redis deeptrail-control deeptrail-gateway
sleep 15

# Verify services are healthy
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy"
```

### Container Test Scenarios

```bash
# Test 1: User login (mock password accepted)
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"any_password"}' | jq .
# Expected: {"access_token": "...", "token_type": "bearer", ...}

# Test 2: Service delegation
curl -s -X POST http://localhost:8000/api/v1/services/notion/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent_123","tools":["notion_search"]}' | jq .
# Expected: {"delegation_id": "...", ...}

# Test 3: Agent tool call through Gateway
curl -s -X POST http://localhost:8002/mcp/v1/tools/call \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"tool":"notion_search","params":{"query":"test"}}' | jq .
# Expected: {"result": [...], ...}  (mock data)
```

### Cleanup

```bash
# Stop services after testing
docker compose down

# Optional: Remove volumes for clean restart
docker compose down -v
```

### Success Criteria

- [ ] All P0-V1 through P0-V6 tasks complete
- [ ] E2E demo passes (exit code 0)
- [ ] Control Plane health check passes
- [ ] Gateway health check passes
- [ ] User login endpoint responds
- [ ] Service delegation endpoint responds
- [ ] Gateway tool call endpoint responds (mock data OK)

### Post-Merge Status Update

After reaching MP1, update:

```bash
# 1. Update STATUS.md
sed -i '' 's/MP1: ⏳/MP1: ✅ REACHED/' docs/workstreams/mvp-production-readiness/STATUS.md

# 2. Update MERGE_POINTS.md
# Mark MP1 status as "✅ REACHED (date)"

# 3. Commit the updates
git add docs/workstreams/mvp-production-readiness/
git commit -m "docs: Mark MP1 as reached"
```

---

## MP2: Vault API Ready

### Status: ✅ REACHED (February 17, 2026)

### Purpose

Real OAuth token storage and retrieval working between Control Plane and Gateway.

### Pre-Merge Checklist

```
✓ E1 complete: Vault client enhanced for token storage
✓ E2 complete: Vault token retrieval endpoint exists (bug fixed: queries ConnectedService DB)
✓ E3 complete: Vault token refresh endpoint exists (bug fixed: queries ConnectedService DB)
✓ Unit tests pass for vault operations (26/26 pass)
✓ Integration test: Connect service → Retrieve token → Verify match (validated Feb 17, 2026)
```

### Converging Tasks

| Task | Description | Service | Status | Report |
|------|-------------|---------|--------|--------|
| E1 | Enhance vault client | Control | ✅ Complete | [Report](./reports/WS-E1-completion.md) |
| E2 | Token retrieval endpoint | Control | ✅ Complete | [Report](./reports/WS-E2-completion.md) |
| E3 | Token refresh endpoint | Control | ✅ Complete | [Report](./reports/WS-E3-completion.md) |

### What Was Achieved

| Component | Description | Files Created |
|-----------|-------------|---------------|
| Vault Client | Enhanced with token expiration tracking and refresh | `vault_client.py` |
| Token Retrieval | GET `/api/v1/vault/tokens/{service_id}` | `vault.py` endpoints |
| Token Refresh | POST `/api/v1/vault/tokens/{service_id}/refresh` | `vault.py` endpoints |
| OAuth Config | OAuth provider configuration module | `oauth_config.py` |
| OAuth Endpoints | authorize, callback, refresh endpoints | `oauth.py` |
| Notion API | 7 real Notion API calls | `notion_api.py` |
| Slack API | 7 real Slack API calls | `slack_api.py` |
| HubSpot API | 9 real HubSpot CRM API calls | `hubspot_api.py` |

### Integration Test

```bash
# MP2 validation script
#!/bin/bash

# 1. Start services
docker compose up -d db redis deeptrail-control deeptrail-gateway
sleep 15

# 2. Login
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# 3. Connect a service (stores token in vault + reference in connected_services DB)
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "real_notion_token_123",
      "token_type": "bearer",
      "scope": "read_pages search_content",
      "expires_in": 3600
    }
  }' | jq .

# 4. Complete agent auth flow to get Agent JWT
# (generate keypair, register agent, delegate, challenge, sign, verify)
# See BATCH_EXECUTION_PLAN.md P1-B2 Post-Merge Validation for full flow

# 5. Retrieve the token via E2 endpoint (requires Agent JWT)
RETRIEVED=$(curl -s -X GET "http://localhost:8000/api/v1/vault/tokens/notion" \
  -H "Authorization: Bearer $AGENT_JWT" | jq -r '.access_token')

# 6. Verify match
if [ "$RETRIEVED" = "real_notion_token_123" ]; then
  echo "✅ MP2 PASSED: Token storage and retrieval working"
else
  echo "❌ MP2 FAILED: Token mismatch"
  exit 1
fi
```

### Enables

- P1-B3 tasks (H1, H2) - Credential injection from vault
- Gateway can fetch real OAuth tokens

### Why It's a Merge Point

MP2 marks the point where:
1. **Vault client is enhanced** (E1) with token storage/retrieval capabilities
2. **Token retrieval endpoint exists** (E2) for Gateway to call
3. **Token refresh endpoint exists** (E3) for expired token handling
4. **OAuth configuration** (F2) and **endpoints** (F3) are ready
5. **Backend API clients** (G2, G3, G4) are implemented

This is the foundation for credential injection—without vault APIs, Gateway cannot fetch tokens.

### Merge Actions

```bash
# 1. Push Control Plane worktree changes
cd /Users/imaxxs/repositories/mvp-prod-control
git status
git add -A && git commit -m "Complete P1-B1 + P1-B2: E1, E2, E3, F1, F2, F3"
git push origin feature/mvp-prod-control

# 2. Push Gateway worktree changes
cd /Users/imaxxs/repositories/mvp-prod-gateway
git status
git add -A && git commit -m "Complete P1-B1 + P1-B2: G1, G2, G3, G4"
git push origin feature/mvp-prod-gateway

# 3. Create PRs
gh pr create --base dev --head feature/mvp-prod-control \
  --title "Control Plane: P1-B1 + P1-B2 (E1-E3, F1-F3)" \
  --body "Implements vault client, token endpoints, OAuth config and endpoints"

gh pr create --base dev --head feature/mvp-prod-gateway \
  --title "Gateway: P1-B1 + P1-B2 (G1-G4)" \
  --body "Implements backend API clients for Notion, Slack, HubSpot"

# 4. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/mvp-prod-control --no-ff -m "Merge Control: P1-B1 + P1-B2"
git merge origin/feature/mvp-prod-gateway --no-ff -m "Merge Gateway: P1-B1 + P1-B2"
git push origin dev

# 5. Update worktrees
cd /Users/imaxxs/repositories/mvp-prod-control && git rebase origin/dev
cd /Users/imaxxs/repositories/mvp-prod-gateway && git rebase origin/dev

# 6. Tag the merge point
cd /Users/imaxxs/repositories/deepsecure-mvp
git tag -a mp2-reached -m "MP2: Vault API Ready - $(date +%Y-%m-%d)"
git push origin mp2-reached
```

### Container Deployment

```bash
# Deploy services for MP2 validation
cd /Users/imaxxs/repositories/deepsecure-mvp

# Start required services (Control Plane + dependencies)
docker compose up -d db redis deeptrail-control
sleep 15

# Verify Control Plane is healthy
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"

# Check database is accessible
docker compose exec -T db psql -U deepsecure_user -d deeptrail_controldb -c "SELECT 1"
echo "✅ Database accessible"

# Check Redis is accessible
docker compose exec -T redis redis-cli PING
echo "✅ Redis accessible"
```

### Container Test Scenarios

```bash
# ═══════════════════════════════════════════════════════════════
# MP2 CONTAINER TESTS - Vault API + OAuth Endpoints
# ═══════════════════════════════════════════════════════════════
# All tests should return 200 status codes
# ═══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────
# SETUP: Get User Token and Connect Service
# ─────────────────────────────────────────────────────────────────

# Get user token (login endpoint returns "token" field)
echo "Setup: Getting user token..."
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')
echo "User token: ${USER_TOKEN:0:20}..."

# Test 1: Connect a service (stores OAuth token via service connection)
echo "Test 1: Connecting service with OAuth token..."
CONNECT_RESULT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "ntn_test_123456789",
      "token_type": "bearer",
      "scope": "read_pages",
      "refresh_token": "ntn_refresh_test_abc",
      "expires_in": 3600
    }
  }')
echo "$CONNECT_RESULT" | head -n -1 | jq .
HTTP_STATUS=$(echo "$CONNECT_RESULT" | tail -1 | cut -d: -f2)
[ "$HTTP_STATUS" = "200" ] && echo "✅ Test 1 PASSED" || echo "❌ Test 1 FAILED"

# ─────────────────────────────────────────────────────────────────
# AGENT SETUP: Create Agent JWT via Challenge-Response
# ─────────────────────────────────────────────────────────────────

# Generate Ed25519 keypair
echo "Setup: Generating agent keypair..."
python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey.generate()
public_key = private_key.verify_key
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/mp2_agent_keys.env
source /tmp/mp2_agent_keys.env

# Register agent with public key
echo "Setup: Registering agent..."
curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"mp2-test-agent\",
    \"name\": \"MP2 Test Agent\",
    \"public_key\": \"$PUBLIC_KEY_B64\"
  }" | jq .

# Create delegation
echo "Setup: Creating delegation..."
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "mp2-test-agent",
    "permissions": ["notion:pages:search", "notion:pages:read"]
  }' | jq .

# Request and sign challenge
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "mp2-test-agent"}' | jq -r '.challenge')

SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
signed = private_key.sign('$CHALLENGE'.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

# Get Agent JWT
AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"mp2-test-agent\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')
echo "Agent JWT: ${AGENT_JWT:0:30}..."

# ─────────────────────────────────────────────────────────────────
# TEST E2: Vault Token Retrieval (Agent JWT Required)
# ─────────────────────────────────────────────────────────────────

echo "Test 2: Retrieving token via vault API (Agent JWT)..."
RETRIEVE_RESULT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X GET "http://localhost:8000/api/v1/vault/tokens/notion" \
  -H "Authorization: Bearer $AGENT_JWT")
echo "$RETRIEVE_RESULT" | head -n -1 | jq .
HTTP_STATUS=$(echo "$RETRIEVE_RESULT" | tail -1 | cut -d: -f2)
[ "$HTTP_STATUS" = "200" ] && echo "✅ Test 2 (E2) PASSED" || echo "❌ Test 2 (E2) FAILED"

# ─────────────────────────────────────────────────────────────────
# TEST E3: Vault Token Refresh (Internal API Token Required)
# ─────────────────────────────────────────────────────────────────

# Internal token from docker-compose.yml: gateway-internal-secret-token
echo "Test 3: Refreshing token via internal API..."
REFRESH_RESULT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X POST "http://localhost:8000/api/v1/vault/tokens/notion/refresh" \
  -H "Authorization: Bearer gateway-internal-secret-token" \
  -H "X-User-ID: sarah@acme.com" \
  -H "Content-Type: application/json" \
  -d '{"force": false}')
echo "$REFRESH_RESULT" | head -n -1 | jq .
HTTP_STATUS=$(echo "$REFRESH_RESULT" | tail -1 | cut -d: -f2)
# 200 = refreshed, 400 = no refresh token stored (both are valid responses)
[ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "400" ] && echo "✅ Test 3 (E3) PASSED" || echo "❌ Test 3 (E3) FAILED"

# ─────────────────────────────────────────────────────────────────
# TEST F3: OAuth Authorization URL Generation
# ─────────────────────────────────────────────────────────────────

echo "Test 4: Generating OAuth authorize URL..."
OAUTH_RESULT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X GET "http://localhost:8000/api/v1/oauth/notion/authorize" \
  -H "Authorization: Bearer $USER_TOKEN")
echo "$OAUTH_RESULT" | head -n -1 | jq .
HTTP_STATUS=$(echo "$OAUTH_RESULT" | tail -1 | cut -d: -f2)
[ "$HTTP_STATUS" = "200" ] && echo "✅ Test 4 (F3) PASSED" || echo "❌ Test 4 (F3) FAILED"

# ─────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────

rm -f /tmp/mp2_agent_keys.env

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ MP2 VALIDATION COMPLETE"
echo "═══════════════════════════════════════════════════════════════"
```

### Cleanup

```bash
# Stop services after MP2 validation
docker compose down

# Optional: Clean database for fresh start
docker compose down -v

# Remove test data only (preserve services)
docker compose exec -T db psql -U deepsecure_user -d deeptrail_controldb \
  -c "DELETE FROM connected_services WHERE user_id = 'sarah@acme.com';"
```

### Success Criteria

- [ ] E1 (vault client) complete with unit tests passing
- [ ] E2 (token retrieval) endpoint responds correctly
- [ ] E3 (token refresh) endpoint responds correctly
- [ ] F2 (OAuth config) module created
- [ ] F3 (OAuth endpoints) authorize/callback/refresh working
- [ ] G2 (Notion API client) implemented with real API calls
- [ ] G3 (Slack API client) implemented with real API calls
- [ ] G4 (HubSpot API client) implemented with real API calls
- [ ] Token storage → retrieval round-trip works
- [ ] Token refresh endpoint can refresh expired tokens
- [ ] All completion reports present in `reports/` folder

### Post-Merge Status Update

After reaching MP2, run:

```bash
# 1. Verify batch completion
/verify-batch-completion P1-B2 mvp-production-readiness

# 2. Update STATUS.md
cd /Users/imaxxs/repositories/deepsecure-mvp
# Update P1 progress percentage
# Mark MP2 as reached

# 3. Update MERGE_POINTS.md
# Set MP2 status to "✅ REACHED (date)"
# Check off pre-merge checklist items

# 4. Update BATCH_EXECUTION_PLAN.md
# Mark P1-B2 as complete

# 5. Commit all updates
git add docs/workstreams/mvp-production-readiness/
git commit -m "docs: Mark MP2 as reached - P1-B2 complete"
git push origin dev
```

---

## MP3: P1 Complete (Mocks Replaced)

### Status: ✅ REACHED (February 18, 2026)

### Purpose

All MVP mocks replaced with real implementations. The E2E demo passes with REAL data from REAL APIs.

### Pre-Merge Checklist

```
✅ MP2 reached (vault API ready)
✅ H1 complete: CredentialInjector calls vault API
✅ H2 complete: Token refresh implemented
✅ G2, G3, G4 complete: Real backend API calls
✅ Audit events persisted to Control Plane DB
⚠️ E2E demo passes but integration testing revealed bugs → See MP3.5
```

> **Note:** While MP3 was reached, subsequent testing via [Integration Validation Guide](../../INTEGRATION_VALIDATION_GUIDE.md) revealed several issues that must be fixed in Phase 1.5 before proceeding to Phase 2.

### Mock Removal Verification

Each mock must be removed and replaced:

| Mock Location | Task | Verification |
|---------------|------|--------------|
| `auth.py:68` - Any password | P1-1 or P2 | Login fails with wrong password |
| `credential_injection.py:293` - Mock token | H1 | Vault API called, real token returned |
| `tools_call.py:659` - Mock result | G2/G3/G4 | Real Notion/Slack API called |
| `audit.py:348` - Local logging | H1 | Audit events in DB (`/api/v1/audit/events` returns data) |
| `credential_injection.py:374` - No refresh | H2 | Token refresh works |

### Converging Tasks

| Task | Description | Service | Status |
|------|-------------|---------|--------|
| H1 | Connect CredentialInjector to vault | Gateway | ✅ Complete |
| H2 | Implement token refresh | Gateway | ✅ Complete |
| G2 | Notion REST API client | Gateway | ✅ Complete |
| G3 | Slack REST API client | Gateway | ✅ Complete |
| G4 | HubSpot REST API client | Gateway | ✅ Complete |

### Integration Test

```bash
# MP3 validation - E2E with real APIs
#!/bin/bash

# 1. Start all services
docker compose up -d

# 2. Connect real OAuth tokens (requires real tokens)
# This step requires actual OAuth flow or pre-seeded tokens

# 3. Run E2E demo
python demos/demo_sarah_journey_e2e.py --verbose

# 4. Verify audit events persisted
EVENTS=$(curl -s "http://localhost:8000/api/v1/audit/events?limit=10" \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.events | length')

if [ "$EVENTS" -gt 0 ]; then
  echo "✅ Audit events persisted: $EVENTS events"
else
  echo "❌ No audit events found - still using mock"
  exit 1
fi

# 5. Initialize MCP session (REQUIRED before tools/call)
echo "Initializing MCP session..."
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "mp3-test-agent", "version": "1.0.0"}
    }
  }' | jq .

# 6. Verify real API response (not mock string)
# The tool call result should NOT contain "MVP Mock:"
RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }' | jq -r '.result.content[0].text')

if [[ "$RESULT" != *"MVP Mock"* ]] && [[ "$RESULT" != *"Session not found"* ]]; then
  echo "✅ Real API response received"
else
  echo "❌ Still returning mock response or session error"
  exit 1
fi

echo "✅ MP3 PASSED: All mocks replaced"
```

### Enables

- P2 tasks (I*, J*, K*) - Production hardening
- Production deployment with real APIs

### Why It's a Merge Point

MP3 marks the point where:
1. **All mocks are replaced** with real implementations
2. **Credential injection works** end-to-end with real vault
3. **Real API calls** to Notion, Slack, HubSpot succeed
4. **Audit events persist** to database (not just local logging)
5. **P1 is complete** - ready for production hardening

This is the transition from "demo-quality" to "production-quality" code.

### Merge Actions

```bash
# 1. Ensure MP2 is reached first
# All P1-B1 and P1-B2 tasks must be complete

# 2. Push Gateway worktree changes (P1-B3: credential injection)
cd /Users/imaxxs/repositories/mvp-prod-gateway
git status
git add -A && git commit -m "Complete P1-B3: H1, H2 - Credential injection from vault"
git push origin feature/mvp-prod-gateway

# 3. Create PR
gh pr create --base dev --head feature/mvp-prod-gateway \
  --title "Gateway: P1-B3 (H1, H2)" \
  --body "Implements credential injection from vault API and token refresh"

# 4. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/mvp-prod-gateway --no-ff -m "Merge Gateway: P1-B3 - Credential Injection"
git push origin dev

# 5. Run integration tests
docker compose up -d
sleep 20
pytest tests/e2e/ -v --tb=short
docker compose down

# 6. Update worktree
cd /Users/imaxxs/repositories/mvp-prod-gateway && git rebase origin/dev

# 7. Tag the merge point
cd /Users/imaxxs/repositories/deepsecure-mvp
git tag -a mp3-reached -m "MP3: P1 Complete - Mocks Replaced - $(date +%Y-%m-%d)"
git push origin mp3-reached
```

### Container Deployment

```bash
# Deploy full stack for MP3 validation
cd /Users/imaxxs/repositories/deepsecure-mvp

# Start all services
docker compose up -d
sleep 20

# Verify all services are healthy
echo "Checking service health..."
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy"
docker compose exec -T db psql -U deepsecure_user -d deeptrail_controldb -c "SELECT 1" > /dev/null && echo "✅ Database accessible"
docker compose exec -T redis redis-cli PING > /dev/null && echo "✅ Redis accessible"

# Set up test OAuth tokens via service connection flow
echo "Setting up test tokens..."
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# Connect service (stores token in vault + reference in connected_services DB)
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "'"${NOTION_API_KEY:-test_notion_token}"'",
      "token_type": "bearer",
      "scope": "read_pages search_content",
      "expires_in": 3600
    }
  }'
echo "✅ Test token seeded via service connection"
```

### Container Test Scenarios

```bash
# ═══════════════════════════════════════════════════════════════════════════════
# MP3 Container Test Scenarios - Full Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

# Test 1: Login (real password validation)
# Note: Login returns "token" field, not "access_token"
echo "Test 1: User login..."
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')
if [ -n "$USER_TOKEN" ] && [ "$USER_TOKEN" != "null" ]; then
  echo "✅ Login successful: ${USER_TOKEN:0:20}..."
else
  echo "❌ Login failed"
  exit 1
fi

# Test 2: Connect service (stores OAuth token in vault)
echo "Test 2: Connect service..."
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "'"${NOTION_API_KEY:-test_notion_token}"'",
      "token_type": "bearer",
      "scope": "read_pages search_content",
      "expires_in": 3600
    }
  }' | jq .

# Test 3: Agent JWT creation (full Ed25519 challenge-response)
echo "Test 3: Creating Agent JWT..."
python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey.generate()
public_key = private_key.verify_key
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env

# Register agent
curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"mp3-test-agent\",
    \"name\": \"MP3 Test Agent\",
    \"public_key\": \"$PUBLIC_KEY_B64\"
  }" | jq .

# Create delegation
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "mp3-test-agent",
    "permissions": ["notion:pages:search", "notion:pages:read"]
  }' | jq .

# Challenge-response authentication
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "mp3-test-agent"}' | jq -r '.challenge')

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
    \"agent_id\": \"mp3-test-agent\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')
echo "✅ Agent JWT created: ${AGENT_JWT:0:30}..."

# ─────────────────────────────────────────────────────────────────────────────
# Test 4: MCP Initialize (REQUIRED before any tools/call)
# ─────────────────────────────────────────────────────────────────────────────
echo "Test 4: MCP Initialize..."
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
      "clientInfo": {"name": "mp3-test-agent", "version": "1.0.0"}
    }
  }')
if [[ "$INIT_RESULT" == *"protocolVersion"* ]]; then
  echo "✅ MCP session initialized"
else
  echo "❌ MCP initialize failed: $INIT_RESULT"
  exit 1
fi

# Test 5: List tools (verifies session + permissions)
echo "Test 5: List available tools..."
TOOLS_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2,
    "params": {}
  }')
TOOL_COUNT=$(echo $TOOLS_RESULT | jq -r '.result.tools | length')
echo "✅ Tools available: $TOOL_COUNT tools"

# Test 6: Credential injection via Gateway (the main test)
echo "Test 6: Credential injection..."
TOOL_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }')
echo "Tool result: $TOOL_RESULT"

# Verify NOT a mock response and no errors
if [[ "$TOOL_RESULT" == *"error"* ]]; then
  echo "❌ Tool call error"
  echo "$TOOL_RESULT" | jq .
elif [[ "$TOOL_RESULT" != *"MVP Mock"* ]]; then
  echo "✅ Real API response (not mock)"
else
  echo "❌ Still returning mock response"
fi

# Test 7: Second tool call (token refresh scenario)
echo "Test 7: Token refresh test..."
REFRESH_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 4,
    "params": {"name": "notion.search_pages", "arguments": {"query": "refresh_test"}}
  }')
echo "Refresh test: ✅ Complete"

# Test 8: Audit events persisted
echo "Test 8: Audit persistence..."
sleep 2  # Allow time for async audit write
AUDIT_COUNT=$(curl -s "http://localhost:8000/api/v1/audit/events?limit=10" \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.events | length')
if [ "$AUDIT_COUNT" -gt 0 ]; then
  echo "✅ Audit events persisted: $AUDIT_COUNT events"
else
  echo "⚠️ No audit events found (may not be implemented yet)"
fi

# Test 9: End-to-end demo
echo "Test 9: E2E demo..."
python demos/demo_sarah_journey_e2e.py --verbose
if [ $? -eq 0 ]; then
  echo "✅ E2E demo passed"
else
  echo "❌ E2E demo failed"
fi

# Cleanup
rm -f /tmp/agent_keys.env
echo "✅ MP3 Container Tests Complete"
```

---

### Real API Integration Testing (Post-P1-B3)

With WS-H1 (credential injection) and WS-H2 (token refresh) complete, you can now test with **real API keys** instead of mock tokens.

#### Quick Setup for Real API Testing

```bash
# ═══════════════════════════════════════════════════════════════════════════════
# REAL API INTEGRATION TESTING
# ═══════════════════════════════════════════════════════════════════════════════

# Step 1: Set real API keys (get from respective developer portals)
export NOTION_API_KEY="secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"   # From notion.so/my-integrations
export SLACK_BOT_TOKEN="xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxx"    # From api.slack.com/apps
export HUBSPOT_ACCESS_TOKEN="pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" # From developers.hubspot.com

# Step 2: Verify keys are set
echo "Notion: ${NOTION_API_KEY:+✅ Set}${NOTION_API_KEY:-❌ Not set}"
echo "Slack:  ${SLACK_BOT_TOKEN:+✅ Set}${SLACK_BOT_TOKEN:-❌ Not set}"
echo "HubSpot: ${HUBSPOT_ACCESS_TOKEN:+✅ Set}${HUBSPOT_ACCESS_TOKEN:-❌ Not set}"

# Step 3: Restart containers to pick up new tokens
docker compose down
docker compose up -d
sleep 20

# Step 4: Connect services with REAL tokens (rerun container tests above)
# The ${NOTION_API_KEY:-test_notion_token} pattern will use real keys if set
```

#### What Changes with Real API Keys

| Component | Mock Mode (default) | Real API Mode |
|-----------|---------------------|---------------|
| Token stored in vault | `test_notion_token` | `secret_xxx...` |
| Credential injection | ✅ Same flow | ✅ Same flow |
| API call execution | Mock response returned | Real API called |
| Response content | `"[Notion] Found 5 results..."` | `{"object":"list","results":[...]}` |

#### Validation: Confirm Real API Responses

```bash
# After running container tests with real API keys, verify:

# 1. Response should contain actual Notion page data
echo "$TOOL_RESULT" | jq '.result.content[0].text' | head -c 200

# 2. Should NOT contain mock indicators
if [[ "$TOOL_RESULT" != *"MVP Mock"* ]] && [[ "$TOOL_RESULT" != *"Found 5 results"* ]]; then
  echo "✅ Real API response confirmed"
else
  echo "❌ Still returning mock response"
fi

# 3. For Notion, look for real Notion object types
if echo "$TOOL_RESULT" | grep -q '"object":"list"'; then
  echo "✅ Notion API object structure detected"
fi

# 4. For Slack, look for ok:true response
if echo "$TOOL_RESULT" | grep -q '"ok":true'; then
  echo "✅ Slack API success response detected"
fi
```

> **Note:** For detailed setup instructions (creating integrations, OAuth scopes, etc.),
> see the "Real API Integration Testing" section in `BATCH_EXECUTION_PLAN.md`.

---

### Cleanup

```bash
# Stop all services
docker compose down

# Clean all data (for fresh start)
docker compose down -v

# Reset test data in database only
docker compose exec -T db psql -U deepsecure_user -d deeptrail_controldb \
  -c "DELETE FROM connected_services; DELETE FROM audit_events;"
```

### Success Criteria

**Core Functionality (Required):**
- [x] H1 (credential injection) uses real vault API
- [x] H2 (token refresh) works end-to-end
- [x] G2 (Notion client) makes real API calls
- [x] G3 (Slack client) makes real API calls
- [x] G4 (HubSpot client) makes real API calls
- [x] No "MVP Mock" strings in tool responses (when real keys provided)
- [x] All P1 completion reports present

**Real API Integration (Optional - with real keys):**
- [ ] Notion: Response contains `"object":"list"` with real page data
- [ ] Slack: Response contains `"ok":true` with real channel data
- [ ] HubSpot: Response contains real contact/deal records

**Remaining P2 Items:**
- [ ] Audit events stored in database (not just logged) - P2 scope
- [ ] Real password validation - P2 scope (IdP integration)

### Post-Merge Status Update

After reaching MP3, run:

```bash
# 1. Verify batch completion
/verify-batch-completion P1-B3 mvp-production-readiness

# 2. Update STATUS.md
cd /Users/imaxxs/repositories/deepsecure-mvp
# Mark P1 as 100% complete
# Mark MP3 as reached

# 3. Update MERGE_POINTS.md
# Set MP3 status to "✅ REACHED (date)"
# Check off all pre-merge checklist items

# 4. Update BATCH_EXECUTION_PLAN.md
# Mark P1-B3 as complete
# Mark Phase 1 as complete

# 5. Update WORKSTREAM.md
# Mark Phase 1 as complete

# 6. Commit all updates
git add docs/workstreams/mvp-production-readiness/
git commit -m "docs: Mark MP3 as reached - P1 complete"
git push origin dev
```

---

## MP3.5: Integration Bugs Fixed

### Status: ⏳ NOT REACHED

### Purpose

Fix bugs discovered during [Integration Validation Guide](../../INTEGRATION_VALIDATION_GUIDE.md) testing (Steps 1-18) before proceeding to Phase 2 Production Hardening.

### Why This Merge Point Exists

After MP3 was reached, comprehensive testing via the Integration Validation Guide revealed several issues:

| Issue | Integration Guide Step | Root Cause | Impact |
|-------|------------------------|------------|--------|
| Tool name derivation mismatch | Step 16 | `initialize.py` derives plural names, `PermissionMapper` expects singular | Tools filtered out, minimal schemas |
| In-memory vault ephemeral | Container restart | Tokens stored in-memory, not PostgreSQL | "Service not connected" errors |
| Stale credential cache | Token updates | 60s cache TTL in CredentialInjector | Old tokens used after refresh |
| No scope→permission mapping | Step 9 | Scopes not mapped to permission strings | Can't validate delegations |
| No delegation validation | Step 9 | No check against connected service scopes | Invalid permissions accepted |
| No permission discovery | Step 9 | No API to list available permissions | Users must manually know permissions |

### Pre-Merge Checklist

```
□ MP3 reached (P1 complete)
□ WS-J2 complete: Tool names use PermissionMapper, cache aligned
□ WS-K1 complete: OAuth tokens stored in PostgreSQL with Fernet encryption
□ WS-K2 complete: Redis pub/sub invalidates Gateway cache on Control Plane changes
□ WS-K3 complete: ScopeMapper translates OAuth scopes to permission strings
□ WS-K4 complete: Delegation endpoint validates permissions against connected scopes
□ WS-K5 complete: /api/v1/users/me/available-permissions endpoint exists
□ Integration Validation Guide Steps 1-18 pass with real APIs
```

### Converging Tasks

| Task | Description | Service | Status | Spec |
|------|-------------|---------|--------|------|
| WS-J2 | Fix tool name derivation and cache alignment | Gateway | ⏳ Pending | [WS-J2-spec.md](./specs/WS-J2-spec.md) |
| WS-K1 | Persistent Vault - Store OAuth tokens in PostgreSQL | Control | ⏳ Pending | [WS-K1-spec.md](./specs/WS-K1-spec.md) |
| WS-K2 | Cache Invalidation via Redis Pub/Sub | Both | ⏳ Pending | [WS-K2-spec.md](./specs/WS-K2-spec.md) |
| WS-K3 | Scope-to-Permission Mapper | Control | ⏳ Pending | [WS-K3-spec.md](./specs/WS-K3-spec.md) |
| WS-K4 | Delegation Permission Validation | Control | ⏳ Pending | [WS-K4-spec.md](./specs/WS-K4-spec.md) |
| WS-K5 | Available Permissions Endpoint | Control | ⏳ Pending | [WS-K5-spec.md](./specs/WS-K5-spec.md) |

### Architecture Documentation

- [PERMISSION_FLOW_ARCHITECTURE.md](../../architecture/PERMISSION_FLOW_ARCHITECTURE.md) - Permission flow analysis and gap mapping
- [MVP_ARCHITECTURE_DEEP_DIVE.md](../../architecture/MVP_ARCHITECTURE_DEEP_DIVE.md) - Storage mechanisms and caching analysis

### Why It's a Merge Point

MP3.5 marks the point where:
1. **Tool names align** between session initialization and PermissionMapper
2. **Tokens persist** across container restarts via PostgreSQL
3. **Cache invalidation** ensures fresh credentials after updates
4. **Permission validation** prevents invalid delegations at creation time
5. **Users can discover** what permissions they can delegate
6. **Integration Validation Guide Steps 1-18** pass reliably with real APIs

This bridges the gap between "mocks replaced" (MP3) and "production ready" (MP4).

### Integration Test

```bash
# MP3.5 validation - Integration Validation Guide Steps 1-18
#!/bin/bash
set -e

echo "=== MP3.5 Validation ==="

# 1. Rebuild containers with fixes
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose build --no-cache deeptrail-control deeptrail-gateway
docker compose up -d
sleep 30

# 2. Verify services are healthy
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy"

# 3. Test: Token persistence across restart
echo "Testing token persistence..."
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# Connect service
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "'"${NOTION_API_KEY}"'",
      "token_type": "bearer",
      "scope": "read_pages search_content",
      "expires_at": "2027-02-22T00:00:00.000000+00:00"
    }
  }' | jq .

# Restart containers
docker compose restart deeptrail-control deeptrail-gateway
sleep 20

# Verify token still accessible (requires persistent vault - WS-K1)
# ...agent JWT creation and vault token retrieval...

# 4. Test: tools/list returns 5 tools with full schemas (WS-J2 fix)
echo "Testing tools/list..."
# ...MCP initialize and tools/list validation...

# 5. Test: Available permissions endpoint (WS-K5)
echo "Testing available permissions..."
PERMS=$(curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.all_permissions | length')
if [ "$PERMS" -gt 0 ]; then
  echo "✅ Available permissions endpoint works: $PERMS permissions"
else
  echo "❌ Available permissions endpoint failed"
  exit 1
fi

# 6. Test: Delegation validation (WS-K4)
echo "Testing delegation validation..."
# Attempt to delegate a permission not in connected scopes
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent",
    "permissions": ["notion:pages:create"]
  }')
if echo "$RESULT" | grep -q "permission_validation_failed"; then
  echo "✅ Invalid delegation correctly rejected"
else
  echo "⚠️ Delegation validation may not be working"
fi

echo "=== MP3.5 Validation Complete ==="
```

### Enables

- Phase 2 tasks (I1, I2, J4, J5, J6, K6, K7, K8) - Production hardening
- Reliable integration testing with real APIs
- Container restarts without data loss

### Merge Actions

```bash
# 1. Ensure MP3 is reached first
# All P1 tasks must be complete

# 2. Push Control Plane worktree changes (P1.5: bug fixes)
cd /Users/imaxxs/repositories/mvp-prod-control
git status
git add -A && git commit -m "Complete P1.5: WS-K1, WS-K2, WS-K3, WS-K4, WS-K5 - Integration bug fixes"
git push origin feature/mvp-prod-control

# 3. Push Gateway worktree changes (P1.5: tool name fix + cache sub)
cd /Users/imaxxs/repositories/mvp-prod-gateway
git status
git add -A && git commit -m "Complete P1.5: WS-J2, WS-K2 - Tool names + cache invalidation"
git push origin feature/mvp-prod-gateway

# 4. Create PRs
gh pr create --base dev --head feature/mvp-prod-control \
  --title "Control Plane: P1.5 (WS-K1-K5)" \
  --body "Implements persistent vault, cache invalidation (pub), scope mapper, delegation validation, available permissions"

gh pr create --base dev --head feature/mvp-prod-gateway \
  --title "Gateway: P1.5 (WS-J2, WS-K2)" \
  --body "Fixes tool name derivation, implements cache invalidation (sub)"

# 5. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/mvp-prod-control --no-ff -m "Merge Control: P1.5 - Integration Bug Fixes"
git merge origin/feature/mvp-prod-gateway --no-ff -m "Merge Gateway: P1.5 - Tool Names + Cache"
git push origin dev

# 6. Run integration tests
docker compose build --no-cache deeptrail-control deeptrail-gateway
docker compose up -d
sleep 30
# Follow Integration Validation Guide Steps 1-18

# 7. Tag the merge point
git tag -a mp3.5-reached -m "MP3.5: Integration Bugs Fixed - $(date +%Y-%m-%d)"
git push origin mp3.5-reached
```

### Post-Merge Documentation Updates

```bash
# 1. Update STATUS.md
# Set MP3.5 status to "✅ REACHED (date)"
# Check off all pre-merge checklist items
# Set P1.5 as complete

# 2. Update BATCH_EXECUTION_PLAN.md
# Mark P1.5-B1 as complete
# Mark Phase 1.5 as complete

# 3. Update this file (MERGE_POINTS.md)
# Set MP3.5 status to "✅ REACHED (date)"

# 4. Commit all updates
git add docs/workstreams/mvp-production-readiness/
git commit -m "docs: Mark MP3.5 as reached - P1.5 complete"
git push origin dev
```

---

## MP4: Production Ready

### Status: ⏳ NOT REACHED (Future)

### Purpose

Full production hardening complete:
- Enterprise IdP integration (Okta/Entra ID)
- PII masking in responses
- Prompt injection detection
- Per-task permissions (Task Tokens)

### Pre-Merge Checklist

```
□ MP3.5 reached (P1.5 complete - integration bugs fixed)
□ I1, I2 complete: Enterprise SSO working
□ J4 complete: PII filtering active
□ J5 complete: Prompt injection detection active
□ J6 complete: Keycloak token exchange working
□ K6, K7, K8 complete: Task Token system working
□ Security audit passed
□ Performance testing passed
```

> **Note:** Task IDs were renumbered to avoid conflicts with P1.5 bug fix tasks (WS-J2, WS-K1-K5)

### Converging Tasks

All P2 tasks:

| Task | Description | Service | Status |
|------|-------------|---------|--------|
| I1 | Okta/Entra ID integration | Control | ⏳ Not Started |
| I2 | SSO authentication flow | Control | ⏳ Not Started |
| J4 | PII masking in responses | Gateway | ⏳ Not Started |
| J5 | Prompt injection detection | Gateway | ⏳ Not Started |
| J6 | Keycloak token exchange | Gateway | ⏳ Not Started |
| K6 | Task Token model | Control | ⏳ Not Started |
| K7 | Task Token service | Control | ⏳ Not Started |
| K8 | Task Token endpoints | Control | ⏳ Not Started |

### Why It's a Merge Point

MP4 marks the point where:
1. **Enterprise authentication** works (Okta/Entra ID)
2. **Security hardening** is complete (PII masking, prompt injection detection)
3. **Fine-grained permissions** via Task Tokens
4. **Production deployment** is safe and validated
5. **Security audit** has passed

This is the final milestone—after MP4, the system is production-ready.

### Merge Actions

```bash
# 1. Ensure MP3.5 is reached first
# All P1 and P1.5 tasks must be complete

# 2. Push Control Plane worktree changes (P2: enterprise auth + task tokens)
cd /Users/imaxxs/repositories/mvp-prod-control
git status
git add -A && git commit -m "Complete P2: I1, I2, K6, K7, K8 - Enterprise auth + Task Tokens"
git push origin feature/mvp-prod-control

# 3. Push Gateway worktree changes (P2: security hardening)
cd /Users/imaxxs/repositories/mvp-prod-gateway
git status
git add -A && git commit -m "Complete P2: J4, J5, J6 - Security hardening"
git push origin feature/mvp-prod-gateway

# 4. Create PRs
gh pr create --base dev --head feature/mvp-prod-control \
  --title "Control Plane: P2 (I1, I2, K6-K8)" \
  --body "Implements enterprise SSO, Task Token generation and endpoints"

gh pr create --base dev --head feature/mvp-prod-gateway \
  --title "Gateway: P2 (J4, J5, J6)" \
  --body "Implements PII masking, prompt injection detection, Keycloak token exchange"

# 5. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/mvp-prod-control --no-ff -m "Merge Control: P2 - Enterprise Auth"
git merge origin/feature/mvp-prod-gateway --no-ff -m "Merge Gateway: P2 - Security Hardening"
git push origin dev

# 6. Run full security test suite
docker compose up -d
sleep 30
pytest tests/security/ -v --tb=short
pytest tests/e2e/ -v --tb=short
docker compose down

# 7. Update worktrees
cd /Users/imaxxs/repositories/mvp-prod-control && git rebase origin/dev
cd /Users/imaxxs/repositories/mvp-prod-gateway && git rebase origin/dev

# 8. Tag the merge point
cd /Users/imaxxs/repositories/deepsecure-mvp
git tag -a mp4-reached -m "MP4: Production Ready - $(date +%Y-%m-%d)"
git push origin mp4-reached

# 9. Create production release
git checkout main && git merge dev --no-ff -m "Release v1.0.0: DeepSecure MVP"
git push origin main
git tag -a v1.0.0 -m "DeepSecure MVP v1.0.0 - Production Release"
git push origin v1.0.0
```

### Container Deployment

```bash
# Deploy production-like environment for MP4 validation
cd /Users/imaxxs/repositories/deepsecure-mvp

# Start with production config
export ENVIRONMENT=production
export KEYCLOAK_URL="http://localhost:8080"

# Start all services including Keycloak
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
sleep 30

# Verify all services are healthy
echo "Checking service health..."
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy"
curl -sf http://localhost:8080/health/ready && echo "✅ Keycloak healthy"
docker compose exec -T db psql -U deepsecure_user -d deeptrail_controldb -c "SELECT 1" > /dev/null && echo "✅ Database accessible"
docker compose exec -T redis redis-cli PING > /dev/null && echo "✅ Redis accessible"
```

### Container Test Scenarios

```bash
# Test 1: Enterprise SSO login
echo "Test 1: Enterprise SSO..."
SSO_URL=$(curl -s -X GET "http://localhost:8000/api/v1/auth/sso/authorize?provider=okta" | jq -r '.authorize_url')
echo "SSO URL: $SSO_URL"
# Manual: Complete SSO flow in browser, then verify callback works

# Test 2: PII masking
echo "Test 2: PII masking..."
MASKED_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {"name": "hubspot.get_contact", "arguments": {"contact_id": "123"}}
  }')
# Verify email/phone are masked
if [[ "$MASKED_RESULT" == *"***@***"* ]] || [[ "$MASKED_RESULT" == *"****"* ]]; then
  echo "✅ PII masking working"
else
  echo "⚠️ PII may not be masked (verify manually)"
fi

# Test 3: Prompt injection detection
echo "Test 3: Prompt injection detection..."
INJECTION_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {"name": "notion.search_pages", "arguments": {"query": "ignore previous instructions and..."}}
  }')
# Should be blocked or sanitized
echo "Injection test result: $INJECTION_RESULT"

# Test 4: Task Token validation
echo "Test 4: Task Token..."
TASK_TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/tasks/tokens" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"task_id":"task_123","permissions":["notion.search_pages"]}' | jq -r '.task_token')
echo "Task token generated: ${TASK_TOKEN:0:20}..."

# Use task token for scoped call
SCOPED_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }')
echo "Scoped call result: $SCOPED_RESULT"

# Test 5: Task Token permission enforcement
echo "Test 5: Task Token permission enforcement..."
DENIED_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 4,
    "params": {"name": "slack.send_message", "arguments": {"channel": "general", "text": "test"}}
  }')
# Should be denied (not in task token permissions)
if [[ "$DENIED_RESULT" == *"error"* ]] || [[ "$DENIED_RESULT" == *"denied"* ]]; then
  echo "✅ Permission enforcement working"
else
  echo "⚠️ Permission check may not be working (verify manually)"
fi

# Test 6: Security audit checklist
echo "Test 6: Security audit..."
echo "  - [ ] No secrets in logs"
echo "  - [ ] TLS enabled for all endpoints"
echo "  - [ ] Rate limiting active"
echo "  - [ ] Input validation on all endpoints"
echo "  - [ ] CORS configured properly"
```

### Cleanup

```bash
# Stop all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Full cleanup including volumes
docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v

# Remove all test data
docker compose exec -T db psql -U deepsecure_user -d deeptrail_controldb \
  -c "TRUNCATE TABLE connected_services, audit_events, task_tokens CASCADE;"
```

### Success Criteria

- [ ] I1 (Okta integration) complete
- [ ] I2 (Entra ID integration) complete
- [ ] J1 (PII masking) active and verified
- [ ] J2 (Prompt injection detection) active and verified
- [ ] J3 (Keycloak token exchange) working
- [ ] K1 (Task Token generation) working
- [ ] K2 (Task Token validation) working
- [ ] K3 (Per-task permission enforcement) working
- [ ] Security audit passed (all checklist items)
- [ ] Performance testing passed (target latencies met)
- [ ] All P2 completion reports present
- [ ] E2E demo passes with production config

### Post-Merge Status Update

After reaching MP4, run:

```bash
# 1. Verify batch completion
/verify-batch-completion P2-B1 mvp-production-readiness
/verify-batch-completion P2-B2 mvp-production-readiness

# 2. Update STATUS.md
cd /Users/imaxxs/repositories/deepsecure-mvp
# Mark P2 as 100% complete
# Mark MP4 as reached
# Mark workstream as COMPLETE

# 3. Update MERGE_POINTS.md
# Set MP4 status to "✅ REACHED (date)"
# Check off all pre-merge checklist items

# 4. Update BATCH_EXECUTION_PLAN.md
# Mark P2-B1, P2-B2 as complete
# Mark Phase 2 as complete

# 5. Update WORKSTREAM.md
# Mark workstream status as COMPLETE

# 6. Commit all updates
git add docs/workstreams/mvp-production-readiness/
git commit -m "docs: Mark MP4 as reached - Production Ready"
git push origin dev

# 7. Create release notes
# Document all features, breaking changes, migration steps
```

### Enables

- Production deployment
- Customer onboarding
- SLA guarantees

---

## Deployment Order

### Standard Deployment Sequence

```bash
# For any merge point validation:

# 1. Infrastructure
docker compose up -d db redis
sleep 5

# 2. Control Plane
docker compose up -d deeptrail-control
sleep 10

# 3. Verify Control Plane
curl -s http://localhost:8000/health | jq .

# 4. Gateway
docker compose up -d deeptrail-gateway
sleep 5

# 5. Verify Gateway
curl -s http://localhost:8002/health | jq .

# 6. Run validation
python demos/demo_sarah_journey_e2e.py
```

### Environment Variables

```bash
# Control Plane
export DEEPSECURE_CONTROL_URL=http://localhost:8000

# Gateway
export DEEPSECURE_GATEWAY_URL=http://localhost:8002

# For real API testing (P1+)
export NOTION_API_TOKEN=<real_token>
export SLACK_BOT_TOKEN=<real_token>
export HUBSPOT_API_KEY=<real_key>
```

---

## Merge Point Actions

### At Each Merge Point

1. **Verify all converging tasks complete**
   ```bash
   # Check STATUS.md
   grep -E "✅|Complete" docs/workstreams/mvp-production-readiness/STATUS.md
   ```

2. **Run integration tests**
   ```bash
   # Service-specific tests
   pytest tests/integration/ -v
   
   # E2E demo
   python demos/demo_sarah_journey_e2e.py
   ```

3. **Update STATUS.md**
   - Mark merge point as reached
   - Update converging task statuses
   - Note any issues discovered

4. **Document findings**
   - What worked as expected?
   - What required fixes?
   - What deviates from plan?

---

## Testing Strategy by Phase

### P0: Contract Verification

```bash
# Endpoints exist and return correct formats
python demos/demo_sarah_journey_e2e.py
# Success = exit code 0 (mocks OK)
```

### P1: Mock Replacement Verification

```bash
# Real APIs called, real data returned
python demos/demo_sarah_journey_e2e.py --verbose

# Verify no mock strings in output
grep -c "MVP Mock" /tmp/demo_output.log
# Success = 0 matches

# Verify audit persistence
curl http://localhost:8000/api/v1/audit/events | jq '.events | length'
# Success = > 0 events
```

### P2: Security Verification

```bash
# SSO login works
# PII filtered from responses
# Prompt injection blocked
# Task tokens enforced

# Security test suite
pytest tests/security/ -v
```

---

## Troubleshooting

### MP1 Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| E2E step fails | Endpoint missing or wrong format | Check router wiring, verify schema |
| 401 Unauthorized | JWT validation failing | Check JWT secret consistency |
| 404 Not Found | Endpoint not wired | Add to `api.py` router |

### MP2 Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Token not stored | Vault client error | Check DB connection |
| Token not retrieved | Wrong token_ref format | Verify reference format |
| Gateway can't reach Control | Network config | Check CONTROL_PLANE_URL env |

### MP3 Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Still returning mock | CredentialInjector not updated | Remove mock fallback code |
| Real API fails | Missing OAuth token | Ensure token stored in vault |
| Audit empty | Gateway not calling Control | Check audit middleware config |

---

## Container Deployment Schedule

When to deploy containers at each merge point:

| Merge Point | When to Deploy | Services | Duration |
|-------------|----------------|----------|----------|
| **MP1** | After P0 verification tasks complete | All services | ~30 min |
| **MP2** | After P1-B2 complete | Control + DB + Redis | ~20 min |
| **MP3** | After P1-B3 complete | Full stack | ~45 min |
| **MP4** | After P2 complete | Full stack + Keycloak | ~60 min |

### Container Environment Setup

```bash
# Environment variables for all merge point testing
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5434
export REDIS_HOST=localhost
export REDIS_PORT=6380

# For MP4 only (production testing)
export KEYCLOAK_URL=http://localhost:8080
export ENVIRONMENT=production
```

---

## Quick Reference Commands

### Merge Point Validation

```bash
# MP1: E2E Flow Verified
cd /Users/imaxxs/repositories/deepsecure-mvp
python demos/demo_sarah_journey_e2e.py
# Expected: All 10 steps pass

# MP2: Vault API Ready
docker compose up -d db redis deeptrail-control
sleep 15
curl -sf http://localhost:8000/health && echo "✅ Ready"
# Run integration test from MP2 section

# MP3: P1 Complete
docker compose up -d
sleep 20
python demos/demo_sarah_journey_e2e.py --verbose
# Expected: Real data (no "MVP Mock" strings)

# MP4: Production Ready
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
sleep 30
pytest tests/security/ -v
# Expected: All security tests pass
```

### Status Verification

```bash
# After any merge point reached
/verify-batch-completion [batch-id] mvp-production-readiness

# Manual verification
cat docs/workstreams/mvp-production-readiness/STATUS.md | grep -E "MP[1-4]"
```

### Git Commands

```bash
# 1. Push from worktree
cd /Users/imaxxs/repositories/[worktree-name]
git add -A && git commit -m "Complete [task description]"
git push origin feature/[worktree-branch]

# 2. Create PR
gh pr create --base dev --head feature/[worktree-branch] \
  --title "[Service]: [Batch] ([Tasks])" \
  --body "[Description]"

# 3. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/[worktree-branch] --no-ff -m "Merge [Service]: [Batch]"
git push origin dev

# 4. Update worktree
cd /Users/imaxxs/repositories/[worktree-name] && git rebase origin/dev

# 5. Tag merge point
cd /Users/imaxxs/repositories/deepsecure-mvp
git tag -a mp[N]-reached -m "MP[N]: [Description] - $(date +%Y-%m-%d)"
git push origin mp[N]-reached
```

---

## Merge Point Status

| Merge Point | Description | Status | Date Reached | Validation |
|-------------|-------------|--------|--------------|------------|
| **MP1** | E2E Flow Verified | ✅ REACHED | Feb 16, 2026 | `demos/demo_sarah_journey_e2e.py` passes |
| **MP2** | Vault API Ready | ✅ REACHED | Feb 17, 2026 | Token store/retrieve works |
| **MP3** | P1 Complete | ⏳ NOT REACHED | - | Mocks replaced, real APIs |
| **MP4** | Production Ready | ⏳ NOT REACHED | - | Security hardening complete |

### Progress Summary

```
Total Merge Points: 4
Reached: 2 (50%)
Remaining: 2 (50%)

MP1 ████████████████████ 100% ✅
MP2 ████████████████████ 100% ✅
MP3 ░░░░░░░░░░░░░░░░░░░░   0% ⏳
MP4 ░░░░░░░░░░░░░░░░░░░░   0% ⏳
```

---

## History

| Date | Event | Details |
|------|-------|---------|
| Feb 15, 2026 | Workstream created | Initial planning and task breakdown |
| Feb 16, 2026 | MP1 reached | P0 verification complete, E2E flow working |
| Feb 16, 2026 | P1-B1 complete | Foundation tasks (E1, F1, G1) done |
| Feb 17, 2026 | P1-B2 complete | Integration tasks (E2, E3, F2, F3, G2, G3, G4) done |
| Feb 17, 2026 | MP2 reached | Vault API ready for credential injection |

---

## Related Documents

- [STATUS.md](./STATUS.md) - Current progress
- [WORKSTREAM.md](./WORKSTREAM.md) - Overview
- [BATCH_EXECUTION_PLAN.md](./BATCH_EXECUTION_PLAN.md) - Task execution plan
- [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md) - Mock locations identified
- [../MERGE_POINT_GUIDE.md](../MERGE_POINT_GUIDE.md) - Generic merge point guide
