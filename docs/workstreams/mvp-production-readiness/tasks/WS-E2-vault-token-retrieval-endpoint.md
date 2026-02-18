# Task: WS-E2 Vault Token Retrieval Endpoint

> **Status:** `ready`
> **Batch:** P1-B2
> **Worktree:** mvp-prod-control

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-E2 |
| **Workstream** | E (Vault & Credential Storage) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | WS-E1 (VaultClient) ✅ Complete |
| **Complexity** | M (1-3 hours) |
| **Service** | deeptrail-control |
| **Validates** | Gateway credential retrieval, P1-B3 (H1, H2) |

---

## Specification

> See full specification: [../specs/WS-E2-spec.md](../specs/WS-E2-spec.md)

### Key Contracts

**Endpoint:**
| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/vault/tokens/{service_id}` |
| **Auth** | Agent JWT (Bearer token with `delegated_permissions`) |

**Response (200):**
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600,
  "scope": "read write"
}
```

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 401 | Invalid/missing JWT |
| 403 | Service not in `delegated_permissions` |
| 404 | Service not connected |

---

## API Contracts

### Endpoint: Get Service Token

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/vault/tokens/{service_id}` |
| **Auth** | Agent JWT (Bearer token) |
| **Purpose** | Retrieve OAuth access token for a connected service |

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `service_id` | string | Service identifier (e.g., `notion`, `slack`, `hubspot`) |

**Request Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer <agent_jwt>` with `delegated_permissions` |

**Success Response (200):**
```json
{
  "access_token": "xoxb-...",
  "token_type": "bearer",
  "expires_in": 3600,
  "scope": "read write"
}
```

**Error Responses:**
| Status | Error | Condition |
|--------|-------|-----------|
| 401 | `unauthorized` | Invalid/missing JWT |
| 403 | `forbidden` | Service not in `delegated_permissions` |
| 404 | `not_found` | Service not connected for user |

---

## Pre-Conditions

- [x] WS-E1 complete (VaultClient with token storage)
- [x] ConnectedServiceService exists with `get_token_for_service()` method
- [x] Agent JWT authentication middleware exists
- [x] P1-B1 complete (foundation services)

---

## Task Description

### Objective

Create an API endpoint that allows the Gateway to retrieve OAuth access tokens for a user's connected service. This endpoint is called by the Gateway during credential injection.

### Background

The Gateway needs to retrieve OAuth tokens from the Control Plane vault to inject into backend API calls. The endpoint must:
1. Validate the agent JWT
2. Check that the requested service is in the agent's delegated permissions
3. Retrieve the token from the vault
4. Return only the access token (NOT the refresh token)

### What to Implement

1. **Create `app/schemas/vault.py`**:
   ```python
   from pydantic import BaseModel

   class TokenResponse(BaseModel):
       """Response schema for token retrieval."""
       access_token: str
       token_type: str = "bearer"
       expires_in: int | None = None
       scope: str | None = None

   class TokenErrorResponse(BaseModel):
       """Error response schema."""
       error: str
       message: str
   ```

2. **Create `app/api/v1/endpoints/vault.py`**:
   ```python
   from fastapi import APIRouter, Depends, HTTPException
   from app.schemas.vault import TokenResponse
   from app.services.connected_service_service import ConnectedServiceService
   from app.api.deps import get_current_agent

   router = APIRouter(prefix="/vault", tags=["vault"])

   @router.get("/tokens/{service_id}", response_model=TokenResponse)
   async def get_token(
       service_id: str,
       agent_claims: dict = Depends(get_current_agent),
       connected_service: ConnectedServiceService = Depends(),
   ):
       # 1. Validate service is in delegated_permissions
       delegated = agent_claims.get("delegated_permissions", [])
       if not any(service_id in p for p in delegated):
           raise HTTPException(403, detail={"error": "forbidden", "message": "Service not delegated"})

       # 2. Get user_id from agent claims
       user_id = agent_claims.get("user_id")
       if not user_id:
           raise HTTPException(401, detail={"error": "unauthorized", "message": "Invalid token"})

       # 3. Retrieve token from vault
       token_data = await connected_service.get_token_for_service(user_id, service_id)
       if not token_data:
           raise HTTPException(404, detail={"error": "not_found", "message": "Service not connected"})

       # 4. Return (excluding refresh_token)
       return TokenResponse(
           access_token=token_data.access_token,
           token_type=token_data.token_type,
           expires_in=token_data.expires_in,
           scope=token_data.scope
       )
   ```

