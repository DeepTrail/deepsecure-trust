# DeepSecure Data Flow & Authorization Architecture

How identity, permissions, and organization context flow from the Identity Provider through every token layer, gateway enforcement, MCP sessions, and into the audit trail.

## End-to-End Flow Overview

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Identity    │────▶│  Control Plane    │────▶│    Gateway        │
│   Provider    │     │  (deeptrail-      │     │  (deeptrail-      │
│  (Keycloak)   │     │   control)        │     │   gateway)        │
└──────────────┘     └──────────────────┘     └──────────────────┘
       │                    │    │    │               │    │
       ▼                    ▼    ▼    ▼               ▼    ▼
   OIDC Claims         User  Deleg  Agent         MCP    Audit
                       JWT   Token  JWT          Session  Events
                       (L2)  (L5)  (L3/L4)
```

## 1. Identity Provider → User Session JWT (Layer 2)

### SSO Path (primary — via Keycloak, Okta, Azure AD)

The user authenticates via OIDC with an external IdP. The IdP returns an ID token with claims.

```
Keycloak                           Control Plane
────────                           ─────────────
ID Token (OIDC)                    POST /api/v1/auth/sso/{idp}/callback
  ├─ sub: "sarah-uuid"
  ├─ email: "sarah@acme.com"       provision_user_from_claims()
  ├─ name: "Sarah Chen"              ├─ Maps IdP groups → roles
  ├─ groups: ["acme-org"]            ├─ Derives organization_id from groups[0]
  └─ roles: ["user"]                 └─ Returns user_data dict
                                           │
                                           ▼
                                   User Session JWT (Layer 2)
                                     ├─ sub: "sarah@acme.com"
                                     ├─ session_id: "usess-<uuid>"
                                     ├─ organization_id: "acme-org"  ← from IdP
                                     ├─ idp: "keycloak"
                                     ├─ iat: <now>
                                     └─ exp: <now + 8h>
```

**Key files:**
- `deeptrail-control/app/api/v1/endpoints/sso.py` — SSO callback, mints User JWT
- `deeptrail-control/app/services/idp_service.py` — `provision_user_from_claims()`, maps IdP claims

### Fallback Path (when IdP is unavailable)

```
POST /api/v1/auth/login
  { "email": "sarah@acme.com", "password": "..." }

  → organization_id derived from email domain: "org-acme-001"
  → Same JWT structure as SSO path
```

**Key file:** `deeptrail-control/app/api/v1/endpoints/auth.py`

### What flows from IdP into the User JWT

| IdP Claim | User JWT Claim | Source |
|-----------|---------------|--------|
| `email` | `sub` | Direct from OIDC |
| `groups[0]` | `organization_id` | First group membership |
| Issuer URL | `idp` | Which IdP authenticated |
| — | `session_id` | Generated: `usess-<uuid>` |
| — | `exp` | 8-hour TTL |

---

## 2. User JWT → Delegation (Layer 5)

When the user delegates permissions to an agent, the delegation endpoint extracts the user's identity **and** `organization_id` from the User JWT and stores them with the delegation.

```
User JWT (Layer 2)                 POST /api/v1/auth/delegate
  ├─ sub: "sarah@acme.com"          { agent_id, permissions, constraints }
  ├─ organization_id: "acme-org"        │
  └─ session_id: "usess-..."           ▼
                                   _parse_user_token(authorization)
                                     ├─ Extracts full JWT payload
                                     ├─ Returns { sub, organization_id, ... }
                                     └─ Stores in delegation dict:
                                          {
                                            id: "del-<uuid>",
                                            user_id: "sarah@acme.com",
                                            agent_id: "sdr-assistant-123",
                                            permissions: [...],
                                            organization_id: "acme-org",  ← from User JWT
                                            token: "<macaroon>",
                                            constraints: { rate_limit, expires_in_hours }
                                          }
```

### Permission Validation at Delegation Time (Monotonic Attenuation)

Before creating the delegation, the system validates that the user can only delegate permissions they actually have:

```
User's Connected Services (OAuth)
  ├─ Notion: scopes = [read_content, update_content, search]
  └─ Slack: scopes = [channels:read, channels:history, chat:write]
                │
                ▼
         ScopeMapper.validate_permissions()
           Requested: [notion:pages:search, notion:pages:create]
                              ✅ allowed        ❌ blocked
                              (read_content)    (insert_content not connected)
