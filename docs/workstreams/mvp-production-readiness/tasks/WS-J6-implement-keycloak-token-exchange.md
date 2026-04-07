# Task: WS-J6 Implement Keycloak Token Exchange

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-J6 |
| **Task Name** | Implement Keycloak Token Exchange |
| **Workstream** | mvp-production-readiness |
| **Phase** | P2 (Production Hardening) |
| **Batch** | P2-B2 |
| **Status** | `ready` |
| **Dependencies** | WS-J4 (PII masking — ✅ Complete), WS-J5 (Prompt injection — ✅ Complete), WS-L1 (Keycloak infra — ✅ Complete) |
| **Complexity** | L (3+ hours) |
| **Service** | deeptrail-gateway |
| **Validates** | RFC 8693 token exchange, backend OAuth token acquisition, production-grade credential injection |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-J6-spec.md](../specs/WS-J6-spec.md) |
| **Source** | `deepsecure-comprehensive-architecture-consolidated.md` (OAuth Authorization Layer, Token Exchange Client), RFC 8693 |
| **L1 Dependency** | [WS-L1-spec.md](../specs/WS-L1-spec.md) — Keycloak realm config, gateway client setup |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **TokenExchangeClient** | Class in `app/security/token_exchange.py`; `exchange_token()` sends RFC 8693 POST to Keycloak; `get_backend_token()` is cache-first entry point |
| **RFC 8693 Form Params** | `grant_type`, `client_id`, `client_secret`, `subject_token`, `subject_token_type`, `requested_token_type`, `audience`, optional `scope` |
| **Token Caching** | In-memory dict keyed by `sha256(token)[:16]:backend_id`; TTL = `expires_in - buffer_seconds` |
| **Module Accessor** | `get_token_exchange_client()`, `configure_token_exchange_client()`, `reset_token_exchange_client()` |
| **Credential Injection** | Token exchange as primary path, vault as fallback in `credential_injection.py` |
| **Error Hierarchy** | `TokenExchangeError` → `TokenExchangeUnavailableError`, `TokenExchangeDeniedError` |
| **Keycloak Endpoint** | `POST {keycloak_url}/realms/{realm}/protocol/openid-connect/token` |

---

## API Contracts

> **Note:** This task implements an internal security module, not API endpoints.
> The `TokenExchangeClient` operates within the credential injection pipeline.
> No new HTTP endpoints are created on the gateway.
>
> The gateway calls Keycloak's token endpoint externally:
> `POST {keycloak_url}/realms/{realm}/protocol/openid-connect/token`

### Keycloak Token Exchange Request (RFC 8693)

```
POST /realms/deepsecure/protocol/openid-connect/token HTTP/1.1
Host: localhost:8080
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&client_id=gateway
&client_secret=gateway-secret
&subject_token=eyJhbGciOiJIUzI1NiJ9...
&subject_token_type=urn:ietf:params:oauth:token-type:access_token
&requested_token_type=urn:ietf:params:oauth:token-type:access_token
&audience=hubspot
```

### Keycloak Token Exchange Response (Success — 200)

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 300,
  "scope": "contacts:read"
}
```

### Keycloak Token Exchange Response (Error — 400)

```json
{
  "error": "invalid_grant",
  "error_description": "token is not active"
}
```

---

## Pre-Conditions

- [x] WS-J4 complete (PII masking — governance layer prerequisite)
- [x] WS-J5 complete (Prompt injection detection — governance layer prerequisite)
- [x] WS-L1 complete (Keycloak infrastructure — realm, gateway client, token exchange permissions)
- [ ] `deeptrail-gateway` service compiles and starts
- [ ] Keycloak `gateway` confidential client configured with token exchange enabled (from L1)
- [ ] `credential_injection.py` middleware exists in gateway (current vault-based path)
- [ ] `app/security/` directory exists with module accessor pattern (e.g., `fail_closed.py`)

---

## Task Description

### Objective

Create a `TokenExchangeClient` that implements RFC 8693 (OAuth 2.0 Token Exchange) to swap DeepSecure JWTs for backend-specific OAuth access tokens via Keycloak. Integrate it into the credential injection pipeline as the primary token source, with vault as fallback.

### Background

The gateway's `CredentialInjector` currently retrieves backend OAuth tokens from the Control Plane's vault (`vault://` credential references). These are static tokens — they expire, require manual refresh, and don't support per-request audience/scope narrowing.

