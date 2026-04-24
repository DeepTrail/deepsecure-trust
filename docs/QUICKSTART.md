# DeepSecure Platform -- Quickstart Guide

> Get from zero to a working agent-to-API call in 15 minutes.
> For the full HTTP API reference, see [API_REFERENCE.md](API_REFERENCE.md).
> For the Python SDK, see [SDK_REFERENCE.md](SDK_REFERENCE.md).

---

## Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Python 3.10+** with `pynacl`: `pip install pynacl`
- **curl** and **jq**

## Step 0: Start Services

```bash
cd /path/to/deepsecure-mvp
docker compose up -d --build
```

Wait for healthy status:

```bash
# Control Plane (auth, agents, delegation, audit)
curl -sf http://localhost:8000/health | jq .

# Gateway (MCP protocol, tool execution, credential injection)
curl -sf http://localhost:8002/health | jq .
```

Both should return `"status": "ok"`. The Control Plane runs on **port 8000**, the Gateway on **port 8002**.

```bash
CONTROL=http://localhost:8000
GATEWAY=http://localhost:8002
```

---

## Step 1: Authenticate the User

The user (Sarah) logs in and receives a **User Session JWT** (Layer 2). This token authorizes user-facing APIs like agent registration and delegation.

**Option A -- SSO (Keycloak)**

```bash
# 1. Get the authorization URL
curl -s "$CONTROL/api/v1/auth/sso/keycloak/authorize" | jq .

# 2. Open the authorization_url in a browser, log in, and capture the token
#    from the callback redirect. See the demo script for the full browser flow.
```

**Option B -- Password Login (development fallback)**

```bash
USER_TOKEN=$(curl -s -X POST "$CONTROL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' \
  | jq -r '.token')

echo "User token: ${USER_TOKEN:0:30}..."
```

**Response:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "email": "sarah@acme.com",
    "id": "sarah@acme.com",
    "organization_id": "acme-org"
  },
  "expires_in": 28800
}
```

> The `token` field is the User Session JWT. It does **not** authorize Gateway tool calls -- only Control Plane user APIs.

---

## Step 2: Connect a Backend Service

Store an OAuth token for a service Sarah wants her agents to access. The token is encrypted in the vault; the agent never sees it.

```bash
curl -s -X POST "$CONTROL/api/v1/users/me/services/connect" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "ntn_YOUR_NOTION_API_KEY",
      "token_type": "bearer",
      "scope": "read_pages search_content"
    }
  }' | jq .
```

**Response:**

```json
{
  "success": true,
  "service_id": "notion",
  "service_name": "Notion",
  "scopes_stored": ["read_pages", "search_content"],
  "connected_at": "2026-04-14T07:14:06.717497+00:00"
}
```

Check what permissions are now available for delegation:

```bash
curl -s "$CONTROL/api/v1/users/me/available-permissions" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

This returns the **monotonic attenuation boundary** -- the maximum set of permissions Sarah can delegate to any agent.

---

## Step 3: Register an Agent and Create a Delegation

### 3a. Generate an Ed25519 Keypair

The agent's cryptographic identity. The public key goes to the server; the private key stays with the agent.

```bash
python3 -c "
from nacl.signing import SigningKey
import base64
sk = SigningKey.generate()
pk = sk.verify_key
print(f'export PRIVATE_KEY_HEX={sk.encode().hex()}')
print(f'export PUBLIC_KEY_B64={base64.b64encode(pk.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env
```

### 3b. Register the Agent

```bash
AGENT_ID="my-agent-$(date +%s)"

curl -s -X POST "$CONTROL/api/v1/agents/" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"name\": \"My Assistant\",
    \"public_key\": \"$PUBLIC_KEY_B64\"
  }" | jq .
```

### 3c. Create a Delegation

Grant the agent a subset of Sarah's available permissions:

```bash
curl -s -X POST "$CONTROL/api/v1/auth/delegate" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"permissions\": [
      \"notion:pages:search\",
      \"notion:pages:read\"
    ],
    \"constraints\": {
      \"rate_limit\": 100,
      \"expires_in_hours\": 8
    }
  }" | jq .
```

**Response:**

```json
{
  "delegation_token": "MDAyNmxvY2F0aW9u...",
  "delegation_id": "del-65819f41-...",
  "permissions": ["notion:pages:search", "notion:pages:read"],
  "expires_in": 28800
}
```

Permissions follow the URN format `{service}:{resource}:{action}`. You can only delegate permissions that are within Sarah's OAuth scopes -- attempting to delegate `notion:pages:create` when she only has `read_pages` scope will return a `422`.