```

The delegation can never exceed the user's own OAuth scopes. This is the **monotonic attenuation principle** — permissions can only narrow, never widen, as they flow downstream.

**Key files:**
- `deeptrail-control/app/api/v1/endpoints/delegation.py` — `_parse_user_token()`, stores delegation
- `deeptrail-control/app/services/scope_mapper.py` — Permission validation
- `deeptrail-control/app/services/macaroon_service.py` — Delegation token minting

---

## 3. Delegation → Agent Session JWT (Layer 3)

The agent authenticates via Ed25519 challenge-response, proving possession of its private key. The Control Plane then creates an Agent Session JWT with the user's `organization_id` from the delegation.

```
Agent                              Control Plane
─────                              ─────────────
1. POST /auth/agent/challenge      → Returns 256-bit nonce
   { agent_id }                      Stored in _pending_challenges

2. Sign(nonce, private_key)        → Agent signs with Ed25519

3. POST /auth/agent/verify         → Verifies signature against
   { agent_id, challenge,             registered public key
     signature }                        │
                                        ▼
                                   _create_mvp_session()
                                     ├─ Looks up delegation for agent_id
                                     ├─ Reads: permissions, user_id, organization_id
                                     └─ Creates MVPSession:
                                          { id, agent_id, owner_email,
                                            scoped_permissions, organization_id }
                                        │
                                        ▼
                                   _generate_mvp_jwt()
                                     Agent Session JWT (Layer 3):
                                       ├─ sub: "sdr-assistant-123"     ← agent identity
                                       ├─ owner: "sarah@acme.com"     ← from delegation
                                       ├─ session_id: "asess-<hex>"
                                       ├─ delegation_id: "mvp-delegation"
                                       ├─ organization_id: "acme-org" ← from delegation
                                       ├─ delegated_permissions: [    ← from delegation
                                       │    "notion:pages:search",
                                       │    "slack:channels:list", ...
                                       │  ]
                                       ├─ iat: <now>
                                       └─ exp: <now + 8h>
```

### What changes from User JWT to Agent Session JWT

| User JWT (L2) | Agent Session JWT (L3) | Change |
|---------------|----------------------|--------|
| `sub` = user email | `sub` = agent_id | Identity shifts to agent |
| — | `owner` = user email | Human accountability preserved |
| All user permissions | `delegated_permissions` = subset | Narrowed by delegation |
| — | `delegation_id` | Links to specific delegation |
| `organization_id` | `organization_id` | Passed through unchanged |
| `session_id` = usess-* | `session_id` = asess-* | New agent session |

**Key files:**
- `deeptrail-control/app/services/agent_session_service.py` — Session creation, JWT minting
- `deeptrail-control/app/api/v1/endpoints/agent_auth.py` — Challenge/verify endpoints

---

## 4. Agent Session JWT → Task Token JWT (Layer 4)

Task tokens narrow permissions further for a specific unit of work. They are the most restrictive token in the hierarchy.

```
Agent Session JWT (Layer 3)        POST /api/v1/tasks/
  ├─ sub: "sdr-assistant-123"        { name, requested_permissions,
  ├─ delegated_permissions: [7]        deadline_minutes }
  ├─ organization_id: "acme-org"           │
  └─ delegation_id: "mvp-del"             ▼
                                   _get_caller_identity()
                                     ├─ Extracts: agent_id, user_id, delegation_id
                                     └─ Extracts: organization_id  ← from Agent JWT
                                           │
                                           ▼
                                   TaskService.create_task()
                                     ├─ Validates: requested ⊆ delegated_permissions
                                     ├─ Stores organization_id on Task record
                                     └─ Creates Task in database
                                           │
                                     POST /api/v1/tasks/{id}/token
                                           │
                                           ▼
                                   task.to_token_claims()
                                     Task Token JWT (Layer 4):
                                       ├─ task_id: "task-<uuid>"
                                       ├─ agent_id: "sdr-assistant-123"
                                       ├─ owner: "sarah@acme.com"
                                       ├─ organization_id: "acme-org" ← from Task record
                                       ├─ scoped_permissions: [       ← narrower subset
                                       │    { urn: "notion:pages:search",
                                       │      constraints: {} }
                                       │  ]
                                       ├─ deadline: "2026-04-16T17:00:00Z"
                                       ├─ auto_revoke_on_complete: true
                                       ├─ token_type: "task_token"
                                       └─ exp: min(deadline, now + 1h)
```

### Permission Narrowing Across Layers

```
Layer 2 (User)    : All user permissions via OAuth scopes
                    ↓  monotonic attenuation
