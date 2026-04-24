# DeepSecure Platform -- API Reference

> **Version:** 2.0  
> **Last Updated:** April 2026  
> **Status:** MVP Implementation  
> **Quickstart:** [QUICKSTART.md](QUICKSTART.md) | **Python SDK:** [SDK_REFERENCE.md](SDK_REFERENCE.md)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Authentication Model](#2-authentication-model)
3. [Permission System](#3-permission-system)
4. [Health and Status APIs](#4-health-and-status-apis)
5. [User Authentication APIs](#5-user-authentication-apis)
6. [Agent Management APIs](#6-agent-management-apis)
7. [Delegation APIs](#7-delegation-apis)
8. [Agent Authentication APIs](#8-agent-authentication-apis)
9. [Service Connection APIs](#9-service-connection-apis)
10. [Task Token APIs](#10-task-token-apis)
11. [MCP Gateway Protocol](#11-mcp-gateway-protocol)
12. [MCP Tool Catalog](#12-mcp-tool-catalog)
13. [Security](#13-security)
14. [Audit APIs](#14-audit-apis)
15. [Vault APIs](#15-vault-apis)
16. [OAuth APIs](#16-oauth-apis)
17. [Policy APIs](#17-policy-apis)
18. [Bootstrap APIs](#18-bootstrap-apis)
19. [Error Reference](#19-error-reference)
20. [Appendix: Proxy Gateway](#20-appendix-proxy-gateway)

---

## 1. Overview

The DeepSecure platform consists of two backend services:

| Service | Purpose | Dev Port | Base URL |
|---------|---------|----------|----------|
| **Control Plane** (`deeptrail-control`) | Authentication, agent management, delegation, policies, audit, vault | 8000 | `http://localhost:8000` |
| **Gateway** (`deeptrail-gateway`) | MCP protocol, tool execution, credential injection, security scanning | 8002 | `http://localhost:8002` |

Supporting services:

| Service | Dev Port | Purpose |
|---------|----------|---------|
| PostgreSQL | 5434 | Control Plane database |
| Redis | 6380 | Gateway credential cache |
| Keycloak (optional) | 8080 | Identity Provider for SSO |

### API Conventions

- All Control Plane APIs are prefixed with `/api/v1`
- Gateway APIs use root paths (`/mcp`, `/health`, `/proxy`)
- Request/response bodies are JSON (`Content-Type: application/json`)
- Authentication uses `Authorization: Bearer <token>` headers
- Timestamps are ISO 8601 with timezone (`2026-04-14T07:14:06.717497+00:00`)

---

## 2. Authentication Model

### The 6-Layer Token Hierarchy

```
L1: Organization Key         Platform bootstrap (not shown in typical flows)
L2: User Session JWT      <- SSO or password login
L3: Agent Session JWT     <- Ed25519 challenge-response
L4: Task Token JWT        <- Task lifecycle API
L5: Delegation Token         Macaroon, embedded in L3 claims
L6: Secret Share Tokens      Internal, transparent to agent
```

### Token Types

| Token | Obtained Via | Used For | TTL | Header |
|-------|-------------|----------|-----|--------|
| **User Session JWT** (L2) | `POST /api/v1/auth/login` or SSO callback | Control Plane user APIs (agents, delegation, services, audit) | 8 hours | `Authorization: Bearer <USER_TOKEN>` |
| **Agent Session JWT** (L3) | `POST /api/v1/auth/agent/verify` | Gateway MCP calls (`POST /mcp`) | 8 hours | `Authorization: Bearer <AGENT_JWT>` |
| **Task Token JWT** (L4) | `POST /api/v1/tasks/{id}/token` | Task-scoped Gateway MCP calls | Until task deadline | `Authorization: Bearer <TASK_TOKEN>` |
| **Delegation Token** (L5) | `POST /api/v1/auth/delegate` | Embedded in Agent JWT claims | 8 hours default | Not sent directly |
| **Backend API Token** | Environment variable | Admin vault/credential operations | Static | `Authorization: Bearer <API_TOKEN>` |
| **Internal API Token** | Environment variable | Gateway-to-Control internal calls | Static | `X-Internal-API-Token: <token>` |

### User Session JWT Claims

```json
{
  "sub": "sarah@acme.com",
  "session_id": "usess-0ff7924d-...",
  "organization_id": "acme-org",
  "idp": "keycloak",
  "exp": 1776237222,
  "iat": 1776150822
}
```

### Agent Session JWT Claims

```json
{
  "iss": "deeptrail-control",
  "aud": "deeptrail-gateway",
  "sub": "sdr-assistant-1776150868",
  "owner": "sarah@acme.com",
  "session_id": "asess-aaf12deb534d",
  "delegated_permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:channels:list"
  ],
  "delegation_id": "del-65819f41-...",
  "exp": 1776179705,
  "iat": 1776150905
}
```

### Task Token JWT Claims

```json
{
  "iss": "deeptrail-control",
  "aud": "deeptrail-gateway",
  "token_type": "task_token",
  "task_id": "task-338e0801-...",
  "agent_id": "sdr-assistant-1776150868",
  "owner": "sarah@acme.com",
  "scoped_permissions": [
    {"urn": "notion:pages:search", "constraints": {}}
  ],
  "deadline": "2026-04-14T08:06:20Z",
  "auto_revoke_on_complete": true,
  "exp": 1776153980,
  "iat": 1776150380
}
```

---

## 3. Permission System

### Permission URN Format

Permissions follow the pattern `{service}:{resource}:{action}`:

```
notion:pages:search
slack:channels:list
gdrive:files:read
gcalendar:events:list
gmail:messages:search
hubspot:contacts:create
```

### Wildcard Rules

The Gateway's `DelegationValidator` supports wildcards during `tools/call` enforcement:

| Pattern | Matches |
|---------|---------|
| `notion:pages:search` | Exact match only |
| `notion:pages:*` | All actions on `notion:pages` |
| `notion:*` | All Notion permissions |
| `*:*` | All permissions (superuser) |

> `tools/list` uses strict exact matching (no wildcards) when filtering visible tools.

### Monotonic Attenuation

Permissions can only narrow at each layer:

1. **User OAuth scopes** -- the ceiling (e.g., `read_pages`, `search_content`)
2. **Delegation permissions** -- a subset of the user's scopes (e.g., `notion:pages:search`, `notion:pages:read`)
3. **Task-scoped permissions** -- a subset of the delegation (e.g., `notion:pages:search` only)

Attempting to delegate beyond the user's scopes returns a `422` with the invalid permissions listed.

### Scope-to-Permission Mapping

OAuth scopes from connected services are mapped to permission URNs by the `ScopeMapper`:

| Service | OAuth Scope | Permission URNs |
|---------|-------------|-----------------|
| Notion | `read_pages` | `notion:pages:read`, `notion:pages:search` |
| Notion | `search_content` | `notion:pages:search` |
| Notion | `insert_content` | `notion:pages:create`, `notion:pages:update` |
| Slack | `channels:read` | `slack:channels:list` |
| Slack | `channels:history` | `slack:channels:history` |
| Slack | `chat:write` | `slack:messages:send` |
| Slack | `search:read` | `slack:messages:search` |
| Slack | `users:read` | `slack:users:list` |

### Constraint Types

Constraints can be applied at delegation or task level:

| Constraint | Description | Example |
|-----------|-------------|---------|
| `rate_limit` | Max requests per period | `100` |
| `expires_in_hours` | TTL for the delegation | `8` |
| `max_usage` | Max uses of a permission (task level) | `10` |
| `deadline_minutes` | Task deadline (1--1440 minutes) | `60` |

---

## 4. Health and Status APIs

### Control Plane Health

```
GET /health
```

No authentication required.

**Response (200):**

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

### Gateway Health

```
GET http://localhost:8002/health
```

No authentication required.

**Response (200):**

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

### Gateway Readiness

```
GET http://localhost:8002/ready
```

Returns `200` with `{"status": "ready"}` or `503` with `{"status": "not_ready"}`.

---

## 5. User Authentication APIs

Base: `http://localhost:8000/api/v1/auth`

### POST /api/v1/auth/login

Password-based login. Returns a User Session JWT (Layer 2).

| Field | Value |
|-------|-------|
| **Auth** | None |
| **Content-Type** | `application/json` |

**Request:**

```json
{
  "email": "sarah@acme.com",
  "password": "test_password"
}
```

**Response (200):**

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

> **MVP Note:** Password is not validated; any password is accepted. The response field is `token`, not `access_token`.

---

### GET /api/v1/auth/sso/{idp}/authorize

Initiate SSO login via an identity provider. Supports `keycloak` and `google`.

| Field | Value |
|-------|-------|
| **Auth** | None |
| **Path Params** | `idp` -- identity provider (`keycloak` or `google`) |
| **Query Params** | `redirect_uri` (optional), `response_mode` (`json` or `redirect`, default `json`), `post_login_redirect` (optional URL) |

**Response (200, JSON mode):**

```json
{
  "authorization_url": "http://localhost:8080/realms/deepsecure/protocol/openid-connect/auth?client_id=...&code_challenge=...&code_challenge_method=S256",
  "state": "n2n3WJ-FYWt5Ouxo...",
  "expires_in": 300
}
```

Redirect the user's browser to `authorization_url`. The IdP authenticates the user and redirects back to the callback endpoint.

If `post_login_redirect` is provided, the callback will redirect the browser to that URL with the `token` as a query parameter.

---

### GET /api/v1/auth/sso/{idp}/callback

Handles the OAuth callback from the identity provider. Exchanges the authorization code for tokens and creates a user session.

| Field | Value |
|-------|-------|
| **Auth** | None (state validation) |
| **Query Params** | `code`, `state`, `error`, `error_description` |

**Response (JSON, without post_login_redirect):**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "email": "sarah@acme.com",
    "name": "Sarah Chen",
    "organization_id": "acme-org"
  },
  "idp": "keycloak",
  "expires_in": 86400,
  "refresh_available": true
}
```

**Response (with post_login_redirect):** `302 Redirect` to `{post_login_redirect}?token={jwt}&email={email}&name={name}`

---

### POST /api/v1/auth/sso/refresh

Refresh the user session using the IdP's refresh token (if `refresh_available` was `true` at login).

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` (accepts recently expired tokens within grace period) |

**Response (200):**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 86400,
  "idp": "keycloak",
  "refreshed_at": "2026-04-14T15:14:06Z"
}
```

---

### POST /api/v1/auth/sso/logout

Revoke the IdP session and get the provider's logout URL.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` |

**Request (optional body):**

```json
{
  "post_logout_redirect_uri": "http://localhost:3000/logged-out"
}
```

**Response (200):**

```json
{
  "logout_url": "http://localhost:8080/realms/deepsecure/protocol/openid-connect/logout?...",
  "message": "Session revoked. Redirect to logout_url to complete IdP logout."
}
```

---

## 6. Agent Management APIs

Base: `http://localhost:8000/api/v1/agents`

### POST /api/v1/agents/

Register a new agent with an Ed25519 public key.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` |

**Request:**

```json
{
  "agent_id": "sdr-assistant-001",
  "name": "SDR Sales Assistant",
  "public_key": "UjK/ZWJ0MOfZ6FwdGTymetEIQIkbFICroNngZKViAgM=",
  "description": "AI assistant for sales development"
}
```

- `agent_id` -- optional; auto-generated if omitted
- `public_key` -- Base64-encoded Ed25519 public key
- `description` -- optional

**Response (201):**

```json
{
  "name": "SDR Sales Assistant",
  "description": "AI assistant for sales development",
  "agent_id": "sdr-assistant-001",
  "publicKey": "UjK/ZWJ0MOfZ6FwdGTymetEIQIkbFICroNngZKViAgM=",
  "status": "active",
  "created_at": "2026-04-14T07:14:28.924359Z",
  "updated_at": "2026-04-14T07:14:28.924359Z",
  "last_seen_at": null
}
```

**Errors:**
- `409 Conflict` -- duplicate public key

---

### GET /api/v1/agents/

List all agents.

| Field | Value |
|-------|-------|
| **Auth** | None |
| **Query Params** | `skip` (default 0), `limit` (default 100, max 500) |

**Response (200):**

```json
{
  "agents": [
    {
      "agent_id": "sdr-assistant-001",
      "name": "SDR Sales Assistant",
      "status": "active",
      "created_at": "2026-04-14T07:14:28Z",
      "updated_at": "2026-04-14T07:14:28Z"
    }
  ],
  "total": 1
}
```

---

### GET /api/v1/agents/{agent_id}

Get a single agent by ID.

**Response (200):** Same shape as the POST response.

**Errors:** `404 Not Found`

---

### PATCH /api/v1/agents/{agent_id}

Update agent fields.

**Request (all fields optional):**

```json
{
  "name": "Updated Name",
  "description": "New description",
  "status": "inactive"
}
```

---

### DELETE /api/v1/agents/{agent_id}

Soft-deactivate an agent (sets status to `inactive`).

**Response (200):** Returns the agent with updated status.

---

## 7. Delegation APIs

Base: `http://localhost:8000/api/v1/auth`

### POST /api/v1/auth/delegate

Create a user-to-agent delegation with scoped permissions.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` |

**Request:**

```json
{
  "agent_id": "sdr-assistant-001",
  "permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:channels:list"
  ],
  "constraints": {
    "rate_limit": 100,
    "expires_in_hours": 8
  }
}
```

**Response (200):**

```json
{
  "delegation_token": "MDAyNmxvY2F0aW9uIGh0dHA6Ly9kZWVwdHJhaWwtZ2F0ZXdheQ...",
  "delegation_id": "del-65819f41-5fd0-4a14-bc46-9fed5431eb0e",
  "permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:channels:list"
  ],
  "expires_in": 28800
}
```

**Errors:**

`422 Unprocessable Entity` -- permission validation failed:

```json
{
  "detail": {
    "error": "permission_validation_failed",
    "message": "Some requested permissions are not available...",
    "invalid_permissions": ["notion:pages:create"],
    "allowed_permissions": ["notion:pages:read", "notion:pages:search", "slack:channels:list"]
  }
}
```

This enforces monotonic attenuation: you cannot delegate permissions beyond what the user's connected OAuth scopes allow.

---

### POST /api/v1/auth/agent-delegate

Create an agent-to-agent delegation (for multi-agent workflows).

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` |

**Request:**

```json
{
  "target_agent_id": "sub-agent-002",
  "resource": "notion",
  "permissions": ["notion:pages:search"],
  "ttl_seconds": 3600
}
```

**Response (200):**

```json
{
  "delegation_token": "MDAyNmxvY2F0aW9u..."
}
```

---

## 8. Agent Authentication APIs

Base: `http://localhost:8000/api/v1/auth/agent`

The agent proves its identity via Ed25519 challenge-response.

### POST /api/v1/auth/agent/challenge

Request a cryptographic challenge nonce.

| Field | Value |
|-------|-------|
| **Auth** | None |

**Request:**

```json
{
  "agent_id": "sdr-assistant-001"
}
```

**Response (200):**

```json
{
  "challenge": "NgBHOOghvcLgPur8DO51ZeS4W_xwfh...",
  "expires_in": 300
}
```

The challenge is a single-use 256-bit random nonce that expires in 300 seconds.

**Errors:** `404 Not Found` if agent_id does not exist.

---

### POST /api/v1/auth/agent/verify

Verify the signed challenge and receive an Agent Session JWT (Layer 3).

| Field | Value |
|-------|-------|
| **Auth** | None |

**Request:**

```json
{
  "agent_id": "sdr-assistant-001",
  "challenge": "NgBHOOghvcLgPur8DO51ZeS4W_xwfh...",
  "signature": "gckOa2wPSTCzBVPgyEcjLtejNu2vPwv1Xnk...",
  "delegation_id": "del-65819f41-..."
}
```

- `signature` -- Base64url-encoded Ed25519 signature of the challenge string
- `delegation_id` -- optional; if provided, the delegation's permissions are embedded in the JWT

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 28800,
  "session_id": "asess-aaf12deb534d"
}
```

The `access_token` is the Agent Session JWT. Its claims include the `delegated_permissions` array, `owner` (the delegating user), and `delegation_id`.

---

## 9. Service Connection APIs

Base: `http://localhost:8000/api/v1/users`

### POST /api/v1/users/me/services/connect

Connect a backend service by storing its OAuth token in the encrypted vault.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` |

**Request:**

```json
{
  "service_id": "notion",
  "oauth_token": {
    "access_token": "ntn_YOUR_NOTION_API_KEY",
    "token_type": "bearer",
    "refresh_token": "optional_refresh_token",
    "scope": "read_pages search_content",
    "expires_at": "2027-01-01T00:00:00Z"
  }
}
```

Supported `service_id` values: `notion`, `slack`, `hubspot`, `gdrive`, `gcalendar`, `gmail`.

**Response (200):**

```json
{
  "success": true,
  "connection": {
    "id": "conn-abc123",
    "service_id": "notion",
    "service_name": "Notion",
    "scopes_granted": ["read_pages", "search_content"],
    "connected_at": "2026-04-14T07:14:06.717497+00:00"
  }
}
```

---

### GET /api/v1/users/me/available-permissions

List all permissions available for delegation based on connected services.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` |

**Response (200):**

```json
{
  "services": {
    "notion": {
      "connected": true,
      "service_name": "Notion",
      "scopes_granted": ["read_pages", "search_content"],
      "available_permissions": ["notion:pages:read", "notion:pages:search"],
      "connected_at": "2026-04-14T07:14:06Z"
    },
    "slack": {
      "connected": true,
      "service_name": "Slack",
      "scopes_granted": ["channels:read", "chat:write"],
      "available_permissions": ["slack:channels:list", "slack:messages:send"],
      "connected_at": "2026-04-14T07:14:06Z"
    }
  },
  "all_permissions": [
    "notion:pages:read",
    "notion:pages:search",
    "slack:channels:list",
    "slack:messages:send"
  ],
  "total_services": 2,
  "total_permissions": 4
}
```

This defines the **monotonic attenuation boundary** -- the maximum set of permissions the user can delegate to any agent.

---

### DELETE /api/v1/users/me/services/{service_id}

Disconnect a backend service.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` |
| **Path Params** | `service_id` |

**Response (200):**

```json
{
  "success": true,
  "service_id": "notion",
  "message": "Service disconnected successfully"
}
```

---

## 10. Task Token APIs

Base: `http://localhost:8000/api/v1/tasks`

Task tokens provide per-task least-privilege. An agent with 5 delegated permissions can request a task token with only 1, ensuring the task cannot exceed its intended scope.

### POST /api/v1/tasks/

Create a task with requested permissions (a subset of the agent's delegation).

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` |

**Request:**

```json
{
  "name": "Research competitor analysis",
  "description": "Search competitor analysis pages in Notion",
  "requested_permissions": [
    {
      "permission_urn": "notion:pages:search",
      "max_usage": 10,
      "constraints": {}
    }
  ],
  "deadline_minutes": 60,
  "auto_revoke_on_complete": true
}
```

- `requested_permissions` -- at least 1 required; each must be within the agent's `delegated_permissions`
- `deadline_minutes` -- 1 to 1440 (24 hours)
- `auto_revoke_on_complete` -- if `true`, the task token is invalidated when the task completes

**Response (201):**

```json
{
  "task_id": "task-338e0801-283f-4ad9-82e5-869c8eb30488",
  "name": "Research competitor analysis",
  "status": "pending",
  "agent_id": "sdr-assistant-001",
  "scoped_permissions": [
    {"permission_urn": "notion:pages:search", "max_usage": 10, "constraints": {}}
  ],
  "deadline": "2026-04-14T08:06:12Z",
  "auto_revoke_on_complete": true,
  "created_at": "2026-04-14T07:06:12Z"
}
```

---

### GET /api/v1/tasks/{task_id}

Get task details.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` |

**Response (200):** Same shape as the create response.

---

### GET /api/v1/tasks/

List tasks for the authenticated agent.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` |
| **Query Params** | `status` (filter), `limit` (1--100, default 50), `offset` (default 0) |

**Response (200):**

```json
{
  "tasks": [...],
  "total": 3,
  "limit": 50,
  "offset": 0
}
```

---

### POST /api/v1/tasks/{task_id}/activate

Transition task from `pending` to `active`.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` |

**Response (200):**

```json
{
  "task_id": "task-338e0801-...",
  "status": "active",
  "started_at": "2026-04-14T07:06:12Z"
}
```

**Errors:** `409 Conflict` if task is not in `pending` state.

---

### POST /api/v1/tasks/{task_id}/token

Issue a Task Token JWT (Layer 4) for the active task.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` |

**Response (200):**

```json
{
  "task_id": "task-338e0801-...",
  "task_token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_at": "2026-04-14T08:06:20Z",
  "scoped_permissions": ["notion:pages:search"]
}
```

Use the `task_token` as the Bearer token for Gateway MCP calls. The Gateway will enforce the task's narrowed permissions instead of the agent's full delegation.

---

### POST /api/v1/tasks/{task_id}/complete

Complete the task. If `auto_revoke_on_complete` is `true`, the task token is invalidated.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` |

**Response (200):**

```json
{
  "task_id": "task-338e0801-...",
  "status": "completed",
  "completed_at": "2026-04-14T07:10:00Z"
}
```

---

### POST /api/v1/tasks/{task_id}/revoke

Revoke the task (cancel with permission revocation).

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` |

**Response (200):** Task with `status: "revoked"`.

---

## 11. MCP Gateway Protocol

The Gateway implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) over a single HTTP endpoint using JSON-RPC 2.0.

### POST /mcp

All MCP operations go through this single endpoint.

| Field | Value |
|-------|-------|
| **Base URL** | `http://localhost:8002` |
| **Auth** | `Authorization: Bearer <AGENT_JWT>` or `Bearer <TASK_TOKEN>` |
| **Content-Type** | `application/json` |
| **Max Body Size** | 1 MB |

The Gateway supports three MCP methods and batch requests (array of JSON-RPC objects).

---

### Method: initialize

**Must be called before `tools/list` or `tools/call`.** Establishes an MCP session for the authenticated agent.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "my-agent",
      "version": "1.0.0"
    }
  }
}
```

- `clientInfo.name` is required

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "serverInfo": {
      "name": "DeepTrail Virtual MCP Server",
      "version": "0.1.0"
    },
    "capabilities": {
      "tools": {"listChanged": true}
    }
  }
}
```

**What happens during initialize:**

1. Gateway validates the Agent/Task JWT
2. Extracts `delegated_permissions` (or `scoped_permissions` for task tokens) from claims
3. Determines which backend services to connect based on permission prefixes (`notion:`, `slack:`, `gdrive:`, etc.)
4. Creates the MCP session
5. Returns server capabilities

**Error (no JWT):** `401 Unauthorized`

---

### Method: tools/list

Returns tools available to the agent, filtered by delegated permissions. Tools outside the delegation are completely hidden.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

**Response:**

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
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results", "default": 10}
          },
          "required": ["query"]
        }
      }
    ]
  }
}
```

Tool names are namespaced: `{backend}.{tool_name}`. The agent cannot discover tools outside its permissions.

**Error (-32002):** `"Session not found. Call initialize first."`

---

### Method: tools/call

Execute a tool. The Gateway injects the user's OAuth credentials server-side -- the agent never sees them.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "notion.search_pages",
    "arguments": {
      "query": "quarterly report",
      "limit": 5
    }
  }
}
```

**Response (success):**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"object\": \"list\", \"results\": [...]}"
      }
    ]
  }
}
```

**Processing pipeline:**

1. **Fail-closed check** -- verify Control Plane is reachable
2. **Permission check** -- map tool name to permission URN, validate against JWT claims
3. **Constraint check** -- verify rate limits, quotas
4. **Prompt injection scan** -- scan `arguments` for injection patterns
5. **Credential injection** -- retrieve user's OAuth token from vault
6. **Backend call** -- forward to the actual API (Notion, Slack, etc.)
7. **PII filter** -- mask sensitive data in the response
8. **Audit log** -- record the event

**Error (permission denied, -32603):**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32603,
    "message": "Permission denied: notion:pages:create not delegated",
    "data": null
  }
}
```

**Error (prompt injection, -32602):**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32602,
    "message": "Prompt injection detected in tool arguments",
    "data": {
      "threat_level": "high",
      "blocked_fields": "query"
    }
  }
}
```

---

### Batch Requests

Send multiple JSON-RPC calls in a single HTTP request:

```json
[
  {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "notion.search_pages", "arguments": {"query": "report"}}},
  {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "slack.list_channels", "arguments": {}}}
]
```

Response is an array of JSON-RPC results in the same order.

---

## 12. MCP Tool Catalog

All 34 tools available through the Gateway, organized by backend service.

### Notion (8 tools)

| Tool Name | Description | Permission URN |
|-----------|-------------|----------------|
| `notion.search_pages` | Search for pages in Notion workspace | `notion:pages:search` |
| `notion.read_page` | Read a specific Notion page by ID | `notion:pages:read` |
| `notion.get_page_content` | Get the content blocks of a Notion page | `notion:blocks:read` |
| `notion.create_page` | Create a new page in Notion | `notion:pages:create` |
| `notion.update_page` | Update an existing Notion page | `notion:pages:update` |
| `notion.delete_page` | Archive/delete a Notion page | `notion:pages:delete` |
| `notion.list_databases` | List all databases in Notion workspace | `notion:databases:list` |
| `notion.query_database` | Query a Notion database with filters | `notion:databases:query` |

#### notion.search_pages

```json
{
  "properties": {
    "query": {"type": "string", "description": "Search query"},
    "limit": {"type": "integer", "description": "Max results", "default": 10},
    "filter": {"type": "object", "description": "Filter criteria", "properties": {"property": {"type": "string"}, "value": {"type": "string"}}}
  },
  "required": ["query"]
}
```

#### notion.read_page

```json
{
  "properties": {
    "page_id": {"type": "string", "description": "Notion page ID"}
  },
  "required": ["page_id"]
}
```

#### notion.get_page_content

```json
{
  "properties": {
    "page_id": {"type": "string", "description": "Notion page ID"},
    "page_size": {"type": "integer", "description": "Number of blocks to return", "default": 100}
  },
  "required": ["page_id"]
}
```

#### notion.create_page

```json
{
  "properties": {
    "parent_id": {"type": "string", "description": "Parent page or database ID"},
    "title": {"type": "string", "description": "Page title"},
    "content": {"type": "string", "description": "Page content (markdown)"}
  },
  "required": ["parent_id", "title"]
}
```

#### notion.update_page

```json
{
  "properties": {
    "page_id": {"type": "string", "description": "Notion page ID"},
    "properties": {"type": "object", "description": "Properties to update"}
  },
  "required": ["page_id"]
}
```

#### notion.delete_page

```json
{
  "properties": {
    "page_id": {"type": "string", "description": "Notion page ID"}
  },
  "required": ["page_id"]
}
```

#### notion.list_databases

```json
{
  "properties": {
    "page_size": {"type": "integer", "description": "Max databases to return", "default": 10}
  },
  "required": []
}
```

#### notion.query_database

```json
{
  "properties": {
    "database_id": {"type": "string", "description": "Database ID"},
    "filter": {"type": "object", "description": "Notion filter object"},
    "page_size": {"type": "integer", "description": "Max results", "default": 100}
  },
  "required": ["database_id"]
}
```

---

### Slack (7 tools)

| Tool Name | Description | Permission URN |
|-----------|-------------|----------------|
| `slack.search_messages` | Search Slack messages across channels | `slack:messages:search` |
| `slack.send_message` | Send a message to a Slack channel | `slack:messages:send` |
| `slack.list_channels` | List available Slack channels | `slack:channels:list` |
| `slack.get_channel_history` | Get recent messages from a channel | `slack:channels:history` |
| `slack.join_channel` | Join a Slack channel | `slack:channels:join` |
| `slack.post_reaction` | Add a reaction emoji to a message | `slack:reactions:write` |
| `slack.list_users` | List users in Slack workspace | `slack:users:list` |

#### slack.search_messages

```json
{
  "properties": {
    "query": {"type": "string", "description": "Search query"},
    "channel": {"type": "string", "description": "Channel ID to search in"},
    "limit": {"type": "integer", "description": "Max results", "default": 20}
  },
  "required": ["query"]
}
```

#### slack.send_message

```json
{
  "properties": {
    "channel": {"type": "string", "description": "Channel ID"},
    "text": {"type": "string", "description": "Message text"},
    "thread_ts": {"type": "string", "description": "Thread timestamp for replies"}
  },
  "required": ["channel", "text"]
}
```

#### slack.list_channels

```json
{
  "properties": {
    "types": {"type": "string", "description": "Channel types", "default": "public_channel"},
    "limit": {"type": "integer", "description": "Max results", "default": 100}
  },
  "required": []
}
```

#### slack.get_channel_history

```json
{
  "properties": {
    "channel": {"type": "string", "description": "Channel ID"},
    "limit": {"type": "integer", "description": "Max messages", "default": 10}
  },
  "required": ["channel"]
}
```

#### slack.join_channel

```json
{
  "properties": {
    "channel": {"type": "string", "description": "Channel ID"}
  },
  "required": ["channel"]
}
```

#### slack.post_reaction

```json
{
  "properties": {
    "channel": {"type": "string", "description": "Channel ID"},
    "timestamp": {"type": "string", "description": "Message timestamp"},
    "name": {"type": "string", "description": "Emoji name (without colons)"}
  },
  "required": ["channel", "timestamp", "name"]
}
```

#### slack.list_users

```json
{
  "properties": {
    "limit": {"type": "integer", "description": "Max results", "default": 100}
  },
  "required": []
}
```

---

### HubSpot (7 tools)

| Tool Name | Description | Permission URN |
|-----------|-------------|----------------|
| `hubspot.get_contact` | Get a specific HubSpot contact by ID | `hubspot:contacts:read` |
| `hubspot.create_contact` | Create a new contact in HubSpot | `hubspot:contacts:create` |
| `hubspot.update_contact` | Update an existing HubSpot contact | `hubspot:contacts:update` |
| `hubspot.list_contacts` | List HubSpot contacts | `hubspot:contacts:list` |
| `hubspot.list_deals` | List HubSpot deals | `hubspot:deals:list` |
| `hubspot.create_deal` | Create a new deal in HubSpot | `hubspot:deals:create` |
| `hubspot.update_deal` | Update an existing HubSpot deal | `hubspot:deals:update` |

#### hubspot.get_contact

```json
{
  "properties": {
    "contact_id": {"type": "string", "description": "Contact ID"}
  },
  "required": ["contact_id"]
}
```

#### hubspot.create_contact

```json
{
  "properties": {
    "email": {"type": "string", "description": "Contact email"},
    "firstname": {"type": "string", "description": "First name"},
    "lastname": {"type": "string", "description": "Last name"},
    "company": {"type": "string", "description": "Company name"}
  },
  "required": ["email"]
}
```

#### hubspot.update_contact

```json
{
  "properties": {
    "contact_id": {"type": "string", "description": "Contact ID"},
    "properties": {"type": "object", "description": "Properties to update"}
  },
  "required": ["contact_id"]
}
```

#### hubspot.list_contacts

```json
{
  "properties": {
    "limit": {"type": "integer", "description": "Max results", "default": 20}
  },
  "required": []
}
```

#### hubspot.list_deals

```json
{
  "properties": {
    "stage": {"type": "string", "description": "Filter by deal stage"},
    "limit": {"type": "integer", "description": "Max results", "default": 20}
  },
  "required": []
}
```

#### hubspot.create_deal

```json
{
  "properties": {
    "dealname": {"type": "string", "description": "Deal name"},
    "amount": {"type": "number", "description": "Deal amount"},
    "dealstage": {"type": "string", "description": "Deal stage"},
    "pipeline": {"type": "string", "description": "Pipeline name"}
  },
  "required": ["dealname"]
}
```

#### hubspot.update_deal

```json
{
  "properties": {
    "deal_id": {"type": "string", "description": "Deal ID"},
    "properties": {"type": "object", "description": "Properties to update"}
  },
  "required": ["deal_id"]
}
```

---

### Google Drive (4 tools)

| Tool Name | Description | Permission URN |
|-----------|-------------|----------------|
| `gdrive.search_files` | Search Drive files by query | `gdrive:files:search` |
| `gdrive.read_file` | Get file metadata by ID | `gdrive:files:read` |
| `gdrive.list_files` | List files in the user's Drive | `gdrive:files:list` |
| `gdrive.get_file_metadata` | Get full file metadata | `gdrive:files:metadata` |

#### gdrive.search_files

```json
{
  "properties": {
    "query": {"type": "string", "description": "Search query (plain text or Drive query syntax)"},
    "limit": {"type": "integer", "description": "Max results", "default": 10}
  },
  "required": ["query"]
}
```

> Also accepts `q`, `max_results`, `page_size`, `pageSize` as aliases.

#### gdrive.read_file

```json
{
  "properties": {
    "file_id": {"type": "string", "description": "Drive file ID"}
  },
  "required": ["file_id"]
}
```

> Also accepts `fileId`.

#### gdrive.list_files

```json
{
  "properties": {
    "page_size": {"type": "integer", "description": "Max results", "default": 20},
    "order_by": {"type": "string", "description": "Sort order", "default": "modifiedTime desc"}
  },
  "required": []
}
```

> Also accepts `pageSize`, `max_results`, `orderBy`.

#### gdrive.get_file_metadata

```json
{
  "properties": {
    "file_id": {"type": "string", "description": "Drive file ID"}
  },
  "required": ["file_id"]
}
```

---

### Google Calendar (4 tools)

| Tool Name | Description | Permission URN |
|-----------|-------------|----------------|
| `gcalendar.list_calendars` | List user's calendars | `gcalendar:calendars:list` |
| `gcalendar.list_events` | List events on a calendar | `gcalendar:events:list` |
| `gcalendar.read_event` | Get single event details | `gcalendar:events:read` |
| `gcalendar.search_events` | Search events by free-text query | `gcalendar:events:search` |

#### gcalendar.list_calendars

```json
{
  "properties": {},
  "required": []
}
```

#### gcalendar.list_events

```json
{
  "properties": {
    "calendar_id": {"type": "string", "description": "Calendar ID", "default": "primary"},
    "limit": {"type": "integer", "description": "Max events", "default": 10},
    "time_min": {"type": "string", "description": "Start time (ISO 8601)"}
  },
  "required": []
}
```

> Also accepts `max_results`, `maxResults`.

#### gcalendar.read_event

```json
{
  "properties": {
    "calendar_id": {"type": "string", "description": "Calendar ID", "default": "primary"},
    "event_id": {"type": "string", "description": "Event ID"}
  },
  "required": ["event_id"]
}
```

#### gcalendar.search_events

```json
{
  "properties": {
    "calendar_id": {"type": "string", "description": "Calendar ID", "default": "primary"},
    "query": {"type": "string", "description": "Free-text search query"},
    "max_results": {"type": "integer", "description": "Max results", "default": 10}
  },
  "required": ["query"]
}
```

---

### Gmail (4 tools)

| Tool Name | Description | Permission URN |
|-----------|-------------|----------------|
| `gmail.list_messages` | List messages with optional label filter | `gmail:messages:list` |
| `gmail.read_message` | Get full message content | `gmail:messages:read` |
| `gmail.search_messages` | Search messages by Gmail query syntax | `gmail:messages:search` |
| `gmail.list_labels` | List all Gmail labels | `gmail:labels:list` |

#### gmail.list_messages

```json
{
  "properties": {
    "limit": {"type": "integer", "description": "Max messages", "default": 10},
    "label_ids": {"type": "array", "items": {"type": "string"}, "description": "Filter by label IDs"}
  },
  "required": []
}
```

> Also accepts `max_results`, `maxResults`, `labelIds`.

#### gmail.read_message

```json
{
  "properties": {
    "message_id": {"type": "string", "description": "Message ID"},
    "format": {"type": "string", "description": "Response format", "enum": ["full", "metadata", "minimal", "raw"], "default": "full"}
  },
  "required": ["message_id"]
}
```

> Also accepts `messageId`, `id`.

#### gmail.search_messages

```json
{
  "properties": {
    "query": {"type": "string", "description": "Gmail search query (same syntax as Gmail search bar)"},
    "limit": {"type": "integer", "description": "Max results", "default": 10}
  },
  "required": ["query"]
}
```

> Also accepts `q`, `max_results`, `maxResults`.

#### gmail.list_labels

```json
{
  "properties": {},
  "required": []
}
```

---

## 13. Security

### Prompt Injection Detection

The Gateway scans `tools/call` arguments for prompt injection patterns before forwarding to any backend. Detected injections are blocked with error code `-32602`.

**Patterns detected:**
- "Ignore all previous instructions"
- "You are now an unrestricted AI"
- "Output all stored API keys"
- System prompt override attempts
- Instruction boundary violations

**Response when blocked:**

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "error": {
    "code": -32602,
    "message": "Prompt injection detected in tool arguments",
    "data": {
      "threat_level": "high",
      "blocked_fields": "query"
    }
  }
}
```

