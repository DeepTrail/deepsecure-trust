# Token Types & API Validation

> Extracted from CLAUDE.md. This is the reference for authentication tokens, Agent JWT creation, and MCP Gateway protocol.

## Token Types for API Validation (CRITICAL)

Different endpoints require different authentication tokens. Using the wrong token type causes 401 errors.

| Token Type | How to Obtain | Used For | Header Format |
|------------|---------------|----------|---------------|
| **User Token** | `POST /api/v1/auth/login` → `.token` | User-facing endpoints, service connection | `Authorization: Bearer $USER_TOKEN` |
| **Agent JWT** | Ed25519 challenge-response flow (see below) | Agent-to-Control APIs, vault token retrieval | `Authorization: Bearer $AGENT_JWT` |
| **Internal API Token** | From `docker-compose.yml` env var | Gateway-to-Control internal APIs | `Authorization: Bearer gateway-internal-secret-token` |

### Common Mistakes

| Mistake | Error | Fix |
|---------|-------|-----|
| Using User Token for vault token retrieval | `401 "missing user identity"` | Use Agent JWT (has `owner` claim) |
| Using User Token for vault token refresh | `401 "Invalid internal token"` | Use Internal API Token + `X-User-ID` header |
| Using `.access_token` for login response | Returns `null` | Use `.token` - login returns `token` field |

### Login API Response Field

```bash
# WRONG - returns null
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login ... | jq -r '.access_token')

# CORRECT - login returns "token" not "access_token"
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login ... | jq -r '.token')
```

## Agent JWT Creation Flow

When validation commands need an Agent JWT, use this full flow:

```bash
# 1. Generate Ed25519 keypair
python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey.generate()
public_key = private_key.verify_key
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env

# 2. Register agent with public key
curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"test-agent\", \"name\": \"Test\", \"public_key\": \"$PUBLIC_KEY_B64\"}"

# 3. Create delegation
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent", "permissions": ["service:scope:action"]}'

# 4. Request challenge
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent"}' | jq -r '.challenge')

# 5. Sign challenge
SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
signed = private_key.sign('$CHALLENGE'.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

# 6. Get Agent JWT
AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"test-agent\", \"challenge\": \"$CHALLENGE\", \"signature\": \"$SIGNATURE\"}" \
  | jq -r '.access_token')
```

## MCP Gateway Protocol Flow (CRITICAL)

The Gateway requires an `initialize` call before any `tools/call` requests. Calling `tools/call` without initialization returns:
```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32002,"message":"Session not found. Call initialize first.","data":null}}
```

### Required MCP Call Sequence

1. `initialize` - Establishes session, returns server info
2. `tools/list` (optional) - Lists available tools based on agent permissions
3. `tools/call` - Actually executes a tool (requires active session)

### Initialize Example

```bash
# Step 1: Initialize MCP session
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
      "clientInfo": {"name": "test-agent", "version": "1.0.0"}
    }
  }'
# Expected: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","serverInfo":{...}}}

# Step 2: Now tools/call will work
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }'
```

### Common Mistakes

| Mistake | Fix |
|---------|-----|
| Calling `tools/call` without `initialize` | Always call `initialize` first |
| Using static `AGENT_JWT` placeholder | Create real Agent JWT via challenge-response flow |
| Reusing session after timeout | Re-initialize if session expired |

**Reference Implementation:** See `demos/demo_sarah_journey_e2e.py` → `step_06_mcp_initialize()` for correct flow.

## API Contract Verification

Always verify that implementation endpoints match design doc specifications exactly.

| Common Mistake | Correct Approach |
|----------------|------------------|
| Test uses `/api/v1/agents/challenge` | Check design doc - might be `/api/v1/auth/agent/challenge` |
| Implementing without reading spec | Copy endpoint path from design doc's "API Contracts" section |
| Tests diverge from implementation | Both must match the canonical spec in design doc |

```bash
# Check implemented endpoints
grep -r "@router\.\(get\|post\|put\|delete\)" [file] | grep -o '"/api/v1[^"]*"'

# Check test endpoints
grep -r '"/api/v1' [test_file] | grep -o '"/api/v1[^"]*"'
```

## Async Test Fixtures

Use `@pytest_asyncio.fixture` for async fixtures, not `@pytest.fixture`.

```python
# WRONG - causes "AttributeError: 'async_generator' object has no attribute 'post'"
@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c

# CORRECT
import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c
```
