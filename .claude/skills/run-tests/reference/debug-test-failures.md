# Debug Test Failures — Reference

This file is loaded on-demand when the agent needs detailed failure debugging patterns.

## Common Failure Patterns

### 1. `AttributeError: 'async_generator' object has no attribute 'post'`

**Root cause:** Used `@pytest.fixture` instead of `@pytest_asyncio.fixture` for an async fixture.

**Fix:**
```python
# Before (broken)
@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c

# After (fixed)
import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c
```

### 2. `401 "missing user identity"` in vault tests

**Root cause:** Using User Token where Agent JWT is required. Vault endpoints need the `owner` claim only present in Agent JWTs.

**Fix:** Use the Ed25519 challenge-response flow to obtain an Agent JWT. See `CLAUDE.md` → "Agent JWT Creation Flow."

### 3. `ConnectionRefusedError` on localhost:8000

**Root cause:** Backend services not running. Tests marked as integration or e2e need live services.

**Fix:**
```bash
# Start backend
docker compose up -d db redis deeptrail-control deeptrail-gateway

# Wait for health
curl -sf http://localhost:8000/health || echo "Not ready"

# Or skip these tests
pytest -m "not e2e and not integration"
```

### 4. `Session not found. Call initialize first.`

**Root cause:** MCP Gateway requires `initialize` before `tools/call`. Test is calling `tools/call` without prior initialization.

**Fix:** Add an initialization step in the test setup:
```python
async def mcp_initialize(client, agent_jwt):
    return await client.post("/mcp", json={
        "jsonrpc": "2.0", "method": "initialize", "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0.0"}
        }
    }, headers={"Authorization": f"Bearer {agent_jwt}"})
```

### 5. `null` token from login

**Root cause:** Login API returns `.token`, not `.access_token`.

**Fix:**
```python
# Wrong
token = response.json()["access_token"]  # Returns None

# Correct
token = response.json()["token"]
```

## Coverage Analysis Commands

```bash
# Full coverage report
pytest --cov=deepsecure --cov-report=html --cov-report=term

# Coverage for specific module
pytest --cov=deepsecure._core --cov-report=term tests/_core/

# Show uncovered lines
pytest --cov=deepsecure --cov-report=term-missing

# Open HTML report
open htmlcov/index.html
```

## Test File Naming Convention

| Source file | Expected test file |
|-------------|-------------------|
| `deepsecure/client.py` | `tests/test_sdk_client.py` |
| `deepsecure/_core/vault_client.py` | `tests/_core/test_vault_client.py` |
| `deepsecure/commands/agent.py` | `tests/commands/test_agent.py` |
| `deeptrail-control/app/services/auth_service.py` | `deeptrail-control/tests/services/test_auth_service.py` |
