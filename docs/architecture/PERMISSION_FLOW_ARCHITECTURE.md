# Permission Flow Architecture: End-to-End Deep Dive

> **Created:** February 22, 2026  
> **Last Updated:** May 7, 2026  
> **Purpose:** Document the complete permission flow from Notion capabilities to agent tool access

---

## Table of Contents

1. [Overview Diagram](#1-overview-diagram)
2. [Four Layers of Permissions](#2-four-layers-of-permissions)
3. [Step-by-Step Flow](#3-step-by-step-flow)
4. [Current Implementation Analysis](#4-current-implementation-analysis)
5. [Gap Analysis](#5-gap-analysis)
6. [Proposed Fixes](#6-proposed-fixes)
7. [Two Mappers: Permission Mapper vs Scope Mapper](#7-two-mappers-permission-mapper-vs-scope-mapper)
8. [ScopeMapper: Current Design, Risks, and Evolution Path](#8-scopemapper-current-design-risks-and-evolution-path)
9. [Implementation Status (May 2026)](#9-implementation-status-may-2026)

---

## 1. Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              LAYER 1: NOTION INTEGRATION                                 │
│                         (What Notion allows the integration to do)                       │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │ Notion Internal Integration Settings (image shows these)                         │    │
│  │                                                                                   │    │
│  │ Content capabilities:          Comment capabilities:    User capabilities:       │    │
│  │ ☑ Read content                 ☐ Read comments          ○ No user information   │    │
│  │ ☑ Update content               ☐ Insert comments        ○ Read user info        │    │
│  │ ☑ Insert content                                        ● Read user + email     │    │
│  │                                                                                   │    │
│  │ ─────────────────────────────────────────────────────────────────────────────    │    │
│  │ Internal Integration Secret: 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 │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
│  These capabilities determine what API calls the token CAN make to Notion API.          │
│  Notion enforces these - calls outside capabilities return 403/401.                     │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ (Manual copy of API key + capability knowledge)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              LAYER 2: SERVICE CONNECTION                                 │
│                      (Step 6: What Sarah tells DeepSecure she allows)                   │
│                                                                                          │
│  POST /api/v1/users/me/services/connect                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │ {                                                                                │    │
│  │   "service_id": "notion",                                                       │    │
│  │   "oauth_token": {                                                              │    │
│  │     "access_token": "ntn_xxx...",           ← Notion API key                    │    │
│  │     "token_type": "bearer",                                                     │    │
│  │     "scope": "read_pages search_content",   ← ARBITRARY STRING (user-defined)  │    │
│  │     "expires_at": "2027-02-22T00:00:00Z"                                        │    │
│  │   }                                                                              │    │
│  │ }                                                                                │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
│  IMPORTANT: The `scope` field is SELF-DECLARED by Sarah!                                │
│  DeepSecure does NOT validate these against Notion's actual capabilities.               │
│  This is a TRUST boundary - Sarah declares what she's allowing.                         │
│                                                                                          │
│  Stored in:                                                                              │
│    - ConnectedService.scopes_granted: ["read_pages", "search_content"]                  │
│    - VaultClient: Encrypted token data (including scope)                                │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ (Sarah creates delegation)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              LAYER 3: DELEGATION                                         │
│                      (Step 9: What Sarah explicitly grants to agent)                    │
│                                                                                          │
│  POST /api/v1/auth/delegate                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │ {                                                                                │    │
│  │   "agent_id": "sdr-assistant-001",                                              │    │
│  │   "permissions": [                                                               │    │
│  │     "notion:pages:search",    ← Fine-grained permission format                  │    │
│  │     "notion:pages:read",                                                        │    │
│  │     "notion:databases:query",                                                   │    │
│  │     "slack:messages:search",                                                    │    │
│  │     "slack:channels:list"                                                       │    │
│  │   ],                                                                             │    │
│  │   "constraints": {                                                               │    │
│  │     "rate_limit": 100,                                                          │    │
│  │     "expires_in_hours": 8                                                       │    │
│  │   }                                                                              │    │
│  │ }                                                                                │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
│  These permissions are embedded in the Agent JWT:                                        │
│    jwt.delegated_permissions = ["notion:pages:search", "notion:pages:read", ...]        │
│                                                                                          │
│  ⚠️  CURRENT GAP: No validation that delegated_permissions ⊆ connected scopes!         │
│  Sarah COULD delegate "notion:pages:create" even if she only connected with             │
│  "read_pages" scope. The system would allow it until Notion API rejects it.            │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ (Agent authenticates and calls tools)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              LAYER 4: TOOL ACCESS                                        │
│                      (Steps 15-17: What agent can actually use)                         │
│                                                                                          │
│  Gateway's Permission Mapper enforces delegated_permissions → tools                     │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │ TOOL_TO_PERMISSION = {                                                            │   │
│  │   "notion.search_pages": "notion:pages:search",                                  │   │
│  │   "notion.read_page":    "notion:pages:read",                                    │   │
│  │   "notion.create_page":  "notion:pages:create",  ← Would be blocked              │   │
│  │   "notion.update_page":  "notion:pages:update",  ← Would be blocked              │   │
│  │   ...                                                                             │   │
│  │ }                                                                                 │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  Flow:                                                                                   │
│  1. tools/list: Filter tools by jwt.delegated_permissions                              │
│  2. tools/call: Check PermissionMapper.is_tool_permitted(tool, delegated_permissions)  │
│  3. If allowed: Inject credentials and call Notion API                                  │
│  4. Notion API enforces its own capabilities (final backstop)                           │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Four Layers of Permissions

### Layer 1: Notion Integration Capabilities (External)

| Capability | Description | Notion API Scope |
|------------|-------------|------------------|
| **Read content** | Access page content | `read_content` or included in API key |
| **Update content** | Modify existing pages | `update_content` |
| **Insert content** | Create new pages/blocks | `insert_content` |
| **Read comments** | Read page comments | `read_comments` |
| **Insert comments** | Create comments | `insert_comments` |
| **Read user info** | Access workspace users | `read_user` |

**Source:** Notion's integration settings page (as shown in the image)

**Enforcement:** Notion API server - returns 403/401 if token doesn't have capability

### Layer 2: Connected Service Scopes (DeepSecure)

| Field | Location | Purpose |
|-------|----------|---------|
| `scope` | Request body | User-declared capabilities they're granting |
| `scopes_granted` | `ConnectedService` table | Stored for reference |
| Token data | VaultClient | Encrypted, includes scope |

**Current State:** Self-declared, not validated against Notion

**Example Mapping:**
```
User-Declared Scope          Intended Meaning
─────────────────────        ─────────────────────
"read_pages"                 Can read Notion pages
"search_content"             Can search across workspace
"write_pages"                Can create/update pages
```

### Layer 3: Delegated Permissions (DeepSecure)

| Field | Location | Purpose |
|-------|----------|---------|
| `permissions` | Delegation request | Explicit list from user |
| `delegated_permissions` | Agent JWT | Embedded in token |

**Format:** `<service>:<resource>:<action>`

**Examples:**
```
Permission String            Maps To Tool
─────────────────────        ─────────────────────
notion:pages:search          notion.search_pages
notion:pages:read            notion.read_page
notion:databases:query       notion.query_database
slack:messages:search        slack.search_messages
```

### Layer 4: Tool Access (Gateway)

| Component | Purpose |
|-----------|---------|
| `PermissionMapper` | Maps tool → permission |
| `tools/list` handler | Filters visible tools |
| `tools/call` handler | Validates before execution |
| Backend clients | Actually call external APIs |

---

## 3. Step-by-Step Flow

### Complete Sequence Diagram

```
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│   Sarah    │     │  Control   │     │   Vault    │     │  Gateway   │     │   Notion   │
│   (User)   │     │   Plane    │     │ (In-memory)│     │            │     │    API     │
└─────┬──────┘     └─────┬──────┘     └─────┬──────┘     └─────┬──────┘     └─────┬──────┘
      │                  │                  │                  │                  │
      │ Step 5: Login    │                  │                  │                  │
      │─────────────────>│                  │                  │                  │
      │                  │                  │                  │                  │
      │  USER_TOKEN (JWT)│                  │                  │                  │
      │<─────────────────│                  │                  │                  │
      │                  │                  │                  │                  │
      │ Step 6: Connect Service            │                  │                  │
      │  service_id: "notion"              │                  │                  │
      │  scope: "read_pages search_content"│                  │                  │
      │  access_token: "ntn_xxx..."        │                  │                  │
      │─────────────────>│                  │                  │                  │
      │                  │                  │                  │                  │
      │                  │  store_token()   │                  │                  │
      │                  │─────────────────>│                  │                  │
      │                  │                  │                  │                  │
      │                  │  token_ref       │                  │                  │
      │                  │<─────────────────│                  │                  │
      │                  │                  │                  │                  │
      │                  │  Save to DB:     │                  │                  │
      │                  │  ConnectedService│                  │                  │
      │                  │  (scopes_granted)│                  │                  │
      │                  │                  │                  │                  │
      │  success, scopes_granted=["read_pages", "search_content"]                 │
      │<─────────────────│                  │                  │                  │
      │                  │                  │                  │                  │
      │ Step 9: Create Delegation          │                  │                  │
      │  agent_id: "sdr-assistant-001"     │                  │                  │
      │  permissions: ["notion:pages:search", "notion:pages:read", ...]           │
      │─────────────────>│                  │                  │                  │
      │                  │                  │                  │                  │
      │                  │ ⚠️ NO VALIDATION │                  │                  │
      │                  │ of permissions   │                  │                  │
      │                  │ against scopes!  │                  │                  │
      │                  │                  │                  │                  │
      │  delegation_token│(Macaroon)        │                  │                  │
      │<─────────────────│                  │                  │                  │
      │                  │                  │                  │                  │
      │ ════════════════ Agent Authentication ══════════════════                  │
      │                  │                  │                  │                  │
      │                  │ Steps 10-11: Challenge/Verify       │                  │
      │                  │<───────────────────────────────────>│                  │
      │                  │                  │                  │                  │
      │                  │  AGENT_JWT with:  │                  │                  │
      │                  │  - owner: sarah@acme.com            │                  │
      │                  │  - delegated_permissions: [...]     │                  │
      │                  │─────────────────────────────────────>│                  │
      │                  │                  │                  │                  │
      │ ════════════════ Tool Discovery & Execution ════════════                  │
      │                  │                  │                  │                  │
      │                  │                  │  Step 15: MCP Initialize            │
      │                  │                  │  (creates session with tools)       │
      │                  │                  │<─────────────────│                  │
      │                  │                  │                  │                  │
      │                  │                  │  Step 16: tools/list                │
      │                  │                  │  Permission Mapper filters          │
      │                  │                  │<─────────────────│                  │
      │                  │                  │                  │                  │
      │                  │                  │  Returns only:   │                  │
      │                  │                  │  - notion.search_pages              │
      │                  │                  │  - notion.read_page                 │
      │                  │                  │  - notion.query_database            │
      │                  │                  │  - slack.search_messages            │
      │                  │                  │  - slack.list_channels              │
      │                  │                  │                  │                  │
      │                  │                  │  Step 17: tools/call                │
      │                  │                  │  notion.search_pages                │
      │                  │                  │<─────────────────│                  │
      │                  │                  │                  │                  │
      │                  │                  │  PermissionMapper│                  │
      │                  │                  │  .is_tool_permitted()               │
      │                  │                  │         │        │                  │
      │                  │                  │         ▼        │                  │
      │                  │                  │  CredentialInjector                 │
      │                  │                  │  GET /vault/tokens/notion           │
      │                  │                  │────────>│        │                  │
      │                  │                  │         │        │                  │
      │                  │                  │  token_data      │                  │
      │                  │                  │<────────│        │                  │
      │                  │                  │                  │                  │
      │                  │                  │  NotionDirectClient                 │
      │                  │                  │  POST /v1/search │                  │
      │                  │                  │  Auth: Bearer ntn_xxx...            │
      │                  │                  │─────────────────────────────────────>│
      │                  │                  │                  │                  │
      │                  │                  │  Notion API response                │
      │                  │                  │<─────────────────────────────────────│
      │                  │                  │                  │                  │
```

---

## 4. Current Implementation Analysis

### What Gets Stored Where

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONTROL PLANE                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ConnectedService (PostgreSQL)                                        │    │
│  │                                                                       │    │
│  │ id: conn-xxx                                                          │    │
│  │ user_id: sarah@acme.com                                               │    │
│  │ service_id: notion                                                    │    │
│  │ scopes_granted: ["read_pages", "search_content"]  ← Layer 2 scopes   │    │
│  │ oauth_token_ref: vault://sarah-notion-abc123                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ VaultClient (In-memory, encrypted)                                   │    │
│  │                                                                       │    │
│  │ vault://sarah-notion-abc123:                                          │    │
│  │   access_token: "ntn_xxx..." (encrypted)                              │    │
│  │   token_type: "bearer"                                                │    │
│  │   scope: "read_pages search_content"                                  │    │
│  │   expires_at: "2027-02-22T00:00:00Z"                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Delegation Storage (In-memory)                                       │    │
│  │                                                                       │    │
│  │ del-xxx:                                                              │    │
│  │   agent_id: sdr-assistant-001                                         │    │
│  │   user_id: sarah@acme.com                                             │    │
│  │   permissions: ["notion:pages:search", "notion:pages:read", ...]     │    │
│  │   token: (Macaroon)                                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          GATEWAY                                            │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Agent JWT (from auth/verify)                                         │    │
│  │                                                                       │    │
│  │ {                                                                     │    │
│  │   "sub": "sdr-assistant-001",                                         │    │
│  │   "owner": "sarah@acme.com",                                          │    │
│  │   "delegated_permissions": [         ← Layer 3 permissions           │    │
│  │     "notion:pages:search",                                            │    │
│  │     "notion:pages:read",                                              │    │
│  │     "notion:databases:query",                                         │    │
│  │     "slack:messages:search",                                          │    │
│  │     "slack:channels:list"                                             │    │
│  │   ],                                                                  │    │
│  │   "session_id": "asess-xxx"                                           │    │
│  │ }                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Permission Mapper (Static mapping)                                   │    │
│  │                                                                       │    │
│  │ "notion.search_pages" → "notion:pages:search"                        │    │
│  │ "notion.read_page"    → "notion:pages:read"                          │    │
│  │ "notion.create_page"  → "notion:pages:create"  (not in delegation)  │    │
│  │ ...                                                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ MCP Session (Created during initialize)                              │    │
│  │                                                                       │    │
│  │ agent_session_id: asess-xxx                                           │    │
│  │ delegator: sarah@acme.com                                             │    │
│  │ delegated_permissions: [...]                                          │    │
│  │ backend_sessions:                                                     │    │
│  │   notion:                                                             │    │
│  │     allowed_tools: ["search_pages", "read_page", "query_database"]   │    │
│  │     credential_ref: vault://notion-oauth-xxx                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### How Permissions Flow Through Code

```python
# Step 6: Connect Service (users.py)
@router.post("/me/services/connect")
def connect_service(request: ConnectServiceRequest):
    # Sarah passes: scope = "read_pages search_content"
    scopes = request.oauth_token.scope.split()  # ["read_pages", "search_content"]
    
    # Store in DB
    connection = ConnectedService(
        scopes_granted=scopes,  # Stored but NOT validated!
        oauth_token_ref=token_ref,
    )
    
# Step 9: Create Delegation (delegation.py)
@router.post("/delegate")
def create_user_delegation(request: UserDelegationRequest):
    # Sarah passes: permissions = ["notion:pages:search", ...]
    
    # ⚠️ NO VALIDATION that permissions ⊆ scopes_granted!
    _delegations[delegation_id] = {
        "permissions": request.permissions,  # Stored as-is
    }

# Steps 10-11: Agent Auth (agent_session_service.py)
def _create_jwt(self, session):
    # Permissions embedded in JWT
    return jwt.encode({
        "delegated_permissions": session.scoped_permissions,  # From delegation
    })

# Step 15: Initialize (initialize.py)
async def handle_initialize(params, context):
    delegated_permissions = context.get("delegated_permissions", [])
    
    # ⚠️ CURRENT BUG: Tool names derived incorrectly
    for perm in notion_perms:
        parts = perm.split(":")
        tool_name = f"{parts[2]}_{parts[1]}"  # "search_pages" (wrong)
        # Should be: PermissionMapper.get_all_tools_for_permission(perm)

# Step 16: List Tools (tools_list.py)
async def handle_tools_list(params, context):
    delegated_permissions = context.get("delegated_permissions", [])
    
    for tool in all_tools:
        if PermissionMapper.is_tool_permitted(tool.name, delegated_permissions):
            filtered_tools.append(tool)

# Step 17: Call Tool (tools_call.py)
async def handle_tools_call(params, context):
    tool_name = params.name  # "notion.search_pages"
    delegated_permissions = context.get("delegated_permissions")
    
    if not PermissionMapper.is_tool_permitted(tool_name, delegated_permissions):
        raise MCPError(-32001, "Permission denied")
    
    # Get credentials and call backend
    result = await injector.inject_credentials(...)
    response = await backend_client.call(tool_name, args, headers)
```

---

## 5. Gap Analysis

### Gap 1: No Validation of Delegation Against Connected Scopes

**Problem:**
```
Connected scopes:     ["read_pages", "search_content"]
Delegated permissions: ["notion:pages:search", "notion:pages:read", 
                        "notion:pages:create"]  ← CREATE not in scopes!
```

Sarah could delegate `notion:pages:create` even though her Notion integration only has "Read content" capability. The system would allow the delegation, and the agent would only fail when Notion API rejects the call.

**Impact:** Poor UX, confusing errors, security ambiguity

### Gap 2: No Mapping Between Scope Strings and Permission Strings

**Problem:**
```
Connected scope:      "read_pages"     (arbitrary string)
Permission string:    "notion:pages:read"  (structured format)
```

There's no mapping that says `"read_pages"` → `["notion:pages:read", "notion:pages:search"]`

**Impact:** Can't validate delegation permissions against connected scopes

### Gap 3: Tool Name Derivation Mismatch (WS-J2)

**Problem:** Already documented in WS-J2-spec.md
- Initialize handler derives `read_pages` (plural)
- Permission Mapper expects `read_page` (singular)

**Impact:** Tools not visible, cache misses, "unknown tool" errors

#### Detailed Flow: Current Bug (Before WS-J2 Fix)

This flow shows what happens in Steps 15-16 of the Integration Validation Guide with the **current buggy code**:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 15: MCP Initialize                                                         │
│ (deeptrail-gateway/app/mcp/handlers/initialize.py)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ Step 1: Agent JWT arrives with permissions from delegation:                     │
│         jwt.delegated_permissions = ["notion:pages:read", "notion:pages:search"]│
│                   │                                                             │
│                   ▼                                                             │
│ Step 2: Initialize handler DERIVES tool names (WRONG):                         │
│         for perm in notion_perms:                                               │
│             parts = perm.split(":")                                             │
│             tool_name = f"{parts[2]}_{parts[1]}"  # ← BUG!                     │
│                                                                                 │
│         "notion:pages:read"   → "read_pages"    ← WRONG (plural)               │
│         "notion:pages:search" → "search_pages"  ← WRONG (plural)               │
│                   │                                                             │
│                   ▼                                                             │
│ Step 3: Session stores WRONG tool names:                                        │
│         backend_sessions["notion"].allowed_tools = [                            │
│             "read_pages",      ← WRONG                                         │
│             "search_pages"     ← WRONG                                         │
│         ]                                                                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 16: MCP tools/list                                                         │
│ (deeptrail-gateway/app/mcp/handlers/tools_list.py)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ Step 4: For each tool in session.allowed_tools:                                │
│         tool_name = "notion.read_pages"  (from session)                        │
│                   │                                                             │
│                   ▼                                                             │
│ Step 5: PermissionMapper.is_tool_permitted("notion.read_pages", perms)         │
│                                                                                 │
│         TOOL_TO_PERMISSION = {                                                  │
│           "notion.search_pages": "notion:pages:search",                        │
│           "notion.read_page": "notion:pages:read",   ← Singular!               │
│           ...                                                                   │
│         }                                                                       │
│                                                                                 │
│         "notion.read_pages" NOT IN mapping!                                     │
│         → Returns False (unknown tool, fail-closed)                            │
│         → WARNING: "Permission denied for unknown tool: notion.read_pages"     │
│                   │                                                             │
│                   ▼                                                             │
│ Step 6: Tool filtered out! Agent sees fewer tools than expected.               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Detailed Flow: What SHOULD Happen (After WS-J2 Fix)

The fix uses `PermissionMapper.get_all_tools_for_permission()` to get canonical tool names:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 15: MCP Initialize (FIXED)                                                │
│ (deeptrail-gateway/app/mcp/handlers/initialize.py)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ Step 1: Agent JWT arrives with permissions:                                     │
│         jwt.delegated_permissions = ["notion:pages:read", "notion:pages:search"]│
│                   │                                                             │
│                   ▼                                                             │
│ Step 2: Use PermissionMapper reverse lookup (FIXED):                           │
│         for perm in notion_perms:                                               │
│             tools = PermissionMapper.get_all_tools_for_permission(perm)         │
│                                                                                 │
│         "notion:pages:read"   → ["notion.read_page"]     ← CORRECT (singular)  │
│         "notion:pages:search" → ["notion.search_pages"]  ← CORRECT             │
│                   │                                                             │
│                   ▼                                                             │
│ Step 3: Session stores CORRECT tool names:                                      │
│         backend_sessions["notion"].allowed_tools = [                            │
│             "read_page",       ← CORRECT                                       │
│             "search_pages"     ← CORRECT                                       │
│         ]                                                                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 16: MCP tools/list (WORKS)                                                │
│ (deeptrail-gateway/app/mcp/handlers/tools_list.py)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ Step 4: For each tool in session.allowed_tools:                                │
│         tool_name = "notion.read_page"  (from session, CORRECT)                │
│                   │                                                             │
│                   ▼                                                             │
│ Step 5: PermissionMapper.is_tool_permitted("notion.read_page", perms)          │
│                                                                                 │
│         TOOL_TO_PERMISSION = {                                                  │
│           "notion.search_pages": "notion:pages:search",                        │
│           "notion.read_page": "notion:pages:read",   ← FOUND!                  │
│           ...                                                                   │
│         }                                                                       │
│                                                                                 │
│         "notion.read_page" FOUND! Required: "notion:pages:read"                │
│         "notion:pages:read" IN jwt.delegated_permissions? YES ✓                │
│         → Returns True                                                          │
│                   │                                                             │
│                   ▼                                                             │
│ Step 6: Tool cache lookup for "notion.read_page":                              │
│                                                                                 │
│         tool_cache = {                                                          │
│           "notion.read_page": {                                                │
│             "name": "notion.read_page",                                        │
│             "description": "Read a Notion page by ID",                         │
│             "inputSchema": {"type": "object", "properties": {...}}             │
│           },                                                                    │
│           ...                                                                   │
│         }                                                                       │
│                                                                                 │
│         FOUND! Returns full tool definition with schema ✓                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Response to Agent                                                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│ {                                                                               │
│   "jsonrpc": "2.0",                                                             │
│   "id": 2,                                                                      │
│   "result": {                                                                   │
│     "tools": [                                                                  │
│       {                                                                         │
│         "name": "notion.read_page",                                            │
│         "description": "Read a Notion page by ID",                             │
│         "inputSchema": {                                                        │
│           "type": "object",                                                     │
│           "properties": {                                                       │
│             "page_id": {"type": "string", "description": "Page ID to read"}    │
│           },                                                                    │
│           "required": ["page_id"]                                               │
│         }                                                                       │
│       },                                                                        │
│       {                                                                         │
│         "name": "notion.search_pages",                                         │
│         "description": "Search for pages in Notion workspace",                 │
│         "inputSchema": {...}                                                    │
│       }                                                                         │
│     ]                                                                           │
│   }                                                                             │
│ }                                                                               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Integration Validation Guide Step Mapping

| Step | Description | Before WS-J2 | After WS-J2 |
|------|-------------|--------------|-------------|
| **Step 15** | MCP Initialize | Session has wrong tool names | Session has correct tool names |
| **Step 16** | MCP List Tools | Tools filtered out, minimal schemas | Full tool definitions returned |
| **Step 17** | MCP Tool Call | May fail on unknown tool | Works correctly |

#### Key Code Locations

| Component | File | Issue |
|-----------|------|-------|
| **Tool Name Derivation** | `initialize.py:~300` | Derives `read_pages` (wrong) |
| **Permission Mapper** | `permission_mapper.py:53-79` | Has `read_page` (correct) |
| **Tool Definitions** | `tool_definitions.py` | Has `read_page` (correct) |
| **Tool Cache** | `main.py:startup` | Populated with correct names |

**WS-J2 Fix:** Change `initialize.py` to use `PermissionMapper.get_all_tools_for_permission()` instead of deriving tool names from permission strings.

### Gap 4: No Scope Discovery UI

**Problem:** User must know what scope strings to pass when connecting. No UI to show what's available or what maps to what permissions.

**Impact:** Manual, error-prone configuration

---

## 6. Proposed Fixes

### Fix 1: Scope-to-Permission Mapping (New Module)

Create a mapping from OAuth scopes to DeepSecure permissions:

```python
# deeptrail-control/app/services/scope_mapper.py

class ScopeMapper:
    """Maps OAuth scopes to DeepSecure permissions."""
    
    # Notion scope → permissions
    NOTION_SCOPE_MAP = {
        "read_content": [
            "notion:pages:read",
            "notion:pages:search",
            "notion:databases:list",
            "notion:databases:query",
        ],
        "update_content": [
            "notion:pages:update",
        ],
        "insert_content": [
            "notion:pages:create",
        ],
        # Simplified scopes (user-friendly)
        "read_pages": ["notion:pages:read", "notion:pages:search"],
        "write_pages": ["notion:pages:create", "notion:pages:update"],
        "search_content": ["notion:pages:search"],
    }
    
    @classmethod
    def get_allowed_permissions(
        cls, 
        service_id: str, 
        scopes: list[str]
    ) -> set[str]:
        """Get all permissions allowed by the given scopes."""
        permissions = set()
        scope_map = getattr(cls, f"{service_id.upper()}_SCOPE_MAP", {})
        
        for scope in scopes:
            permissions.update(scope_map.get(scope, []))
        
        return permissions
```

### Fix 2: Validate Delegation Against Connected Scopes

```python
# deeptrail-control/app/api/v1/endpoints/delegation.py

@router.post("/delegate")
def create_user_delegation(request: UserDelegationRequest, db: Session):
    # Get connected service for this user and service
    connected_services = db.query(ConnectedService).filter(
        ConnectedService.user_id == current_user,
        ConnectedService.disconnected_at.is_(None),
    ).all()
    
    # Get allowed permissions from all connected services
    allowed_permissions = set()
    for svc in connected_services:
        svc_perms = ScopeMapper.get_allowed_permissions(
            svc.service_id, 
            svc.scopes_granted
        )
        allowed_permissions.update(svc_perms)
    
    # Validate requested permissions are subset
    requested = set(request.permissions)
    not_allowed = requested - allowed_permissions
    
    if not_allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_permissions",
                "message": f"Cannot delegate permissions not in connected scopes: {list(not_allowed)}",
                "allowed_permissions": list(allowed_permissions),
            }
        )
    
    # Continue with delegation...
```

### Fix 3: WS-J2 (Tool Name Derivation)

Already specified in `WS-J2-spec.md`:
- Use `PermissionMapper.get_all_tools_for_permission()` in initialize.py
- Complete tool definitions in `tool_definitions.py`

### Fix 4: Available Permissions Endpoint (Future)

```python
# GET /api/v1/users/me/available-permissions
@router.get("/me/available-permissions")
def get_available_permissions(current_user: str, db: Session):
    """Return all permissions user can delegate based on connected services."""
    
    connected = db.query(ConnectedService).filter(
        ConnectedService.user_id == current_user,
        ConnectedService.disconnected_at.is_(None),
    ).all()
    
    available = {}
    for svc in connected:
        perms = ScopeMapper.get_allowed_permissions(
            svc.service_id,
            svc.scopes_granted
        )
        available[svc.service_id] = {
            "scopes_granted": svc.scopes_granted,
            "available_permissions": list(perms),
        }
    
    return {"available_permissions": available}
```

---

## Summary: What Happens After WS-J2

### WS-J2 Fixes (Tool Name Derivation)

| Before WS-J2 | After WS-J2 |
|--------------|-------------|
| `read_pages` derived (wrong) | `read_page` from PermissionMapper |
| Tools don't match cache | Tools match cache |
| "Unknown tool" warnings | Clean tool lookup |

### Gap-to-Spec Mapping

| Gap | Description | Spec | Status |
|-----|-------------|------|--------|
| **Gap 1** | No Delegation Validation Against Scopes | [WS-K4-spec.md](../workstreams/mvp-production-readiness/specs/WS-K4-spec.md) | ⏳ Spec Created |
| **Gap 2** | No Scope→Permission Mapping | [WS-K3-spec.md](../workstreams/mvp-production-readiness/specs/WS-K3-spec.md) | ⏳ Spec Created |
| **Gap 3** | Tool Name Derivation Mismatch | [WS-J2-spec.md](../workstreams/mvp-production-readiness/specs/WS-J2-spec.md) | ⏳ Spec Created |
| **Gap 4** | No Scope Discovery UI | [WS-K5-spec.md](../workstreams/mvp-production-readiness/specs/WS-K5-spec.md) | ⏳ Spec Created |

### Related Specs (From MVP_ARCHITECTURE_DEEP_DIVE.md)

| Issue | Description | Spec | Status |
|-------|-------------|------|--------|
| Issue 1 | In-Memory Vault is Ephemeral | [WS-K1-spec.md](../workstreams/mvp-production-readiness/specs/WS-K1-spec.md) | ⏳ Spec Created |
| Issue 2 | Credential Cache Can Be Stale | [WS-K2-spec.md](../workstreams/mvp-production-readiness/specs/WS-K2-spec.md) | ⏳ Spec Created |

### Dependency Order for Implementation

```
Phase 1 (Standalone):
├── WS-J2: Tool Name Derivation Fix
├── WS-K1: Persistent Vault  
└── WS-K2: Cache Invalidation

Phase 2 (Scope Mapping):
├── WS-K3: Scope Mapper (standalone)
├── WS-K4: Delegation Validation (depends on WS-K3)
└── WS-K5: Available Permissions Endpoint (depends on WS-K3)
```

### Complete Flow After All Fixes

```
1. Sarah connects Notion with scope: "read_content"
   → ScopeMapper expands to: ["notion:pages:read", "notion:pages:search", ...]
   → Stored in ConnectedService

2. Sarah creates delegation with: ["notion:pages:search"]
   → Validated: notion:pages:search ∈ allowed_permissions ✓
   → Stored in Delegation

3. Agent authenticates
   → JWT contains: delegated_permissions = ["notion:pages:search"]

4. Agent calls tools/list
   → PermissionMapper filters tools
   → Only notion.search_pages visible

5. Agent calls notion.search_pages
   → Permission validated
   → Credentials injected
   → Notion API called with Sarah's token
   → Real results returned
```

---

## 7. Two Mappers: Permission Mapper vs Scope Mapper

This section clarifies why both mappers exist and how they work together.

### Why Permission Mapper Exists (and Must Stay)

The **Permission Mapper** serves a specific purpose in the Gateway - it translates **tool names** to **permission strings** at runtime:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    GATEWAY: Permission Mapper                                │
│                                                                              │
│  Agent calls:  "notion.search_pages"                                         │
│       │                                                                      │
│       ▼                                                                      │
│  Permission Mapper                                                           │
│  TOOL_TO_PERMISSION = {                                                      │
│    "notion.search_pages": "notion:pages:search",  ──┐                        │
│    "notion.read_page":    "notion:pages:read",     │                         │
│    "notion.create_page":  "notion:pages:create",   │ Required permission     │
│  }                                                 │                         │
│       │                                            │                         │
│       ▼                                            ▼                         │
│  Check: Is "notion:pages:search" in jwt.delegated_permissions?               │
│         ["notion:pages:search", "notion:pages:read"] ← Agent's JWT           │
│                                                                              │
│  Yes → Allow tool call                                                       │
│  No  → Reject with -32001                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

**This is enforcement at runtime** - it cannot be removed.

### What WS-K3/K4/K5 Would Add (Different Purpose)

The proposed specs address **validation at delegation time** in the Control Plane:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    CONTROL PLANE: Scope Mapper (WS-K3)                       │
│                                                                              │
│  Sarah connected with scope: "read_pages"                                    │
│       │                                                                      │
│       ▼                                                                      │
│  Scope Mapper (NEW - WS-K3)                                                  │
│  SCOPE_TO_PERMISSIONS = {                                                    │
│    "read_pages": ["notion:pages:read", "notion:pages:search"],               │
│    "write_pages": ["notion:pages:create", "notion:pages:update"],            │
│  }                                                                           │
│       │                                                                      │
│       ▼                                                                      │
│  Allowed permissions: ["notion:pages:read", "notion:pages:search"]           │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  Sarah tries to delegate: ["notion:pages:search", "notion:pages:create"]     │
│       │                                                                      │
│       ▼                                                                      │
│  Validation (WS-K4):                                                         │
│    notion:pages:search ∈ allowed? ✓                                          │
│    notion:pages:create ∈ allowed? ✗ → REJECT at delegation time             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Comparison: Two Different Mappers

| Aspect | Permission Mapper (Existing) | Scope Mapper (Proposed WS-K3) |
|--------|------------------------------|-------------------------------|
| **Location** | Gateway | Control Plane |
| **Purpose** | Enforce tool access | Validate delegation |
| **Timing** | Runtime (every tool call) | Delegation creation |
| **Maps** | Tool → Permission | Scope → Permissions |
| **Example** | `notion.search_pages` → `notion:pages:search` | `read_pages` → `["notion:pages:read", ...]` |

### Visual: Complete Flow with Both Mappers

```
                    CONTROL PLANE                          GATEWAY
                    ─────────────────────────────────────  ─────────────────────────
                    
Step 6: Connect     ┌─────────────────────────────────┐
                    │ scope: "read_pages"              │
                    │              │                   │
                    │              ▼                   │
                    │ Scope Mapper (WS-K3)             │
                    │ Expands to:                      │
                    │ ["notion:pages:read",            │
                    │  "notion:pages:search"]          │
                    └─────────────────────────────────┘
                                   │
                                   │ allowed_permissions
                                   ▼
Step 9: Delegate    ┌─────────────────────────────────┐
                    │ User requests:                   │
                    │ ["notion:pages:search"]          │
                    │              │                   │
                    │              ▼                   │
                    │ Validation (WS-K4)               │
                    │ Is request ⊆ allowed? ✓         │
                    └─────────────────────────────────┘
                                   │
                                   │ jwt.delegated_permissions
                                   ▼
Step 16: tools/list                                    ┌─────────────────────────────┐
                                                       │ For each tool in cache:     │
                                                       │              │              │
                                                       │              ▼              │
                                                       │ Permission Mapper           │
                                                       │ "notion.search_pages"       │
                                                       │    → "notion:pages:search"  │
                                                       │              │              │
                                                       │              ▼              │
                                                       │ Is in delegated_permissions?│
                                                       │ Yes → Include in response   │
                                                       └─────────────────────────────┘
                                                       
Step 17: tools/call                                    ┌─────────────────────────────┐
                                                       │ Agent calls:                │
                                                       │ "notion.search_pages"       │
                                                       │              │              │
                                                       │              ▼              │
                                                       │ Permission Mapper           │
                                                       │ Required: "notion:pages:search"│
                                                       │              │              │
                                                       │              ▼              │
                                                       │ Enforce: Is permitted? ✓   │
                                                       │              │              │
                                                       │              ▼              │
                                                       │ Execute tool               │
                                                       └─────────────────────────────┘
```

### Do WS-K3/K4/K5 Change the Permission Mapper?

**No.** They complement it:

| Task | What It Adds | Changes Permission Mapper? |
|------|--------------|---------------------------|
| **WS-K3** | Scope Mapper in Control Plane | No - different service, different purpose |
| **WS-K4** | Delegation validation logic | No - uses Permission Mapper's permission strings as reference |
| **WS-K5** | API endpoint for available permissions | No - just exposes data |

However, **both mappers must use the same permission strings**. The shared vocabulary is:

```
notion:pages:search
notion:pages:read
notion:pages:create
notion:databases:query
slack:messages:search
slack:channels:list
gmail:messages:read
...
```

### Alternative: Single Source of Truth (Future)

If we want to reduce duplication, we could create a **shared permissions definition**:

```python
# Shared (could be in a common package or config)
PERMISSION_DEFINITIONS = {
    "notion:pages:search": {
        "tool": "notion.search_pages",
        "scopes": ["read_pages", "read_content", "search_content"],
        "description": "Search Notion pages",
    },
    "notion:pages:read": {
        "tool": "notion.read_page", 
        "scopes": ["read_pages", "read_content"],
        "description": "Read a Notion page",
    },
    "notion:pages:create": {
        "tool": "notion.create_page",
        "scopes": ["write_pages", "insert_content"],
        "description": "Create a Notion page",
    },
    # ...
}

# Gateway derives Permission Mapper from this
TOOL_TO_PERMISSION = {
    defn["tool"]: perm 
    for perm, defn in PERMISSION_DEFINITIONS.items()
}

# Control Plane derives Scope Mapper from this
def build_scope_map(service_id: str) -> Dict[str, List[str]]:
    scope_map = defaultdict(list)
    for perm, defn in PERMISSION_DEFINITIONS.items():
        if perm.startswith(f"{service_id}:"):
            for scope in defn["scopes"]:
                scope_map[scope].append(perm)
    return dict(scope_map)
```

**But for MVP, keeping them separate is simpler** - they're in different services and we don't want to add cross-service dependencies.

### Summary Table

| Question | Answer |
|----------|--------|
| **Why Permission Mapper?** | Runtime enforcement: Tool → Permission → Check JWT |
| **Does WS-K3 replace it?** | No - different purpose (validation vs enforcement) |
| **Does WS-K3 change it?** | No - but both use same permission strings |
| **What WS-K3 adds** | Scope → Permissions mapping for delegation validation |
| **What WS-K4 adds** | Uses WS-K3 to validate delegations at creation time |
| **What WS-K5 adds** | UI-friendly endpoint showing available permissions |

### Key Insight: Defense in Depth

The two mappers provide **defense in depth**:

```
Layer 1: Scope Mapper (Control Plane)
         ↓
         Validates at DELEGATION TIME
         "Can Sarah delegate notion:pages:create?"
         "No - she only has read_pages scope"
         → EARLY REJECTION with clear error
         
Layer 2: Permission Mapper (Gateway)
         ↓
         Enforces at RUNTIME
         "Can agent call notion.create_page?"
         "No - not in delegated_permissions"
         → RUNTIME REJECTION (defense in depth)
```

Even if Layer 1 has a bug, Layer 2 still enforces. This is the security principle of **fail-closed at multiple layers**.

---

## 8. ScopeMapper: Current Design, Risks, and Evolution Path

> **Added:** May 7, 2026  
> **Context:** Discussion of how `available-permissions` endpoint works, what happens when OAuth scopes change, and the architectural trade-offs of code-as-configuration vs. DB-driven mappings.

### 8.1 How Available Permissions Are Computed Today

The `GET /users/me/available-permissions` endpoint does **not** store or query a permissions table. It computes permissions on-the-fly every time it is called:

```
Request: GET /users/me/available-permissions

1. Query connected_services WHERE user_id = current_user
   → finds 5 rows: notion, slack, gmail, gdrive, gcalendar

2. For each row, read scopes_granted (stored as JSON array):
   e.g. notion: ["read_content", "update_content", "insert_content"]
        slack:  ["channels:history", "channels:read", "chat:write", ...]

3. For each service+scope, call ScopeMapper.get_permissions_for_scopes()
   e.g. "channels:history" → ["slack:channels:history", "slack:messages:search"]

4. Aggregate into all_permissions flat list → 23 strings returned to UI
```

The `ScopeMapper` class in `deeptrail-control/app/services/scope_mapper.py` holds a **static hardcoded dict** (`SCOPE_TO_PERMISSIONS`) mapping every known service scope to a list of fine-grained permission strings.

### 8.2 Why This Design Was Chosen

The rationale for computing rather than storing:

- **Scopes are ground truth.** The OAuth provider (Google, Slack, etc.) grants scopes. Storing derived permissions would create a second copy that could drift from what the provider actually allows.
- **Permissions are a view.** They are a product enrichment layer on top of raw OAuth scopes. Recomputing them keeps the derivation logic in one place (`ScopeMapper`) rather than in a migration or a background job.
- **Monotonic attenuation is preserved.** Users can only delegate permissions they can compute from their scopes. The computation happens at delegation time, so a user can never delegate more than their current scopes allow.

### 8.3 Failure Modes When Scopes or the Mapper Change

#### Case A: User re-authorizes with more scopes (scope expansion)

The OAuth callback stores the new, wider `scopes_granted` in the DB. The next call to `available-permissions` recomputes from the new scopes and returns the expanded permission set. **This works correctly** -- no action needed.

#### Case B: User's scopes are reduced (e.g., they revoke a Google scope)

The OAuth callback (or a future revocation handler) should update `scopes_granted` to the smaller set. On the next `available-permissions` call the narrower set is returned. **Existing delegations are NOT retroactively narrowed** -- they still embed the old permission strings in the JWT. This is an open gap.

#### Case C: `ScopeMapper` code is updated (new permission added to a scope)

A developer adds `"slack:messages:list"` as a new permission for `channels:history`. After deploy:

- `available-permissions` immediately returns the new permission for any user who has that scope connected.
- Existing Agent JWTs do **not** contain the new permission (JWTs are issued at auth time and are immutable until re-authentication).
- The Gateway's `PermissionMapper` **must be updated simultaneously** or the new permission string will be unknown to the Gateway and calls will fail closed.

**Risk:** The two mapper files (`scope_mapper.py` in Control Plane and `permission_mapper.py` in Gateway) must stay in sync manually. There is no automated check.

#### Case D: `ScopeMapper` code is updated (permission removed from a scope)

A developer removes `"slack:messages:search"` from `channels:history`. After deploy:

- `available-permissions` no longer returns that permission.
- Existing delegations that included it still embed it in the Agent JWT.
- The Gateway still enforces it (as long as `PermissionMapper` also still has it). If `PermissionMapper` removes it too, existing agent sessions silently lose that tool.

#### Case E: OAuth provider changes their scope name

Unlikely for Google/Slack but possible. The `ScopeMapper` has both short-form (`drive.readonly`) and full-URL form (`https://www.googleapis.com/auth/drive.readonly`) entries to guard against this. Any scope string the provider returns that is not in the map produces **zero permissions silently** -- no error, no warning to the user.

### 8.4 The Two-Mapper Sync Problem

Both `ScopeMapper` (Control Plane) and `PermissionMapper` (Gateway) use the same permission string vocabulary. They are maintained in separate files in separate services with no automated consistency check:

| Component | File | Purpose |
|-----------|------|---------|
| `ScopeMapper` | `deeptrail-control/app/services/scope_mapper.py` | Scope → Permission (at delegation time) |
| `PermissionMapper` | `deeptrail-gateway/app/mcp/permission_mapper.py` | Tool → Permission (at tool call time) |

**Current risk:** A developer updating one without updating the other will cause silent permission mismatches. The comment on line 26 of `scope_mapper.py` acknowledges this: *"Permission strings MUST match those used by the Gateway's PermissionMapper."*

There is no test that verifies both mappers use the same set of permission strings.

### 8.5 Evolution Path

#### Level 0 (Current): Hardcoded static dict

- All mappings in Python source
- Change requires code deploy
- No admin control
- No audit trail of mapping changes

#### Level 1 (Recommended next step): Store computed permissions in DB

Add an `available_permissions` JSON column to `connected_services`. Populate it at OAuth callback time by calling `ScopeMapper` once and storing the result. The `available-permissions` endpoint reads from DB.

```
OAuth callback:
  → ScopeMapper.get_permissions_for_scopes(service_id, scopes)
  → Store result in connected_services.available_permissions
  → This column is the user's permission ceiling

available-permissions endpoint:
  → SELECT available_permissions FROM connected_services
  → No computation at query time
```

**Benefits:**
- Permissions are stable across code deploys (no silent expansion/contraction when mapper is updated)
- Admins can see and audit what permissions each user holds
- A single `POST /admin/recompute-permissions` endpoint can refresh all users after a mapper change, making the change explicit and auditable

**New migration needed:** Add `available_permissions JSONB` to `connected_services` table. This fits naturally with the C1 migrations already planned in the Integration Verification Pipeline plan (`~/.cursor/plans/integration_verification_pipeline_e3462407.plan.md`).

#### Level 2 (Future): DB-driven scope-to-permission mapping table

Replace the hardcoded dict with a `scope_permission_mappings` table:

```sql
CREATE TABLE scope_permission_mappings (
    id          UUID PRIMARY KEY,
    service_id  TEXT NOT NULL,
    scope       TEXT NOT NULL,
    permission  TEXT NOT NULL,
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ
);
```

- IT Admin or Security team updates mappings via UI without code deploy
- Changes are versioned and auditable
- `ScopeMapper` reads from DB instead of the hardcoded dict
- Seeded from current `SCOPE_TO_PERMISSIONS` dict via migration

**Trade-off:** More complex. Admin UI required. Startup latency for DB read. DB becomes a dependency for permission computation.

#### Level 3 (Future): Shared permission registry as single source of truth

As described in Section 7, a `PERMISSION_DEFINITIONS` shared registry from which both `ScopeMapper` and `PermissionMapper` are derived. Eliminates the two-mapper sync problem. Appropriate when the permission vocabulary grows significantly or when a shared config package is introduced.

### 8.6 Recommended Action Items

| Priority | Action | Files |
|----------|--------|-------|
| **Now** | Add a test that asserts every permission string in `ScopeMapper.SCOPE_TO_PERMISSIONS` exists in `PermissionMapper.TOOL_TO_PERMISSION` (and vice versa) | New test file in `deeptrail-control/tests/` |
| **With C1 migrations** | Add `available_permissions JSONB` column to `connected_services` | New Alembic migration |
| **With C2 DB persistence** | Populate `available_permissions` in OAuth callback handler | `deeptrail-control/app/api/v1/endpoints/oauth.py` |
| **After C2** | Update `available-permissions` endpoint to read from DB column | `deeptrail-control/app/api/v1/endpoints/users.py` |
| **After C2** | Add `POST /admin/recompute-permissions` management endpoint | New endpoint |
| **Future** | Consider Level 2 DB-driven mappings if scope vocabulary grows | New migration + admin UI |

---

## 9. Implementation Status (May 2026)

This section tracks the current state of the permission architecture relative to the gaps and fixes documented above.

### 9.1 What Is Implemented

| Component | Status | Notes |
|-----------|--------|-------|
| `ScopeMapper` class | **Done** | `deeptrail-control/app/services/scope_mapper.py` -- full static mapping for notion, slack, gdrive, gcalendar, gmail, github |
| `GET /users/me/available-permissions` | **Done** | Computes on-the-fly from `connected_services.scopes_granted` |
| `PermissionMapper` (Gateway) | **Done** | `deeptrail-gateway/app/mcp/permission_mapper.py` -- enforces at tool call time |
| OAuth connect flow (browser-based) | **Done** | `services/page.tsx` uses real OAuth via `GET /oauth/{serviceId}/authorize` |
| Delegation creation UI | **Done** | `delegation/create/page.tsx` fetches `available-permissions`, parses strings into objects, passes to `PermissionChecklist` |
| Delegation validation against scopes (WS-K4) | **Not done** | `delegation.py` accepts any permission string without checking against user's connected scopes |

### 9.2 What Is Still In-Memory (Lost on Restart)

| Data | Location | Impact |
|------|----------|--------|
| Delegations | `_delegations: Dict` in `delegation.py` line 49 | Restart wipes all delegations; agent re-authentication returns empty permissions |
| Audit events | `_mvp_audit_events: list` in `audit.py` line 29 | Restart wipes audit trail |

These are tracked in **C2 of the Integration Verification Pipeline plan** (`~/.cursor/plans/integration_verification_pipeline_e3462407.plan.md`). C1 (Alembic migrations for `delegation_tokens`, `agent_sessions`, `audit_events` tables) is a prerequisite.

### 9.3 Known Sync Gaps Between the Two Mappers

The following permission strings appear in `ScopeMapper` but their presence in `PermissionMapper` has not been formally verified:

- `slack:users:search` (from `search:read.users` scope)
- `slack:reactions:write` (from `reactions:write` scope)  
- `slack:channels:join` (from `channels:join` scope)
- `github:*` permissions (GitHub backend is listed as supported but not confirmed wired in gateway)

**Action:** Add a cross-mapper consistency test before adding any new permission strings.

### 9.4 Open Gaps from Original Gap Analysis (Section 5)

| Gap | Original Status | Current Status |
|-----|----------------|----------------|
| Gap 1: No delegation validation against scopes | Spec created (WS-K4) | Still not implemented |
| Gap 2: No scope→permission mapping | Spec created (WS-K3) | Implemented (`ScopeMapper`) |
| Gap 3: Tool name derivation mismatch | Spec created (WS-J2) | Status unknown -- needs verification |
| Gap 4: No scope discovery UI | Spec created (WS-K5) | `available-permissions` endpoint implemented; UI shows permission checklist on delegation create page |
