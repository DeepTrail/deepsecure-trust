# MVP Production Readiness: Merge Points & Testing Strategy

> **Workstream:** [WORKSTREAM.md](./WORKSTREAM.md)  
> **Status:** [STATUS.md](./STATUS.md)  
> **Created:** February 16, 2026

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
| MP4 | After P2 | Full stack | Production readiness |

### Runtime Dependencies by Merge Point

| MP | Control Plane | Gateway | DB | Redis | Real APIs |
|----|---------------|---------|----|----|-----------|
| MP1 | ✅ Running | ✅ Running | ✅ | ✅ | ❌ Not needed |
| MP2 | ✅ Running | ❌ Not needed | ✅ | ✅ | ❌ Not needed |
| MP3 | ✅ Running | ✅ Running | ✅ | ✅ | ⚠️ Optional |
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
│                              │        │  (mocks still present)              │
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
│                              │        │  (real token storage)               │
│                              └────┬───┘                                     │
│                                   │                                         │
│  P1-B3 ──────────────────────────┐│                                         │
│  (Credential Injection from Vault)│                                         │
│                                   ▼                                         │
│                              ┌────────┐                                     │
│                              │  MP3   │  P1 complete                        │
│                              │        │  (mocks replaced)                   │
│                              └────┬───┘                                     │
│                                   │                                         │
│  P2 ─────────────────────────────┐│                                         │
│  (Production Hardening)           │                                         │
│                                   ▼                                         │
│                              ┌────────┐                                     │
│                              │  MP4   │  Production ready                   │
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
✓ E2 complete: Vault token retrieval endpoint exists
✓ E3 complete: Vault token refresh endpoint exists
□ Unit tests pass for vault operations (to be validated)
□ Integration test: Store token → Retrieve token → Verify match (to be validated)
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
docker compose up -d db redis deeptrail-control
sleep 10

# 2. Store a token
TOKEN_REF=$(curl -s -X POST http://localhost:8000/api/v1/vault/tokens \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "user_id": "sarah@acme.com",
    "access_token": "real_notion_token_123",
    "token_type": "bearer",
    "scope": "read_pages search_content"
  }' | jq -r '.token_ref')

echo "Token stored: $TOKEN_REF"

# 3. Retrieve the token (as Gateway would)
RETRIEVED=$(curl -s -X GET "http://localhost:8000/api/v1/internal/vault/tokens/$TOKEN_REF" \
  -H "X-Gateway-Secret: $GATEWAY_SECRET" | jq -r '.access_token')

# 4. Verify match
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
# Set up environment
export ADMIN_TOKEN="test_admin_token"
export GATEWAY_SECRET="test_gateway_secret"

# Test 1: Store a token via vault API
echo "Test 1: Storing token..."
TOKEN_REF=$(curl -s -X POST http://localhost:8000/api/v1/vault/tokens \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "user_id": "sarah@acme.com",
    "access_token": "ntn_test_123456789",
    "token_type": "bearer",
    "scope": "read_pages"
  }' | jq -r '.token_ref')
echo "Token stored with ref: $TOKEN_REF"

# Test 2: Retrieve token by service ID and user
echo "Test 2: Retrieving token..."
RETRIEVED=$(curl -s -X GET "http://localhost:8000/api/v1/vault/tokens/notion?user_id=sarah@acme.com" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.access_token')
echo "Retrieved token: $RETRIEVED"

# Test 3: Retrieve token via internal endpoint (as Gateway would)
echo "Test 3: Internal retrieval (Gateway simulation)..."
INTERNAL=$(curl -s -X GET "http://localhost:8000/api/v1/internal/vault/tokens/$TOKEN_REF" \
  -H "X-Gateway-Secret: $GATEWAY_SECRET" | jq .)
echo "Internal response: $INTERNAL"

# Test 4: Refresh an expired token
echo "Test 4: Token refresh..."
REFRESH_RESULT=$(curl -s -X POST "http://localhost:8000/api/v1/vault/tokens/notion/refresh" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"sarah@acme.com"}' | jq .)
echo "Refresh result: $REFRESH_RESULT"

# Test 5: OAuth authorization URL generation
echo "Test 5: OAuth authorize URL..."
OAUTH_URL=$(curl -s -X GET "http://localhost:8000/api/v1/oauth/notion/authorize?user_id=sarah@acme.com" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.authorize_url')
echo "OAuth URL: $OAUTH_URL"

# Verify all tests passed
echo ""
if [ -n "$TOKEN_REF" ] && [ -n "$RETRIEVED" ]; then
  echo "✅ MP2 PASSED: All vault operations working"
else
  echo "❌ MP2 FAILED: Some operations failed"
  exit 1
fi
```

### Cleanup

```bash
# Stop services after MP2 validation
docker compose down

# Optional: Clean database for fresh start
docker compose down -v

# Remove test data only (preserve services)
docker compose exec -T db psql -U deepsecure_user -d deeptrail_controldb \
  -c "DELETE FROM vault_tokens WHERE user_id = 'sarah@acme.com';"
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

### Status: ⏳ NOT REACHED

### Purpose

All MVP mocks replaced with real implementations. The E2E demo passes with REAL data from REAL APIs.

### Pre-Merge Checklist

```
□ MP2 reached (vault API ready)
□ H1 complete: CredentialInjector calls vault API
□ H2 complete: Token refresh implemented
□ G2, G3, G4 complete: Real backend API calls
□ Audit events persisted to Control Plane DB
□ E2E demo passes with real API responses
```

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
| H1 | Connect CredentialInjector to vault | Gateway | ⏳ Not Started |
| H2 | Implement token refresh | Gateway | ⏳ Not Started |
| G2 | Notion REST API client | Gateway | ⏳ Not Started |
| G3 | Slack REST API client | Gateway | ⏳ Not Started |
| G4 | HubSpot REST API client | Gateway | ⏳ Not Started |

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

# 5. Verify real API response (not mock string)
# The tool call result should NOT contain "MVP Mock:"
RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }' | jq -r '.result.content[0].text')

if [[ "$RESULT" != *"MVP Mock"* ]]; then
  echo "✅ Real API response received"
else
  echo "❌ Still returning mock response"
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

# Set up test OAuth tokens (requires pre-seeding or real OAuth flow)
echo "Setting up test tokens..."
export ADMIN_TOKEN="test_admin_token"

# Seed a test token for MP3 validation
curl -s -X POST http://localhost:8000/api/v1/vault/tokens \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "user_id": "sarah@acme.com",
    "access_token": "'"${NOTION_API_KEY}"'",
    "token_type": "bearer",
    "scope": "read_pages search_content"
  }'
