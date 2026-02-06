# Virtual MCP Server MVP: Merge Points & Testing Strategy

> **Workstream:** [WORKSTREAM.md](./WORKSTREAM.md)
>
> **Status:** [STATUS.md](./STATUS.md)
>
> **Last Updated:** February 6, 2026

---

## Overview

This document defines the merge point actions and testing strategy for the Virtual MCP Server MVP implementation. Merge points are synchronization gates where parallel workstreams converge before dependent tasks can begin.

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
│  Example: E3 (audit middleware) needs E2 (audit service) API contract       │
│           to know endpoint format: POST /api/v1/audit/events                │
│                                                                              │
│  RUNTIME DEPENDENCY (Deployment-level)                                      │
│  ────────────────────────────────────                                       │
│  • Task needs another service RUNNING for integration testing               │
│  • Does NOT block task from starting                                        │
│  • Resolved at MERGE POINTS when services are deployed together             │
│  • Development proceeds with mocks/local fallbacks                          │
│                                                                              │
│  Example: E3 needs Control Plane running to POST audit events               │
│           During development, E3 logs locally instead                       │
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

## Service Deployment Order

At each merge point, services must be deployed in a specific order to ensure dependencies are available.

### General Deployment Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DEPLOYMENT ORDER (General)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. INFRASTRUCTURE                                                          │
│     └── Database (PostgreSQL)                                               │
│     └── Cache (Redis)                                                       │
│     └── Message Queue (if applicable)                                       │
│                                                                              │
│  2. CONTROL PLANE                                                           │
│     └── Provides: User auth, agent auth, delegation, audit logging          │
│     └── Health check: GET /health → 200                                     │
│     └── Depends on: Database, Redis                                         │
│                                                                              │
│  3. GATEWAY                                                                 │
│     └── Provides: MCP protocol, tool routing, credential injection          │
│     └── Health check: GET /health → 200                                     │
│     └── Depends on: Control Plane (for JWT validation, audit logging)       │
│                                                                              │
│  4. BACKEND MCP SERVERS (if needed for testing)                             │
│     └── Notion, Slack, HubSpot mock servers                                 │
│     └── Used for integration testing                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Docker Compose Deployment Commands

```bash
# Standard deployment order for all merge points:

# Step 1: Start infrastructure
docker compose up -d db redis
sleep 5  # Wait for DB to initialize

# Step 2: Start Control Plane
docker compose up -d deeptrail-control
sleep 10  # Wait for Control Plane to be healthy

# Step 3: Verify Control Plane health
curl -s http://localhost:8000/health | jq .
# Expected: {"status": "healthy", ...}

# Step 4: Start Gateway
docker compose up -d deeptrail-gateway
sleep 5  # Wait for Gateway to be healthy

# Step 5: Verify Gateway health
curl -s http://localhost:8002/health | jq .
# Expected: {"status": "healthy", ...}

# Step 6: Verify cross-service connectivity
curl -s http://localhost:8002/health/dependencies | jq .
# Expected: {"control_plane": "connected", ...}
```

### Environment Configuration

Set these environment variables before running integration tests:

```bash
# Control Plane
export DEEPSECURE_CONTROL_URL=http://localhost:8000

# Gateway
export DEEPSECURE_GATEWAY_URL=http://localhost:8002

# Database (for Control Plane)
export DATABASE_URL=postgresql://deepsecure_user:password@localhost:5434/deeptrail_controldb

# Redis (for Gateway session cache)
export REDIS_URL=redis://localhost:6380

# JWT Configuration (shared between services)
export JWT_SECRET_KEY=your-test-secret-key
export JWT_ALGORITHM=HS256
```

### Service Health Check Protocol

Before running integration tests, verify all services are healthy:

```bash
#!/bin/bash
# health_check.sh - Run before integration tests

echo "Checking infrastructure..."
docker compose ps db redis | grep -q "running" || exit 1

echo "Checking Control Plane..."
for i in {1..30}; do
  curl -sf http://localhost:8000/health > /dev/null && break
  echo "Waiting for Control Plane... ($i/30)"
  sleep 2
done
curl -sf http://localhost:8000/health || exit 1

echo "Checking Gateway..."
for i in {1..30}; do
  curl -sf http://localhost:8002/health > /dev/null && break
  echo "Waiting for Gateway... ($i/30)"
  sleep 2
done
curl -sf http://localhost:8002/health || exit 1

echo "All services healthy!"
```

---

## Development Mode vs Integration Mode

### Development Mode (In Worktree)

When developing tasks with runtime dependencies that aren't deployed:

| Service Unavailable | Fallback Behavior |
|---------------------|-------------------|
| Control Plane | Use mock responses, local JWT validation |
| Audit Service (E2) | Log locally instead of POSTing |
| Backend MCP Servers | Use mock backends with canned responses |
| Redis | Use in-memory session cache |

**Example: E3 Audit Middleware in Development Mode**

```python
class AuditMiddleware:
    def __init__(self, control_plane_url: str | None = None):
        self.control_plane_url = control_plane_url
    
    async def log_event(self, event: AuditEvent):
        if not self.control_plane_url:
            # Development mode: log locally
            logger.info("AUDIT [dev mode]: %s", event)
            return
        
        # Production mode: POST to Control Plane
        await self._send_to_control_plane(event)
```