Token exchange replaces this with a dynamic flow:

```
Current:  Agent JWT → Gateway → Vault (static token) → Backend API
                                     ↓
                              May be expired
                              No per-request scoping

Target:   Agent JWT → Gateway → TokenExchangeClient → Keycloak → Fresh OAuth Token → Backend API
                                     ↓                    ↓
                              Cache-first lookup      RFC 8693 exchange
                              TTL-buffered             Audience-scoped
```

This enables fresh, audience-scoped tokens per backend, eliminates static token expiration issues, and aligns with the architecture's OAuth Authorization Layer design.

### What to Implement

#### 1. Data Models and Error Types

In `deeptrail-gateway/app/security/token_exchange.py`:

- **Enums:** `TokenExchangeGrantType`, `SubjectTokenType`, `RequestedTokenType` (RFC 8693 URNs)
- **`TokenExchangeConfig`** dataclass: `enabled`, `keycloak_url`, `realm`, `client_id`, `client_secret`, `cache_ttl_buffer_seconds` (default 60), `request_timeout_seconds` (default 10), `audience_map: Dict[str, str]`
- **`ExchangedToken`** dataclass: `access_token`, `token_type`, `expires_in`, `scope`, `issued_at`; `is_expired` property
- **Error hierarchy:** `TokenExchangeError` (base, with `error_code` and `details`), `TokenExchangeUnavailableError`, `TokenExchangeDeniedError`

#### 2. TokenExchangeClient Class

- **`__init__(config)`:** Accepts optional `TokenExchangeConfig`; initializes empty cache dict and lazy `httpx.AsyncClient`
- **`token_endpoint` property:** Constructs `{keycloak_url}/realms/{realm}/protocol/openid-connect/token`
- **`exchange_token(subject_token, backend_id, scopes)`:**
  - Builds RFC 8693 form parameters via `_build_exchange_params()`
  - POSTs to `token_endpoint` with `application/x-www-form-urlencoded`
  - On 200: parses response into `ExchangedToken`
  - On `invalid_grant` / `unauthorized_client`: raises `TokenExchangeDeniedError`
  - On connection error / timeout: raises `TokenExchangeUnavailableError`
  - On other errors: raises `TokenExchangeError`
- **`get_backend_token(subject_token, backend_id, scopes, force_refresh)`:**
  - Generates cache key via `_cache_key()`
  - If not `force_refresh`, checks cache via `_get_cached()`
  - On cache hit: returns cached `ExchangedToken` (no HTTP call)
  - On cache miss: calls `exchange_token()`, stores result via `_put_cache()`, returns
- **`_build_exchange_params(subject_token, backend_id, scopes)`:** Builds RFC 8693 form dict with audience mapping
- **`_cache_key(subject_token, backend_id)`:** `sha256(token)[:16]:backend_id`
- **`_get_cached(cache_key)`:** Returns token if exists and not expired; evicts expired entries
- **`_put_cache(cache_key, token)`:** Reduces `expires_in` by `cache_ttl_buffer_seconds` before storing
- **`close()`:** Closes `httpx.AsyncClient`

#### 3. Module-Level Accessor

- `get_token_exchange_client() -> Optional[TokenExchangeClient]`
- `configure_token_exchange_client(config) -> TokenExchangeClient`
- `reset_token_exchange_client() -> None`

#### 4. Credential Injection Integration

In `deeptrail-gateway/app/middleware/credential_injection.py`:

- Import `get_token_exchange_client` and `TokenExchangeError`
- In `inject_credentials()`: before existing vault path, check if exchange client exists and is enabled
- On success: return `InjectionResult` with `credential_source="token_exchange"`
- On `TokenExchangeError`: log warning, fall through to existing vault path (graceful degradation)

#### 5. Startup Configuration

In `deeptrail-gateway/app/main.py`:

