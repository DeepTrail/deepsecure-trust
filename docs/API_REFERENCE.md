# DeepSecure Virtual MCP Server - API Reference

> **Document Version:** 1.1  
> **Last Updated:** February 17, 2026  
> **Status:** MVP Implementation (P1-B2 Complete)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Service Endpoints](#2-service-endpoints)
3. [Control Plane APIs](#3-control-plane-apis)
   - [Authentication APIs](#31-authentication-apis)
   - [Agent Authentication APIs](#32-agent-authentication-apis)
   - [Agent Management APIs](#33-agent-management-apis)
   - [Delegation APIs](#34-delegation-apis)
   - [User Service APIs](#35-user-service-apis)
   - [Vault (Secret Management) APIs](#36-vault-secret-management-apis)
   - [OAuth APIs](#37-oauth-apis)
   - [Policy APIs](#38-policy-apis)
   - [Audit APIs](#39-audit-apis)
   - [Bootstrap APIs](#310-bootstrap-apis)
   - [Internal APIs](#311-internal-apis)
4. [Gateway APIs](#4-gateway-apis)
   - [Health & Status APIs](#41-health--status-apis)
   - [Unified MCP Endpoint](#42-unified-mcp-endpoint)
   - [MCP Protocol Methods](#43-mcp-protocol-methods)
   - [Internal APIs](#44-internal-apis)
5. [Sarah's Journey API Flow](#5-sarahs-journey-api-flow)
6. [Authentication Tokens](#6-authentication-tokens)
7. [Error Codes](#7-error-codes)
8. [Use Case API Mappings](#8-use-case-api-mappings)

---

## 1. Overview

The DeepSecure Virtual MCP Server MVP consists of two main services:

| Service | Purpose | Port (Dev) |
|---------|---------|------------|
| **Control Plane** (`deeptrail-control`) | Authentication, delegation, agent management, policies, audit | 8000 |
| **Gateway** (`deeptrail-gateway`) | MCP protocol handling, tool execution, credential injection | 8002 |

### Key Value Propositions Demonstrated by APIs

| Value Proposition | APIs That Demonstrate It |
|-------------------|--------------------------|
| **Unified MCP Connection** | `POST /mcp` (Gateway) |
| **Delegation-Based Consent** | `POST /api/v1/auth/delegate` (Control Plane) |
| **Tool Filtering** | `tools/list` via `/mcp` (Gateway) |
| **Namespace Resolution** | `tools/list`, `tools/call` via `/mcp` (Gateway) |
| **Audit Trail** | `GET /api/v1/audit/events` (Control Plane) |
| **Fail-Closed Security** | All Gateway MCP operations |

---

## 2. Service Endpoints

### Development Environment

```bash
# Control Plane
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000

# Gateway
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
```

### Docker Compose Services

```yaml
services:
  deeptrail-control:
    ports: ["8000:8001"]
  deeptrail-gateway:
    ports: ["8002:8001"]
  db:
    ports: ["5434:5432"]
  redis:
    ports: ["6380:6379"]
```

---

## 3. Control Plane APIs

Base URL: `http://localhost:8000/api/v1`

### 3.1 Authentication APIs

Prefix: `/api/v1/auth`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `POST` | `/auth/login` | User login with email/password | No | ✅ Implemented (MVP: accepts any password) |
| `POST` | `/auth/challenge` | Request authentication challenge | No | ✅ Implemented |
| `POST` | `/auth/token` | Get access token | No | ✅ Implemented |

#### POST /api/v1/auth/login

User authentication endpoint. Returns JWT token for subsequent requests.

**Request:**
```json
{
  "email": "sarah@acme.com",
  "password": "password123"
}
```

**Response (200 OK):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "email": "sarah@acme.com",
    "id": "sarah@acme.com",
    "organization_id": "org-acme-001"
  },
  "expires_in": 28800
}
```

**MVP Note:** For MVP, this endpoint accepts any password and generates a session without database persistence.

---

### 3.2 Agent Authentication APIs

Prefix: `/api/v1/auth/agent`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `POST` | `/auth/agent/challenge` | Request challenge nonce for Ed25519 signing | No | ✅ Implemented |
| `POST` | `/auth/agent/verify` | Verify signature and issue Agent Session JWT | No | ✅ Implemented |

#### POST /api/v1/auth/agent/challenge

Request a cryptographic challenge for agent authentication.

**Request:**
```json
{
  "agent_id": "agent-sdr-001"
}
```

**Response (200 OK):**
```json
{
  "challenge": "random-nonce-xyz123",
  "expires_in": 300
}
```

#### POST /api/v1/auth/agent/verify

Verify the signed challenge and issue an Agent Session JWT.

**Request:**
```json
{
  "agent_id": "agent-sdr-001",
  "challenge": "random-nonce-xyz123",
  "signature": "base64url-encoded-ed25519-signature"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 28800
}
```

**Agent Session JWT Claims:**
```json
{
  "sub": "agent-sdr-001",
  "owner": "sarah@acme.com",
  "idp_issuer": "https://acme.okta.com",
  "party_type": "first_party",
  "delegated_permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "delegation_id": "del-sarah-sdr-001",
  "session_id": "asess-sdr-001-ghi789",
  "exp": 1737936000
}
```

---

### 3.3 Agent Management APIs

Prefix: `/api/v1/agents`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `POST` | `/agents/` | Register a new agent with public key | User JWT | ✅ Implemented |
| `GET` | `/agents/` | List all agents | User JWT | ✅ Implemented |
| `GET` | `/agents/{agent_id}` | Get agent details | User JWT | ✅ Implemented |
| `PATCH` | `/agents/{agent_id}` | Update agent | User JWT | ✅ Implemented |
| `DELETE` | `/agents/{agent_id}` | Delete agent | User JWT | ✅ Implemented |

#### POST /api/v1/agents/

Register a new agent with its Ed25519 public key.

**Request:**
```json
{
  "id": "agent-sdr-001",
  "name": "SDR Assistant",
  "owner": "sarah@acme.com",
  "public_key": "base64-encoded-ed25519-public-key",
  "organization_id": "org-acme-001"
}
```

**Response (201 Created):**
```json
{
  "id": "agent-sdr-001",
  "name": "SDR Assistant",
  "owner": "sarah@acme.com",
  "organization_id": "org-acme-001",
  "status": "active",
  "created_at": "2026-01-21T10:00:00Z"
}
```

---

### 3.4 Delegation APIs

Prefix: `/api/v1/auth` (delegation endpoints are under auth)

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `POST` | `/auth/delegate` | Create user-to-agent delegation | User JWT | ✅ Implemented (MVP: in-memory) |
| `POST` | `/auth/agent-delegate` | Create agent-to-agent delegation | Agent JWT | ✅ Implemented |

#### POST /api/v1/auth/delegate

Create a delegation from a user to an agent with scoped permissions.

**Request:**
```json
{
  "agent_id": "agent-sdr-001",
  "permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "constraints": {
    "max_actions_per_day": 100
  },
  "expires_in": 604800
}
```

**Response (201 Created):**
```json
{
  "delegation_id": "del-sarah-sdr-001-abc123",
  "agent_id": "agent-sdr-001",
  "delegator": "sarah@acme.com",
  "permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "expires_at": "2026-01-28T10:00:00Z",
  "created_at": "2026-01-21T10:00:00Z"
}
```

**MVP Note:** Delegations are stored in-memory for MVP. In production, they would be stored in the database as Macaroon tokens.

---

### 3.5 User Service APIs

Prefix: `/api/v1/users`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `POST` | `/users/me/services/connect` | Connect a backend service (OAuth) | User JWT | ✅ Implemented (MVP: in-memory) |

#### POST /api/v1/users/me/services/connect

Connect a backend service by storing OAuth tokens.

**Request:**
```json
{
  "service_id": "notion",
  "oauth_token": "notion-oauth-token-xyz",
  "oauth_refresh_token": "notion-refresh-token-abc",
  "scopes": ["read_content", "search", "create_pages"]
}
```

**Response (201 Created):**
```json
{
  "service_id": "notion",
  "user_id": "sarah@acme.com",
  "scopes_granted": ["read_content", "search", "create_pages"],
  "connected_at": "2026-01-21T10:05:00Z"
}
```

**MVP Note:** OAuth tokens are stored in the in-memory VaultClient for MVP.

---

### 3.6 Vault (Secret Management) APIs

Prefix: `/api/v1/vault`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `GET` | `/vault/secrets` | List secrets | User/Agent JWT | ✅ Implemented |
| `POST` | `/vault/store` | Store a secret | User/Agent JWT | ✅ Implemented |
| `GET` | `/vault/secrets/{name}` | Get secret metadata | User/Agent JWT | ✅ Implemented |
| `GET` | `/vault/secrets/{name}/value` | Get secret value | User/Agent JWT | ✅ Implemented |
| `DELETE` | `/vault/secrets/{name}` | Delete secret | User/Agent JWT | ✅ Implemented |
| `POST` | `/vault/credentials` | Issue credential | User/Agent JWT | ✅ Implemented |
| `POST` | `/vault/credentials/{id}/revoke` | Revoke credential | User/Agent JWT | ✅ Implemented |
| `GET` | `/vault/credentials/{id}/verify` | Verify credential | User/Agent JWT | ✅ Implemented |
| `POST` | `/vault/agents/{agent_id}/rotate-identity` | Rotate agent keys | User JWT | ✅ Implemented |
| `GET` | `/vault/tokens/{service_id}` | Get OAuth token for service | User/Agent JWT | ✅ Implemented (P1-B2) |
| `POST` | `/vault/tokens/{service_id}/refresh` | Refresh OAuth token | User/Agent JWT | ✅ Implemented (P1-B2) |

#### GET /api/v1/vault/tokens/{service_id}

Retrieve stored OAuth token for a specific service.

**Path Parameters:**
- `service_id`: Service identifier (e.g., `notion`, `slack`, `hubspot`)

**Headers:**
```
Authorization: Bearer <user-jwt or agent-jwt>
```

**Response (200 OK):**
```json
{
  "service_id": "notion",
  "user_id": "sarah@acme.com",
  "access_token": "notion-oauth-token-xyz",
  "token_type": "bearer",
  "scope": "read_content search",
  "expires_at": "2026-01-28T10:00:00Z",
  "is_expired": false
}
```

**Error Responses:**
- `404 Not Found`: Token not found for service
- `401 Unauthorized`: Invalid or missing JWT

#### POST /api/v1/vault/tokens/{service_id}/refresh

Request token refresh for an OAuth token.

**Path Parameters:**
- `service_id`: Service identifier

**Request:**
```json
{
  "force": false
}
```

**Response (200 OK):**
```json
{
  "service_id": "notion",
  "user_id": "sarah@acme.com",
  "access_token": "new-notion-token-abc",
  "token_type": "bearer",
  "expires_at": "2026-02-04T10:00:00Z",
  "refreshed": true
}
```

**Error Responses:**
- `404 Not Found`: Token not found for service
- `400 Bad Request`: Token cannot be refreshed (no refresh token)

---

### 3.7 OAuth APIs

Prefix: `/api/v1/oauth`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `GET` | `/oauth/{service_id}/authorize` | Initiate OAuth authorization flow | User JWT | ✅ Implemented (P1-B2) |
| `GET` | `/oauth/{service_id}/callback` | OAuth callback handler | No (state verification) | ✅ Implemented (P1-B2) |
| `POST` | `/oauth/{service_id}/refresh` | Refresh OAuth token | User JWT | ✅ Implemented (P1-B2) |

#### GET /api/v1/oauth/{service_id}/authorize

Initiate OAuth authorization flow for a service. Redirects to provider's authorization page.

**Path Parameters:**
- `service_id`: Service identifier (e.g., `notion`, `slack`, `hubspot`)

**Query Parameters:**
- `redirect_uri` (optional): Custom redirect URI after completion
- `scopes` (optional): Comma-separated list of requested scopes

**Headers:**
```
Authorization: Bearer <user-jwt>
```

**Response:** `302 Redirect` to OAuth provider authorization URL

#### GET /api/v1/oauth/{service_id}/callback

OAuth callback endpoint. Handles authorization code exchange.

**Query Parameters:**
- `code`: Authorization code from OAuth provider
- `state`: State parameter for CSRF protection

**Response (Success):** `302 Redirect` to configured redirect URI with success status

**Response (Error):** `302 Redirect` with error parameter

#### POST /api/v1/oauth/{service_id}/refresh

Manually trigger OAuth token refresh.

**Path Parameters:**
- `service_id`: Service identifier

**Request:**
```json
{
  "force": true
}
```

**Response (200 OK):**
```json
{
  "service_id": "notion",
  "refreshed": true,
  "expires_at": "2026-02-04T10:00:00Z"
}
```

---

### 3.8 Policy APIs

Prefix: `/api/v1/policies`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `GET` | `/policies/` | List policies | User JWT | ✅ Implemented |
| `POST` | `/policies/` | Create policy | User JWT | ✅ Implemented |
| `GET` | `/policies/{policy_id}` | Get policy | User JWT | ✅ Implemented |
| `PUT` | `/policies/{policy_id}` | Update policy | User JWT | ✅ Implemented |
| `DELETE` | `/policies/{policy_id}` | Delete policy | User JWT | ✅ Implemented |

#### Attestation Policies

Prefix: `/api/v1/policies/attestation`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `GET` | `/policies/attestation/` | List attestation policies | User JWT | ✅ Implemented |
| `POST` | `/policies/attestation/` | Create attestation policy | User JWT | ✅ Implemented |
| `GET` | `/policies/attestation/{policy_id}` | Get attestation policy | User JWT | ✅ Implemented |
| `PUT` | `/policies/attestation/{policy_id}` | Update attestation policy | User JWT | ✅ Implemented |
| `DELETE` | `/policies/attestation/{policy_id}` | Delete attestation policy | User JWT | ✅ Implemented |

---

### 3.9 Audit APIs

Prefix: `/api/v1/audit`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `GET` | `/audit/events` | Query audit events | User JWT | ✅ Implemented (MVP: in-memory) |
| `GET` | `/audit/events/{event_id}` | Get single audit event | User JWT | ✅ Implemented |
| `GET` | `/audit/summary` | Get audit statistics | User JWT | ✅ Implemented |
| `POST` | `/audit/events` | Log audit event (internal) | Internal | ✅ Implemented |

#### GET /api/v1/audit/events

Query audit events with filtering and pagination.

**Query Parameters:**
- `agent_id` (optional): Filter by agent ID
- `user_id` (optional): Filter by user ID
- `event_type` (optional): Filter by event type
- `start_time` (optional): Start of time range
- `end_time` (optional): End of time range
- `skip` (optional): Pagination offset
- `limit` (optional): Pagination limit

**Response (200 OK):**
```json
{
  "events": [
    {
      "timestamp": "2026-01-21T10:15:32Z",
      "event_type": "mcp_tool_call",
      "agent_id": "agent-sdr-001",
      "on_behalf_of": "sarah@acme.com",
      "tool": "notion.search_pages",
      "arguments": {"query": "competitor analysis", "limit": 5},
      "result_summary": "3 pages found",
      "session_id": "asess-sdr-001-ghi789"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

---

### 3.10 Bootstrap APIs

Prefix: `/api/v1/bootstrap` and `/api/v1/auth/bootstrap`

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `POST` | `/bootstrap/attest` | Attest and create agent | Platform token | ✅ Implemented |
| `POST` | `/auth/bootstrap/kubernetes` | Kubernetes ServiceAccount bootstrap | K8s token | ✅ Implemented |
| `POST` | `/auth/bootstrap/aws` | AWS IAM role bootstrap | AWS creds | ✅ Implemented |
| `POST` | `/auth/bootstrap/azure` | Azure managed identity bootstrap | Azure token | ✅ Implemented |
| `POST` | `/auth/bootstrap/docker` | Docker container bootstrap | Docker attestation | ✅ Implemented |

---

### 3.11 Internal APIs

Prefix: `/api/v1/internal` (not included in OpenAPI schema)

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `GET` | `/internal/secrets/{secret_name}/share` | Get secret share for split-key | Internal token | ✅ Implemented |

---

## 4. Gateway APIs

Base URL: `http://localhost:8002`

### 4.1 Health & Status APIs

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `GET` | `/` | Root health check | No | ✅ Implemented |
| `GET` | `/health` | Detailed health check | No | ✅ Implemented |
| `GET` | `/ready` | Readiness check | No | ✅ Implemented |
| `GET` | `/metrics` | Prometheus metrics | No | ⏳ Placeholder |
| `GET` | `/config` | Get configuration | No | ⏳ Placeholder |

#### GET /health

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "control_plane": "connected"
}
```

---

### 4.2 Unified MCP Endpoint

The core value proposition of the Virtual MCP Server pattern.

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `POST` | `/mcp` | MCP JSON-RPC 2.0 endpoint | Agent JWT | ✅ Implemented |

#### POST /mcp

Single endpoint for all MCP protocol operations. Agent connects to ONE endpoint and accesses tools from MULTIPLE backends.

**Headers:**
```
Authorization: Bearer <agent-session-jwt>
Content-Type: application/json
```

**Request (JSON-RPC 2.0):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "notion.search_pages",
        "description": "[Notion] Search pages in workspace",
        "inputSchema": {...}
      }
    ]
  }
}
```

---

### 4.3 MCP Protocol Methods

All MCP methods are invoked through `POST /mcp` using JSON-RPC 2.0.

| MCP Method | Description | MVP Status |
|------------|-------------|------------|
| `initialize` | Establish MCP session | ✅ Implemented |
| `tools/list` | Get available tools (filtered by delegation) | ✅ Implemented |
| `tools/call` | Execute a tool | ✅ Implemented |

#### initialize

Establishes an MCP session with the Virtual MCP Server.

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
      "name": "SDR-Assistant",
      "version": "1.0.0"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "DeepTrail Gateway",
      "version": "0.1.0"
    }
  }
}
```

**What happens during initialize:**
1. Gateway validates Agent Session JWT
2. Extracts `delegated_permissions` from JWT
3. Looks up connected services for the delegator
4. Creates MCP Sessions for each backend
5. Returns server capabilities

---

#### tools/list

Returns available tools filtered by agent's delegated permissions.

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
        "description": "[Notion] Search pages in workspace",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 10}
          },
          "required": ["query"]
        }
      },
      {
        "name": "notion.read_page",
        "description": "[Notion] Read a specific page by ID",
        "inputSchema": {...}
      },
      {
        "name": "slack.search_messages",
        "description": "[Slack] Search messages in channels",
        "inputSchema": {...}
      },
      {
        "name": "slack.list_channels",
        "description": "[Slack] List available channels",
        "inputSchema": {...}
      }
    ]
  }
}
```

**Key Properties:**
- Agent sees ONLY tools matching their delegated permissions
- Tools are namespace-prefixed: `{backend}.{tool_name}`
- 90%+ reduction in visible tools compared to raw backend access

---

#### tools/call

Execute a tool with the delegator's credentials.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "notion.search_pages",
    "arguments": {
      "query": "competitor analysis",
      "limit": 5
    }
  }
}
```

**Response (Success):**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Found 3 pages: ..."
      }
    ]
  }
}
```

**Response (Permission Denied):**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32001,
    "message": "Permission denied: notion:pages:create not delegated"
  }
}
```

**Processing Flow:**
1. Parse namespace: `notion.search_pages` → server: `notion`, tool: `search_pages`
2. Map to permission: `notion:pages:search`
3. Validate against `delegated_permissions` in JWT
4. Check constraints (e.g., `max_actions_per_day`)
5. Get user's OAuth token from vault
6. Forward to backend MCP server with user's credentials
7. Log audit event
8. Return result to agent

---

### 4.4 Internal APIs

These APIs are for Control Plane ↔ Gateway communication.

| Method | Endpoint | Description | Auth Required | MVP Status |
|--------|----------|-------------|---------------|------------|
| `POST` | `/internal/shares` | Receive secret share | Internal token | ✅ Implemented |
| `GET` | `/internal/shares/{secret_name}` | Get secret share | Internal token | ✅ Implemented |
| `DELETE` | `/internal/shares/{secret_name}` | Delete secret share | Internal token | ✅ Implemented |

---

## 5. Sarah's Journey API Flow

Complete API flow for the Sarah's Journey use case:

```
Step 2: User Authentication
────────────────────────────────────────────────────────────────────
POST http://localhost:8000/api/v1/auth/login
  Body: {"email": "sarah@acme.com", "password": "password123"}
  Returns: User JWT token

Step 3: Connect Backend Services
────────────────────────────────────────────────────────────────────
POST http://localhost:8000/api/v1/users/me/services/connect
  Headers: Authorization: Bearer <user-jwt>
  Body: {"service_id": "notion", "oauth_token": "..."}

POST http://localhost:8000/api/v1/users/me/services/connect
  Headers: Authorization: Bearer <user-jwt>
  Body: {"service_id": "slack", "oauth_token": "..."}

Step 4: Register Agent & Create Delegation
────────────────────────────────────────────────────────────────────
POST http://localhost:8000/api/v1/agents/
  Headers: Authorization: Bearer <user-jwt>
  Body: {"id": "agent-sdr-001", "name": "SDR Assistant", ...}

POST http://localhost:8000/api/v1/auth/delegate
  Headers: Authorization: Bearer <user-jwt>
  Body: {"agent_id": "agent-sdr-001", "permissions": [...]}

Step 5: Agent Authentication
────────────────────────────────────────────────────────────────────
POST http://localhost:8000/api/v1/auth/agent/challenge
  Body: {"agent_id": "agent-sdr-001"}
  Returns: {"challenge": "nonce-xyz"}

POST http://localhost:8000/api/v1/auth/agent/verify
  Body: {"agent_id": "agent-sdr-001", "challenge": "nonce-xyz", "signature": "..."}
  Returns: Agent JWT token

Step 6: MCP Initialize
────────────────────────────────────────────────────────────────────
POST http://localhost:8002/mcp
  Headers: Authorization: Bearer <agent-jwt>
  Body: {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {...}}

Step 7: Discover Tools
────────────────────────────────────────────────────────────────────
POST http://localhost:8002/mcp
  Headers: Authorization: Bearer <agent-jwt>
  Body: {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

Step 8: Execute Authorized Tool
────────────────────────────────────────────────────────────────────
POST http://localhost:8002/mcp
  Headers: Authorization: Bearer <agent-jwt>
  Body: {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "notion.search_pages", ...}}

Step 9: Unauthorized Tool (Denied)
────────────────────────────────────────────────────────────────────
POST http://localhost:8002/mcp
  Headers: Authorization: Bearer <agent-jwt>
  Body: {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "notion.create_page", ...}}
  Returns: Error -32001: Permission denied

Step 10: Review Audit Trail
────────────────────────────────────────────────────────────────────
GET http://localhost:8000/api/v1/audit/events?agent_id=agent-sdr-001
  Headers: Authorization: Bearer <user-jwt>
```

---

## 6. Authentication Tokens

### Token Hierarchy

| Layer | Token Type | Issuer | Purpose | TTL |
|-------|------------|--------|---------|-----|
| **0** | User ID-Token | Enterprise IdP (Okta) | User identity from SSO | 1 hour |
| **1** | User Session | Control Plane | Track connected services | 8 hours |
| **2** | Delegation Token | Control Plane | User→Agent permission grant | 7 days |
| **3** | Agent Session JWT | Control Plane | Agent runtime identity | 8 hours |

### JWT Claim Structures

#### User Session Token Claims
```json
{
  "sub": "sarah@acme.com",
  "session_id": "usess-sarah-abc123",
  "organization_id": "org-acme-001",
  "exp": 1737936000,
  "iat": 1737907200
}
```

#### Agent Session JWT Claims
```json
{
  "sub": "agent-sdr-001",
  "owner": "sarah@acme.com",
  "idp_issuer": "https://acme.okta.com",
  "party_type": "first_party",
  "delegated_permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "delegation_id": "del-sarah-sdr-001",
  "session_id": "asess-sdr-001-ghi789",
  "exp": 1737936000
}
```

---

## 7. Error Codes

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful request |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid request body |
| 401 | Unauthorized | Missing or invalid JWT |
| 403 | Forbidden | Valid JWT but insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists |
| 500 | Internal Server Error | Unexpected server error |

### MCP JSON-RPC Error Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| -32700 | Parse Error | Invalid JSON |
| -32600 | Invalid Request | Invalid JSON-RPC structure |
| -32601 | Method Not Found | Unknown MCP method |
| -32602 | Invalid Params | Invalid method parameters |
| -32603 | Internal Error | Server error |
| -32000 | Security Denial | Control plane unavailable (fail-closed) |
| -32001 | Permission Denied | Tool not in delegated permissions |
| -32002 | Session Required | No agent session (call initialize first) |

---

## 8. Use Case API Mappings

### Use Case 1: AI Agent Vendor Integration

| Step | API | Purpose |
|------|-----|---------|
| Connect | `POST /api/v1/users/me/services/connect` | User connects enterprise tools |
| Delegate | `POST /api/v1/auth/delegate` | User grants vendor agent permissions |
| Operate | `POST /mcp` | Vendor agent uses single endpoint |
| Revoke | `DELETE /api/v1/delegations/{id}` | Instant revocation |

### Use Case 2: Enterprise Agent Onboarding

| Step | API | Purpose |
|------|-----|---------|
| Authenticate | `POST /api/v1/auth/login` | Employee SSO login |
| Register | `POST /api/v1/agents/` | Employee registers agent |
| Connect | `POST /api/v1/users/me/services/connect` | Employee connects approved tools |
| Delegate | `POST /api/v1/auth/delegate` | Employee delegates scoped permissions |
| Operate | `POST /mcp` | Agent operates within guardrails |
| Monitor | `GET /api/v1/audit/events` | View agent activity |

### Use Case 3: MCP Server Rollout

| Step | API | Purpose |
|------|-----|---------|
| Register | `POST /mcp-registry/servers` | Register new MCP server (sandbox) |
| Test | `POST /mcp` | Test traffic in sandbox mode |
| Review | `GET /api/v1/audit/events` | Analyze access patterns |
| Promote | `PUT /mcp-registry/servers/{id}` | Move to production |
| Monitor | `GET /metrics` | Production monitoring |
| Circuit Break | `POST /mcp-registry/servers/{id}/circuit-breaker` | Emergency stop |

---

## Appendix: Quick Reference

### Control Plane API Summary

```
POST   /api/v1/auth/login                       # User login
POST   /api/v1/auth/agent/challenge             # Agent challenge
POST   /api/v1/auth/agent/verify                # Agent verify → JWT
POST   /api/v1/auth/delegate                    # Create delegation
POST   /api/v1/agents/                          # Register agent
GET    /api/v1/agents/                          # List agents
POST   /api/v1/users/me/services/connect        # Connect OAuth service
GET    /api/v1/audit/events                     # Query audit logs
POST   /api/v1/vault/store                      # Store secret
GET    /api/v1/vault/secrets/{name}/value       # Get secret
GET    /api/v1/vault/tokens/{service_id}        # Get OAuth token (P1-B2)
POST   /api/v1/vault/tokens/{service_id}/refresh # Refresh OAuth token (P1-B2)
GET    /api/v1/oauth/{service_id}/authorize     # OAuth authorize (P1-B2)
GET    /api/v1/oauth/{service_id}/callback      # OAuth callback (P1-B2)
POST   /api/v1/oauth/{service_id}/refresh       # OAuth refresh (P1-B2)
GET    /api/v1/policies/                        # List policies
```

### Gateway API Summary

```
GET    /health                                  # Health check
GET    /ready                                   # Readiness check
POST   /mcp                                     # MCP JSON-RPC 2.0 endpoint
         method: initialize                     # Start session
         method: tools/list                     # Discover tools
         method: tools/call                     # Execute tool
```

---

*Document Version: 1.0 | Generated: February 2026 | Source: MVP Implementation*