### Integration Mode (At Merge Point)

When all services are deployed for merge point testing:

1. **Configure endpoints**: Set `CONTROL_PLANE_URL`, `GATEWAY_URL`
2. **Verify connectivity**: Run health checks
3. **Run integration tests**: `pytest tests/integration/ -v`
4. **Validate cross-service behavior**: Container test scenarios

---

## Merge Point Timeline

```
Batch 1 → Batch 2 → Batch 3 → Batch 4 → MP1 → Batch 5 → MP2 → Batch 6 → MP3 → Batch 7 → Batch 8 → MP4 → Batch 9
                                  ↑              ↑              ↑                            ↑
                            First merge    Auth ready    Execution     Complete system
                                          path ready
```

---

## Merge Points Summary

| Point | After Batch | Converging Tasks | Enables | Integration Type |
|-------|-------------|------------------|---------|------------------|
| **MP1** | Batch 4 | A8 + B3 | C1 | Control Plane ↔ Gateway |
| **MP2** | Batch 5 | B8 + C3 | D1 | Full Auth Flow |
| **MP3** | Batch 6 | C7 + D6 | E3 | Full Execution Path |
| **MP4** | Batch 8 | E3 + backends | F1 | Complete System |

### Runtime Dependencies by Merge Point

This matrix shows which services must be deployed for each merge point's integration testing:

| Merge Point | Database | Redis | Control Plane | Gateway | Mock Backends |
|-------------|----------|-------|---------------|---------|---------------|
| **MP1** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ⬜ Not needed |
| **MP2** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ⬜ Not needed |
| **MP3** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **MP4** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |

### Runtime Dependencies by Task (Cross-Service)

Tasks that have runtime dependencies on services from a different worktree:

| Task | Worktree | Runtime Dependency | Endpoint Needed | Fallback in Dev |
|------|----------|-------------------|-----------------|-----------------|
| C1 | gateway | Control Plane (A8) | `/api/v1/agents/verify` | Mock JWT validation |
| C3 | gateway | Control Plane (JWT) | Shared signing key | Local key validation |
| E3 | gateway | Control Plane (E2) | `/api/v1/audit/events` | Local logging |
| E6 | control | - | - | N/A |
| F1 | both | All services | All endpoints | Cannot run without deployment |

> **Key Insight:** Tasks in the Gateway worktree often have runtime dependencies on Control Plane services. During development, use fallbacks. At merge points, deploy both.

---

## MP1: Control Plane ↔ Gateway Integration

### What's Converging

| Worktree | Task | Description |
|----------|------|-------------|
| vmcp-control | A8 | AgentSessionService - challenge/verify/issue JWT |
| vmcp-gateway | B3 | MCP Session tracking - track backend connections |

### Why It's a Merge Point

- Gateway needs to validate Agent Session JWTs issued by Control Plane
- First time both services need to communicate
- Shared JWT signing/verification keys required

### Pre-Merge Checklist

- [ ] A8 (AgentSessionService) complete with tests passing
- [ ] B3 (MCP Session tracking) complete with tests passing
- [ ] JWT signing key configuration aligned between services
- [ ] Agent Session JWT format documented

### Merge Actions

```bash
# 1. Push worktree branches
cd /Users/imaxxs/repositories/vmcp-control
git add -A && git commit -m "Complete A8: AgentSessionService"
git push origin feature/vmcp-control

cd /Users/imaxxs/repositories/vmcp-gateway
git add -A && git commit -m "Complete B3: MCP Session tracking"
git push origin feature/vmcp-gateway

# 2. Create PRs
gh pr create --base dev --head feature/vmcp-control \
  --title "Control Plane: Batch 1-4 (A1-A8, E1)" \
  --body "Implements user sessions, delegation, and agent authentication"

gh pr create --base dev --head feature/vmcp-gateway \
  --title "Gateway: Batch 1-4 (B1-B8)" \
  --body "Implements MCP protocol, session tracking, tool aggregation"

# 3. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-control --no-ff -m "Merge Control Plane: Batch 1-4"
git merge origin/feature/vmcp-gateway --no-ff -m "Merge Gateway: Batch 1-4"
git push origin dev

# 4. Update worktrees
cd /Users/imaxxs/repositories/vmcp-control && git rebase origin/dev
cd /Users/imaxxs/repositories/vmcp-gateway && git rebase origin/dev
```

### Testing Requirements

| Test Type | Description | Command | Required? |
|-----------|-------------|---------|-----------|
| Unit | Both services pass | `pytest deeptrail-control/tests/ deeptrail-gateway/tests/` | ✅ Yes |
| Integration | Agent auth flow | `pytest tests/integration/test_agent_auth.py` | ✅ Yes |
| Container | Services communicate | See below | ✅ Yes |

### Container Deployment