- Import `configure_token_exchange_client` and `TokenExchangeConfig`
- During app startup: call `configure_token_exchange_client()` with settings from environment/config
- Add environment variables: `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_GATEWAY_CLIENT_ID`, `KEYCLOAK_GATEWAY_CLIENT_SECRET`

#### 6. Exports

Update `deeptrail-gateway/app/security/__init__.py` to export key symbols.

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/security/token_exchange.py` | Create | TokenExchangeClient, data models, error types, module accessor |
| `deeptrail-gateway/app/security/__init__.py` | Modify | Export TokenExchangeClient, config, accessors |
| `deeptrail-gateway/app/middleware/credential_injection.py` | Modify | Add token exchange as primary path, vault as fallback |
| `deeptrail-gateway/app/main.py` | Modify | Add `configure_token_exchange_client()` call on startup |
| `deeptrail-gateway/tests/security/test_token_exchange.py` | Create | Unit tests (14+ test cases) |

---

## Acceptance Criteria

### Functional

- [ ] `TokenExchangeClient` sends correct RFC 8693 form POST to Keycloak token endpoint
- [ ] `exchange_token()` returns `ExchangedToken` on successful 200 response
- [ ] `get_backend_token()` returns cached token on cache hit (no HTTP call)
- [ ] `get_backend_token()` performs fresh exchange on cache miss
- [ ] `get_backend_token(force_refresh=True)` bypasses cache
- [ ] Cache entries expire according to `expires_in - cache_ttl_buffer_seconds`
- [ ] Expired cache entries are evicted on access
- [ ] Audience mapping: `audience_map` config maps `backend_id` to Keycloak audience; unknown backends fall back to `backend_id` as audience
- [ ] Scopes are space-separated in the `scope` form parameter
- [ ] `token_endpoint` property constructs correct Keycloak URL

### Security

- [ ] `client_secret` never appears in log output
- [ ] Exchanged token values never logged
- [ ] Token exchange errors don't leak Keycloak internals to callers
- [ ] Cache key uses SHA-256 hash of subject token (not the token itself)
- [ ] TLS required for Keycloak URL in production (validation/warning if HTTP)
- [ ] Confidential client authentication via `client_id` + `client_secret` in form body

### Error Handling

- [ ] Keycloak `invalid_grant` → `TokenExchangeDeniedError`
- [ ] Keycloak `unauthorized_client` → `TokenExchangeDeniedError`
- [ ] Connection timeout / refused → `TokenExchangeUnavailableError`
- [ ] Non-200 unknown errors → `TokenExchangeError` with `error_code` and `details`
- [ ] All errors include `error_code` and `details` dict for diagnostics

### Integration

- [ ] Credential injection uses token exchange as primary path when configured
- [ ] On `TokenExchangeError`, falls back to existing vault credential path
- [ ] `configure_token_exchange_client()` called during gateway startup
- [ ] Module accessor lifecycle: `configure → get → reset` works correctly
- [ ] No regression in existing vault-based credential injection when exchange is disabled

---

## Test Cases

| Test Case | Method | Module | Expected | Notes |
|-----------|--------|--------|----------|-------|
| Token endpoint URL | `token_endpoint` | `TokenExchangeClient` | Correct Keycloak URL | Realm substitution |
| Build exchange params | `_build_exchange_params()` | `TokenExchangeClient` | RFC 8693 params | With audience mapping |
| Audience map fallback | `_build_exchange_params()` | `TokenExchangeClient` | `backend_id` as audience | Unknown backend |
| Scopes in params | `_build_exchange_params()` | `TokenExchangeClient` | `scope` space-separated | Multiple scopes |
| Exchange success | `exchange_token()` | `TokenExchangeClient` | `ExchangedToken` returned | Mock 200 |
| Exchange denied | `exchange_token()` | `TokenExchangeClient` | `TokenExchangeDeniedError` | Mock `invalid_grant` |
| Exchange unavailable | `exchange_token()` | `TokenExchangeClient` | `TokenExchangeUnavailableError` | Mock connection error |
| Cache hit | `get_backend_token()` | `TokenExchangeClient` | Cached token (no HTTP) | Pre-seeded cache |
| Cache miss | `get_backend_token()` | `TokenExchangeClient` | Fresh exchange | Empty cache |
| Cache expired | `get_backend_token()` | `TokenExchangeClient` | Fresh exchange | Expired entry evicted |
| Force refresh | `get_backend_token()` | `TokenExchangeClient` | Fresh exchange | `force_refresh=True` |
| Cache TTL buffer | `_put_cache()` | `TokenExchangeClient` | `expires_in` reduced | Buffer subtracted |
| Cache key deterministic | `_cache_key()` | `TokenExchangeClient` | Same key for same inputs | Hash-based |
| Cache key varies by backend | `_cache_key()` | `TokenExchangeClient` | Different keys | Same token, different backend |
| Token not expired | `is_expired` | `ExchangedToken` | `False` | Within TTL |
| Token expired | `is_expired` | `ExchangedToken` | `True` | Past expiry |
| Module accessor lifecycle | `configure/get/reset` | Module-level | Lifecycle correct | Global state |
| Credential injection with exchange | `inject_credentials()` | `credential_injection.py` | Exchange token used | `credential_source="token_exchange"` |
| Credential injection fallback | `inject_credentials()` | `credential_injection.py` | Vault token used | Exchange fails → vault |

---

## Post-Conditions

After this task is complete:

- [ ] Gateway can acquire fresh, audience-scoped OAuth tokens via Keycloak
- [ ] Static vault tokens serve as fallback when exchange is unavailable
- [ ] P2 validation criteria for token exchange can be executed
- [ ] Production deployment can use Keycloak (or any OIDC AS) for backend token acquisition
- [ ] End-to-end flow: Agent JWT → Gateway → Keycloak exchange → Backend API

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway

# Run token exchange tests
pytest tests/security/test_token_exchange.py -v

# Run credential injection tests (regression check)
pytest tests/middleware/test_credential_injection.py -v

# Run all security module tests
pytest tests/security/ -v
```

