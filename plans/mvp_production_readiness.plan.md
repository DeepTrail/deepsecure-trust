---
name: MVP Production Readiness
overview: "Convert the Virtual MCP Server MVP from mock implementations to production-ready deployment by implementing missing endpoints, real OAuth integration, real backend connections, and production security features across three phases (P0: E2E enablement, P1: real backend integration, P2: production hardening)."
todos:
  - id: p0-1
    content: "Create user login endpoint: POST /api/v1/auth/login with UserAuthService"
    status: pending
  - id: p0-2
    content: "Create service connection endpoint: POST /api/v1/users/me/services/connect"
    status: pending
  - id: p0-3
    content: Update delegation endpoint response to include delegation_token and permissions
    status: pending
  - id: p0-4
    content: Verify agent registration endpoint matches E2E test expectations
    status: pending
  - id: p0-5
    content: Wire new endpoints to API router in api.py
    status: pending
  - id: p0-6
    content: Test E2E demo passes all 10 steps
    status: pending
  - id: p1-1
    content: Implement secure vault token storage and retrieval endpoints
    status: pending
  - id: p1-2
    content: Implement OAuth flow endpoints (authorize, callback, refresh)
    status: pending
  - id: p1-3
    content: Implement real REST API calls in backend clients (Notion, Slack, HubSpot)
    status: pending
  - id: p1-4
    content: Connect CredentialInjector to Control Plane vault API
    status: pending
  - id: p1-5
    content: Implement token refresh in CredentialInjector
    status: pending
  - id: p2-1
    content: Implement Enterprise IdP integration (Okta/Entra ID)
    status: pending
  - id: p2-2
    content: Implement Keycloak token exchange (RFC 8693)
    status: pending
  - id: p2-3
    content: Implement result filtering (PII masking)
    status: pending
  - id: p2-4
    content: Implement Task Token system for per-task permissions
    status: pending
  - id: p2-5
    content: Implement prompt injection detection
    status: pending
isProject: false
---

# Virtual MCP Server: Mock to Production Conversion Plan

## Current State Analysis

The MVP has successfully implemented the **core gateway architecture** with all the structural components in place, but uses mocks/stubs in several critical areas. Based on the coverage analysis:

- **Token Layer 3 (Agent Session JWT)**: ~90% complete
- **MCP Gateway Core**: ~85% complete  
- **Audit & Security**: ~80% complete
- **Token Layers 0-2 (IdP/User/Delegation)**: ~15% complete
- **OAuth Authorization Layer**: ~10% complete
- **Per-Task Permissions**: ~5% complete

## Phase 0 (P0): Enable E2E Tests - Immediate Priority

The E2E demo (`demos/demo_sarah_journey_e2e.py`) is blocked by **two missing endpoints**. These are required for the test to run against live services.

### P0-1: Add User Login Endpoint

**File to create/modify:** `deeptrail-control/app/api/v1/endpoints/user_auth.py`

```python
# Required endpoint: POST /api/v1/auth/login
# Request: { "email": "sarah@acme.com", "password": "..." }
# Response: { "token": "...", "user": { "email": "...", "id": "..." } }
```

**Implementation:**

- Create `UserAuthService` in `deeptrail-control/app/services/user_auth_service.py`
- Use existing `UserSession` model from `app/models/user_session.py`
- Generate user session token (JWT or simple token)
- MVP: Basic password validation (hardcoded or config-based)
- Production: Integrate with IdP

### P0-2: Add Service Connection Endpoint

**File to create/modify:** `deeptrail-control/app/api/v1/endpoints/user_services.py`

```python
# Required endpoint: POST /api/v1/users/me/services/connect
# Request: { "service_id": "notion", "oauth_token": { "access_token": "...", "token_type": "bearer", "scope": "..." } }
# Response: { "connected": true, "service_id": "notion" }
```

**Implementation:**

- Use existing `ConnectedService` model from `app/models/connected_service.py`
- Use existing `ConnectedServiceService` from `app/services/connected_service_service.py`
- Store OAuth tokens in database (encrypted in production)
- Wire up to router in `app/api/v1/api.py`

### P0-3: Update Delegation Endpoint Response