```bash
# ═══════════════════════════════════════════════════════════════
# MP1 CONTAINER DEPLOYMENT - Control Plane ↔ Gateway Integration
# ═══════════════════════════════════════════════════════════════

# 1. Build services with latest changes
docker compose build deeptrail-control deeptrail-gateway

# 2. Start infrastructure and services
docker compose up -d db redis deeptrail-control deeptrail-gateway

# 3. Wait for services to be healthy
sleep 15
echo "=== Checking Control Plane Health ===" 
curl -s http://localhost:8000/health | jq .
echo "=== Checking Gateway Health ==="
curl -s http://localhost:8002/health | jq .

# 4. Set environment for tests
export DEEPSECURE_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002

# 5. Run MP1 integration tests
pytest tests/integration/test_agent_auth.py -v
pytest tests/integration/test_mcp_session.py -v
```

### Container Test Scenarios

**Scenario 1: Agent Requests Challenge from Control Plane**
```bash
# Register an agent with its Ed25519 public key
# First, generate a key pair (for testing)
AGENT_ID="test-agent-mp1"

# Register agent in Control Plane
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "'$AGENT_ID'",
    "name": "MP1 Test Agent",
    "public_key": "MCowBQYDK2VwAyEA..."
  }'

# Request a challenge
CHALLENGE_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/agents/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "'$AGENT_ID'"}')

echo "Challenge Response: $CHALLENGE_RESPONSE"
CHALLENGE=$(echo $CHALLENGE_RESPONSE | jq -r '.challenge')
echo "Challenge: $CHALLENGE"

# Expected: 
# {
#   "challenge": "base64-encoded-random-bytes",
#   "expires_at": "2026-01-30T12:00:00Z"
# }
```

**Scenario 2: Agent Signs Challenge and Receives JWT**
```bash
# In a real scenario, the agent signs the challenge with its private key
# For testing, we'll use a pre-signed value or mock

# Verify the challenge with signature
VERIFY_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/agents/verify \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "'$AGENT_ID'",
    "challenge": "'$CHALLENGE'",
    "signature": "<ed25519_signature_of_challenge>"
  }')

echo "Verify Response: $VERIFY_RESPONSE"
JWT=$(echo $VERIFY_RESPONSE | jq -r '.jwt')
echo "Agent Session JWT: $JWT"

# Expected:
# {
#   "jwt": "eyJhbGciOiJFZDI1NTE5...",
#   "expires_at": "2026-01-30T13:00:00Z",
#   "agent_id": "test-agent-mp1"
# }

# Decode JWT to inspect claims (without verification)
echo $JWT | cut -d'.' -f2 | base64 -d 2>/dev/null | jq .
# Expected claims: agent_id, delegated_permissions, exp, iat
```

**Scenario 3: Agent Connects to Gateway with JWT**
```bash
# Use the JWT to call Gateway's MCP initialize endpoint
INIT_RESPONSE=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "mp1-test-client",
        "version": "1.0.0"
      }
    }
  }')

echo "Initialize Response: $INIT_RESPONSE"

# Expected:
# {
#   "jsonrpc": "2.0",
#   "id": 1,
#   "result": {
#     "protocolVersion": "2024-11-05",
#     "capabilities": {"tools": {}},
#     "serverInfo": {"name": "deepsecure-gateway", "version": "0.1.0"}
#   }
# }
```

**Scenario 4: Gateway Validates JWT and Creates MCP Sessions**
```bash
# Verify that Gateway created MCP session for the agent
# Check gateway logs for session creation
docker compose logs deeptrail-gateway --tail=20 | grep -i "session\|jwt\|agent"

# Expected log entries:
# - "JWT validated for agent: test-agent-mp1"
# - "MCP session created: <session_id>"
# - "Backend sessions initialized"

# Try another MCP request to verify session persists
curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2,
    "params": {}
  }'

# Expected: tools/list response (may be empty if no backends configured yet)
```

**Scenario 5: JWT Validation Rejects Invalid Tokens**
```bash
# Test with no Authorization header
curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {}}'

# Expected: 401 Unauthorized

# Test with invalid JWT
curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid.jwt.token" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {}}'

# Expected: 401 Unauthorized with "Invalid token" message

# Test with malformed Authorization header
curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: NotBearer $JWT" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {}}'

# Expected: 401 Unauthorized
```

**Scenario 6: Verify Shared JWT Signing Key Configuration**
```bash
# Both services must use the same JWT signing key
# Check Control Plane's JWT configuration
docker compose exec deeptrail-control env | grep -i jwt

# Check Gateway's JWT configuration  
docker compose exec deeptrail-gateway env | grep -i jwt

# Both should reference the same JWT_SECRET_KEY or public key path

# Verify by:
# 1. Getting a JWT from Control Plane
# 2. Using it on Gateway
# If Gateway accepts the JWT, keys are aligned
```

### Cleanup

```bash
# Stop and remove containers
docker compose down

# Full cleanup including volumes (database data)
docker compose down -v
```

### Success Criteria

- [ ] Agent can authenticate with Control Plane
- [ ] Control Plane issues valid Agent Session JWT
- [ ] Gateway accepts and validates JWT
- [ ] MCP sessions created for connected backends
- [ ] Integration tests pass
- [ ] Container deployment works

### Post-Merge Status Update

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

Update WORKSTREAM.md:
```markdown
| **MP1** | A8 + B3 | C1 (agent auth) | ✅ `complete` |
```

---