Layer 5 (Deleg)   : 7 permissions (subset of user's scopes)
                    ↓  monotonic attenuation
Layer 3 (Agent)   : 7 permissions (same as delegation)
                    ↓  monotonic attenuation
Layer 4 (Task)    : 1 permission  (just what this task needs)
```

**Key files:**
- `deeptrail-control/app/api/v1/endpoints/tasks.py` — Task endpoints, `_get_caller_identity()`
- `deeptrail-control/app/services/task_service.py` — `create_task()`, permission validation
- `deeptrail-control/app/models/task_token.py` — Task model, `to_token_claims()`

---

## 5. JWT → Gateway → MCP Session

When the agent sends an MCP `initialize` request to the Gateway, the JWT is validated and an MCP session is created.

```
Agent                              Gateway (deeptrail-gateway)
─────                              ──────────────────────────
POST /mcp                          JWTValidationMiddleware
  Authorization: Bearer <JWT>        ├─ Decodes JWT (HS256, verify exp/iss/aud)
  { method: "initialize" }          ├─ Creates AgentContext:
                                     │    { agent_id, owner, delegation_id,
                                     │      session_id, delegated_permissions,
                                     │      organization_id, token_type }
                                     └─ Stores in request.state.agent_context
                                           │
                                           ▼
                                     handle_initialize()
                                       ├─ Reads AgentContext from request
                                       ├─ Filters permissions by service:
                                       │    notion_perms = [p for p if p.startswith("notion:")]
                                       │    slack_perms  = [p for p if p.startswith("slack:")]
                                       ├─ Maps permissions → available tools:
                                       │    PermissionMapper.get_all_tools_for_permission()
                                       └─ Creates agent session in SessionManager:
                                            │
                                            ▼
                                     MCPSessionManager.create_agent_session()
                                       AgentMCPSession:
                                         ├─ agent_session_id: "asess-408c..."
                                         ├─ delegator: "sarah@acme.com"
                                         ├─ delegated_permissions: [7 perms]
                                         └─ backend_sessions:
                                              ├─ BackendMCPSession("notion"):
                                              │    ├─ mcp_session_id: "mcpsess-notion-<hex>"
                                              │    ├─ credential_ref: "vault://sarah-notion-..."
                                              │    └─ available_tools: [search_pages, ...]
                                              └─ BackendMCPSession("slack"):
                                                   ├─ mcp_session_id: "mcpsess-slack-<hex>"
                                                   ├─ credential_ref: "vault://sarah-slack-..."
                                                   └─ available_tools: [list_channels, ...]
```

### Session Hierarchy

```
Agent Connection to Gateway
  │
  ├── AgentMCPSession (1 per agent)
  │     ├── agent_session_id = from JWT session_id
  │     ├── delegator = from JWT owner
  │     └── delegated_permissions = from JWT
  │
  ├── BackendMCPSession: Notion (1 per backend service)
  │     ├── mcp_session_id = "mcpsess-notion-<uuid>"  (generated)
  │     ├── credential_ref = "vault://..." (resolved from vault)
  │     └── available_tools = [mapped from permissions]
  │
  └── BackendMCPSession: Slack
        ├── mcp_session_id = "mcpsess-slack-<uuid>"
        ├── credential_ref = "vault://..."
        └── available_tools = [mapped from permissions]
```

**Key files:**
- `deeptrail-gateway/app/middleware/jwt_validation.py` — JWT validation, `AgentContext`
- `deeptrail-gateway/app/mcp/handlers/initialize.py` — MCP initialize handler
- `deeptrail-gateway/app/mcp/session_manager.py` — Session management
- `deeptrail-gateway/app/mcp/permission_mapper.py` — Permission → tool mapping

---

## 6. Authorization at the Gateway (tools/call)

Every `tools/call` request goes through a multi-stage security pipeline before reaching the backend API.

```
Agent sends: tools/call { name: "notion.search_pages", arguments: {...} }
                                     │
                    ┌────────────────────────────────────┐
                    │    Gateway Security Pipeline        │
                    │                                    │
                    │  1. JWT Validation                 │
                    │     └─ Verify token, extract       │
                    │        AgentContext                 │
                    │                                    │
                    │  2. Fail-Closed Check              │
                    │     └─ If Control Plane             │
                    │        unreachable → DENY           │
                    │                                    │
                    │  3. Namespace Parsing              │
                    │     └─ "notion.search_pages" →     │
                    │        backend="notion",            │
                    │        tool="search_pages"          │
                    │                                    │
                    │  4. Permission Validation (C6)     │
                    │     └─ DelegationValidator checks:  │
                    │        tool → required permission   │
                    │        e.g., notion:pages:search    │
                    │        ∈ delegated_permissions?     │
                    │        If NO → DENY + audit log     │
                    │                                    │
                    │  5. Constraint Check (E5)          │
                    │     └─ Rate limits, quotas          │
                    │        If violated → DENY           │
                    │                                    │
                    │  6. Prompt Injection Scan (J5)     │
                    │     └─ Scan arguments for           │
                    │        injection patterns           │
                    │        If threat=high → BLOCK       │
                    │                                    │
                    │  7. Credential Injection (C7)      │
                    │     └─ Resolve vault ref →          │
                    │        OAuth token                  │
                    │        Inject into backend request  │
                    │        Agent NEVER sees token       │
                    │                                    │
                    │  8. Backend Forwarding             │
                    │     └─ Forward to Notion/Slack API  │
                    │        with injected credentials    │
                    │                                    │
                    │  9. PII Result Filter (J4)         │
                    │     └─ Mask sensitive data in       │
                    │        response (phone, email)      │
                    │                                    │
                    │ 10. Audit Log                      │
                    │     └─ Log success/failure with     │
                    │        full attribution             │
                    │                                    │
                    └────────────────────────────────────┘
                                     │
                                     ▼
                              Result returned to agent
```

### Permission Mapping (how tool names map to permission URNs)

```
Tool Name                  Required Permission       Decision
─────────────────────      ─────────────────────     ────────
notion.search_pages    →   notion:pages:search    →  ✅ (in delegation)
notion.get_page_content →  notion:blocks:read     →  ✅ (in delegation)
notion.update_page     →   notion:pages:update    →  ✅ (in delegation)
notion.create_page     →   notion:pages:create    →  ❌ DENIED (not delegated)
slack.list_channels    →   slack:channels:list    →  ✅ (in delegation)
slack.send_message     →   slack:messages:send    →  ✅ (in delegation)
```

### Credential Injection (Agent never sees OAuth tokens)

```
                    Gateway (server-side)
                    ─────────────────────
Backend Session                         Backend API
  credential_ref ──┐
  "vault://sarah   │   Credential
   -notion-xyz"    │   Injector (C7)
                   │      │
                   ▼      ▼
              Vault API → OAuth Token → Authorization: Bearer <token>
              (Control     (resolved     (injected into request)
               Plane)      just-in-time)
                                         → Notion API / Slack API
                                           (receives authenticated request)

Agent sees: { content: [...] }     ← result only, no token exposure
```

**Key files:**
- `deeptrail-gateway/app/mcp/handlers/tools_call.py` — Full pipeline
- `deeptrail-gateway/app/middleware/delegation_validator.py` — Permission checking (C6)
- `deeptrail-gateway/app/middleware/credential_injection.py` — Token injection (C7)
- `deeptrail-gateway/app/security/constraint_checker.py` — Rate limits (E5)
- `deeptrail-gateway/app/security/prompt_injection.py` — Input scanning (J5)
- `deeptrail-gateway/app/security/fail_closed.py` — Fail-closed enforcement (E4)
- `deeptrail-gateway/app/middleware/result_filter.py` — PII masking (J4)

---

## 7. Audit Trail — Full Attribution Chain

Every action through the Gateway generates an audit event with complete attribution back to the human user.

```
Gateway AuditMiddleware              Control Plane
────────────────────               ─────────────
AuditEvent (dataclass)             POST /api/v1/audit/events
  ├─ event_type: "mcp_tool_call"     │
  │   or "permission_denied"         ▼
  │   or "tool_error"              In-memory store (MVP)
  │   or "credential_error"        or AuditLoggerService (DB)
  │   or "delegation_revoked"        │
  ├─ success: true/false             ▼
  ├─ agent_id ◀── AgentContext     GET /api/v1/audit/events
  ├─ on_behalf_of ◀── .owner         ├─ Filter by agent_id
  ├─ organization_id ◀── .org_id     ├─ Filter by on_behalf_of
  ├─ tool: "notion.search_pages"     ├─ Filter by event_type
  ├─ delegation_id ◀── .deleg_id     └─ Filter by time range
  ├─ session_id ◀── .session_id
  ├─ agent_session_id ◀── .session_id
  ├─ mcp_session_id ◀── BackendMCPSession
  ├─ arguments: { query: "..." }   (redacted of sensitive fields)
  ├─ result_summary: "Found 5..."  (truncated to 100 chars)
  ├─ reason: null or "Permission denied: ..."
  ├─ duration_ms: 430
  └─ extra_data: { duration_ms, error_type, ... }
```

### How `organization_id` flows into audit events

```
IdP claims
  └─ groups[0] = "acme-org"
       │
       ▼
User JWT → organization_id: "acme-org"
       │
       ▼
Delegation dict → organization_id: "acme-org"
       │
       ▼
Agent Session JWT → organization_id: "acme-org"
       │                     (or)
Task Token JWT → organization_id: "acme-org"
       │
       ▼
Gateway: AgentContext.organization_id = "acme-org"
       │
       ▼
AuditMiddleware → AuditEvent.organization_id = agent_context.organization_id
       │
       ▼
Control Plane → stored in audit event → queryable by org
```

### Example Audit Trail (success + denial)

```json
{
    "event_type": "mcp_tool_call",
    "success": true,
    "agent_id": "sdr-assistant-123",
    "on_behalf_of": "sarah@acme.com",
    "organization_id": "acme-org",
    "tool": "notion.search_pages",
    "reason": null,
    "agent_session_id": "asess-408c90643c03",
    "mcp_session_id": "mcpsess-notion-6c9b3f1b7be1",
    "delegation_id": "mvp-delegation",
    "duration_ms": 430
}
```

```json
{
    "event_type": "permission_denied",
    "success": false,
    "agent_id": "sdr-assistant-123",
    "on_behalf_of": "sarah@acme.com",
    "organization_id": "acme-org",
    "tool": "notion.create_page",
    "reason": "Permission denied: notion:pages:create",
    "extra_data": {
        "required_permission": "notion:pages:create",
        "denial_reason": "permission_not_delegated"
    }
}
```

**Key files:**
- `deeptrail-gateway/app/middleware/audit.py` — AuditMiddleware, AuditEvent
- `deeptrail-control/app/api/v1/endpoints/audit.py` — Audit API endpoints

---

## Complete Data Lineage: `organization_id`

```
┌─────────────┐  groups[0]  ┌──────────┐ organization_id ┌────────────┐
│  Keycloak   │────────────▶│ User JWT │────────────────▶│ Delegation │
│  (IdP)      │             │  (L2)    │                 │  (L5)      │
└─────────────┘             └──────────┘                 └─────┬──────┘
                                                               │
                                          ┌────────────────────┤
                                          │                    │
                                          ▼                    ▼
                                   ┌────────────┐      ┌────────────┐
                                   │ Agent JWT  │      │ Task Token │
                                   │  (L3)      │      │  (L4)      │
                                   └──────┬─────┘      └──────┬─────┘
                                          │                    │
                                          ▼                    ▼
                                   ┌──────────────────────────────┐
                                   │ Gateway: AgentContext         │
                                   │   .organization_id            │
                                   └──────────────┬───────────────┘
                                                  │
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │ AuditMiddleware               │
                                   │   → AuditEvent.organization_id│
                                   └──────────────┬───────────────┘
                                                  │
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │ Control Plane Audit Store     │
                                   │   → Queryable by org          │
                                   └──────────────────────────────┘
```

## Complete Data Lineage: User Identity (`on_behalf_of`)

```
┌─────────────┐  email      ┌──────────┐  user_id       ┌────────────┐
│  Keycloak   │────────────▶│ User JWT │────────────────▶│ Delegation │
│  (IdP)      │             │ sub=email│                 │ user_id    │
└─────────────┘             └──────────┘                 └─────┬──────┘
                                                               │
                                          ┌────────────────────┤
                                          │                    │
                                          ▼                    ▼
                                   ┌────────────┐      ┌────────────┐
                                   │ Agent JWT  │      │ Task Token │
                                   │ owner=email│      │ owner=email│
                                   └──────┬─────┘      └──────┬─────┘
                                          │                    │
                                          ▼                    ▼
                                   ┌──────────────────────────────┐
                                   │ Gateway: AgentContext.owner   │
                                   └──────────────┬───────────────┘
                                                  │
                                        ┌─────────┴─────────┐
                                        ▼                   ▼
                                   AuditEvent          MCP Session
                                   .on_behalf_of       .delegator
                                   = "sarah@acme.com"  = "sarah@acme.com"
```

## Security Invariants

1. **No hardcoded identity data** — `organization_id`, user email, and permissions all originate from the IdP or user actions, never from hardcoded values in production code.

2. **Monotonic attenuation** — Permissions can only narrow as they flow through each layer:
   - OAuth scopes ⊇ delegation permissions ⊇ agent permissions ⊇ task permissions

3. **Agent never sees credentials** — OAuth tokens are resolved server-side by the Credential Injector and injected into backend requests. The agent only sees tool results.

4. **Fail-closed** — If the Control Plane is unreachable, the Gateway denies all requests rather than failing open.

5. **Complete audit attribution** — Every audit event traces back to a human (`on_behalf_of`), an organization (`organization_id`), and the specific delegation chain (`delegation_id`, `session_id`).

6. **Single-use challenges** — Agent authentication challenges are deleted after use, preventing replay attacks.