**File:** `deeptrail-control/app/api/v1/endpoints/delegation.py`

The E2E test expects `delegation_token` in response but the current implementation returns different format. Ensure response includes:

```python
# Required response: { "delegation_token": "...", "permissions": [...] }
```

### P0-4: Wire Agent Registration Endpoint

**File:** `deeptrail-control/app/api/v1/endpoints/agents.py`

Ensure POST `/api/v1/agents/` accepts and stores:

- `agent_id`
- `name`
- `public_key` (Ed25519 base64-encoded)

Currently exists but needs verification of schema matching E2E expectations.

---

## Phase 1 (P1): Real Backend Integration

Replace mock implementations with real OAuth and backend MCP connections.

### P1-1: Real Credential Storage (Vault Integration)

**Files:**

- `deeptrail-control/app/services/vault_client.py` - Enhance for production
- `deeptrail-control/app/api/v1/endpoints/vault.py` - Add token retrieval endpoint

**Current state:** `CredentialInjector` in gateway returns mock tokens when `control_plane_url` is None

**Implementation:**

- Implement secure token storage (encrypt at rest)
- Add `/api/v1/vault/tokens/{credential_ref}` endpoint
- Add `/api/v1/vault/tokens/{credential_ref}/refresh` endpoint
- Connect gateway's `CredentialInjector` to Control Plane vault API

### P1-2: Real OAuth Flow for Service Connection

**Files:**

- `deeptrail-control/app/services/oauth_service.py` (new)
- `deeptrail-control/app/api/v1/endpoints/oauth.py` (new)

**Endpoints to add:**

- `GET /api/v1/oauth/{service_id}/authorize` - Generate OAuth authorization URL
- `GET /api/v1/oauth/{service_id}/callback` - Handle OAuth callback
- `POST /api/v1/oauth/{service_id}/refresh` - Refresh expired tokens

**Per-service OAuth configuration:**

- Notion: OAuth 2.0 with PKCE
- Slack: OAuth 2.0 with bot/user tokens
- HubSpot: OAuth 2.0 with refresh tokens

### P1-3: Real Backend MCP Server Connections

**Files:**

- `deeptrail-gateway/app/backends/connection_manager.py` - Configure real endpoints
- `deeptrail-gateway/app/config.py` (or similar) - Backend configuration

**Current state:** Backend clients (`NotionMCPClient`, etc.) are properly structured to call real MCP servers, but:

- No real MCP server URLs configured
- Mock tokens being used

**Implementation:**

- Configure backend MCP server URLs (if they exist) OR
- Implement direct API calls to backend services (more realistic for MVP):
  - Notion API: `https://api.notion.com/v1/`
  - Slack API: `https://slack.com/api/`
  - HubSpot API: `https://api.hubapi.com/`

**Decision Required:** 

- Option A: Connect to real MCP servers (requires Notion/Slack/HubSpot to expose MCP endpoints)
- Option B: Implement direct REST API calls translated from MCP tool calls (more practical for MVP)

### P1-4: Token Refresh Implementation

**File:** `deeptrail-gateway/app/middleware/credential_injection.py`

**Current state:** `_refresh_token()` returns `None` in MVP mode

**Implementation:**

- Call Control Plane's token refresh endpoint
- Handle refresh failures gracefully
- Cache refreshed tokens appropriately

---

## Phase 2 (P2): Production Hardening

### P2-1: Enterprise IdP Integration (Okta/Entra ID)

**Files:**

- `deeptrail-control/app/services/idp_service.py` (new)
- `deeptrail-control/app/api/v1/endpoints/sso.py` (new)

**Endpoints:**

- `GET /api/v1/auth/sso/{idp}/authorize` - Redirect to IdP
- `GET /api/v1/auth/sso/{idp}/callback` - Handle OIDC callback
- `POST /api/v1/auth/sso/logout` - SSO logout

**Implementation:**

- OIDC client library integration
- User provisioning from IdP claims
- Group-to-role mapping
- Automatic session invalidation on IdP changes

### P2-2: Keycloak Token Exchange (RFC 8693)

**Files:**

