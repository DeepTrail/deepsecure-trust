# E2E Test Suite

End-to-end tests for the DeepSecure Virtual MCP Server MVP.

## Test Files

| File | Purpose |
|------|---------|
| `test_sarah_journey.py` | Complete 10-step user journey validation |
| `test_fixtures.py` | Test data fixtures and MCP request helpers |
| `conftest.py` | Pytest configuration and shared fixtures |
| `SARAH_JOURNEY_TESTS.md` | Detailed test documentation |

---

## Quick Start

### Unit Tests Only (No Services Required)

```bash
# Run unit/mock tests that don't require live services
pytest tests/e2e/test_sarah_journey.py -v -k "Scenario or mcp_request"
```

### Full E2E Tests (Requires Live Services)

```bash
# Step 1: Start all services
docker compose up -d

# Step 2: Verify services are healthy
curl http://localhost:8000/health  # Control Plane
curl http://localhost:8002/health  # Gateway

# Step 3: Run all E2E tests
pytest tests/e2e/test_sarah_journey.py -v -m e2e

# Step 4: Stop services when done
docker compose down
```

### Complete Journey Only

```bash
# Run just the complete journey test (all 10 steps in sequence)
pytest tests/e2e/test_sarah_journey.py -v -k "complete_sarah_journey"
```

---

## Running Tests by Step

Run specific steps of Sarah's journey:

```bash
# Step 1: Enterprise Registration
pytest tests/e2e/test_sarah_journey.py -v -k "Step01"

# Step 2: Sarah Authenticates
pytest tests/e2e/test_sarah_journey.py -v -k "Step02"

# Step 3: Sarah Connects Services
pytest tests/e2e/test_sarah_journey.py -v -k "Step03"

# Step 4: Sarah Delegates to Agent
pytest tests/e2e/test_sarah_journey.py -v -k "Step04"

# Step 5: Agent Authenticates
pytest tests/e2e/test_sarah_journey.py -v -k "Step05"

# Step 6: Agent Connects to Gateway
pytest tests/e2e/test_sarah_journey.py -v -k "Step06"

# Step 7: Agent Discovers Tools
pytest tests/e2e/test_sarah_journey.py -v -k "Step07"

# Step 8: Agent Executes Tool
pytest tests/e2e/test_sarah_journey.py -v -k "Step08"

# Step 9: Agent Denied
pytest tests/e2e/test_sarah_journey.py -v -k "Step09"

# Step 10: Sarah Reviews Audit
pytest tests/e2e/test_sarah_journey.py -v -k "Step10"
```

---

## Running Tests by Demo Capability

Run tests that validate specific demo value propositions:

### Demo 1: Unified MCP Connection

**What It Proves:** Agent connects to ONE gateway and sees tools from MULTIPLE backends.

```bash
# Tests: Step 6 (MCP Initialize) + Step 7 (Tools List)
pytest tests/e2e/test_sarah_journey.py -v -k "Step06 or Step07"
```

**Related Demo:** `demos/demo_01_unified_connection.py`

---

### Demo 2: Filtered Tool Visibility

**What It Proves:** Agent sees ONLY delegated tools, not all backend tools. 90%+ attack surface reduction.

```bash
# Tests: Step 7 (both tests - filtered tools + limited count)
pytest tests/e2e/test_sarah_journey.py -v -k "Step07"
```

**Expected Behavior:**
- Agent sees ≤15 tools (not 37 from all backends)
- Hidden tools like `notion.delete_page` are NOT visible

**Related Demo:** `demos/demo_02_filtered_visibility.py`

---

### Demo 3: Delegation-Based Execution

**What It Proves:** Sarah consents once, agent uses her credentials safely without seeing them.

```bash
# Tests: Step 4 (Delegation) + Step 8 (Tool Execution)
pytest tests/e2e/test_sarah_journey.py -v -k "Step04 or Step08"
```

**Expected Behavior:**
- Agent calls `notion.search_pages` successfully
- Response contains NO OAuth tokens

**Related Demo:** `demos/demo_03_delegation_execution.py`

---

### Demo 4: Permission Enforcement

**What It Proves:** Unauthorized actions are blocked at the gateway.

```bash
# Tests: Step 9 (Agent Denied)
pytest tests/e2e/test_sarah_journey.py -v -k "Step09"
```

**Expected Behavior:**
- `notion.create_page` returns error code -32001 (Permission Denied)
- Error message contains "permission" or "denied"

**Related Demo:** `demos/demo_04_permission_enforcement.py`

---

### Demo 5: Unified Audit Trail

**What It Proves:** All agent actions are logged with full attribution.

```bash
# Tests: Step 10 (Audit Trail)
pytest tests/e2e/test_sarah_journey.py -v -k "Step10"
```

**Expected Behavior:**
- Audit events are queryable by `agent_id`
- Each event has `agent_id`, `timestamp` attribution

**Related Demo:** `demos/demo_05_unified_audit.py`

---

### Demo 6: Fail-Closed Security

**What It Proves:** System fails safely when things go wrong.

```bash
# Not directly tested in sarah_journey, but covered by security tests
# See: deeptrail-gateway/tests/security/
```

