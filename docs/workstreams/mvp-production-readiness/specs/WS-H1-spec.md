# Task Specification: WS-H1 Connect CredentialInjector to Vault API

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** BATCH_EXECUTION_PLAN.md P1-B3, MERGE_POINTS.md MP3

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-H1 |
| **Task Name** | Connect CredentialInjector to Vault API |
| **Type** | Middleware (Service/Handler) |
| **Service** | deeptrail-gateway |
| **Complexity** | M (1-3 hrs) |
| **Dependencies** | MP2 (E2, E3 endpoints) |
| **Validates** | E2E Step 8 (Execute Tool) with real token, MP3 criteria |

---

## Component Specification

### Class: `CredentialInjector`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-gateway/app/middleware/credential_injection.py` |
| **Type** | Class (singleton via module-level functions) |
| **Purpose** | Inject real OAuth credentials into backend API calls by fetching tokens from Control Plane vault |

### Constructor Change

```python
def __init__(
    self,
    control_plane_url: str | None = None,
    cache_ttl_seconds: int = 60,
    internal_api_token: str | None = None,  # NEW
):
```

### Method Signature Changes

```python
# Main entry point — add agent_jwt_token and user_id
async def inject_credentials(
    self,
    credential_ref: str | None,
    backend_id: str,
    agent_jwt_token: str | None = None,  # NEW
    user_id: str | None = None,          # NEW (for H2 refresh)
) -> InjectionResult:

# Cache wrapper — add backend_id and agent_jwt_token
async def _get_token(
    self,
    credential_ref: str,
    backend_id: str,                      # NEW
    agent_jwt_token: str | None = None,   # NEW
) -> dict[str, Any] | None:

# Vault fetch — add backend_id and agent_jwt_token
async def _fetch_from_vault(
    self,
    credential_ref: str,
    backend_id: str,                      # NEW — service_id for E2 URL
    agent_jwt_token: str | None = None,   # NEW — Bearer token for E2
) -> dict[str, Any] | None:

# Refresh — add backend_id and user_id (for H2)
async def _refresh_token(
    self,
    credential_ref: str,
    token_data: dict[str, Any],
    backend_id: str,                      # NEW — service_id for E3 URL
    user_id: str | None = None,           # NEW — for X-User-ID header
) -> dict[str, Any] | None:
```

### Module-Level Functions Update

```python
def configure_credential_injector(
    control_plane_url: str | None = None,
    cache_ttl_seconds: int = 60,
    internal_api_token: str | None = None,  # NEW
) -> CredentialInjector:

async def inject_credentials(
    credential_ref: str | None,
    backend_id: str,
    agent_jwt_token: str | None = None,   # NEW
    user_id: str | None = None,           # NEW
) -> InjectionResult:
```

---

## API Contract: E2 Vault Token Retrieval (called by this middleware)

### Endpoint Definition

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/vault/tokens/{service_id}` |
| **Auth** | Agent Session JWT via `Authorization: Bearer <agent-jwt>` |
| **Content-Type** | N/A (GET request) |

### Request

- **Path Parameter:** `service_id` (string) — e.g., `"notion"`, `"slack"`, `"hubspot"`
- **Header:** `Authorization: Bearer <agent-jwt-token>`

### Response Schema (Success - 200)

```json
{
  "access_token": "string — OAuth access token",
  "token_type": "string — default: bearer",
  "expires_in": "int | null — seconds until expiration",
  "scope": "string | null — space-separated scopes"
}
```

### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 401 | Invalid/missing Agent JWT | `{"detail": {"error": "unauthorized", ...}}` |
| 403 | Service not in delegated_permissions | `{"detail": {"error": "forbidden", "message": "Service not delegated"}}` |
| 404 | Service not connected for user | `{"detail": {"error": "not_found", "message": "Service not connected"}}` |

---

## Implementation: Fixed `_fetch_from_vault`

### Key Fix: URL uses `backend_id` (service_id), NOT `credential_ref`

```python
async def _fetch_from_vault(
    self,
    credential_ref: str,
    backend_id: str,
    agent_jwt_token: str | None = None,
) -> dict[str, Any] | None:
    if not self.control_plane_url:
        # MVP mode: unchanged
        logger.debug("MVP mode: returning mock token")
        return {
            "access_token": "mock_access_token_never_exposed_to_agent",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    # Production: Call Control Plane E2 endpoint
    if not agent_jwt_token:
        logger.error("No agent JWT token available for vault fetch")
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.control_plane_url}/api/v1/vault/tokens/{backend_id}",
                headers={"Authorization": f"Bearer {agent_jwt_token}"},
                timeout=5.0,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                logger.warning("Vault 403: service %s not delegated", backend_id)
                return None
            elif response.status_code == 404:
                logger.warning("Vault 404: service %s not connected", backend_id)
                return None
            else:
                logger.error("Vault status %d for service %s", response.status_code, backend_id)
                return None

    except httpx.TimeoutException:
        logger.error("Vault fetch timeout for service %s", backend_id)
        return None
    except Exception as e:
        logger.error("Vault fetch error: %s", type(e).__name__)
        return None