## MP2: Full Auth Flow Ready

### What's Converging

| Worktree | Task | Description |
|----------|------|-------------|
| vmcp-gateway | B8 | Tool aggregator - combine tools from backends |
| vmcp-gateway | C3 | JWT validation middleware - validate on every request |

### Why It's a Merge Point

- Complete authentication and authorization pipeline
- tools/list now fully functional with permission filtering
- Ready to implement backend connectors

### Pre-Merge Checklist

- [ ] B8 (Tool aggregator) complete
- [ ] C3 (JWT validation middleware) complete
- [ ] C4 (Tool→permission mapper) complete
- [ ] D3, D4, D5 (Backend clients) complete
- [ ] D6 (Backend router) complete
- [ ] tools/list returns filtered, namespaced tools

### Merge Actions

```bash
# 1. Ensure vmcp-gateway has all Batch 5 commits
cd /Users/imaxxs/repositories/vmcp-gateway
git status
git add -A && git commit -m "Complete Batch 5: C3, C4, D3-D6"
git push origin feature/vmcp-gateway

# 2. Create PR for Batch 5 changes
gh pr create --base dev --head feature/vmcp-gateway \
  --title "Gateway: Batch 5 (C3, C4, D3-D6)" \
  --body "Implements JWT validation, permission mapping, backend clients and router"

# 3. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-gateway --no-ff -m "Merge Gateway: Batch 5"
git push origin dev

# 4. Update worktree
cd /Users/imaxxs/repositories/vmcp-gateway && git rebase origin/dev
```

### Testing Requirements

| Test Type | Description | Command | Required? |
|-----------|-------------|---------|-----------|
| Unit | Aggregator, middleware | `pytest deeptrail-gateway/tests/` | ✅ Yes |
| Integration | Auth → tools/list flow | `pytest tests/integration/test_tools_list.py` | ✅ Yes |
| Container | Full auth with real JWT | See below | ✅ Yes |

### Container Deployment

```bash
# ═══════════════════════════════════════════════════════════════
# MP2 CONTAINER DEPLOYMENT - Full Auth Flow Testing
# ═══════════════════════════════════════════════════════════════

# 1. Build services with latest changes
docker compose build deeptrail-control deeptrail-gateway

# 2. Start infrastructure and services
docker compose up -d db redis deeptrail-control deeptrail-gateway

# 3. Wait for services to be healthy
sleep 15
echo "=== Checking Control Plane Health ===" 
curl -s http://localhost:8000/health | jq .
echo "=== Checking Gateway Health ==="
curl -s http://localhost:8002/health | jq .

# 4. Set environment for tests
export DEEPSECURE_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002

# 5. Run MP2 integration tests
pytest tests/integration/test_tools_list.py -v
pytest tests/integration/test_permission_filter.py -v
```

### Container Test Scenarios

**Scenario 1: Agent Authentication and JWT Issuance**
```bash
# Create a test user and agent in Control Plane
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email": "sarah@acme.com", "name": "Sarah"}'

# Register agent with public key
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent-001", "public_key": "<ed25519_public_key>"}'

# Request challenge
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/agents/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent-001"}' | jq -r '.challenge')

# Verify with signature and get JWT
JWT=$(curl -s -X POST http://localhost:8000/api/v1/agents/verify \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"test-agent-001\", \"challenge\": \"$CHALLENGE\", \"signature\": \"<signed_challenge>\"}" \
  | jq -r '.jwt')

echo "Agent JWT: $JWT"
```

**Scenario 2: Gateway MCP Initialize**
```bash
# Connect to Gateway with JWT and call initialize
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test-client", "version": "1.0.0"}
    }
  }'

# Expected: Server capabilities returned with tools capability
```

**Scenario 3: tools/list with Permission Filtering**
```bash
# Call tools/list - should return only delegated tools
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2,
    "params": {}
  }'

# Expected: Only tools matching agent's delegated_permissions
# Tools should be namespaced: notion.search_pages, slack.post_message
```

**Scenario 4: Verify Namespace Prefixing**
```bash
# Check that tools from different backends have correct prefixes
# notion.search_pages, notion.create_page
# slack.post_message, slack.list_channels
# hubspot.search_contacts, hubspot.create_deal

# Test with undelegated permission - should not see tool
# If agent only has notion:* but not slack:*, slack tools should be hidden
```

**Scenario 5: JWT Validation - Reject Invalid Tokens**
```bash
# Test with invalid JWT - should get 401
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid_jwt_token" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1, "params": {}}'

# Expected: 401 Unauthorized or MCP error

# Test with expired JWT
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $EXPIRED_JWT" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1, "params": {}}'

# Expected: 401 Unauthorized with "token expired" message
```

### Cleanup

```bash
# Stop and remove containers
docker compose down

# Full cleanup including volumes (database data)
docker compose down -v
```

### Success Criteria

- [ ] tools/list returns only delegated tools
- [ ] Tools are namespaced (e.g., `notion.search_pages`)
- [ ] Undelegated tools are hidden
- [ ] JWT validation rejects invalid tokens

### Post-Merge Status Update

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

Update WORKSTREAM.md:
```markdown
| **MP2** | B8 + C3 | D1 (backend connectors) | ✅ `complete` |
```

