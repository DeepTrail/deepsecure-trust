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

---

## MP2: Vault API Ready

### Status: ⏳ NOT REACHED

### Purpose

Real OAuth token storage and retrieval working between Control Plane and Gateway.

### Pre-Merge Checklist

```
□ E1 complete: Vault client enhanced for token storage
□ E2 complete: Vault token retrieval endpoint exists
□ E3 complete: Vault token refresh endpoint exists
□ Unit tests pass for vault operations
□ Integration test: Store token → Retrieve token → Verify match
```

### Converging Tasks

| Task | Description | Service | Status |
|------|-------------|---------|--------|
| E1 | Enhance vault client | Control | ⏳ Not Started |
| E2 | Token retrieval endpoint | Control | ⏳ Not Started |
| E3 | Token refresh endpoint | Control | ⏳ Not Started |

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

All P2 tasks (I*, J*, K*)

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

## Related Documents

- [STATUS.md](./STATUS.md) - Current progress
- [WORKSTREAM.md](./WORKSTREAM.md) - Overview
- [BATCH_EXECUTION_PLAN.md](./BATCH_EXECUTION_PLAN.md) - Task execution plan
- [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md) - Mock locations identified