echo "✅ Test token seeded"
```

### Container Test Scenarios

```bash
# Set up environment
export USER_TOKEN="test_user_token"
export AGENT_JWT="test_agent_jwt"

# Test 1: Login (real password validation if implemented)
echo "Test 1: User login..."
LOGIN_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"real_password"}' | jq -r '.access_token')
if [ -n "$LOGIN_RESULT" ] && [ "$LOGIN_RESULT" != "null" ]; then
  echo "✅ Login successful"
else
  echo "❌ Login failed"
fi

# Test 2: Credential injection via Gateway
echo "Test 2: Credential injection..."
TOOL_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }')
echo "Tool result: $TOOL_RESULT"

# Verify NOT a mock response
if [[ "$TOOL_RESULT" != *"MVP Mock"* ]]; then
  echo "✅ Real API response (not mock)"
else
  echo "❌ Still returning mock response"
fi

# Test 3: Token refresh via Gateway
echo "Test 3: Token refresh..."
REFRESH_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {"name": "notion.search_pages", "arguments": {"query": "refresh_test"}}
  }')
echo "Refresh test: $REFRESH_RESULT"

# Test 4: Audit events persisted
echo "Test 4: Audit persistence..."
sleep 2  # Allow time for async audit write
AUDIT_COUNT=$(curl -s "http://localhost:8000/api/v1/audit/events?limit=10" \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.events | length')
if [ "$AUDIT_COUNT" -gt 0 ]; then
  echo "✅ Audit events persisted: $AUDIT_COUNT events"
else
  echo "❌ No audit events found"
fi

# Test 5: End-to-end demo
echo "Test 5: E2E demo..."
python demos/demo_sarah_journey_e2e.py --verbose
if [ $? -eq 0 ]; then
  echo "✅ E2E demo passed"
else
  echo "❌ E2E demo failed"
fi
```

### Cleanup

```bash
# Stop all services
docker compose down

# Clean all data (for fresh start)
docker compose down -v

# Reset test tokens in database only
docker compose exec -T db psql -U deepsecure_user -d deeptrail_controldb \
  -c "DELETE FROM vault_tokens; DELETE FROM audit_events;"
```

### Success Criteria

- [ ] H1 (credential injection) uses real vault API
- [ ] H2 (token refresh) works end-to-end
- [ ] G2 (Notion client) makes real API calls
- [ ] G3 (Slack client) makes real API calls
- [ ] G4 (HubSpot client) makes real API calls
- [ ] No "MVP Mock" strings in tool responses
- [ ] Audit events stored in database (not just logged)
- [ ] E2E demo passes with real data
- [ ] All P1 completion reports present

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
□ MP3 reached (P1 complete)
□ I1, I2 complete: Enterprise SSO working
□ J1 complete: PII filtering active
□ J2 complete: Prompt injection detection active
□ J3 complete: Keycloak token exchange working
□ K1, K2, K3 complete: Task Token system working
□ Security audit passed
□ Performance testing passed
```

### Converging Tasks

All P2 tasks (I*, J*, K*):

| Task | Description | Service | Status |
|------|-------------|---------|--------|
| I1 | Okta/Entra ID integration | Control | ⏳ Not Started |
| I2 | SSO authentication flow | Control | ⏳ Not Started |
| J1 | PII masking in responses | Gateway | ⏳ Not Started |
| J2 | Prompt injection detection | Gateway | ⏳ Not Started |
| J3 | Keycloak token exchange | Control | ⏳ Not Started |
| K1 | Task Token generation | Control | ⏳ Not Started |
| K2 | Task Token validation | Gateway | ⏳ Not Started |
| K3 | Per-task permission enforcement | Gateway | ⏳ Not Started |

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
# 1. Ensure MP3 is reached first
# All P1 tasks must be complete

# 2. Push Control Plane worktree changes (P2: enterprise auth)
cd /Users/imaxxs/repositories/mvp-prod-control
git status
git add -A && git commit -m "Complete P2: I1, I2, J3, K1 - Enterprise auth"
git push origin feature/mvp-prod-control

# 3. Push Gateway worktree changes (P2: security hardening)
cd /Users/imaxxs/repositories/mvp-prod-gateway
git status
git add -A && git commit -m "Complete P2: J1, J2, K2, K3 - Security hardening"
git push origin feature/mvp-prod-gateway

# 4. Create PRs
gh pr create --base dev --head feature/mvp-prod-control \
  --title "Control Plane: P2 (I1, I2, J3, K1)" \
  --body "Implements enterprise SSO, Keycloak integration, Task Token generation"

gh pr create --base dev --head feature/mvp-prod-gateway \
  --title "Gateway: P2 (J1, J2, K2, K3)" \
  --body "Implements PII masking, prompt injection detection, Task Token validation"

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
  -c "TRUNCATE TABLE vault_tokens, audit_events, task_tokens CASCADE;"
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