3. **Register router in `app/api/v1/api.py`**:
   ```python
   from app.api.v1.endpoints import vault
   api_router.include_router(vault.router)
   ```

4. **Create tests in `tests/api/test_vault.py`**

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/schemas/vault.py` | Create | Pydantic schemas |
| `deeptrail-control/app/api/v1/endpoints/vault.py` | Create | Vault endpoints |
| `deeptrail-control/app/api/v1/api.py` | Modify | Register router |
| `deeptrail-control/tests/api/test_vault.py` | Create | Unit tests |

---

## Acceptance Criteria

### Functional Criteria

- [ ] `GET /api/v1/vault/tokens/{service_id}` endpoint created
- [ ] Returns `TokenResponse` with access_token, token_type, expires_in, scope
- [ ] Does NOT return refresh_token (security requirement)

### Security Criteria

- [ ] Validates agent JWT before processing
- [ ] Checks `service_id` is in `delegated_permissions` array
- [ ] Returns 403 if service not delegated
- [ ] Returns 401 if JWT invalid/missing

### Integration Criteria

- [ ] Uses existing `ConnectedServiceService.get_token_for_service()`
- [ ] Uses existing agent JWT authentication dependency
- [ ] Router registered in API router

### Contract Verification (from spec)

- [ ] Endpoint path matches: `/api/v1/vault/tokens/{service_id}`
- [ ] Response schema matches spec (4 fields)
- [ ] Error responses match spec format
- [ ] Tests cover all 4 cases (200, 401, 403, 404)

---

## Test Cases

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Happy path | GET | `/api/v1/vault/tokens/notion` | 200 | Valid JWT, connected service |
| Missing JWT | GET | `/api/v1/vault/tokens/notion` | 401 | No Authorization header |
| Invalid JWT | GET | `/api/v1/vault/tokens/notion` | 401 | Malformed/expired JWT |
| Service not delegated | GET | `/api/v1/vault/tokens/notion` | 403 | notion not in permissions |
| Service not connected | GET | `/api/v1/vault/tokens/notion` | 404 | User hasn't connected |

---

## Post-Conditions

After this task is complete:
- [ ] Gateway can retrieve OAuth tokens from Control Plane
- [ ] Tokens only returned for delegated services
- [ ] refresh_token never exposed to agents
- [ ] WS-E3 (token refresh) can be implemented
- [ ] WS-H1, WS-H2 (credential injection) unblocked

---

## Validation

### Unit Tests
```bash
cd deeptrail-control
pytest tests/api/test_vault.py -v
```

### Manual Verification
```bash
# 1. Get an agent JWT with delegation
# 2. Call the endpoint
curl -X GET http://localhost:8000/api/v1/vault/tokens/notion \
  -H "Authorization: Bearer <agent_jwt>"

# Expected: {"access_token": "...", "token_type": "bearer", ...}
```

---

## References

- **Specification:** [../specs/WS-E2-spec.md](../specs/WS-E2-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Upstream:** WS-E1 (VaultClient) ✅ Complete
- **Downstream:** WS-E3 (Token refresh), WS-H1, WS-H2 (Credential injection)
- **Related Code:**
  - `deeptrail-control/app/services/connected_service_service.py`
  - `deeptrail-control/app/api/deps.py` (get_current_agent)

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-E2 mvp-production-readiness
```