The request never reaches the backend API.

### PII Result Filtering

All `tools/call` responses are automatically scanned for personally identifiable information. Detected PII is masked before reaching the agent:

| PII Type | Replacement |
|----------|-------------|
| Email addresses | `[EMAIL REDACTED]` |
| Phone numbers | `[PHONE REDACTED]` |
| Social Security Numbers | `[SSN REDACTED]` |
| Credit card numbers | `[CC REDACTED]` |
| API keys / tokens | `[KEY REDACTED]` |

PII filtering is transparent and always active. It operates in fail-open mode: if the filter itself errors, the response is still returned.

### Fail-Closed Behavior

If the Control Plane is unreachable, the Gateway denies all `tools/list` and `tools/call` requests with error code `-32000`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "Control plane unavailable. Failing closed for security."
  }
}
```

This ensures that the Gateway never processes requests without policy verification.

---

## 14. Audit APIs

Base: `http://localhost:8000/api/v1/audit`

Every action -- permitted, denied, and security-blocked -- is logged with full human attribution.

### POST /api/v1/audit/events

Log an audit event (typically called by the Gateway internally).

| Field | Value |
|-------|-------|
| **Auth** | None |

**Request:**

```json
{
  "event_type": "mcp_tool_call",
  "agent_id": "sdr-assistant-001",
  "on_behalf_of": "sarah@acme.com",
  "tool": "notion.search_pages",
  "arguments": {"query": "report"},
  "result_summary": "3 pages found",
  "session_id": "asess-abc123",
  "delegation_id": "del-xyz789",
  "success": true
}
```