---

## MP3: Full Execution Path Ready

### What's Converging

| Worktree | Task | Description |
|----------|------|-------------|
| vmcp-gateway | C7 | Credential injection - inject OAuth from vault |
| vmcp-gateway | D6 | Backend router - route to correct backend |

### Why It's a Merge Point

- Complete tools/call execution path
- Credentials injected from vault
- Requests routed to correct backend
- Ready for audit middleware

### Pre-Merge Checklist

- [ ] C5 (Permission filter) complete
- [ ] C6 (Delegation validator) complete
- [ ] C7 (Credential injection) complete
- [ ] D6 (Backend router) complete
- [ ] All backend connectors (D3-D6) complete
- [ ] Vault integration working

### Merge Actions

```bash
# 1. Ensure both worktrees have Batch 6 commits
cd /Users/imaxxs/repositories/vmcp-gateway
git status
git add -A && git commit -m "Complete Batch 6: C5, C6, C7"
git push origin feature/vmcp-gateway

# 2. Create PR for Batch 6 changes
gh pr create --base dev --head feature/vmcp-gateway \
  --title "Gateway: Batch 6 (C5-C7)" \
  --body "Implements permission filter, delegation validator, credential injection"

# 3. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-gateway --no-ff -m "Merge Gateway: Batch 6"
git push origin dev

# 4. Update worktree
cd /Users/imaxxs/repositories/vmcp-gateway && git rebase origin/dev
```

### Testing Requirements

| Test Type | Description | Command | Required? |
|-----------|-------------|---------|-----------|
| Unit | Permission filter, validator, injector | `pytest deeptrail-gateway/tests/middleware/` | ✅ Yes |
| Integration | tools/call with injection | `pytest tests/integration/test_tools_call.py` | ✅ Yes |
| Container | Gateway → Backend flow | See below | ✅ Yes |

### Container Deployment

```bash
# ═══════════════════════════════════════════════════════════════
# MP3 CONTAINER DEPLOYMENT - Full Execution Path Testing
# ═══════════════════════════════════════════════════════════════

# 1. Build services with latest changes
docker compose build deeptrail-control deeptrail-gateway

# 2. Start full stack including mock backends
docker compose up -d db redis deeptrail-control deeptrail-gateway

# 3. Wait for services to be healthy
sleep 15
echo "=== Checking Control Plane Health ===" 
curl -s http://localhost:8000/health | jq .
echo "=== Checking Gateway Health ==="
curl -s http://localhost:8002/health | jq .

# 4. Set environment for tests
export DEEPSECURE_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002

# 5. Run MP3 integration tests
pytest tests/integration/test_tools_call.py -v
pytest tests/integration/test_credential_injection.py -v
pytest tests/integration/test_delegation_validator.py -v
```

### Container Test Scenarios

**Scenario 1: Setup - Create User, Connect Services, Create Delegation**
```bash
# Create user Sarah
USER_ID=$(curl -s -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email": "sarah@acme.com", "name": "Sarah"}' | jq -r '.id')

# Connect Sarah's Notion account (stores OAuth token in vault)
curl -X POST http://localhost:8000/api/v1/users/$USER_ID/services/connect \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {"access_token": "notion_oauth_token_abc123", "token_type": "Bearer"}
  }'

# Create agent and get JWT (see MP2 scenarios for full flow)
# Assume $JWT is set from agent authentication

# Create delegation for agent
curl -X POST http://localhost:8000/api/v1/delegations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -d '{
    "agent_id": "test-agent-001",
    "permissions": ["notion:pages:search", "notion:pages:read"],
    "expires_in": 3600
  }'
```

**Scenario 2: tools/call - Successful Execution with Credential Injection**
```bash
# Agent calls tools/call for a delegated tool
RESPONSE=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {
      "name": "notion.search_pages",
      "arguments": {"query": "meeting notes"}
    }
  }')

echo $RESPONSE | jq .

# Expected: Successful result with search results
# {
#   "jsonrpc": "2.0",
#   "id": 1,
#   "result": {
#     "content": [{"type": "text", "text": "[Notion] Found 5 results..."}],
#     "isError": false
#   }
# }
```

**Scenario 3: Verify Credential Injection (Token Not Visible to Agent)**
```bash
# Check that the response does NOT contain any OAuth tokens
echo $RESPONSE | grep -i "oauth\|access_token\|bearer"
# Expected: No matches - token is never exposed to agent

# Check gateway logs to verify token was injected internally
docker compose logs deeptrail-gateway --tail=20 | grep -i "credential"
# Expected: Log showing "Credentials injected for notion (ref: vault://...)"
```

**Scenario 4: Permission Denied for Non-Delegated Tool**
```bash
# Agent tries to call a tool they don't have permission for
DENIED_RESPONSE=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {
      "name": "slack.post_message",
      "arguments": {"channel": "#general", "text": "Hello"}
    }
  }')

echo $DENIED_RESPONSE | jq .

# Expected: MCP error with permission denied
# {
#   "jsonrpc": "2.0",
#   "id": 2,
#   "error": {
#     "code": -32001,
#     "message": "Permission denied: slack:messages:post required"
#   }
# }
```