```

---

## JWT Token Threading

### Step 1: Store raw JWT in request state

**File:** `deeptrail-gateway/app/middleware/jwt_validation.py` (line 276)

```python
request.state.agent_jwt_token = token  # Add after request.state.jwt_payload
```

### Step 2: Pass through MCP context

**File:** `deeptrail-gateway/app/main.py` (context dict construction)

```python
"agent_jwt_token": getattr(request.state, "agent_jwt_token", None),
```

### Step 3: Extract in tools_call handler

**File:** `deeptrail-gateway/app/mcp/handlers/tools_call.py` (line ~278)

```python
agent_jwt_token = context.get("agent_jwt_token")
```

### Step 4: Pass to `_forward_to_backend` and `inject_credentials`

**File:** `deeptrail-gateway/app/mcp/handlers/tools_call.py`

```python
# _forward_to_backend signature:
async def _forward_to_backend(
    backend_id, backend_session, tool_name, arguments,
    agent_context=None, agent_jwt_token=None,  # NEW
) -> dict[str, Any]:

# inject_credentials call:
injection_result = await injector.inject_credentials(
    credential_ref=cred_ref,
    backend_id=backend_id,
    agent_jwt_token=agent_jwt_token,
)
```

---

## Error Handling Matrix

| E2 Response | Gateway Behavior | InjectionResult |
|-------------|------------------|-----------------|
| 200 | Return token_data dict | (success path) |
| 403 | Log warning, return None | TOKEN_NOT_FOUND |
| 404 | Log warning, return None | TOKEN_NOT_FOUND |
| 5xx | Log error, return None | TOKEN_NOT_FOUND |
| Timeout | Log error, return None | TOKEN_NOT_FOUND |
| No JWT | Log error, return None | TOKEN_NOT_FOUND |

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `deeptrail-gateway/app/middleware/credential_injection.py` |
| JWT storage | `deeptrail-gateway/app/middleware/jwt_validation.py` |
| Handler threading | `deeptrail-gateway/app/mcp/handlers/tools_call.py` |
| Startup config | `deeptrail-gateway/app/main.py` |
| Unit tests | `deeptrail-gateway/tests/middleware/test_credential_injection.py` |

---

## Test Endpoint Mapping

> **CRITICAL**: Tests MUST mock these exact endpoints.

| Test Case | Method | Endpoint | Expected Status |
|-----------|--------|----------|-----------------|
| Happy path | GET | `/api/v1/vault/tokens/notion` | 200 |
| Service not delegated | GET | `/api/v1/vault/tokens/notion` | 403 |
| Service not connected | GET | `/api/v1/vault/tokens/notion` | 404 |
| No JWT token | GET | `/api/v1/vault/tokens/notion` | (return None before call) |
| Timeout | GET | `/api/v1/vault/tokens/notion` | (httpx.TimeoutException) |
| MVP mode | N/A | N/A | Mock token returned |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `_fetch_from_vault` URL uses `backend_id` (service_id), not `credential_ref`
- [ ] `Authorization: Bearer <agent_jwt>` header sent to E2
- [ ] MVP mock path preserved when `control_plane_url` is None
- [ ] Raw JWT stored in `request.state.agent_jwt_token` (jwt_validation.py)
- [ ] JWT threaded through: handler → `_forward_to_backend` → `inject_credentials` → `_fetch_from_vault`
- [ ] All existing tests pass unchanged
- [ ] New `TestRealVaultFetch` tests pass
- [ ] No token values appear in log messages

---

## References

- **Design Doc:** BATCH_EXECUTION_PLAN.md P1-B3
- **Related Specs:** [WS-E2-spec.md](./WS-E2-spec.md), [WS-E3-spec.md](./WS-E3-spec.md)
- **Upstream Dependencies:** WS-E2 (token retrieval endpoint), WS-E3 (token refresh endpoint)
- **Downstream Dependents:** WS-H2 (uses constructor changes and parameter threading from H1)