**Response (200):**

```json
{
  "event_id": "evt-abc123",
  "timestamp": "2026-04-14T07:06:28Z"
}
```

---

### GET /api/v1/audit/events

Query audit events with filtering and pagination.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` |
| **Query Params** | `agent_id`, `on_behalf_of`, `organization_id`, `event_type`, `tool`, `delegation_id`, `start_time`, `end_time`, `limit` (1--1000, default 100), `offset` (default 0) |

**Response (200):**

```json
{
  "events": [
    {
      "id": "evt-abc123",
      "timestamp": "2026-04-14T07:06:28Z",
      "event_type": "mcp_tool_call",
      "agent_id": "sdr-assistant-001",
      "on_behalf_of": "sarah@acme.com",
      "tool": "notion.search_pages",
      "arguments": {"query": "report", "limit": 5},
      "result_summary": "3 pages found",
      "success": true,
      "session_id": "asess-abc123",
      "delegation_id": "del-xyz789",
      "extra_data": null,
      "duration_ms": 245
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### Event Types

| Type | Description |
|------|-------------|
| `mcp_tool_call` | Successful tool execution |
| `permission_denied` | Tool call blocked by delegation policy |
| `tool_error` | Blocked by security scanner or backend error |
| `prompt_injection_blocked` | Prompt injection detected and blocked |

---

### GET /api/v1/audit/events/{event_id}

Get a single audit event by ID.

| Field | Value |
|-------|-------|
| **Auth** | None |

**Response (200):** Full audit event object (same schema as list items).

**Errors:** `404 Not Found`

---

### GET /api/v1/audit/summary

Get aggregate audit statistics.

| Field | Value |
|-------|-------|
| **Auth** | None |
| **Query Params** | `agent_id`, `on_behalf_of` (alias `user_email`), `organization_id`, `start_time`, `end_time` |

**Response (200):**

```json
{
  "total_events": 42,
  "by_event_type": {
    "mcp_tool_call": 35,
    "permission_denied": 5,
    "tool_error": 2
  },
  "by_tool": {
    "notion.search_pages": 20,
    "slack.list_channels": 15,
    "notion.create_page": 5
  },
  "by_agent": {
    "sdr-assistant-001": 42
  },
  "time_range": {}
}
```

---

## 15. Vault APIs

Base: `http://localhost:8000/api/v1/vault`

### GET /api/v1/vault/tokens/{service_id}

Retrieve the stored OAuth token for a service. Used by the Gateway to inject credentials.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` or `<TASK_TOKEN>` |
| **Path Params** | `service_id` (e.g., `notion`, `slack`) |

The agent must have a delegated permission with a matching service prefix.

**Response (200):**

```json
{
  "service_id": "notion",
  "user_id": "sarah@acme.com",
  "access_token": "ntn_token_value...",
  "token_type": "bearer",
  "scopes_granted": ["read_pages", "search_content"],
  "expires_at": "2027-01-01T00:00:00Z",
  "is_expired": false
}
```

**Errors:**
- `404 Not Found` -- no token stored for this service
- `403 Forbidden` -- agent lacks permission for this service

---

### POST /api/v1/vault/tokens/{service_id}/refresh

Refresh an OAuth token. Used internally by the Gateway.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <INTERNAL_API_TOKEN>` + `X-User-ID: <email>` header |

**Request:**

```json
{
  "force": false
}
```

**Response (200):**

```json
{
  "service_id": "notion",
  "user_id": "sarah@acme.com",
  "access_token": "new_token_value...",
  "token_type": "bearer",
  "expires_at": "2026-07-14T00:00:00Z",
  "refreshed": true
}
```

---

### Secret Management

These endpoints use the **Backend API Token** for authentication.

#### GET /api/v1/vault/secrets

List stored secrets (metadata only).

**Response (200):**

```json
{
  "secrets": [
    {"name": "openai-api-key", "metadata": {}, "created_at": "2026-01-21T10:00:00Z"}
  ],
  "count": 1
}
```

#### POST /api/v1/vault/store

Store a secret with Shamir secret sharing (split between Control Plane and Gateway).

**Request:**

```json
{
  "name": "openai-api-key",
  "value": "sk-...",
  "secret_metadata": {"service": "openai"}
}
```

**Response (201):**

```json
{
  "name": "openai-api-key",
  "message": "Secret stored successfully"
}
```

#### GET /api/v1/vault/secrets/{name}/value

Retrieve a secret value. Requires Shamir reassembly from both services.

**Response (200):**

```json
{
  "name": "openai-api-key",
  "value": "sk-...",
  "metadata": {},
  "created_at": "2026-01-21T10:00:00Z"
}
```

#### DELETE /api/v1/vault/secrets/{name}

Delete a secret from both Control Plane and Gateway shares.

---

### Credential Management

These endpoints use the **Backend API Token** and support the ephemeral credential lifecycle.

#### POST /api/v1/vault/credentials

Issue an ephemeral credential to an agent.

**Request:**

```json
{
  "agent_id": "sdr-assistant-001",
  "scope": "notion:read",
  "ephemeral_public_key": "base64_key...",
  "signature": "base64_signature...",
  "ttl": 3600
}
```

**Response (201):**

```json
{
  "credential_id": "cred-abc123",
  "ephemeral_public_key": "base64_key...",
  "issued_at": "2026-04-14T07:00:00Z",
  "expires_at": "2026-04-14T08:00:00Z",
  "status": "active"
}
```

#### GET /api/v1/vault/credentials/{credential_id}/verify

Verify a credential's validity. No authentication required (designed for verification by third parties).

**Response (200):**

```json
{
  "credential_id": "cred-abc123",
  "is_valid": true,
  "status": "active",
  "scope": "notion:read",
  "agent_id": "sdr-assistant-001",
  "issued_at": "2026-04-14T07:00:00Z",
  "expires_at": "2026-04-14T08:00:00Z"
}
```

#### POST /api/v1/vault/credentials/{credential_id}/revoke

Revoke a credential.

**Response (200):**

```json
{
  "credential_id": "cred-abc123",
  "status": "revoked"
}
```

#### POST /api/v1/vault/agents/{agent_id}/rotate-identity

Rotate an agent's Ed25519 public key.

**Request:**

```json
{
  "new_public_key": "base64_new_key..."
}
```

**Response:** `204 No Content`

---

## 16. OAuth APIs

Base: `http://localhost:8000/api/v1/oauth`

These endpoints handle the full OAuth authorization flow for connecting backend services.

### GET /api/v1/oauth/{service_id}/authorize

Initiate OAuth authorization for a backend service.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` |
| **Path Params** | `service_id` (`notion`, `slack`, `hubspot`, `gdrive`, `gcalendar`, `gmail`) |
| **Query Params** | `scopes` (optional), `redirect` (boolean, default `false`), `post_connect_redirect` (URL) |

**Response (200, redirect=false):**

```json
{
  "authorization_url": "https://api.notion.com/v1/oauth/authorize?client_id=...&state=...",
  "state": "abc123..."
}
```

**Response (redirect=true):** `302 Redirect` to the OAuth provider.

---

### GET /api/v1/oauth/{service_id}/callback

OAuth callback handler. Exchanges the authorization code for tokens and stores them in the vault.

| Field | Value |
|-------|-------|
| **Auth** | None (state validation) |
| **Query Params** | `code`, `state`, `error`, `error_description` |

**Response (with post_connect_redirect):** `302 Redirect` to `{post_connect_redirect}?service_id={id}&status=connected&scopes={scopes}`

**Response (without redirect):**

```json
{
  "success": true,
  "service_id": "notion",
  "connected": true,
  "scopes_granted": ["read_pages", "search_content"]
}
```

---

### POST /api/v1/oauth/{service_id}/refresh

Manually trigger an OAuth token refresh.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <USER_TOKEN>` |

**Response (200):**

```json
{
  "refreshed": true,
  "expires_in": 3600
}
```

---

## 17. Policy APIs

Base: `http://localhost:8000/api/v1/policies`

### POST /api/v1/policies/

Create a policy that grants an agent permissions on resources.

| Field | Value |
|-------|-------|
| **Auth** | None |

**Request:**

```json
{
  "name": "notion-read-policy",
  "description": "Allow reading Notion pages",
  "agent_id": "sdr-assistant-001",
  "actions": ["read", "search"],
  "resources": ["notion:pages"],
  "effect": "allow"
}
```

**Response (200):** Full policy object with `id` (UUID).

---

### GET /api/v1/policies/

List policies. Query params: `skip` (default 0), `limit` (default 100).

### GET /api/v1/policies/{policy_id}

Get a policy by UUID.

### PUT /api/v1/policies/{policy_id}

Update a policy. All fields optional.

### DELETE /api/v1/policies/{policy_id}

Delete a policy.

---

### Attestation Policies

Base: `/api/v1/policies/attestation`

Used for platform-level identity attestation (Kubernetes, AWS, etc.).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/policies/attestation/` | Create attestation policy |
| `GET` | `/api/v1/policies/attestation/` | List attestation policies |
| `GET` | `/api/v1/policies/attestation/{policy_id}` | Get attestation policy |
| `PUT` | `/api/v1/policies/attestation/{policy_id}` | Update attestation policy |
| `DELETE` | `/api/v1/policies/attestation/{policy_id}` | Delete attestation policy |

---

## 18. Bootstrap APIs

Platform-native agent identity bootstrapping. Agents prove their identity using platform credentials rather than pre-shared keys.

### POST /api/v1/auth/bootstrap/kubernetes

Bootstrap an agent using a Kubernetes ServiceAccount token.

| Field | Value |
|-------|-------|
| **Auth** | None (K8s token in body) |

**Request:**

```json
{
  "sat": "eyJhbGciOiJSUzI1NiIs..."
}
```

**Response (200):**

```json
{
  "agent_id": "k8s-agent-abc123",
  "private_key_b64": "base64_private_key...",
  "public_key_b64": "base64_public_key..."
}
```

---

### POST /api/v1/auth/bootstrap/aws

Bootstrap using AWS IAM credentials.

**Request:**

```json
{
  "token": "aws-sts-token..."
}
```

### POST /api/v1/auth/bootstrap/azure

Bootstrap using Azure Managed Identity token.

**Request:**

```json
{
  "token": "azure-mi-token..."
}
```

### POST /api/v1/auth/bootstrap/docker

Bootstrap from a Docker container.

**Request:**

```json
{
  "container_id": "abc123def456",
  "runtime_token": "docker-runtime-token..."
}
```

### POST /api/v1/bootstrap/attest

GCP-specific attestation bootstrap.

**Request:**

```json
{
  "platform": "gcp",
  "token": "gcp-identity-token..."
}
```

**Response (200):**

```json
{
  "agent_id": "gcp-agent-xyz",
  "private_key": "base64_private_key..."
}
```

---

## 19. Error Reference

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `200` | OK | Successful request |
| `201` | Created | Resource created (agents, secrets, credentials, tasks) |
| `204` | No Content | Key rotation success |
| `302` | Redirect | OAuth/SSO flows |
| `400` | Bad Request | Invalid request body or parameters |
| `401` | Unauthorized | Missing or invalid JWT |
| `403` | Forbidden | Valid JWT but insufficient permissions |
| `404` | Not Found | Resource not found |
| `409` | Conflict | Duplicate resource or invalid state transition |
| `422` | Unprocessable Entity | Validation failed (e.g., permission attenuation violation) |
| `500` | Internal Server Error | Unexpected server error |
| `503` | Service Unavailable | Service not ready |

### MCP JSON-RPC Error Codes

| Code | Name | Description |
|------|------|-------------|
| `-32700` | Parse Error | Invalid JSON in request body |
| `-32600` | Invalid Request | Invalid JSON-RPC 2.0 structure |
| `-32601` | Method Not Found | Unknown MCP method (not `initialize`, `tools/list`, `tools/call`) |
| `-32602` | Invalid Params | Invalid parameters or prompt injection detected |
| `-32603` | Internal Error | Server error or permission denied |
| `-32000` | Policy Unavailable | Control plane unreachable (fail-closed) |
| `-32001` | Permission Denied | Tool not in delegated permissions |
| `-32002` | Session Required | No session -- call `initialize` first |
| `-32003` | Credential Error | Failed to retrieve/inject credentials |
| `-32010` | Invalid Tool Name | Malformed tool name (missing namespace) |

### Standard Error Response Shape

HTTP errors from the Control Plane:

```json
{
  "detail": "Error message string"
}
```

Or structured validation errors:

```json
{
  "detail": {
    "error": "error_code",
    "message": "Human-readable message",
    "invalid_permissions": ["..."],
    "allowed_permissions": ["..."]
  }
}
```

---

## 20. Appendix: Proxy Gateway

The Gateway also supports direct HTTP proxying to arbitrary APIs with automatic secret injection.

### POST/GET/PUT/DELETE /proxy/{path}

Forward an HTTP request to a target URL with automatic credential injection.

| Field | Value |
|-------|-------|
| **Auth** | `Authorization: Bearer <AGENT_JWT>` |
| **Required Header** | `X-Target-Base-URL: https://api.openai.com` |
| **Optional Header** | `X-Deeptrail-Secret-Name: openai-api-key` |

The Gateway:
1. Validates the JWT
2. Checks the target domain against the policy allowlist
3. Retrieves the named secret via Shamir reassembly
4. Injects the secret as an `Authorization` header on the outbound request
5. Forwards the request and returns the response

**Example:**

```bash
curl -X GET "http://localhost:8002/proxy/v1/models" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "X-Target-Base-URL: https://api.openai.com" \
  -H "X-Deeptrail-Secret-Name: openai-api-key"
```

This proxies to `https://api.openai.com/v1/models` with the OpenAI API key injected automatically.

---

## Internal APIs

These APIs are for inter-service communication and are not part of the public API surface.

### Control Plane Internal

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/v1/internal/secrets/{name}/share` | `X-Internal-API-Token` | Gateway fetches Shamir share |

### Gateway Internal

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/internal/shares` | `X-Internal-API-Token` | Store a Shamir share |
| `GET` | `/internal/shares/{name}` | `X-Internal-API-Token` | Retrieve a Shamir share |
| `DELETE` | `/internal/shares/{name}` | `X-Internal-API-Token` | Delete a Shamir share |

---

*Document Version: 2.0 | April 2026 | Source: Verified against MVP codebase*