### Manual Verification

```bash
# 1. Start services (with Keycloak from L1)
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d
sleep 20

# 2. Verify Keycloak is healthy
curl -sf http://localhost:8080/health/ready && echo "Keycloak healthy"

# 3. Verify gateway starts with token exchange configured
docker compose logs deeptrail-gateway 2>&1 | grep -i "token.exchange"
# Expected: Log line indicating token exchange client configured

# 4. Get a user token
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# 5. Create agent and get Agent JWT (challenge-response flow)
# (See CLAUDE.md "Agent JWT Creation Flow" for full steps)

# 6. Test token exchange via MCP tools/call (triggers credential injection)
# Initialize MCP session
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

# Call a tool (triggers credential injection → token exchange)
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {"name": "hubspot.search_contacts", "arguments": {"query": "test"}}
  }'

# 7. Check gateway logs for token exchange activity
docker compose logs deeptrail-gateway 2>&1 | grep -i "token_exchange\|credential_source"
# Expected: "credential_source=token_exchange" or fallback to vault

# 8. Test graceful degradation (stop Keycloak, try again)
docker compose stop keycloak
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {"name": "hubspot.search_contacts", "arguments": {"query": "test"}}
  }'
# Expected: Falls back to vault credential (no 500 error)
docker compose start keycloak
```

---

## References

- **Spec:** [WS-J6-spec.md](../specs/WS-J6-spec.md) — full class contract, data models, caching, integration
- **RFC 8693:** [OAuth 2.0 Token Exchange](https://datatracker.ietf.org/doc/html/rfc8693)
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` — OAuth Authorization Layer, Token Exchange Client
- **L1 Spec:** [WS-L1-spec.md](../specs/WS-L1-spec.md) — Keycloak realm, gateway client config
- **Existing Credential Injection:** `deeptrail-gateway/app/middleware/credential_injection.py` — vault-based path
- **Module Pattern:** `deeptrail-gateway/app/security/fail_closed.py` — module accessor reference
- **Sibling Modules:** J4 (`result_filter.py`), J5 (`prompt_injection.py`) — same security module structure
- **Upstream:** WS-J4 (✅), WS-J5 (✅), WS-L1 (✅)
- **Downstream:** P2 validation (token exchange test), production deployment

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway

# Execute the task
/execute-task WS-J6 mvp-production-readiness

# After completion
/complete-task WS-J6 mvp-production-readiness
```