---

## Step 4: Authenticate the Agent

The agent proves its identity via Ed25519 challenge-response and receives an **Agent Session JWT** (Layer 3).

```bash
# 4a. Request a challenge
CHALLENGE=$(curl -s -X POST "$CONTROL/api/v1/auth/agent/challenge" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\"}" | jq -r '.challenge')

# 4b. Sign the challenge with the private key
SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
sk = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
sig = sk.sign('$CHALLENGE'.encode()).signature
print(base64.urlsafe_b64encode(sig).decode())
")

# 4c. Verify and get the Agent JWT
AGENT_JWT=$(curl -s -X POST "$CONTROL/api/v1/auth/agent/verify" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')

echo "Agent JWT: ${AGENT_JWT:0:30}..."
```

The Agent JWT contains the `delegated_permissions` as claims. The Gateway reads these to filter tools and enforce access.

---

## Step 5: Call APIs Through the MCP Gateway

The agent connects to a single MCP endpoint and accesses tools from multiple backends. Credentials are injected server-side -- the agent never sees OAuth tokens.

### 5a. Initialize the MCP Session

This **must** be called before `tools/list` or `tools/call`.

```bash
curl -s -X POST "$GATEWAY/mcp" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "method": "initialize", "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "my-agent", "version": "1.0.0"}
    }
  }' | jq .
```

### 5b. Discover Available Tools

Returns only tools matching the agent's delegated permissions. Undelegated tools are completely hidden.

```bash
curl -s -X POST "$GATEWAY/mcp" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2,"params":{}}' | jq .
```

### 5c. Execute a Tool Call

```bash
curl -s -X POST "$GATEWAY/mcp" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "method": "tools/call", "id": 3,
    "params": {
      "name": "notion.search_pages",
      "arguments": {"query": "quarterly report", "limit": 5}
    }
  }' | jq .
```

**What happens behind the scenes:**
1. Gateway validates the Agent JWT
2. Maps `notion.search_pages` to permission `notion:pages:search`
3. Checks the permission exists in `delegated_permissions`
4. Scans arguments for prompt injection
5. Retrieves Sarah's Notion OAuth token from the vault
6. Calls the Notion API with Sarah's credentials
7. Filters PII from the response
8. Logs an audit event
9. Returns the result to the agent

---

## Step 6: Query the Audit Trail

Every action -- permitted and denied -- is logged with full human attribution.

```bash
curl -s "$CONTROL/api/v1/audit/events?agent_id=$AGENT_ID&limit=5" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

**Response:**

```json
{
  "events": [
    {
      "timestamp": "2026-04-14T07:06:28Z",
      "event_type": "mcp_tool_call",
      "agent_id": "my-agent-1713082468",
      "on_behalf_of": "sarah@acme.com",
      "tool": "notion.search_pages",
      "session_id": "asess-aaf12deb534d",
      "delegation_id": "del-65819f41-..."
    }
  ],
  "total": 1,
  "limit": 5,
  "offset": 0
}
```

Every event traces back to: which human authorized it, which agent acted, which delegation granted the permission, and which session it occurred in.

---

## What's Next

| Goal | Document |
|------|----------|
| Full HTTP API reference (all endpoints, all tools) | [API_REFERENCE.md](API_REFERENCE.md) |
| Python SDK and CLI usage | [SDK_REFERENCE.md](SDK_REFERENCE.md) |
| Task-scoped permissions (Layer 4) | [API_REFERENCE.md -- Task Token APIs](API_REFERENCE.md#10-task-token-apis) |
| Security features (prompt injection, PII filtering) | [API_REFERENCE.md -- Security](API_REFERENCE.md#13-security) |
| Full E2E demo walkthrough | [SARAH_JOURNEY_API_REFERENCE.md](SARAH_JOURNEY_API_REFERENCE.md) |
| Run the interactive demo | `./scripts/demo_sarah_journey.sh` |

---

## Token Quick Reference

| Layer | Token | How Obtained | Authorizes |
|-------|-------|-------------|------------|
| L2 | User Session JWT | SSO or password login | Control Plane user APIs |
| L3 | Agent Session JWT | Ed25519 challenge-response | Gateway MCP tool calls |
| L4 | Task Token JWT | Task lifecycle API | Single-task scoped calls |
| L5 | Delegation Token | `POST /auth/delegate` | Embedded in L3 claims |

Permissions can only narrow at each layer (monotonic attenuation):
`User OAuth scopes` > `Delegated permissions` > `Task-scoped permissions`