- `deeptrail-gateway/app/security/token_exchange.py` (new)
- Deploy Keycloak instance

**Purpose:** Exchange Agent Session JWT for backend-specific OAuth tokens (instead of using stored user tokens directly)

### P2-3: Result Filtering (PII Masking)

**File:** `deeptrail-gateway/app/middleware/result_filter.py` (new)

**Implementation:**

- Pattern-based PII detection (emails, phone numbers, SSNs)
- Configurable per-backend field masking
- Data classification awareness

### P2-4: Task Token System

**Files:**

- `deeptrail-control/app/models/task_token.py` (new)
- `deeptrail-control/app/services/task_service.py` (new)
- `deeptrail-control/app/api/v1/endpoints/tasks.py` (new)

**Endpoints:**

- `POST /api/v1/tasks` - Create task with scoped permissions
- `GET /api/v1/tasks/{task_id}` - Get task status
- `POST /api/v1/tasks/{task_id}/complete` - Complete and auto-revoke

### P2-5: Prompt Injection Detection

**File:** `deeptrail-gateway/app/security/prompt_injection.py` (new)

**Implementation:**

- Argument pattern validation
- Known malicious payload detection
- Configurable blocking rules

---

## Key Files Summary

### Control Plane (`deeptrail-control/`) Changes


| File                                    | Action               | Priority |
| --------------------------------------- | -------------------- | -------- |
| `app/api/v1/endpoints/user_auth.py`     | Create               | P0       |
| `app/api/v1/endpoints/user_services.py` | Create               | P0       |
| `app/api/v1/endpoints/delegation.py`    | Modify               | P0       |
| `app/api/v1/api.py`                     | Modify (wire routes) | P0       |
| `app/services/user_auth_service.py`     | Create               | P0       |
| `app/services/vault_client.py`          | Enhance              | P1       |
| `app/api/v1/endpoints/oauth.py`         | Create               | P1       |
| `app/services/oauth_service.py`         | Create               | P1       |
| `app/services/idp_service.py`           | Create               | P2       |


### Gateway (`deeptrail-gateway/`) Changes


| File                                     | Action                   | Priority |
| ---------------------------------------- | ------------------------ | -------- |
| `app/middleware/credential_injection.py` | Modify (real vault)      | P1       |
| `app/backends/connection_manager.py`     | Configure real endpoints | P1       |
| `app/config.py`                          | Add backend URLs         | P1       |
| `app/middleware/result_filter.py`        | Create                   | P2       |
| `app/security/prompt_injection.py`       | Create                   | P2       |


---

## Test Validation

After P0 completion, the following should pass:

```bash
# E2E demo should complete all 10 steps
python demos/demo_sarah_journey_e2e.py

# Interactive demo should work
python demos/demo_sarah_journey_interactive.py --auto
```

After P1 completion:

- Real OAuth tokens stored and used
- Real API calls to Notion/Slack/HubSpot
- Token refresh working

After P2 completion:

- Enterprise SSO login working
- PII filtering active
- Per-task permissions enforced

---

## Architecture Decision: Backend Integration Approach

**Recommendation:** For the MVP, implement **Option B (Direct REST API calls)** rather than waiting for official MCP servers:

The backend clients (`NotionMCPClient`, `SlackMCPClient`, `HubSpotMCPClient`) should:

1. Translate MCP tool calls to REST API calls
2. Use the credential-injected OAuth tokens
3. Transform REST responses to MCP content format

This is more practical because:

- Notion, Slack, HubSpot don't have official MCP servers yet
- The gateway can still aggregate and filter tools
- The security properties (credential isolation, audit) are preserved
- Easier to demo with real data

Example transformation in `NotionMCPClient`:

```python
async def call_tool(self, tool_name: str, arguments: dict, auth_token: str) -> ToolResult:
    if tool_name == "search_pages":
        # Call Notion REST API
        response = await self.http_client.post(
            "https://api.notion.com/v1/search",
            headers={"Authorization": auth_token, "Notion-Version": "2022-06-28"},
            json={"query": arguments.get("query")},
        )
        # Transform to MCP format
        return ToolResult(content=[{"type": "text", "text": json.dumps(response.json())}])
```
