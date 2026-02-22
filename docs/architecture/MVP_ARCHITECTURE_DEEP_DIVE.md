# DeepSecure MVP Architecture Deep Dive

> **Created:** February 22, 2026  
> **Purpose:** End-to-end architecture analysis with identified issues and fixes

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Component Diagram (Mermaid)](#2-component-diagram)
3. [Integration Validation Steps Mapped to Architecture](#3-integration-validation-steps-mapped-to-architecture)
4. [Permission Mapper Location & Role](#4-permission-mapper-location--role)
5. [Storage Mechanisms Deep Dive](#5-storage-mechanisms-deep-dive)
6. [Identified Issues](#6-identified-issues)
7. [Proposed Fixes](#7-proposed-fixes)

---

## 1. Architecture Overview

The DeepSecure MVP consists of two primary services:

| Service | Port | Purpose |
|---------|------|---------|
| **Control Plane** (`deeptrail-control`) | 8000 (→8001 internal) | Identity, Authentication, Token Vault, Delegation |
| **Gateway** (`deeptrail-gateway`) | 8002 (→8001 internal) | MCP Protocol, Permission Filtering, Credential Injection, Backend Calls |

### Supporting Services

| Service | Port | Purpose |
|---------|------|---------|
| **PostgreSQL** | 5434 (→5432) | Persistent storage (users, agents, delegations, connected_services) |
| **Redis** | 6380 (→6379) | Session caching, rate limiting (future) |

---

## 2. Component Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                    USER (Sarah)                                           │
│                                                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
│  │   Login     │     │  Connect    │     │  Create     │     │   Query     │            │
│  │  (Step 5)   │     │  Service    │     │ Delegation  │     │   Audit     │            │
│  │             │     │  (Step 6)   │     │  (Step 9)   │     │  (Step 19)  │            │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘            │
└─────────┼────────────────────┼────────────────────┼────────────────────┼─────────────────┘
          │                    │                    │                    │
          ▼                    ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           CONTROL PLANE (deeptrail-control:8000)                         │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              API Layer (FastAPI)                                  │   │
│  │                                                                                   │   │
│  │  /api/v1/auth/login         → UserToken (JWT)                                    │   │
│  │  /api/v1/users/me/services/connect → Store token in Vault + DB record            │   │
│  │  /api/v1/auth/delegate      → Macaroon delegation token                          │   │
│  │  /api/v1/auth/agent/challenge → Ed25519 challenge                                │   │
│  │  /api/v1/auth/agent/verify  → AgentJWT with delegated_permissions                │   │
│  │  /api/v1/vault/tokens/{svc} → Token retrieval (E2 endpoint)                      │   │
│  │  /api/v1/vault/tokens/{svc}/refresh → Token refresh (E3 endpoint)               │   │
│  │  /api/v1/audit/events       → Audit log query                                    │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                               │
│                    ┌─────────────────────┼─────────────────────┐                        │
│                    ▼                     ▼                     ▼                        │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐           │
│  │    PostgreSQL DB    │   │   In-Memory Vault   │   │   OAuth Service     │           │
│  │                     │   │   (VaultClient)     │   │                     │           │
│  │  • UserSession      │   │                     │   │  • Token Refresh    │           │
│  │  • Agent            │   │  ⚠️ EPHEMERAL!      │   │  • OAuth Flow       │           │
│  │  • Delegation       │   │                     │   │                     │           │
│  │  • ConnectedService │   │  Encrypted tokens   │   │                     │           │
│  │    (oauth_token_ref)│◄──│  (Fernet AES-128)   │   │                     │           │
│  └─────────────────────┘   └─────────────────────┘   └─────────────────────┘           │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ Agent JWT via Authorization header
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              GATEWAY (deeptrail-gateway:8002)                            │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              MCP Endpoint (/mcp)                                  │   │
│  │                                                                                   │   │
│  │   JSON-RPC 2.0                                                                    │   │
│  │   ├── initialize → Creates AgentMCPSession, extracts tools from permissions      │   │
│  │   ├── tools/list → Returns filtered tools based on session + permission mapper   │   │
│  │   └── tools/call → Validates permission, injects credentials, calls backend      │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                               │
│    ┌─────────────────────────────────────┼─────────────────────────────────────────┐    │
│    │                                     │                                          │    │
│    ▼                                     ▼                                          ▼    │
│  ┌───────────────────┐   ┌───────────────────────────┐   ┌───────────────────────┐     │
│  │  JWT Validation   │   │    MCP Session Manager    │   │    Permission Mapper  │     │
│  │   Middleware      │   │                           │   │                       │     │
│  │                   │   │  ┌───────────────────┐    │   │  TOOL_TO_PERMISSION:  │     │
│  │  Extracts:        │   │  │ AgentMCPSession   │    │   │                       │     │
│  │  • agent_id       │   │  │ ├── agent_id      │    │   │  notion.search_pages  │     │
│  │  • owner/delegator│   │  │ ├── delegator     │    │   │   → notion:pages:search│    │
│  │  • delegated_perms│   │  │ ├── permissions   │    │   │                       │     │
│  │  • agent_jwt_token│   │  │ └── BackendSession│◄───┼───│  notion.read_page     │     │
│  │                   │   │  │     ├── tools ⚠️  │    │   │   → notion:pages:read │     │
│  └───────────────────┘   │  │     └── cred_ref  │    │   │                       │     │
│                          │  └───────────────────┘    │   │  (fail-closed: deny   │     │
│                          └───────────────────────────┘   │   unknown tools)      │     │
│                                     │                    └───────────────────────┘     │
│    ┌────────────────────────────────┼────────────────────────────┐                     │
│    │                                │                             │                     │
│    ▼                                ▼                             ▼                     │
│  ┌───────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐         │
│  │    Tool Cache     │   │  Credential Injector  │   │   Backend Clients     │         │
│  │                   │   │                       │   │                       │         │
│  │  Per-backend:     │   │  ┌─────────────────┐  │   │  NotionDirectClient   │         │
│  │  • notion: [...]  │   │  │ Token Cache ⚠️  │  │   │  SlackDirectClient    │         │
│  │  • slack: [...]   │   │  │ (60s TTL)       │  │   │  HubSpotDirectClient  │         │
│  │                   │   │  └─────────────────┘  │   │                       │         │
│  │  TTL: 5 minutes   │   │          │            │   │  Makes real API calls │         │
│  │                   │   │          ▼            │   │  with injected creds  │         │
│  └───────────────────┘   │  GET /vault/tokens/   │   └───────────────────────┘         │
│                          │  (calls Control Plane)│                                      │
│                          └───────────────────────┘                                      │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ OAuth Token in Authorization header
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                            EXTERNAL BACKENDS                                             │
│                                                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                                │
│  │   Notion    │     │    Slack    │     │   HubSpot   │                                │
│  │   API       │     │    API      │     │    API      │                                │
│  │             │     │             │     │             │                                │
│  │ api.notion  │     │ slack.com   │     │ api.hubapi  │                                │
│  │   .com/v1   │     │   /api      │     │   .com      │                                │
│  └─────────────┘     └─────────────┘     └─────────────┘                                │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Integration Validation Steps Mapped to Architecture

| Step | Test Scenario | Component | Flow |
|------|---------------|-----------|------|
| **4** | Health Checks | Both | `GET /health` → Each service |
| **5** | User Login | Control Plane | `POST /auth/login` → UserSession (DB) → JWT |
| **6** | Connect Service | Control Plane | `POST /users/me/services/connect` → **VaultClient (In-Memory)** + ConnectedService (DB) |
| **7** | Generate Keypair | Client-side | Pure Ed25519 key generation |
| **8** | Register Agent | Control Plane | `POST /agents/` → Agent (DB) |
| **9** | Create Delegation | Control Plane | `POST /auth/delegate` → Delegation (DB) → Macaroon token |
| **10** | Agent Challenge | Control Plane | `POST /auth/agent/challenge` → Challenge (ephemeral) |
| **11** | Agent Verify | Control Plane | `POST /auth/agent/verify` → **Agent JWT with delegated_permissions** |
| **12** | Vault Token Retrieval | Control Plane | `GET /vault/tokens/{svc}` → VaultClient.retrieve_token() |
| **13** | Vault Token Refresh | Control Plane | `POST /vault/tokens/{svc}/refresh` → OAuthService |
| **14** | OAuth Authorize | Control Plane | `GET /oauth/authorize` (future) |
| **15** | **MCP Initialize** | Gateway | `POST /mcp` (initialize) → **Session Manager creates AgentMCPSession** |
| **16** | **MCP List Tools** | Gateway | `POST /mcp` (tools/list) → **Permission Mapper + Tool Cache** |
| **17** | **MCP Tool Call** | Gateway | `POST /mcp` (tools/call) → **Permission Mapper + Credential Injector + Backend Client** |
| **18** | MCP Permission Denied | Gateway | `POST /mcp` (tools/call blocked) → Permission Mapper rejects |
| **19** | Audit Events | Control Plane | `GET /audit/events` → Audit DB |

---

## 4. Permission Mapper Location & Role

### Location

```
deeptrail-gateway/app/mcp/permission_mapper.py
```

### Role

The **Permission Mapper** is the single source of truth for:

1. **Tool Name → Permission String** mapping
2. **Fail-closed security** (unknown tools are denied)
3. **Reverse lookup** for deriving tools from permissions

### The Problem

The Permission Mapper defines:
```python
TOOL_TO_PERMISSION = {
    "notion.search_pages": "notion:pages:search",
    "notion.read_page": "notion:pages:read",      # SINGULAR
    "notion.query_database": "notion:databases:query",  # SINGULAR
    ...
}
```

But the **Initialize Handler** derives tool names as:
```python
# Current (BROKEN):
tool_name = f"{parts[2]}_{parts[1]}"  
# notion:pages:read → "read_pages" (PLURAL)

# Expected:
# notion:pages:read → "read_page" (SINGULAR)
```

### Consequence

When `tools/list` handler calls `PermissionMapper.is_tool_permitted()`:
```
Session has: read_pages (derived wrong)
Mapper knows: read_page (correct)
Result: MISMATCH → "unknown tool" → denied
```

---

## 5. Storage Mechanisms Deep Dive

### 5.1 In-Memory Vault (Control Plane)

**Location:** `deeptrail-control/app/services/vault_client.py`

**Purpose:** Store OAuth tokens securely with encryption

**Implementation:**
```python
class VaultClient:
    _instance: Optional["VaultClient"] = None  # Singleton
    _tokens: Dict[str, bytes] = {}  # ref → encrypted_data
    _fernet: Fernet  # AES-128-CBC + HMAC
```

**Issue: EPHEMERAL**
- Tokens stored in Python dict `_tokens`
- When container restarts → **ALL TOKENS LOST**
- User must re-connect all services

### 5.2 Credential Injector's Token Cache (Gateway)

**Location:** `deeptrail-gateway/app/middleware/credential_injection.py`

**Purpose:** Brief cache to avoid repeated vault lookups

**Implementation:**
```python
class CredentialInjector:
    cache_ttl_seconds: int = 60  # 1 minute
    _token_cache: Dict[str, Tuple[Dict, float]] = {}  # ref → (token, cached_at)
```

**Flow:**
```
tools/call request
    │
    ▼
Check _token_cache (60s TTL)
    │
    ├── HIT: Use cached token
    │
    └── MISS: Call Control Plane E2 endpoint
              GET /api/v1/vault/tokens/{service_id}
              │
              ▼
              Cache result for 60s
```

**Issue: STALE TOKENS**
- If Control Plane restarts, cache still holds old refs
- If user re-authorizes, cache may have old token

### 5.3 Tool Cache (Gateway)

**Location:** `deeptrail-gateway/app/mcp/tool_cache.py`

**Purpose:** Cache tool schemas to avoid repeated backend calls

**Implementation:**
```python
class ToolCache:
    ttl_seconds: int = 300  # 5 minutes
    _cache: Dict[str, CacheEntry] = {}  # backend → entry
```

**Current State:**
- Populated at startup from `tool_definitions.py`
- Contains tool schemas with descriptions and inputSchema

**Issue: NOT USED CORRECTLY**
- Session stores `read_pages` (wrong)
- Cache has `read_page` (correct)
- Lookup fails → fallback to minimal schema

### 5.4 MCP Session Manager (Gateway)

**Location:** `deeptrail-gateway/app/mcp/session_manager.py`

**Purpose:** Track agent sessions and their tools

**Implementation:**
```python
class MCPSessionManager:
    _sessions: Dict[str, AgentMCPSession] = {}  # session_id → session
    
class AgentMCPSession:
    agent_session_id: str
    delegator: str
    delegated_permissions: List[str]
    connected_services: List[BackendMCPSession]  # Each has "available_tools"
```

**Issue: TOOL NAMES DERIVED WRONG**
- Initialize handler creates session with `read_pages`
- Should use Permission Mapper's `get_all_tools_for_permission()`

---

## 6. Identified Issues

### Issue 1: In-Memory Vault is Ephemeral

| Aspect | Current State | Impact |
|--------|---------------|--------|
| **Storage** | Python dict in memory | Lost on restart |
| **Persistence** | None | Users must re-connect |
| **Replication** | None | Single point of failure |

**Failure Scenario:**
```
1. User connects Notion → Token stored in VaultClient._tokens
2. docker compose restart deeptrail-control
3. VaultClient singleton recreated → _tokens = {}
4. tools/call fails: "Service not connected"
```

### Issue 2: Credential Cache Can Become Stale

| Aspect | Current State | Impact |
|--------|---------------|--------|
| **TTL** | 60 seconds | Short, but problematic |
| **Invalidation** | None | No way to clear on re-auth |
| **Coordination** | None | Gateway doesn't know when vault changes |

**Failure Scenario:**
```
1. Gateway caches token for ref "vault://sarah-notion-abc"
2. Control Plane restarts → token lost
3. User re-connects → NEW token stored with SAME ref
4. Gateway still using old cached (now invalid) token
5. Backend rejects: "Unauthorized"
```

### Issue 3: Tool Name Derivation Mismatch

| Source | Tool Name | Expected |
|--------|-----------|----------|
| Initialize Handler | `read_pages` (plural) | `read_page` (singular) |
| Permission Mapper | `read_page` (singular) | ✓ |
| Tool Cache | `read_page` (singular) | ✓ |

**Root Cause:** Manual string manipulation instead of using Permission Mapper

### Issue 4: Tool Cache Not Aligned with Session

| Component | Tools Known |
|-----------|-------------|
| Session (from initialize) | `[read_pages, search_pages]` (wrong) |
| Tool Cache | `[read_page, search_pages]` (correct) |
| Permission Mapper | `[read_page, search_pages]` (correct) |

**Result:** Cache lookup fails, fallback returns minimal schema

---

## 7. Proposed Fixes

### Fix 1: Persistent Vault Storage (P2)

**Current:** In-memory dict
**Target:** PostgreSQL or Redis

```python
# Option A: PostgreSQL (recommended for production)
class VaultClient:
    def store_token(self, ref: str, token_data: dict):
        encrypted = self._fernet.encrypt(json.dumps(token_data))
        db.execute(
            "INSERT INTO vault_tokens (ref, encrypted_data) VALUES (?, ?)",
            [ref, encrypted]
        )
    
    def retrieve_token(self, ref: str) -> dict:
        row = db.execute("SELECT encrypted_data FROM vault_tokens WHERE ref = ?", [ref])
        return json.loads(self._fernet.decrypt(row.encrypted_data))

# Option B: Redis (faster, good for MVP+)
class VaultClient:
    def __init__(self):
        self._redis = redis.Redis(host='redis', port=6379)
    
    def store_token(self, ref: str, token_data: dict):
        encrypted = self._fernet.encrypt(json.dumps(token_data))
        self._redis.set(f"vault:{ref}", encrypted)
```

**Migration Path:**
1. Add `vault_tokens` table to PostgreSQL
2. Update VaultClient to use DB
3. Keep encryption (Fernet) for security

### Fix 2: Cache Invalidation Strategy

**Option A: Reduce TTL (Quick Fix)**
```python
class CredentialInjector:
    cache_ttl_seconds: int = 10  # Reduce from 60s to 10s
```

**Option B: Event-Driven Invalidation (Proper Fix)**
```python
# Control Plane publishes event on token change
redis.publish("token_updated", json.dumps({"ref": ref}))

# Gateway subscribes and invalidates
async def on_token_update(message):
    ref = json.loads(message)["ref"]
    if ref in credential_injector._token_cache:
        del credential_injector._token_cache[ref]
```

**Option C: No Cache (Simplest)**
```python
class CredentialInjector:
    cache_ttl_seconds: int = 0  # Disable caching entirely
```

### Fix 3: Use Permission Mapper for Tool Name Derivation (WS-J2)

**Current (`initialize.py`):**
```python
for perm in notion_perms:
    parts = perm.split(":")
    if len(parts) >= 3:
        tool_name = f"{parts[2]}_{parts[1]}"  # WRONG
        notion_tools.append(tool_name)
```

**Fixed:**
```python
from ..permission_mapper import PermissionMapper

for perm in notion_perms:
    tools = PermissionMapper.get_all_tools_for_permission(perm)
    for tool in tools:
        # tool is "notion.read_page" → extract "read_page"
        tool_name = tool.split(".", 1)[1] if "." in tool else tool
        notion_tools.append(tool_name)
```

### Fix 4: Complete Tool Definitions

**Add missing tools to `tool_definitions.py`:**

```python
NOTION_TOOLS = [
    CachedTool(
        name="read_page",  # singular
        description="Read a specific Notion page by ID",
        inputSchema={...}
    ),
    CachedTool(
        name="query_database",  # singular
        description="Query a Notion database with filters",
        inputSchema={...}
    ),
    # ... other missing tools
]
```

---

## Summary: Storage Architecture Issues

| Storage | Location | Persistence | Issue | Fix Priority |
|---------|----------|-------------|-------|--------------|
| **In-Memory Vault** | Control Plane | ❌ None | Lost on restart | P2 (PostgreSQL/Redis) |
| **Credential Cache** | Gateway | ❌ 60s TTL | Stale after restart | P1 (reduce TTL or invalidate) |
| **Tool Cache** | Gateway | ✅ 5 min TTL | Misaligned with session | P1 (WS-J2) |
| **MCP Sessions** | Gateway | ❌ None | Wrong tool names | P1 (WS-J2) |

---

## Recommended Action Plan

### Immediate (P1) - WS-J2

1. Fix tool name derivation in `initialize.py`
2. Complete tool definitions in `tool_definitions.py`
3. Reduce credential cache TTL to 10s

### Short-Term (P1.5)

1. Add cache invalidation on Control Plane restart
2. Add health check that clears Gateway caches

### Medium-Term (P2)

1. Migrate Vault to PostgreSQL `vault_tokens` table
2. Add Redis pub/sub for cross-service events
3. Implement proper token refresh flow