**Scenario 5: Backend Routing - Correct Backend Receives Request**
```bash
# Call tools from different backends to verify routing

# Notion tool
curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "id": 3,
       "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}}'

# HubSpot tool (if delegated)
curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "id": 4,
       "params": {"name": "hubspot.search_contacts", "arguments": {"query": "john"}}}'

# Verify in logs that each request went to correct backend
docker compose logs deeptrail-gateway --tail=30 | grep "Forwarding.*to"
```

**Scenario 6: Vault Token Retrieval Failure Handling**
```bash
# Test behavior when vault token is not found or expired
# This tests the fail-closed behavior

# Disconnect Sarah's service (removes token from vault)
curl -X DELETE http://localhost:8000/api/v1/users/$USER_ID/services/notion

# Try to call the tool - should fail gracefully
curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "id": 5,
       "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}}'

# Expected: Error indicating credential not available
# {
#   "jsonrpc": "2.0",
#   "id": 5,
#   "error": {
#     "code": -32003,
#     "message": "Credential not found. User may need to re-authorize."
#   }
# }
```

### Cleanup

```bash
# Stop and remove containers
docker compose down

# Full cleanup including volumes
docker compose down -v
```

### Success Criteria

- [ ] tools/call reaches correct backend
- [ ] OAuth token injected (agent never sees it)
- [ ] Permission denied for non-delegated tools
- [ ] Backend response returned correctly

### Post-Merge Status Update

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

Update WORKSTREAM.md:
```markdown
| **MP3** | C7 + D6 | E3 (audit middleware) | ✅ `complete` |
```

---

## MP4: Complete System Ready

### What's Converging

| Component | Tasks | Description |
|-----------|-------|-------------|
| Audit | E3 | Audit middleware logs all tool calls |
| Backends | D3, D4, D5 | Notion, Slack, HubSpot connectors |

### Why It's a Merge Point

- Complete system ready for E2E testing
- All demos can be validated
- Sarah's full journey (Steps 1-10) testable

### Pre-Merge Checklist