**Related Demo:** `demos/demo_06_fail_closed.py`

---

### Cryptographic Agent Identity

**What It Proves:** Agents authenticate with Ed25519 challenge-response.

```bash
# Tests: Step 4 (Agent Registration) + Step 5 (Agent Auth)
pytest tests/e2e/test_sarah_journey.py -v -k "Step04 or Step05"
```

**Expected Behavior:**
- Agent is registered with public key (64 hex chars)
- Agent proves identity by signing challenge
- No secrets are shared

---

## Test Markers

| Marker | Description | Example |
|--------|-------------|---------|
| `@pytest.mark.e2e` | Requires live services | `pytest -m e2e` |
| `@pytest.mark.slow` | Slow-running tests | `pytest -m slow` |
| `@pytest.mark.asyncio` | Async test | (Automatic) |

```bash
# Run all E2E tests
pytest tests/e2e/ -v -m e2e

# Skip slow tests
pytest tests/e2e/ -v -m "e2e and not slow"

# Run only unit tests (no live services)
pytest tests/e2e/ -v -m "not e2e"
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSECURE_CONTROL_URL` | `http://localhost:8000` | Control Plane URL |
| `DEEPSECURE_GATEWAY_URL` | `http://localhost:8002` | Gateway URL |

```bash
# Run against custom environment
DEEPSECURE_CONTROL_URL=http://staging:8000 \
DEEPSECURE_GATEWAY_URL=http://staging:8002 \
pytest tests/e2e/test_sarah_journey.py -v -m e2e
```

---

## Troubleshooting

### Tests Skipped with "not available"

**Cause:** Services are not running or not healthy.

**Fix:**
```bash
# Check service health
curl http://localhost:8000/health
curl http://localhost:8002/health

# Restart services
docker compose down && docker compose up -d

# Check logs
docker compose logs deeptrail-control
docker compose logs deeptrail-gateway
```

### Async Fixture Errors

**Cause:** Using `@pytest.fixture` instead of `@pytest_asyncio.fixture`.

**Fix:** Ensure `conftest.py` uses correct decorator:
```python
import pytest_asyncio

@pytest_asyncio.fixture
async def control_plane_client():
    async with httpx.AsyncClient(...) as client:
        yield client
```

### Tool Filtering Not Working

**Cause:** Gateway not applying permission filters.

**Check:**
```bash
# Run filtered visibility test with verbose output
pytest tests/e2e/test_sarah_journey.py -v -k "filtered_tools" -s
```

---

## Test Stages Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SARAH'S JOURNEY (10 STEPS)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SETUP (Steps 1-4)                                                           │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                      │
│  │ Step 1  │──▶│ Step 2  │──▶│ Step 3  │──▶│ Step 4  │                      │
│  │ Pre-seed│   │ Login   │   │ Connect │   │ Delegate│                      │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘                      │
│                                                 │                            │
│  AGENT AUTH (Step 5)                            ▼                            │
│  ┌─────────────────────────────────────────────────┐                        │
│  │ Step 5: Challenge-Response Authentication       │                        │
│  │ • Request challenge nonce                       │                        │
│  │ • Sign with Ed25519 private key                 │                        │
│  │ • Receive agent JWT                             │                        │
│  └─────────────────────────────────────────────────┘                        │
│                                                 │                            │
│  GATEWAY SESSION (Steps 6-9)                    ▼                            │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                      │
│  │ Step 6  │──▶│ Step 7  │──▶│ Step 8  │──▶│ Step 9  │                      │
│  │ Init MCP│   │ Discover│   │ Execute │   │ Denied  │                      │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘                      │
│       │                            │              │                          │
│       │         Demo 1             │   Demo 3     │   Demo 4                │
│       └───────────────────────────┴──────────────┴──────────────────────────│
│                                                 │                            │
│  AUDIT (Step 10)                                ▼                            │
│  ┌─────────────────────────────────────────────────┐                        │
│  │ Step 10: Sarah Reviews Audit Trail              │   Demo 5               │
│  │ • Query events by agent_id                      │                        │
│  │ • Verify attribution (agent_id, timestamp)      │                        │
│  └─────────────────────────────────────────────────┘                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

| Document | Location |
|----------|----------|
| Test Details | `tests/e2e/SARAH_JOURNEY_TESTS.md` |
| Demo Scripts | `demos/README.md` |
| Design Document | `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md` |
| MVP Breakdown | `docs/deepsecure-virtual-mcp-server-mvp-breakdown.md` |

---

## Success Criteria

When all tests pass, you have validated:

| Capability | Status |
|------------|--------|
| Human authentication works | Step 2 passes |
| OAuth service connection works | Step 3 passes |
| Delegation with permissions works | Step 4 passes |
| Agent cryptographic auth works | Step 5 passes |
| Unified MCP endpoint works | Step 6 passes |
| Tool filtering works (90%+ reduction) | Step 7 passes |
| Delegated tool execution works | Step 8 passes |
| Permission enforcement works | Step 9 passes |
| Unified audit trail works | Step 10 passes |
| **Complete MVP validated** | `test_complete_sarah_journey` passes |