- [ ] E2 (Audit logger service) complete
- [ ] E3 (Audit middleware) complete
- [ ] E4 (Fail-closed security) complete
- [ ] E5 (Constraint checker) complete
- [ ] All backend connectors working
- [ ] F1 (Sarah's Journey E2E test) complete

### Merge Actions

```bash
# 1. Ensure both worktrees have Batch 7-8 commits
cd /Users/imaxxs/repositories/vmcp-control
git status
git add -A && git commit -m "Complete Batch 7-8: E2, E6"
git push origin feature/vmcp-control

cd /Users/imaxxs/repositories/vmcp-gateway
git status
git add -A && git commit -m "Complete Batch 7-8: E3, E4, E5, F1-F4"
git push origin feature/vmcp-gateway

# 2. Create PRs for final batches
gh pr create --base dev --head feature/vmcp-control \
  --title "Control Plane: Batch 7-8 (E2, E6)" \
  --body "Implements audit logging and query API"

gh pr create --base dev --head feature/vmcp-gateway \
  --title "Gateway: Batch 7-8 (E3-E5, F1-F4)" \
  --body "Implements audit middleware, fail-closed, demos 1-4"

# 3. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-control --no-ff -m "Merge Control: Batch 7-8"
git merge origin/feature/vmcp-gateway --no-ff -m "Merge Gateway: Batch 7-8"
git push origin dev

# 4. Update worktrees for final batch
cd /Users/imaxxs/repositories/vmcp-control && git rebase origin/dev
cd /Users/imaxxs/repositories/vmcp-gateway && git rebase origin/dev
```

### Testing Requirements

| Test Type | Description | Command | Required? |
|-----------|-------------|---------|-----------|
| Unit | Audit middleware, fail-closed | `pytest deeptrail-gateway/tests/` | ✅ Yes |
| E2E | Sarah's Journey | `pytest tests/e2e/test_sarah_journey.py` | ✅ Yes |
| Demos | All 6 demos | `./scripts/run_demos.sh` | ✅ Yes |
| Container | Complete system | See below | ✅ Yes |
| Load | Basic performance | `pytest tests/performance/` | Optional |

### Container Deployment

```bash
# ═══════════════════════════════════════════════════════════════
# MP4 CONTAINER DEPLOYMENT - Complete System Testing
# ═══════════════════════════════════════════════════════════════

# 1. Build all services with latest changes
docker compose build

# 2. Start complete system
docker compose up -d

# 3. Wait for all services to be healthy
sleep 20
echo "=== Checking All Services Health ===" 
curl -s http://localhost:8000/health | jq .  # Control Plane
curl -s http://localhost:8002/health | jq .  # Gateway

# 4. Set environment for tests
export DEEPSECURE_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002

# 5. Run full E2E test suite
pytest tests/e2e/test_sarah_journey.py -v
pytest tests/integration/ -v

# 6. Run all demos
./scripts/run_demos.sh
```

### Container Test Scenarios

**Scenario 1: Sarah's Complete Journey (Steps 1-10)**
```bash
# This scenario validates the complete user journey from the design doc

# Step 1: Sarah signs in (Control Plane)
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "sarah@acme.com", "password": "secure_password"}' \
  | jq -r '.token')

# Step 2: Sarah sees her dashboard (mock - not in scope)

# Step 3: Sarah connects Notion & Slack
curl -X POST http://localhost:8000/api/v1/users/sarah/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service_id": "notion", "oauth_token": {"access_token": "notion_token"}}'

curl -X POST http://localhost:8000/api/v1/users/sarah/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service_id": "slack", "oauth_token": {"access_token": "slack_token"}}'

# Step 4: Sarah grants delegation to Agent
DELEGATION=$(curl -s -X POST http://localhost:8000/api/v1/delegations \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "sarahs-ai-assistant",
    "permissions": ["notion:pages:search", "notion:pages:read", "slack:messages:post"],
    "constraints": {"time_range": "9am-5pm", "rate_limit": 100}
  }' | jq -r '.delegation_token')

# Step 5: Agent receives delegation token
echo "Delegation Token: $DELEGATION"

# Step 6: Agent authenticates with Gateway
JWT=$(curl -s -X POST http://localhost:8000/api/v1/agents/verify \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "sarahs-ai-assistant", "delegation_token": "'$DELEGATION'"}' \
  | jq -r '.jwt')

# Step 7: Agent sees delegated tools only (tools/list)
TOOLS=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1, "params": {}}')
echo "Available tools: $(echo $TOOLS | jq '.result.tools[].name')"

# Step 8: Agent executes delegated tool
RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "method": "tools/call", "id": 2,
    "params": {"name": "notion.search_pages", "arguments": {"query": "project updates"}}
  }')
echo "Tool result: $RESULT"

# Step 9: Agent denied on non-delegated tool
DENIED=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "method": "tools/call", "id": 3,
    "params": {"name": "hubspot.create_deal", "arguments": {"name": "New Deal"}}
  }')
echo "Permission denied (expected): $DENIED"

# Step 10: Sarah reviews audit logs
AUDIT=$(curl -s http://localhost:8000/api/v1/audit/events \
  -H "Authorization: Bearer $USER_TOKEN" \
  -G --data-urlencode "agent_id=sarahs-ai-assistant")
echo "Audit events: $(echo $AUDIT | jq '.events | length') events logged"
```

**Scenario 2: Demo 1 - Unified Connection**
```bash
# Agent connects once, sees tools from multiple backends

# Initialize connection
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "id": 1,
       "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                  "clientInfo": {"name": "unified-demo", "version": "1.0"}}}'

# List all tools - should see tools from Notion, Slack, HubSpot in ONE list
TOOLS=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}}')

# Verify multiple backends represented
echo "Notion tools: $(echo $TOOLS | jq '[.result.tools[] | select(.name | startswith("notion."))] | length')"
echo "Slack tools: $(echo $TOOLS | jq '[.result.tools[] | select(.name | startswith("slack."))] | length')"
echo "HubSpot tools: $(echo $TOOLS | jq '[.result.tools[] | select(.name | startswith("hubspot."))] | length')"
```

**Scenario 3: Demo 2 - Filtered Visibility**
```bash
# Agent only sees tools they have permission for

# Create agent with LIMITED permissions (only Notion)
LIMITED_JWT=$(curl -s -X POST http://localhost:8000/api/v1/agents/auth \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "limited-agent", "permissions": ["notion:*"]}' \
  | jq -r '.jwt')

# List tools - should ONLY see Notion tools
FILTERED_TOOLS=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $LIMITED_JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1, "params": {}}')

echo "Tool count: $(echo $FILTERED_TOOLS | jq '.result.tools | length')"
echo "All tools should be notion.*: $(echo $FILTERED_TOOLS | jq '.result.tools[].name')"

# Verify NO Slack or HubSpot tools visible
echo "Slack tools (should be 0): $(echo $FILTERED_TOOLS | jq '[.result.tools[] | select(.name | startswith("slack."))] | length')"
```

**Scenario 4: Demo 3 - Delegation Execution**
```bash
# Agent uses Sarah's credentials but never sees them

# Execute tool
RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "id": 1,
       "params": {"name": "notion.search_pages", "arguments": {"query": "meeting"}}}')

# Verify result doesn't contain tokens
echo $RESULT | grep -c "access_token"  # Should be 0
echo $RESULT | grep -c "oauth"          # Should be 0
echo $RESULT | grep -c "Bearer"         # Should be 0

# Check gateway logs for credential injection
docker compose logs deeptrail-gateway --tail=10 | grep "Credentials injected"
```

**Scenario 5: Demo 4 - Permission Enforcement**
```bash
# Unauthorized tools are blocked at gateway

# Try to call tool without permission
DENIED=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $LIMITED_JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "id": 1,
       "params": {"name": "slack.post_message", "arguments": {"channel": "#general", "text": "test"}}}')

# Verify error response
echo $DENIED | jq '.error.code'     # Should be -32001
echo $DENIED | jq '.error.message'  # Should mention permission denied
```

**Scenario 6: Demo 5 - Unified Audit**
```bash
# All actions logged with attribution

# Make several tool calls
for i in 1 2 3; do
  curl -s -X POST http://localhost:8002/mcp \
    -H "Authorization: Bearer $JWT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc": "2.0", "method": "tools/call", "id": '$i',
         "params": {"name": "notion.search_pages", "arguments": {"query": "test'$i'"}}}'
done

# Query audit log
AUDIT=$(curl -s http://localhost:8000/api/v1/audit/events \
  -H "Authorization: Bearer $USER_TOKEN" \
  -G --data-urlencode "limit=10")

# Verify audit entries
echo "Total events: $(echo $AUDIT | jq '.events | length')"
echo "Event types: $(echo $AUDIT | jq '[.events[].event_type] | unique')"
echo "All have agent_id: $(echo $AUDIT | jq '[.events[] | select(.agent_id != null)] | length')"
echo "All have user_id: $(echo $AUDIT | jq '[.events[] | select(.user_id != null)] | length')"
```

**Scenario 7: Demo 6 - Fail-Closed Security**
```bash
# System fails closed on errors

# Test 1: Invalid JWT - should reject
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer invalid_token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1, "params": {}}'
# Expected: 401 Unauthorized

# Test 2: Expired delegation - should reject
# (Create a delegation with 1 second expiry, wait, then try)

# Test 3: Unknown tool - should reject (fail-closed)
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "id": 1,
       "params": {"name": "unknown.tool", "arguments": {}}}'
# Expected: Error, not allowed through

# Test 4: Service unavailable - should error, not bypass
docker compose stop deeptrail-control
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "id": 1,
       "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}}'
# Expected: Error indicating service unavailable, not silent bypass
docker compose start deeptrail-control
```

### Demo Validation

| Demo | Task | Test Script | Container Command |
|------|------|-------------|-------------------|
| Demo 1: Unified Connection | F2 | `examples/demo_01_unified_connection.py` | See Scenario 2 |
| Demo 2: Filtered Visibility | F3 | `examples/demo_02_filtered_visibility.py` | See Scenario 3 |
| Demo 3: Delegation Execution | F4 | `examples/demo_03_delegation_execution.py` | See Scenario 4 |
| Demo 4: Permission Enforcement | F5 | `examples/demo_04_permission_enforcement.py` | See Scenario 5 |
| Demo 5: Unified Audit | F6 | `examples/demo_05_unified_audit.py` | See Scenario 6 |
| Demo 6: Fail-Closed | F7 | `examples/demo_06_fail_closed.py` | See Scenario 7 |

### Cleanup

```bash
# Stop and remove all containers
docker compose down

# Full cleanup including volumes and networks
docker compose down -v --remove-orphans

# Prune unused images (optional)
docker image prune -f
```

### Success Criteria

- [ ] Sarah's 10-step journey works end-to-end
- [ ] All 6 demos pass
- [ ] Audit logs capture all actions
- [ ] Permission denials logged
- [ ] Fail-closed behavior verified

### Post-Merge Status Update

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

Update WORKSTREAM.md:
```markdown
| **MP4** | E3 + backends | F1 (complete system) | ✅ `complete` |
```

---

## Container Deployment Schedule

| After | Deploy? | Purpose | Services | Scenarios |
|-------|---------|---------|----------|-----------|
| Batch 1 | Optional | Verify MCP parser | Gateway only | Basic JSON-RPC parsing |
| Batch 3 | Optional | Test models/services | Control only | Model/service validation |
| **MP1** | **Required** | Control ↔ Gateway integration | Both services | [6 scenarios](#container-deployment) |
| **MP2** | **Required** | Full auth flow | Both services | [5 scenarios](#container-deployment-1) |
| **MP3** | **Required** | Full execution path | Both + mock backend | [6 scenarios](#container-deployment-2) |
| **MP4** | **Required** | Complete system validation | All services | [7 scenarios + 6 demos](#container-deployment-3) |

### Container Environment Setup

```bash
# Ensure Docker and docker-compose are available
docker --version
docker compose version

# Clone and setup (if needed)
cd /Users/imaxxs/repositories/deepsecure-mvp

# Common environment variables for all merge points
export DEEPSECURE_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export POSTGRES_DB=deeptrail_controldb
export POSTGRES_USER=deepsecure_user
export REDIS_URL=redis://localhost:6380
```

---

## Quick Reference Commands

### Push and Merge

```bash
# Push worktree
git push origin feature/vmcp-control

# Create PR
gh pr create --base dev --head feature/vmcp-control --title "..."

# Merge to dev
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-control --no-ff
git push origin dev
```

### Container Testing

```bash
# Start services
docker compose up -d

# Health check
curl localhost:8000/health && curl localhost:8002/health

# Run tests
pytest -m integration -v

# Logs
docker compose logs -f deeptrail-control deeptrail-gateway

# Teardown
docker compose down -v
```

### Status Sync

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

---

## Merge Point Status

| Point | Status | Merged At | Notes |
|-------|--------|-----------|-------|
| MP1 | ⏸️ Pending | - | After Batch 4 |
| MP2 | ⏸️ Pending | - | After Batch 5 |
| MP3 | ⏸️ Pending | - | After Batch 6 |
| MP4 | ⏸️ Pending | - | After Batch 8 |

---

## History

| Date | Event |
|------|-------|
| Jan 2026 | Document created |
