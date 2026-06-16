# MCP Authorization Specification vs DeepSecure Implementation: Gap Analysis Audit

**Date:** 2026-04-30 (Updated: 2026-05-28)
**Auditor:** AI Security Audit Agent
**Scope:** MCP Authorization Spec (2025-11-25) + MCP 2026-07-28 Release Candidate (stateless core + auth hardening) vs DeepSecure (deeptrail-control, deeptrail-gateway, deepsecure SDK)
**Severity Scale:** CRITICAL | HIGH | MEDIUM | LOW | INFO
**Spec Sources:**
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization (current)
- https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/ (incoming, ships July 28 2026)

---

## Executive Summary

DeepSecure implements a **fundamentally different authorization architecture** than what the MCP Authorization specification prescribes. The MCP spec mandates **OAuth 2.1 with Protected Resource Metadata (RFC 9728)** for HTTP-based transports, where the MCP server acts as a standard OAuth 2.1 Resource Server. DeepSecure instead implements a **custom Ed25519 challenge-response authentication system** with proprietary JWT issuance via a Control Plane, where the Gateway acts as a "Virtual MCP Server."

This is not inherently wrong — the MCP spec states authorization is **OPTIONAL** — but it means DeepSecure's Gateway is **not interoperable with standard MCP clients** (like VS Code, Claude Desktop, or any client implementing the MCP auth spec). A standard MCP client connecting to the DeepSecure Gateway would fail at the first `401 Unauthorized` because it would expect a `WWW-Authenticate` header with `resource_metadata` pointing to a Protected Resource Metadata document, which DeepSecure does not serve.

**Critical Update (2026-05-28):** The MCP 2026-07-28 Release Candidate (ships July 28, 2026) introduces **breaking changes** that directly impact DeepSecure's Gateway architecture. The `initialize`/`initialized` handshake and `Mcp-Session-Id` header are **removed** in favor of a fully stateless protocol. DeepSecure's Gateway still requires `initialize` to create in-memory sessions — this must be fixed before July 28 when Tier 1 SDKs begin targeting the new spec. See [Section 0](#0-mcp-2026-07-28-release-candidate-impact-on-deepsecure-critical) for details.

### Overall Assessment

| Area | Status | Impact |
|------|--------|--------|
| MCP OAuth 2.1 compliance | **Not implemented** | Standard MCP clients cannot authenticate |
| Protected Resource Metadata (RFC 9728) | **Not implemented** | Discovery flow completely absent |
| Authorization Server Metadata (RFC 8414 / OIDC Discovery) | **Not implemented** | No AS discovery; spec requires both mechanisms |
| Client ID Metadata Documents (IETF Draft) | **Not implemented** | Recommended ("most common") registration approach absent |
| Dynamic Client Registration (RFC 7591) | **Not implemented** | No DCR support |
| Resource Indicators (RFC 8707) | **Not implemented** | No `resource` param; canonical URI never sent |
| PKCE for MCP client auth (S256 required) | **N/A** — different auth model | PKCE exists for backend OAuth only |
| PKCE discovery via `code_challenge_methods_supported` | **N/A** — no AS metadata | Spec: client MUST refuse if field absent |
| Token audience validation (RFC 8707 §2) | **Partial** — internal aud only, legacy bypass | Not per RFC 8707; legacy fallback disables aud |
| Per-request Bearer authorization | **Partial** — JWT on every /mcp call | Not OAuth Bearer per spec; no refresh flow |
| Scope selection strategy | **Not implemented** | No `scope` in 401, no `scopes_supported` in PRM |
| Scope challenge handling (403 + insufficient_scope) | **Not implemented** | No step-up auth flow |
| Session security | **Partial** — sessions not tied to auth | Session hijacking risk per MCP spec |
| Token passthrough prevention | **Concern** — agent JWT in handler context | Needs explicit audit of all forwarding paths |
| Confused deputy protection | **Partial** — delegation helps | No per-client consent at Gateway |

---

## 0. MCP 2026-07-28 Release Candidate: Impact on DeepSecure (CRITICAL)

> **The release candidate is locked as of May 21, 2026. The final specification ships on July 28, 2026.** This is the largest revision of the protocol since launch.

### 0.1 Stateless Protocol Core — DeepSecure Gateway Is NOT Stateless (CRITICAL)

The headline change in 2026-07-28 is that **MCP is now stateless at the protocol layer**. Six SEPs work together to remove the `initialize`/`initialized` handshake and `Mcp-Session-Id`, so any request can land on any server instance.

**What 2026-07-28 Removes:**
- `initialize` / `initialized` handshake (SEP-2575) — **REMOVED**
- `Mcp-Session-Id` header and protocol-level session (SEP-2567) — **REMOVED**
- Sticky sessions and shared session stores are no longer needed

**What 2026-07-28 Adds:**
- `MCP-Protocol-Version` header on every request
- `_meta` carries `clientInfo` and capabilities on every request (not just `initialize`)
- `server/discover` method replaces `initialize` for capability discovery
- `Mcp-Method` and `Mcp-Name` headers **REQUIRED** (SEP-2243) for routing
- `ttlMs` and `cacheScope` on list/resource results (SEP-2549)
- W3C Trace Context (`traceparent`, `tracestate`, `baggage`) in `_meta` (SEP-414)
- Multi Round-Trip Requests with `InputRequiredResult` and `requestState` (SEP-2322)
- Server-initiated requests only during active client request (SEP-2260)

**DeepSecure's Current Architecture (CRITICAL MISMATCH):**

Despite comments in `main.py` stating "stateless — JWT is source of truth," the Gateway is **actually stateful at the protocol level**:

1. **`initialize` is required.** The `handle_initialize` handler calls `session_manager.create_agent_session()` which creates an in-memory `AgentMCPSession` with backend sessions (Notion, Slack, Gmail, etc.). Without this, `tools/list` and `tools/call` return empty results or fail.

2. **In-memory session store.** `MCPSessionManager._sessions` is a Python `dict` — not distributed, not Redis-backed. The docstring explicitly states: "This is in-memory storage for MVP. Production should use Redis or distributed cache for horizontal scaling."

3. **Session is NOT thread-safe.** The session manager explicitly notes: "This implementation is NOT thread-safe."

4. **Requests must hit the same instance.** Because sessions are in-memory, the Gateway requires sticky routing — exactly what 2026-07-28 eliminates.

5. **`Mcp-Session-Id` still used.** The `/mcp` endpoint reads `Mcp-Session-Id` from headers and returns it on `initialize` responses (line 644 of `main.py`). This header is being removed in 2026-07-28.

6. **Supported versions don't include 2026-07-28.** `SUPPORTED_PROTOCOL_VERSIONS = ["2025-11-25", "2024-11-05", "2024-10-07"]` — the upcoming version is absent.

**The Design Tension:**

There's a fundamental tension in DeepSecure's architecture: the JWT already carries **all the context needed** for stateless operation (`agent_id`, `owner`, `delegated_permissions`, `delegation_id`, `session_id`). The `MCPSessionManager` reconstructs state from the JWT during `initialize`, then later looks it up by `agent_session_id`. This is exactly the anti-pattern that 2026-07-28 eliminates.

The Gateway COULD be made truly stateless by:
1. Deriving tool permissions from JWT `delegated_permissions` directly on each request
2. Using the `PermissionMapper` to resolve tools on each `tools/list` call (no session needed)
3. Resolving credentials on each `tools/call` from the JWT context (no session lookup needed)

This would align perfectly with 2026-07-28 and leverage DeepSecure's existing JWT design.

### 0.2 Routing and Operability Gaps (HIGH)

**`Mcp-Method` and `Mcp-Name` headers (SEP-2243) — NOT IMPLEMENTED:**

2026-07-28 **requires** these headers on every request so load balancers and gateways can route without inspecting the JSON-RPC body. Servers must reject requests where headers and body disagree.

```http
POST /mcp HTTP/1.1
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: search
Content-Type: application/json
```

DeepSecure currently parses the JSON body to extract `method` (line 583 of `main.py`). There is no header-based routing.

**Impact:** Without these headers, the Gateway cannot be placed behind a standard MCP-aware load balancer or API gateway that routes on headers.

### 0.3 Caching — NOT IMPLEMENTED (MEDIUM)

**`ttlMs` and `cacheScope` on responses (SEP-2549):**

List and resource read results now carry cache metadata modeled on HTTP `Cache-Control`:
- `ttlMs`: How long the response is fresh
- `cacheScope`: Whether it's safe to share across users

DeepSecure's `tools/list` response includes no caching metadata. This means clients must re-fetch on every call, adding unnecessary latency.

### 0.4 Trace Context — NOT IMPLEMENTED (MEDIUM)

**W3C Trace Context in `_meta` (SEP-414):**

The spec locks down `traceparent`, `tracestate`, and `baggage` key names so distributed traces correlate across SDKs and gateways. DeepSecure reads `X-Request-ID` but does not propagate W3C Trace Context.

### 0.5 Multi Round-Trip Requests — NOT IMPLEMENTED (MEDIUM)

**`InputRequiredResult` and `requestState` (SEP-2322):**

Instead of holding an SSE stream open, servers return an `InputRequiredResult` with `requestState`. The client gathers answers and re-issues the call with `inputResponses`. Any server instance can handle the retry because state is in the payload.

DeepSecure's GET `/mcp` endpoint is a minimal SSE keepalive stream (line 679 of `main.py`). It does not implement multi round-trip request handling.

### 0.6 Authorization Hardening — 6 SEPs (HIGH)

The 2026-07-28 RC includes six authorization-specific SEPs:

| SEP | Requirement | DeepSecure Status | Impact |
|-----|-------------|-------------------|--------|
| SEP-2468 | Validate `iss` on auth responses (RFC 9207) | **N/A** — no OAuth flow | Mix-up attack prevention for future |
| SEP-837 | Declare `application_type` during DCR | **N/A** — no DCR | Prevents localhost redirect rejection |
| SEP-2352 | Bind credentials to issuer, re-register on migration | **N/A** — no OAuth | Credential lifecycle management |
| SEP-2207 | Request refresh tokens from OIDC AS | **Not implemented** | No refresh tokens at all |
| SEP-2350 | Scope accumulation during step-up | **Not implemented** | No step-up authorization |
| SEP-2351 | `.well-known` discovery suffix clarification | **Not implemented** | No `.well-known` endpoints |

### 0.7 Other Breaking Changes

| Change | DeepSecure Impact | Severity |
|--------|-------------------|----------|
| Extensions framework with reverse-DNS IDs | Not implemented | LOW |
| MCP Apps (server-rendered UIs via iframe) | Not implemented | LOW |
| Tasks extension redesign (server-directed, no `tasks/list`) | Not applicable | INFO |
| Roots deprecated → tool parameters | Not applicable | INFO |
| Sampling deprecated → direct LLM API integration | Not applicable | INFO |
| Logging deprecated → stderr / OpenTelemetry | Not applicable | INFO |
| JSON Schema 2020-12 for `inputSchema`/`outputSchema` | Tool schemas need audit | MEDIUM |
| Error code `-32002` → `-32602` for missing resource | DeepSecure uses `-32002` for `SESSION_INVALID` (different semantics) — may cause confusion | LOW |

### 0.8 Protocol Version Negotiation Gap (HIGH)

`SUPPORTED_PROTOCOL_VERSIONS` in `initialize.py`:
```python
SUPPORTED_PROTOCOL_VERSIONS = ["2025-11-25", "2024-11-05", "2024-10-07"]
```

`2026-07-28` is absent. After July 28, clients targeting the new spec will send requests without `initialize`, using `MCP-Protocol-Version: 2026-07-28` header. The Gateway will:
1. Not recognize the version
2. Require an `initialize` that the client won't send
3. Fail to read `Mcp-Method` / `Mcp-Name` headers
4. Return errors that the client doesn't expect

---

## 1. Authorization Flow Architecture Gap (CRITICAL)

### MCP Spec Normative Role Definitions

The spec defines three OAuth 2.1 roles (§Roles):
- **MCP Server** = OAuth 2.1 **Resource Server** — accepts protected resource requests using access tokens
- **MCP Client** = OAuth 2.1 **Client** — makes protected resource requests on behalf of a resource owner
- **Authorization Server** — issues access tokens; may be co-located or separate from the resource server

The spec's §Overview mandates five normative requirements:
1. AS **MUST** implement OAuth 2.1 for both confidential and public clients
2. AS + clients **SHOULD** support Client ID Metadata Documents
3. AS + clients **MAY** support Dynamic Client Registration (RFC 7591)
4. MCP servers **MUST** implement Protected Resource Metadata (RFC 9728); clients **MUST** use it for AS discovery
5. AS **MUST** provide RFC 8414 or OIDC Discovery 1.0; clients **MUST** support both

### What MCP Spec Requires (Full Flow)

The spec defines a **multi-step OAuth 2.1 flow** for HTTP-based transports:

1. **Initial Handshake**: Client sends request → Server responds `401` with `WWW-Authenticate: Bearer resource_metadata="...", scope="..."` 
2. **Protected Resource Metadata Discovery**: Client fetches PRM document from the `resource_metadata` URL or `/.well-known/oauth-protected-resource[/path]`
3. **Authorization Server Discovery**: Client fetches AS metadata trying endpoints in strict priority order (RFC 8414 first, then OIDC Discovery, with path-insertion variants)
4. **Client Registration**: Via pre-registration (priority 1) → Client ID Metadata Documents (priority 2) → Dynamic Client Registration (priority 3) → manual entry (priority 4)
5. **User Authorization**: OAuth 2.1 Authorization Code + PKCE (S256 MUST); `resource` parameter MUST be included; scope selection per strategy
6. **Token Exchange**: code_verifier + resource parameter included in token request
7. **Authenticated Requests**: `Authorization: Bearer <token>` on **every HTTP request** — even within the same logical session; tokens MUST NOT appear in URI query strings

### What DeepSecure Implements

DeepSecure uses a **completely custom flow**:

1. **Agent Registration**: Agent pre-registered with Ed25519 public key in Control Plane
2. **User Delegation**: Human user creates delegation granting permissions to agent
3. **Agent Challenge-Response**: Agent calls `/api/v1/auth/agent/challenge` → signs nonce with Ed25519 private key → submits to `/api/v1/auth/agent/verify`
4. **Proprietary JWT Issuance**: Control Plane issues HS256 JWT with custom claims (`sub`, `owner`, `delegated_permissions`, `delegation_id`, `session_id`)
5. **Gateway Authentication**: Gateway validates JWT with shared HS256 secret, extracts `AgentContext`
6. **MCP Protocol**: Agent sends JSON-RPC requests to `/mcp` with Bearer JWT

### Gap Analysis

| MCP Spec Requirement | Spec Keyword | DeepSecure Status | Severity |
|---|---|---|---|
| `401` with `WWW-Authenticate` including `resource_metadata` | MUST (RFC 9728 §5.1) | Returns bare `WWW-Authenticate: Bearer` — **no `resource_metadata`, no `scope`** | **CRITICAL** |
| `/.well-known/oauth-protected-resource` endpoint (root or path-based) | MUST (RFC 9728) | **Not implemented** | **CRITICAL** |
| OAuth 2.1 Authorization Code + PKCE flow for MCP client auth | MUST (OAuth 2.1 §4.1) | **Not implemented** — uses Ed25519 challenge-response | **CRITICAL** |
| Authorization Server Metadata (RFC 8414 AND OIDC Discovery) | MUST (both client + server) | **Not implemented** as an MCP authorization server | **CRITICAL** |
| AS metadata discovery priority order (path-insertion variants) | MUST | **Not implemented** — no AS metadata endpoints | **CRITICAL** |
| Client ID Metadata Documents (HTTPS URL as `client_id`) | SHOULD | **Not implemented** — no concept of MCP client registration | **HIGH** |
| `resource` parameter in auth AND token requests (RFC 8707) | MUST | **Not implemented** — no resource indicators at all | **HIGH** |
| `resource` = canonical URI of MCP server (no fragment, consistent trailing slash) | MUST | **Not implemented** | **HIGH** |
| Clients MUST send `resource` regardless of AS support | MUST | **Not implemented** | **HIGH** |
| PKCE with S256 code challenge method | MUST (OAuth 2.1 §4.1.1) | **N/A** for MCP auth (exists for backend OAuth) | **CRITICAL** (if OAuth added) |
| Client MUST check `code_challenge_methods_supported` in AS metadata; refuse if absent | MUST | **Not implemented** | **HIGH** (if OAuth added) |
| Bearer token on every HTTP request (even within same session) | MUST (OAuth 2.1 §5.1.1) | **Partial** — JWT sent per-request, but not standard OAuth Bearer | **MEDIUM** |
| Tokens MUST NOT be in URI query string | MUST (OAuth 2.1 §5) | **Compliant** — tokens only in Authorization header | **OK** |
| Scope-based access control (OAuth `scope`) | Spec convention | Uses custom `delegated_permissions` instead | **HIGH** |
| Scope selection strategy (401 scope → PRM scopes_supported → request all) | SHOULD | **Not implemented** — no scope in 401, no PRM | **MEDIUM** |

### Impact

Any **standard MCP client** (VS Code with MCP support, Claude Desktop, or any client built with the MCP TypeScript/Python/C# SDKs) **cannot authenticate** with the DeepSecure Gateway. This locks DeepSecure into requiring its own custom SDK/client for all interactions.

### Recommendation

DeepSecure should implement an **OAuth 2.1 gateway layer** (potentially backed by Keycloak, which is already configured for RFC 8693 token exchange) that:
1. Serves Protected Resource Metadata at `/.well-known/oauth-protected-resource`
2. Points to an Authorization Server (Keycloak or custom) that supports:
   - Authorization Server Metadata (RFC 8414)
   - Authorization Code + PKCE
   - Dynamic Client Registration or Client ID Metadata Documents
3. Issues audience-scoped access tokens
4. Validates tokens per OAuth 2.1 Section 5.2

The existing Ed25519 challenge-response flow could be preserved as an **alternative authentication mechanism** for programmatic agents (similar to how the MCP spec allows STDIO transports to use environment-based credentials).

---

## 2. Protected Resource Metadata (RFC 9728) — NOT IMPLEMENTED (CRITICAL)

### What MCP Spec Requires

> "MCP servers **MUST** implement OAuth 2.0 Protected Resource Metadata (RFC 9728)."
> "MCP clients **MUST** use OAuth 2.0 Protected Resource Metadata for authorization server discovery."

The spec defines **two mandatory discovery mechanisms** (servers MUST implement at least one, clients MUST support both):

**Mechanism 1 — WWW-Authenticate Header** (preferred when present):
```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer resource_metadata="https://gateway.deepsecure.com/.well-known/oauth-protected-resource",
                         scope="mcp:tools"
```

**Mechanism 2 — Well-Known URI** (fallback, in priority order):
1. Path-based: `https://example.com/.well-known/oauth-protected-resource/public/mcp` (if MCP endpoint is at `/public/mcp`)
2. Root: `https://example.com/.well-known/oauth-protected-resource`

The PRM document MUST include `authorization_servers` containing at least one AS:

```json
{
  "resource": "https://gateway.deepsecure.com/mcp",
  "authorization_servers": ["https://auth.deepsecure.com"],
  "scopes_supported": ["mcp:tools", "mcp:resources"],
  "bearer_methods_supported": ["header"]
}
```

The spec also SHOULD includes a `scope` parameter in the `WWW-Authenticate` header (per RFC 6750 §3) to provide clients with "immediate guidance on the appropriate scopes to request during authorization, following the principle of least privilege." Clients MUST treat scopes in the challenge as authoritative for the current request.

### What DeepSecure Does

The Gateway's `_unauthorized_response` method in `jwt_validation.py` returns:

```python
headers={"WWW-Authenticate": "Bearer"}
```

This is a bare `WWW-Authenticate` with no `resource_metadata`, `realm`, or `scope` parameters.

Additionally:
- No `/.well-known/oauth-protected-resource` endpoint exists (neither root nor path-based)
- No PRM JSON document is served from any endpoint
- The `/mcp` endpoint does not have any associated well-known metadata path

### Impact

- Standard MCP clients have **no way to discover** how to authenticate
- The 401 response provides **no actionable information** for the client to begin an auth flow
- Violates a **MUST** requirement in the spec — both server-side (must serve PRM) and client-side (must parse it)
- The scope guidance mechanism is entirely absent, forcing clients to guess permissions

---

## 3. Authorization Server Metadata Discovery — NOT IMPLEMENTED (CRITICAL)

### What MCP Spec Requires

The spec mandates that AS metadata discovery support **both** OAuth 2.0 Authorization Server Metadata (RFC 8414) **and** OpenID Connect Discovery 1.0. Clients MUST try multiple well-known endpoints in a strict priority order:

**For issuer URLs with path components** (e.g., `https://auth.example.com/tenant1`):
1. `https://auth.example.com/.well-known/oauth-authorization-server/tenant1` (RFC 8414 path insertion)
2. `https://auth.example.com/.well-known/openid-configuration/tenant1` (OIDC path insertion)
3. `https://auth.example.com/tenant1/.well-known/openid-configuration` (OIDC path appending)

**For issuer URLs without path components** (e.g., `https://auth.example.com`):
1. `https://auth.example.com/.well-known/oauth-authorization-server` (RFC 8414)
2. `https://auth.example.com/.well-known/openid-configuration` (OIDC)

The AS **MUST** provide at least one of these. The AS metadata MUST include `code_challenge_methods_supported` (for PKCE discovery) — the spec says if this field is absent, "MCP clients **MUST** refuse to proceed."

### What DeepSecure Does

- No Authorization Server metadata endpoints exist
- Keycloak is deployed for backend token exchange but not configured as an MCP-facing authorization server
- Keycloak natively supports `/.well-known/openid-configuration` — this is the easiest path to compliance

### Impact

- Even if PRM were added pointing to an AS, clients would fail at the next step (discovering AS endpoints)
- Without `code_challenge_methods_supported` advertised, compliant MCP clients MUST abort
- The multi-tenant path-insertion format matters for enterprise deployments

---

## 4. Token Security Architecture Gaps

### 4.1 HS256 Shared Secret (HIGH)

**Current:** Both Control Plane and Gateway share the same HS256 secret key for JWT signing/verification.

**MCP Spec Reference:** The spec recommends following OAuth 2.1 security best practices, which favor asymmetric signing (RS256, ES256, EdDSA) for JWTs.

**Risks:**
- If the Gateway is compromised, the attacker can **forge JWTs** for any agent
- The shared secret must be distributed to every service that validates tokens, expanding the attack surface
- No key rotation mechanism apparent in the codebase

**DeepSecure acknowledges this:** The code comments explicitly note `HS256 with shared secret - MVP` and `JWT_ALGORITHM = "HS256"  # MVP: Use symmetric key; Production: RS256 or EdDSA`.

**Recommendation:** Migrate to RS256 or EdDSA with JWKS endpoint on the Control Plane. The Gateway already has placeholder methods (`_fetch_public_key`, `_validate_jwt_signature`) for this.

### 4.2 Token Audience Validation (HIGH)

**MCP Spec:**
> "MCP servers MUST validate that access tokens were issued specifically for them as the intended audience."

**DeepSecure:**
- The Gateway validates `aud: "deeptrail-gateway"` on Layer 3 JWTs — this is **good** for internal tokens
- However, there's a **legacy fallback** that disables audience verification:

```python
# Fallback: Try without issuer/audience for legacy tokens
payload = jwt.decode(
    token,
    self.jwt_secret_key,
    algorithms=[self.jwt_algorithm],
    options={
        "verify_aud": False,
        "verify_iss": False,
    },
)
```

This fallback **completely bypasses** audience and issuer validation for "legacy" tokens, allowing any validly-signed JWT to be accepted regardless of intended audience.

**Severity:** HIGH — an attacker who obtains any HS256-signed JWT from any DeepSecure service could present it to the Gateway.

### 4.3 Token Passthrough Risk (HIGH)

**MCP Spec:**
> "MCP servers MUST NOT accept or transit any other tokens."
> "Token passthrough is explicitly forbidden."

**DeepSecure concern:** The Gateway implements RFC 8693 Token Exchange via Keycloak (`token_exchange.py`). This exchanges the agent's JWT for backend-specific OAuth tokens — which is the **correct** approach per the spec. However:

1. The raw agent JWT is stored in `request.state.agent_jwt_token` and passed into MCP handler context as `agent_jwt_token`. If any handler or middleware forwards this token to upstream APIs directly, it would constitute token passthrough.
2. The credential injection middleware (`credential_injection.py`) retrieves separate backend tokens — this is the correct pattern.

**Audit Findings (2026-05-28):**

The MCP path is **safe**: `tools/call` uses `CredentialInjector` which exchanges the agent JWT for a backend-specific OAuth token via Keycloak (RFC 8693) or vault fetch. The agent JWT is sent only to Keycloak and the Control Plane vault endpoint, never to external backends.

The `/proxy` path has a **confirmed leak vector**: `SecretInjectionMiddleware` is fail-open — if Shamir reassembly fails or no domain-to-secret mapping exists, the middleware logs and continues. The proxy then forwards the original `Authorization` header (the agent JWT) because `proxy_config.py` explicitly preserves `authorization` in forwarded headers. An attacker controlling an external endpoint could harvest agent JWTs this way.

**Recommendation:**
1. Make secret injection **fail-closed** on the `/proxy` path — if no credential can be injected, reject the request rather than forwarding the agent JWT
2. Strip the original `Authorization` header before proxy forwarding, then inject backend-specific credentials only
3. Add explicit guardrails preventing `agent_jwt_token` from being set on outbound requests

### 4.4 No Token Revocation Mechanism (MEDIUM)

The Gateway has a placeholder `_check_token_revocation` method but no actual implementation. If an agent's delegation is revoked:
- The JWT remains valid until expiration (up to 8 hours)
- No token revocation list or introspection endpoint exists
- The Gateway has no way to learn about revoked tokens in real-time

**MCP Spec (§Token Theft):**
> "Authorization servers **SHOULD** issue short-lived access tokens to reduce the impact of leaked tokens. For public clients, authorization servers **MUST** rotate refresh tokens."

DeepSecure's 8-hour JWT TTL is far too long. The spec's guidance on refresh token rotation for public clients is also unaddressed, since DeepSecure doesn't issue refresh tokens at all.

### 4.5 No Refresh Token Flow (MEDIUM)

**MCP Spec:** The full OAuth 2.1 flow issues both access tokens and refresh tokens. For public clients (like desktop MCP clients), refresh token rotation is MUST-level:
> "For public clients, authorization servers **MUST** rotate refresh tokens as described in OAuth 2.1 Section 4.3.1."

**DeepSecure:** Issues a single JWT with no refresh mechanism. When the JWT expires, the agent must re-authenticate from scratch via the challenge-response flow. No refresh token is issued or supported.

---

## 5. Client Registration Gaps

### MCP Spec Priority Order

The spec defines a strict priority ordering for client registration (§Client Registration Approaches):
1. **Pre-registered client information** if available
2. **Client ID Metadata Documents** if AS advertises `client_id_metadata_document_supported: true`
3. **Dynamic Client Registration** (RFC 7591) if AS advertises `registration_endpoint`
4. **Manual entry** (prompt user) as last resort

### 5.1 No Client ID Metadata Documents (HIGH)

**MCP Spec:**
> "MCP clients and authorization servers **SHOULD** support OAuth Client ID Metadata Documents."

This is the **most common** MCP scenario per the spec — where client and server have no prior relationship. The spec is detailed about requirements:

**For Clients:**
- MUST host metadata at an HTTPS URL
- `client_id` URL MUST use `https` scheme and contain a path component (e.g., `https://app.example.com/client.json`)
- Document MUST include: `client_id`, `client_name`, `redirect_uris`
- `client_id` in document MUST match the URL exactly
- MAY use `private_key_jwt` for client authentication with JWKS

**For Authorization Servers:**
- SHOULD fetch metadata when encountering URL-formatted `client_id`
- MUST validate `client_id` matches URL exactly
- MUST validate redirect URIs against those in the document
- SHOULD cache metadata respecting HTTP headers
- SHOULD consider SSRF risks when fetching metadata
- SHOULD display warnings for `localhost`-only redirect URIs

**Discovery:** AS advertises support via `client_id_metadata_document_supported: true` in its metadata.

**DeepSecure:** No concept of MCP client registration at all. Agents are registered with Ed25519 keys, not as OAuth clients. No AS metadata exists to advertise `client_id_metadata_document_supported`.

### 5.2 No Dynamic Client Registration (MEDIUM)

**MCP Spec:**
> "MCP clients and authorization servers **MAY** support the OAuth 2.0 Dynamic Client Registration Protocol (RFC 7591) to allow MCP clients to obtain OAuth client IDs without user interaction. This option is included for backwards compatibility with earlier versions of the MCP authorization spec."

Not implemented. The Control Plane has no `/register` endpoint for OAuth clients. If Keycloak were configured as the MCP AS, it supports DCR natively.

### 5.3 No Pre-Registration for External MCP Clients (HIGH)

There is no mechanism for an external MCP client (like VS Code, Claude Desktop, or any standard MCP SDK client) to register itself and obtain client credentials. DeepSecure's agent registration is key-based, not client-based.

### 5.4 Client ID Metadata Document Security Gaps (HIGH — Future Risk)

When implementing CIMD, the spec highlights specific security concerns:

**SSRF Risk:** The AS fetches a URL provided by an unknown client. A malicious client could use this to trigger requests to private endpoints. DeepSecure must implement SSRF protections (block private IPs, require HTTPS) when fetching metadata documents.

**Localhost Redirect URI Impersonation:** An attacker can claim to be any legitimate client by providing the real client's metadata URL as their `client_id`, then binding to a `localhost` port. The server sees the legitimate metadata, the user sees the legitimate name. AS implementations SHOULD display additional warnings and MUST clearly display the redirect URI hostname.

**Trust Policies:** The spec allows AS to implement domain-based trust policies (allowlists, reputation checks, domain age). DeepSecure should design its trust policy before implementing CIMD.

---

## 6. Scope Management Gaps

### 6.1 Scope Selection Strategy — NOT IMPLEMENTED (MEDIUM)

**MCP Spec (§Scope Selection Strategy):**
The spec defines a specific priority for scope selection during authorization:

1. Use `scope` from the initial `WWW-Authenticate` header in the 401 response, if provided
2. If `scope` not available, use all scopes from `scopes_supported` in the Protected Resource Metadata, omitting the `scope` parameter from the request if `scopes_supported` is undefined

> "This approach accommodates the general-purpose nature of MCP clients, which typically lack domain-specific knowledge to make informed decisions about individual scope selection."

The `scopes_supported` field is intended to be the minimal set for basic functionality, with additional scopes requested via step-up authorization.

**DeepSecure:** None of this exists. There's no `scope` in 401 responses, no PRM with `scopes_supported`, and no mechanism for clients to discover available permissions before authenticating.

### 6.2 Custom Permission Model vs OAuth Scopes (MEDIUM)

**MCP Spec:**
Uses standard OAuth scope patterns with space-delimited strings (e.g., `files:read files:write user:profile`).

**DeepSecure:**
Uses a custom permission model with URN-like strings (`notion:pages:search`, `slack:messages:search`) stored in the JWT's `delegated_permissions` array. This is semantically richer but:

1. **Not interoperable** with standard OAuth scope mechanisms
2. No step-up authorization flow (insufficient scope → re-auth with elevated scopes)
3. No incremental scope elevation as defined in the MCP spec's "Scope Challenge Handling" section
4. Scopes cannot be discovered by clients via standard metadata endpoints

### 6.3 No Scope Challenge Handling (MEDIUM)

**MCP Spec (§Scope Challenge Handling):**
When a client makes a request with insufficient scope, the server SHOULD respond with:
```http
HTTP/1.1 403 Forbidden
WWW-Authenticate: Bearer error="insufficient_scope",
                         scope="files:read files:write user:profile",
                         resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource",
                         error_description="Additional file write permission required"
```

The spec defines three server strategies for determining which scopes to include:
- **Minimum:** newly-required scopes + existing granted scopes
- **Recommended:** existing relevant scopes + newly required scopes (prevents loss of previously granted permissions)
- **Extended:** existing + new + commonly co-used scopes

**DeepSecure:**
Returns a plain `403 Forbidden` with `{"error": "permission_denied", "detail": "Permission denied: notion:pages:write"}`. No `WWW-Authenticate` header, no `insufficient_scope` error code, no required scopes, no path for the client to upgrade permissions.

### 6.4 No Step-Up Authorization Flow (MEDIUM)

**MCP Spec (§Step-Up Authorization Flow):**
When clients receive `insufficient_scope`, they SHOULD:
1. Parse error info from `WWW-Authenticate` header
2. Determine required scopes per the selection strategy
3. Initiate re-authorization with the determined scope set
4. Retry the original request with new authorization (with retry limits)

> "Clients **SHOULD** implement retry limits and **SHOULD** track scope upgrade attempts to avoid repeated failures for the same resource and operation combination."

**DeepSecure:** No step-up flow exists. Once an agent's JWT is issued with a fixed set of `delegated_permissions`, there is no mechanism to request additional permissions without re-authentication. The delegation model is static for the lifetime of the JWT.

---

## 7. Resource Parameter Implementation (RFC 8707) — NOT IMPLEMENTED (HIGH)

### What MCP Spec Requires

The spec dedicates an entire section to Resource Indicators (§Resource Parameter Implementation):

> "MCP clients **MUST** implement Resource Indicators for OAuth 2.0 as defined in RFC 8707."

Key requirements:
1. `resource` parameter **MUST** be included in **both** authorization requests **and** token requests
2. **MUST** identify the MCP server the client intends to use the token with
3. **MUST** use the canonical URI of the MCP server
4. Clients **MUST** send this parameter "regardless of whether authorization servers support it"

**Canonical URI rules:**
- Must use HTTPS scheme, no fragment
- Consistent trailing slash handling (prefer without unless semantically significant)
- Valid: `https://mcp.example.com/mcp`, `https://mcp.example.com:8443`
- Invalid: `mcp.example.com` (no scheme), `https://mcp.example.com#fragment`

**Token validation:**
> "MCP servers **MUST** validate that access tokens were issued specifically for them as the intended audience, according to RFC 8707 Section 2."

### What DeepSecure Does

- No `resource` parameter is sent in any request (there's no OAuth flow to send it in)
- The Gateway validates `aud: "deeptrail-gateway"` which is a static string, not a canonical URI per RFC 8707
- The legacy JWT fallback disables audience validation entirely

### Security Impact

> "Access Token Privilege Restriction: An attacker can gain unauthorized access if the server accepts tokens issued for other resources. This has two critical dimensions: (1) Audience validation failures, (2) Token passthrough."

Without RFC 8707 resource binding, tokens issued by the DeepSecure AS could theoretically be used at any service that shares the same JWT secret — which, with HS256, is any service that knows the shared secret.

---

## 8. Session Security Gaps

### 8.1 Session Not Bound to Authentication (HIGH)

**MCP Spec (Security Best Practices):**
> "MCP servers that implement authorization MUST verify all inbound requests. MCP Servers MUST NOT use sessions for authentication."
> "MCP servers SHOULD bind session IDs to user-specific information."

**DeepSecure:**
- The `MCPSessionManager` creates sessions keyed by `agent_session_id`
- Sessions are stored in-memory (not distributed)
- While JWT validation happens on every request (good), the `Mcp-Session-Id` header is not used — sessions are tied to the `agent_session_id` from the JWT
- **Risk:** If sessions are shared via a distributed store (future Redis migration as noted in code), session keys must be bound to the authenticated user to prevent session hijacking

### 8.2 Session ID Predictability (MEDIUM)

Session IDs are generated with `uuid.uuid4().hex[:12]` which provides only 48 bits of entropy. The MCP spec recommends "secure, non-deterministic session IDs" — UUIDs are fine but truncating to 12 hex chars reduces the security margin.

---

## 9. Transport Security Gaps

### 9.1 No HTTPS Enforcement (HIGH)

**MCP Spec:**
> "Implementations MUST follow OAuth 2.1 Section 1.5 'Communication Security'."
> "All authorization server endpoints MUST be served over HTTPS."
> "All redirect URIs MUST be either localhost or use HTTPS."

**DeepSecure:**
- Development URLs are all `http://localhost:*`
- No TLS enforcement in the Gateway or Control Plane code
- The `token_exchange.py` has a warning for non-TLS but doesn't block: `"Token exchange configured with non-TLS URL — use HTTPS in production"`
- CORS is configured as `allow_origins=["*"]` — overly permissive

**Note:** This is expected for development but there should be production configuration that enforces HTTPS.

### 9.2 No Open Redirection Protection (HIGH — Future Risk)

**MCP Spec (§Open Redirection):**
> "MCP clients **MUST** have redirect URIs registered with the authorization server."
> "Authorization servers **MUST** validate exact redirect URIs against pre-registered values."
> "MCP clients **SHOULD** use and verify state parameters."
> "Authorization servers **SHOULD** only automatically redirect the user agent if it trusts the redirection URI."

**DeepSecure:** Since there's no OAuth flow for MCP client auth, there are no redirect URIs to validate. However, the existing backend OAuth flows (`deeptrail-control/app/api/v1/endpoints/oauth.py`) do use `state` parameters and redirect URI validation. If an MCP OAuth flow is added, these protections must be applied.

### 9.3 SSRF Vulnerability in OAuth Metadata Discovery (LOW — Not Applicable Yet)

Since DeepSecure doesn't implement OAuth metadata discovery, this attack vector doesn't exist yet. However, if/when implementing RFC 9728 metadata endpoints, the Control Plane and Gateway must validate all URLs to prevent SSRF attacks (blocking private IP ranges, requiring HTTPS, etc.).

---

## 10. Authorization Code Protection (PKCE) — CRITICAL for Future OAuth

### What MCP Spec Requires

The spec has unusually strict requirements for PKCE:

> "MCP clients **MUST** implement PKCE according to OAuth 2.1 Section 7.5.2 and **MUST** verify PKCE support before proceeding with authorization."
> "MCP clients **MUST** use the `S256` code challenge method when technically capable."

**PKCE Discovery (critical detail):**
- **OAuth AS Metadata:** If `code_challenge_methods_supported` is absent → AS does not support PKCE → client **MUST** refuse to proceed
- **OIDC Discovery:** If `code_challenge_methods_supported` is absent → client **MUST** refuse to proceed
- AS providing OIDC Discovery **MUST** include `code_challenge_methods_supported` for MCP compatibility

### What DeepSecure Does

- PKCE is implemented for backend OAuth (Notion, Google) with S256 — this is good
- But there's no PKCE for MCP client authentication (no OAuth flow exists)
- There's no AS metadata to advertise `code_challenge_methods_supported`

### Impact

If DeepSecure implements the MCP OAuth flow, PKCE is not optional — it's MUST-level on both client and server. The existing PKCE implementation in `oauth_service.py` can serve as a foundation.

---

## 11. Backend OAuth Implementation (Partial Compliance)

The Control Plane's OAuth implementation for connecting to **backend services** (Notion, Slack, Gmail) is **well-implemented** relative to OAuth best practices:

| Feature | Status | Notes |
|---|---|---|
| PKCE (RFC 7636) | **Implemented** for Notion, Google (S256 method) | Properly generates code_verifier/code_challenge |
| State parameter | **Implemented** | Cryptographic random state tokens with TTL |
| Token storage | **Implemented** | Vault-backed with encryption |
| Token refresh | **Implemented** | Per-service refresh flow |
| RFC 8693 Token Exchange | **Implemented** | Via Keycloak for backend token acquisition |

However, this backend OAuth is for **connecting to third-party APIs**, not for MCP client authentication. These are two different concerns.

---

## 12. MCP Authorization Extensions Gaps

### 12.1 OAuth Client Credentials Flow (INFO)

**Extension:** `io.modelcontextprotocol/oauth-client-credentials`
**Purpose:** Machine-to-machine auth for CI/CD pipelines, background services
**DeepSecure status:** Not implemented. The Ed25519 challenge-response serves a similar purpose but isn't standard OAuth.

The spec notes extensions are "Optional," "Additive," "Composable," and "Versioned independently."

### 12.2 Enterprise-Managed Authorization (MEDIUM)

**Extension:** `io.modelcontextprotocol/enterprise-managed-authorization`
**Purpose:** Centralized access control via enterprise IdP (Okta, Azure AD)
**DeepSecure status:** 
- DeepSecure has an SSO/IdP integration system (`sso.py`, `idp_service.py`) with providers for Okta, Google, Entra (Azure AD), and Keycloak
- However, this is for **user authentication** to the Control Plane, not for the MCP Enterprise-Managed Authorization flow which uses ID-JAG (Identity Assertion JWT Authorization Grant)
- The concepts align but the protocols differ

---

## 13. Error Handling Gaps

### MCP Spec Error Requirements

The spec defines a specific error code table:

| Status Code | Description | Usage |
|---|---|---|
| 401 | Unauthorized | Authorization required or token invalid |
| 403 | Forbidden | Invalid scopes or insufficient permissions |
| 400 | Bad Request | Malformed authorization request |

Servers MUST return these codes appropriately. 401 responses MUST include `WWW-Authenticate` with `resource_metadata`. 403 responses for insufficient scope SHOULD include `WWW-Authenticate` with `error="insufficient_scope"` and required `scope`.

### 13.1 Error Detail Leakage (MEDIUM)

**MCP Spec (Security Best Practices):**
> "Return generic messages to clients, but log detailed reasons with correlation IDs internally."

**DeepSecure:**
Several error responses include detailed internal information:
- JWT validation errors include specific claim names that are missing
- OAuth errors pass through provider error descriptions
- The catch-all exception handler returns `"An unexpected error occurred"` (good) but individual handlers are more verbose

### 13.2 Missing WWW-Authenticate in 401 and 403 Responses (CRITICAL)

As detailed in Sections 2 and 6, DeepSecure's error responses do not include the structured `WWW-Authenticate` headers that MCP clients need to initiate or step-up authorization. This is the most actionable gap — even without full OAuth implementation, adding proper headers would provide a path for future interoperability.

### 13.3 Error Code Inconsistency: `-32002` vs `-32600` for Missing Session (LOW)

`tools/call` returns `-32002` (`SESSION_INVALID`) when no agent session exists ("Call initialize first"), but `tools/list` returns `-32600` (`INVALID_REQUEST`) for the identical condition. This inconsistency means clients cannot reliably detect "session missing" errors across methods. Additionally, MCP 2026-07-28 (SEP-2164) changes `-32002` semantics for missing resources to standard `-32602`, which may cause confusion with DeepSecure's `SESSION_INVALID` usage.

### 13.4 No Correlation IDs (LOW)

The MCP endpoint supports an `X-Request-ID` header but doesn't generate one if absent. Error logs don't consistently include correlation IDs for troubleshooting.

---

## 14. Confused Deputy Problem

**MCP Spec (§Confused Deputy Problem):**
> "Attackers can exploit MCP servers acting as intermediaries to third-party APIs, leading to confused deputy vulnerabilities. By using stolen authorization codes, they can obtain access tokens without user consent."
> "MCP proxy servers using static client IDs **MUST** obtain user consent for each dynamically registered client before forwarding to third-party authorization servers (which may require additional consent)."

**MCP Spec (§Access Token Privilege Restriction):**
> "An attacker can gain unauthorized access or otherwise compromise an MCP server if the server accepts tokens issued for other resources."

The spec highlights two critical dimensions:
1. **Audience validation failures** — server doesn't verify tokens were intended for it (e.g., via `aud` claim)
2. **Token passthrough** — server accepts incorrect-audience tokens AND forwards them downstream, causing the downstream API to incorrectly trust the token

> "MCP servers **MUST** only accept tokens specifically intended for themselves and **MUST** reject tokens that do not include them in the audience claim."
> "If the MCP server makes requests to upstream APIs, the access token used at the upstream API is a separate token. The MCP server **MUST NOT** pass through the token it received from the MCP client."

**DeepSecure's Gateway acts as an MCP proxy** — it sits between agents and backend APIs (Notion, Slack, etc.). The per-user delegation model partially addresses the confused deputy:

- Users explicitly delegate specific permissions to specific agents (good)
- The delegation is tied to the user who created it via the `owner` JWT claim (good)
- RFC 8693 token exchange is used for backend tokens instead of passthrough (good)
- However, there's no per-client consent mechanism at the Gateway level if multiple MCP clients could connect via the same agent identity
- The legacy JWT fallback that disables `aud` verification directly undermines the access token privilege restriction requirement

---

## 15. Comprehensive Gap Matrix

| # | MCP Spec Requirement | RFC/Section | Spec Keyword | DeepSecure Status | Severity | Recommendation |
|---|---|---|---|---|---|---|
| 1 | Protected Resource Metadata endpoint | RFC 9728 | MUST | **Missing** | CRITICAL | Implement `/.well-known/oauth-protected-resource` (root + path) |
| 2 | `WWW-Authenticate` with `resource_metadata` on 401 | RFC 9728 §5.1 | MUST | **Missing** — bare `Bearer` only | CRITICAL | Add `resource_metadata` + `scope` to all 401 responses |
| 3 | `scope` parameter in 401 `WWW-Authenticate` | RFC 6750 §3 | SHOULD | **Missing** | HIGH | Include required scopes per resource |
| 4 | OAuth 2.1 Authorization Code + PKCE for MCP client auth | OAuth 2.1 §4.1 | MUST | **Missing** — uses Ed25519 | CRITICAL | Add OAuth AS or integrate Keycloak |
| 5 | Authorization Server Metadata (RFC 8414 + OIDC) | RFC 8414 §3.1 | MUST (both) | **Missing** | CRITICAL | Serve via Keycloak (has native OIDC) |
| 6 | AS metadata discovery priority order (path variants) | RFC 8414 §3.1, §5 | MUST | **Missing** | CRITICAL | Keycloak handles this; expose endpoints |
| 7 | `code_challenge_methods_supported` in AS metadata | MCP spec §PKCE | MUST (refuse if absent) | **Missing** — no AS metadata | CRITICAL | Keycloak must advertise this |
| 8 | Client ID Metadata Documents | IETF Draft | SHOULD | **Missing** | HIGH | Implement for standard MCP clients |
| 9 | CIMD: AS fetches URL-format `client_id`, validates match | IETF Draft §4 | MUST (if supported) | **Missing** | HIGH | Requires AS implementation |
| 10 | CIMD: SSRF protection when fetching metadata | IETF Draft §6 | SHOULD | **N/A** (not implemented) | HIGH (future) | Design SSRF protections before CIMD |
| 11 | CIMD: localhost redirect URI warnings | IETF Draft §6 | SHOULD / MUST (display) | **N/A** | MEDIUM (future) | Display redirect URI hostname in consent |
| 12 | Client registration priority order (pre-reg → CIMD → DCR → manual) | MCP spec §Client Reg | SHOULD | **Missing** | MEDIUM | Implement in DeepSecure SDK |
| 13 | Dynamic Client Registration | RFC 7591 | MAY | **Missing** | MEDIUM | Keycloak supports DCR natively |
| 14 | Resource Indicators (`resource` param) in auth + token requests | RFC 8707 | MUST | **Missing** | HIGH | Add `resource` = canonical server URI |
| 15 | Canonical URI for `resource` (HTTPS, no fragment, consistent trailing slash) | RFC 8707 §2 | MUST | **Missing** | HIGH | Define canonical URI for Gateway |
| 16 | `resource` sent regardless of AS support | RFC 8707 | MUST | **Missing** | HIGH | Always include in requests |
| 17 | Token audience validation (per RFC 8707) | RFC 8707 §2 | MUST | **Partial** — legacy bypass disables `aud` | HIGH | Remove legacy fallback |
| 18 | Token audience = canonical URI (not static string) | RFC 8707 / 9068 | MUST | **Partial** — `aud: "deeptrail-gateway"` | MEDIUM | Change to canonical URI |
| 19 | Tokens MUST NOT be in URI query string | OAuth 2.1 §5 | MUST | **Compliant** ✓ | OK | — |
| 20 | Bearer token on every HTTP request (even same session) | OAuth 2.1 §5.1.1 | MUST | **Partial** — JWT per-request, not std OAuth | MEDIUM | Standard once OAuth added |
| 21 | PKCE S256 for MCP client auth | OAuth 2.1 §4.1.1, §7.5.2 | MUST | **N/A** — no OAuth flow | CRITICAL (if OAuth added) | Reuse existing PKCE in oauth_service.py |
| 22 | Redirect URI exact matching | OAuth 2.1 §7.12 | MUST | **N/A** — no OAuth redirect | HIGH (if OAuth added) | Implement exact match |
| 23 | State parameter verification | OAuth 2.1 §7.12 | SHOULD | **Partial** — exists for backend OAuth | MEDIUM | Apply to MCP OAuth flow |
| 24 | HTTPS enforcement for all AS endpoints | OAuth 2.1 §1.5 | MUST | **Missing** (dev-only HTTP) | HIGH | Add production TLS enforcement |
| 25 | Redirect URIs: `localhost` or HTTPS | OAuth 2.1 §1.5 | MUST | **N/A** | HIGH (if OAuth added) | Validate in redirect handler |
| 26 | Scope-based access control | MCP spec §Scope | Convention | **Alternative** — custom permissions | MEDIUM | Map to OAuth scopes for interop |
| 27 | Scope selection strategy (401 scope → PRM scopes) | MCP spec §Scope Selection | SHOULD | **Missing** | MEDIUM | Implement strategy in SDK + Gateway |
| 28 | Insufficient scope challenge (403 + `insufficient_scope`) | RFC 6750 §3.1 | SHOULD | **Missing** | MEDIUM | Add structured 403 responses |
| 29 | Step-up authorization with retry limits | MCP spec §Step-Up | SHOULD | **Missing** | MEDIUM | Implement incremental auth |
| 30 | Token passthrough prevention | MCP spec §Security | MUST NOT | **Needs audit** — agent JWT in handler ctx | HIGH | Verify agent JWT never forwarded |
| 31 | Separate tokens for upstream APIs (not passthrough) | MCP spec §Access Token | MUST | **Compliant** ✓ — RFC 8693 token exchange | OK | Good — already uses token exchange |
| 32 | Short-lived access tokens | MCP spec §Token Theft | SHOULD | **Partial** — 8hr JWT TTL is long | MEDIUM | Reduce TTL, add refresh tokens |
| 33 | Refresh token rotation for public clients | OAuth 2.1 §4.3.1 | MUST | **Missing** — no refresh tokens | HIGH | Implement refresh flow |
| 34 | Token revocation | OAuth 2.1 §7.1 | Best practice | **Missing** (placeholder only) | MEDIUM | Implement revocation or short TTLs |
| 35 | Asymmetric JWT signing (RS256/EdDSA) | OAuth 2.1 best practice | SHOULD | **Missing** (HS256 shared secret) | HIGH | Migrate to RS256 with JWKS |
| 36 | Session bound to user identity | MCP Security BP | SHOULD | **Partial** | MEDIUM | Bind session keys to user ID |
| 37 | Session ID entropy | MCP Security BP | Best practice | **Reduced** (48 bits) | LOW | Use full UUID or 128+ bit random |
| 38 | CORS restrictive policy | OAuth 2.1 | Best practice | **Missing** (`allow_origins=["*"]`) | HIGH | Restrict to known client origins |
| 39 | Confused deputy: per-client consent at proxy | MCP spec §Confused Deputy | MUST | **Partial** — delegation helps | MEDIUM | Add per-client consent at Gateway |
| 40 | No credential logging | MCP Security BP | Best practice | **Not fully audited** | MEDIUM | Scrub Authorization headers from logs |
| 41 | Client credentials flow (M2M) | ext-auth extension | Optional | **Missing** | LOW | Implement for CI/CD agents |
| 42 | Enterprise-managed auth (IdP) | ext-auth extension | Optional | **Partial** — SSO exists, not ID-JAG | MEDIUM | Adapt SSO for MCP enterprise ext |
| | | | | | | |
| | **MCP 2026-07-28 RC (ships July 28)** | | | | | |
| 43 | Stateless: no `initialize` handshake | SEP-2575 | REMOVED | **Still required** — creates in-memory sessions | CRITICAL | Derive state from JWT per-request |
| 44 | Stateless: no `Mcp-Session-Id` | SEP-2567 | REMOVED | **Still used** — returned on init | CRITICAL | Remove session-id dependency |
| 45 | `Mcp-Method` + `Mcp-Name` headers required | SEP-2243 | REQUIRED | **Not implemented** | HIGH | Add header-based routing + validation |
| 46 | `MCP-Protocol-Version` header | SEP-2575 | REQUIRED | **Not implemented** | HIGH | Read version from header |
| 47 | `server/discover` method | SEP-2575 | NEW | **Not implemented** | HIGH | Implement capability endpoint |
| 48 | `ttlMs` + `cacheScope` on responses | SEP-2549 | NEW | **Not implemented** | MEDIUM | Add cache metadata |
| 49 | W3C Trace Context in `_meta` | SEP-414 | Documented | **Not implemented** | MEDIUM | Add OTel trace propagation |
| 50 | Multi Round-Trip Requests | SEP-2322 | NEW | **Not implemented** | MEDIUM | Implement `InputRequiredResult` |
| 51 | Validate `iss` on auth responses (RFC 9207) | SEP-2468 | MUST (future) | **N/A** — no OAuth | HIGH (future) | Add when implementing OAuth |
| 52 | `application_type` during DCR | SEP-837 | NEW | **N/A** | MEDIUM (future) | Include with DCR |
| 53 | Refresh tokens from OIDC AS | SEP-2207 | Documented | **Missing** | HIGH | Request `offline_access` scope |
| 54 | Scope accumulation in step-up | SEP-2350 | Clarified | **Missing** | MEDIUM | Union existing + new scopes |
| 55 | Protocol version `2026-07-28` | Lifecycle | Expected | **Missing** from version list | HIGH | Add to supported versions |
| 56 | In-memory sessions → stateless | Architecture | Pattern | **Anti-pattern** — dict-based sessions | CRITICAL | Derive from JWT per-request |
| 57 | JSON Schema 2020-12 for tools | SEP-2106 | REQUIRED | **Needs audit** | MEDIUM | Update tool schemas |
| 58 | Error code `-32002` semantics | SEP-2164 | Changed | Uses `-32002` for `SESSION_INVALID` | LOW | Review error code usage |
| 59 | `/proxy` path: agent JWT leaked on secret injection failure | MCP spec §Token Passthrough | MUST NOT | **Confirmed leak** — fail-open + preserved `Authorization` | **CRITICAL** | Make secret injection fail-closed |
| 60 | Error code inconsistency (`-32002` vs `-32600` for missing session) | JSON-RPC | Convention | `tools/call` vs `tools/list` return different codes | LOW | Unify to single code |

---

## 16. Prioritized Remediation Roadmap

### Phase 0: Quick Wins + 2026-07-28 Preparation (HIGH — 1-2 days)

**Goal:** Improve spec alignment with minimal architectural change and prepare for the July 28 deadline.

1. **Remove legacy JWT fallback** that bypasses `aud`/`iss` verification in `jwt_validation.py` — this is a single code change with immediate security benefit
2. **Restrict CORS** from `allow_origins=["*"]` to specific allowed origins
3. **Reduce JWT TTL** from 8 hours to 15-30 minutes
4. **Increase session ID entropy** from `uuid4().hex[:12]` (48 bits) to full UUID (128 bits)
5. **Enhance 401 responses** with structured `WWW-Authenticate` headers (even if pointing to non-standard auth, the structure helps clients)
6. **Add `2026-07-28` to `SUPPORTED_PROTOCOL_VERSIONS`** in `initialize.py` — version negotiation should not fail for new clients
7. **Make `/proxy` secret injection fail-closed** — if no credential can be injected for the target domain, reject the request instead of forwarding the agent JWT. This is a confirmed token passthrough vulnerability (the MCP spec says "MUST NOT pass through the token it received from the MCP client").

### Phase 0.5: Stateless Gateway Migration (CRITICAL — 1 week, deadline July 28)

**Goal:** Make the Gateway truly stateless per the 2026-07-28 protocol.

7. **Eliminate `initialize` requirement** — derive tool permissions from JWT `delegated_permissions` directly on each `tools/list` call using `PermissionMapper`. The JWT already carries all needed context.
8. **Remove `MCPSessionManager` dependency from handlers** — the `tools/call` handler should resolve credentials from JWT context per-request, not from a session lookup.
9. **Implement `server/discover` method** — expose server capabilities (tools, protocol version) via the new discovery endpoint.
10. **Add `Mcp-Method` and `Mcp-Name` header validation** — read from headers, validate against JSON-RPC body, reject on mismatch.
11. **Add `MCP-Protocol-Version` header reading** — extract version from header, route to correct handling logic (2025-11-25 legacy vs 2026-07-28 stateless).
12. **Remove `Mcp-Session-Id` from responses** — stop returning it on `initialize` (line 644 of `main.py`). For backward compatibility, accept but ignore if sent.
13. **Add `ttlMs` and `cacheScope` to `tools/list` responses** — tool lists are relatively stable; a 60-second TTL reduces client chatter.
14. **Add W3C Trace Context propagation** — read `traceparent`/`tracestate` from `_meta`, propagate to backend calls via OpenTelemetry.

### Phase 1: MCP Standard Interoperability (CRITICAL — Estimated 2-3 weeks)

**Goal:** Enable standard MCP clients to authenticate with the DeepSecure Gateway.

6. **Implement Protected Resource Metadata** (`/.well-known/oauth-protected-resource`)
   - Serve PRM document from the Gateway at both root and path-based endpoints
   - Point `authorization_servers` to Keycloak (already deployed for token exchange)
   - Define `scopes_supported` mapping DeepSecure permissions to MCP scopes
   - Include `resource` field with canonical gateway URI

7. **Configure Keycloak as MCP Authorization Server**
   - Keycloak is already in the infrastructure for RFC 8693 token exchange
   - OIDC Discovery endpoint is built-in (Keycloak provides `/.well-known/openid-configuration` natively)
   - Ensure `code_challenge_methods_supported: ["S256"]` is in AS metadata (MUST per spec)
   - Configure MCP-specific scopes and audience
   - Enable Dynamic Client Registration in Keycloak realm (optional but easy)
   - Add `client_id_metadata_document_supported: true` to AS metadata if implementing CIMD

8. **Add OAuth 2.1 Bearer Token validation to Gateway**
   - Accept both: DeepSecure proprietary JWTs AND standard OAuth access tokens from Keycloak
   - Validate Keycloak tokens via JWKS endpoint (asymmetric)
   - Map OAuth scopes to internal `delegated_permissions`
   - Validate `aud` claim matches canonical gateway URI per RFC 8707

9. **Update 401/403 responses** per spec:
   - 401: `WWW-Authenticate: Bearer resource_metadata="...", scope="..."`
   - 403: `WWW-Authenticate: Bearer error="insufficient_scope", scope="...", resource_metadata="...", error_description="..."`

10. **Implement `resource` parameter handling**
    - Define canonical URI for Gateway (e.g., `https://gateway.deepsecure.com/mcp`)
    - Validate `resource` parameter matches in token validation
    - Ensure DeepSecure SDK sends `resource` in authorization and token requests

### Phase 2: Security Hardening (HIGH — Estimated 1-2 weeks)

11. **Migrate to asymmetric JWT signing** (RS256 or EdDSA) with JWKS endpoint on Control Plane
12. **Implement refresh token flow** with rotation for public clients (MUST per OAuth 2.1)
13. **Implement token revocation** (short-lived tokens + refresh is preferred over revocation lists)
14. **Enforce HTTPS** in production configuration — both AS endpoints and redirect URIs
15. **Audit token passthrough** — ensure `request.state.agent_jwt_token` is never sent to external services
16. **Add SSRF protections** in any URL-fetching code paths (for future CIMD support)

### Phase 3: Client Registration & Scopes (MEDIUM — Estimated 1-2 weeks)

17. **Implement Client ID Metadata Documents** support:
    - AS fetches metadata from URL-format `client_id`
    - Validates `client_id` matches URL, validates redirect URIs
    - Displays client name in consent, warns for `localhost` redirects
    - Implements domain trust policies

18. **Implement scope challenge handling** (403 with `insufficient_scope` and required scopes)
19. **Add step-up authorization** flow with retry tracking in DeepSecure SDK
20. **Map DeepSecure permission model to OAuth scopes** bidirectionally
21. **Implement scope selection strategy** in SDK (401 scope → PRM scopes → request all)
22. **Add correlation IDs** to all error responses

### Phase 4: Enterprise Extensions (LOW — Future)

23. **Implement OAuth Client Credentials** extension for M2M auth
24. **Adapt SSO/IdP system** for MCP Enterprise-Managed Authorization (ID-JAG flow)
25. **Add per-client consent** mechanism at the Gateway level for confused deputy prevention
26. **Pre-registration support** for known MCP clients (VS Code, Claude Desktop)

---

## 17. What DeepSecure Does Well (Strengths)

Despite the gaps with the MCP authorization spec, DeepSecure has several strong security properties:

1. **Ed25519 Challenge-Response**: Cryptographically strong agent authentication that prevents credential theft (no static secrets transmitted)
2. **Delegation Model**: Users explicitly grant scoped permissions to agents — a principled least-privilege approach
3. **JWT Carries Full Context**: The agent JWT includes `agent_id`, `owner`, `delegated_permissions`, `delegation_id`, and `session_id` — this design is already aligned with the MCP 2026-07-28 stateless model. The `MCPSessionManager` is an implementation artifact, not an architectural necessity.
4. **Split-Key Architecture**: Secrets are split between Control Plane and Gateway, requiring both to reconstruct
5. **Backend OAuth with PKCE**: Properly implements PKCE for backend service connections (Notion, Google)
6. **RFC 8693 Token Exchange**: Uses standard token exchange for backend access tokens instead of token passthrough — this is the correct pattern per the MCP spec's "token passthrough is explicitly forbidden" rule
7. **Middleware Pipeline**: Layered security with JWT validation → Policy enforcement → Secret injection
8. **Fail-Closed Design**: Gateway denies access on any validation failure
9. **Audit Logging**: Comprehensive audit trail for security events
10. **`PermissionMapper` Already Exists**: The `PermissionMapper` class can resolve `delegated_permissions` to tool lists without needing a session — this is the key enabler for stateless `tools/list`

---

## 18. MUST vs SHOULD vs MAY Summary

Understanding the spec's normative language is critical for prioritization:

| Keyword | Meaning | Count (2025-11-25) | Count (2026-07-28 RC) | DeepSecure Compliance |
|---|---|---|---|---|
| **MUST** | Absolute requirement | ~40+ | ~50+ (including SEP changes) | ~3 of ~50+ met |
| **MUST NOT** | Absolute prohibition | ~8 | ~10 | ~5 of ~10 met |
| **SHOULD** | Recommended | ~20+ | ~25+ | ~5 of ~25+ met |
| **MAY** | Optional | ~10 | ~15 | Few applicable |
| **REMOVED** | Breaking change in 2026-07-28 | — | 2 (initialize, Mcp-Session-Id) | DeepSecure still depends on both |
| **REQUIRED** (new) | New mandatory features in 2026-07-28 | — | 3 (Mcp-Method, Mcp-Name, MCP-Protocol-Version) | None implemented |

### Key MUST Requirements DeepSecure Fails

| # | MUST Requirement | Spec Section |
|---|---|---|
| 1 | MCP servers MUST implement RFC 9728 Protected Resource Metadata | §Overview |
| 2 | MCP clients MUST use PRM for AS discovery | §Overview |
| 3 | AS MUST provide RFC 8414 or OIDC Discovery | §Overview |
| 4 | Clients MUST support both discovery mechanisms | §Overview |
| 5 | Clients MUST include `resource` param in auth and token requests | §Resource Parameter |
| 6 | Clients MUST send `resource` regardless of AS support | §Resource Parameter |
| 7 | Servers MUST validate tokens were issued for them as intended audience | §Token Handling |
| 8 | Servers MUST NOT accept or transit other tokens | §Token Handling |
| 9 | Clients MUST implement PKCE with S256 | §Authorization Code Protection |
| 10 | Clients MUST check `code_challenge_methods_supported` | §Authorization Code Protection |
| 11 | Clients MUST refuse if `code_challenge_methods_supported` absent | §Authorization Code Protection |
| 12 | AS MUST serve over HTTPS | §Communication Security |
| 13 | Redirect URIs MUST be localhost or HTTPS | §Communication Security |
| 14 | Clients MUST have redirect URIs registered | §Open Redirection |
| 15 | AS MUST validate exact redirect URIs | §Open Redirection |

### Key MUST NOT Requirements

| # | MUST NOT Requirement | DeepSecure Status |
|---|---|---|
| 1 | Tokens MUST NOT be in URI query string | ✅ Compliant |
| 2 | Servers MUST NOT accept tokens intended for other resources | ⚠️ Partial (legacy bypass) |
| 3 | Servers MUST NOT accept or transit other tokens | ✅ Compliant (token exchange) |
| 4 | Clients MUST NOT send tokens other than from the MCP server's AS | N/A (no standard OAuth) |
| 5 | Clients MUST NOT assume relationship between challenged scope and scopes_supported | N/A (no scopes) |

---

## 19. Conclusion

DeepSecure has built a **security-first platform** with strong cryptographic foundations, but it operates in a **proprietary authorization silo** that is incompatible with the MCP authorization standard. This audit identified **60 specific gaps** against the normative MCP Authorization Specification (2025-11-25) and the MCP 2026-07-28 Release Candidate, including approximately **15 MUST-level requirement failures** in the current spec, **2 CRITICAL architectural mismatches** with the incoming stateless protocol, and **1 confirmed token passthrough vulnerability** on the `/proxy` path.

### Two Urgent Deadlines

**1. MCP 2026-07-28 Ships July 28 (7 weeks away):**

The most time-sensitive finding is that the Gateway's in-memory session architecture directly contradicts the 2026-07-28 stateless protocol core. After July 28, MCP Tier 1 SDKs will stop sending `initialize` and `Mcp-Session-Id`. Clients built with these SDKs will fail against the DeepSecure Gateway.

The good news: **DeepSecure's JWT design is already aligned with statelessness.** The JWT carries `agent_id`, `owner`, `delegated_permissions`, `delegation_id`, and `session_id` — everything the `MCPSessionManager` reconstructs during `initialize`. The fix is to derive state from the JWT on each request rather than looking it up from an in-memory store. This is a refactoring, not a rebuild.

**2. OAuth 2.1 / RFC 9728 for Standard Client Interoperability:**

Any standard MCP client (VS Code, Claude Desktop, or clients built with official MCP SDKs) **cannot authenticate** with the DeepSecure Gateway. The entire OAuth 2.1 discovery → registration → authorization → token flow is absent.

### Infrastructure Building Blocks Already in Place

- **JWT carries full context** — the stateless migration is a refactoring to remove `MCPSessionManager`, not a redesign
- **Keycloak is deployed** for RFC 8693 token exchange — extending it as the MCP Authorization Server is the shortest path to OAuth compliance
- **Keycloak natively provides** OIDC Discovery, `code_challenge_methods_supported`, DCR, and JWKS
- **The Control Plane has OAuth endpoints** for backend services — PKCE, state, and redirect patterns can be reused
- **SSO/IdP integration exists** for enterprise identity providers
- **RFC 8693 token exchange** for backend access is already the correct pattern per the spec

### Immediate Actions

**Before July 28 (Phase 0 + 0.5):**
1. Remove the legacy JWT fallback (single code change, immediate security benefit)
2. Make Gateway stateless — derive tool permissions from JWT per-request, remove `MCPSessionManager` dependency
3. Add `Mcp-Method`/`Mcp-Name` header support for 2026-07-28 compatibility
4. Implement `server/discover` to replace `initialize` capability exchange
5. Add `2026-07-28` to supported protocol versions

**After July 28 (Phase 1-4):**
Address MCP OAuth 2.1 compliance via Keycloak, implement PRM endpoints, Client ID Metadata Documents, scope management, and enterprise extensions.

**Priority:** The stateless migration (Phase 0.5) has a hard deadline of July 28. The OAuth compliance work (Phase 1) is strategically important but not time-bound. Both are prerequisites for MCP ecosystem interoperability.

---

## Appendix A: References

### MCP Specification Documents
- [MCP Authorization Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) — **Primary auth spec for this audit**
- [MCP 2026-07-28 Release Candidate Blog Post](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) — **Incoming spec (ships July 28, 2026)**
- [MCP Draft Specification (2026-07-28 RC)](https://modelcontextprotocol.io/specification/draft) — Full draft spec
- [MCP Authorization Tutorial](https://modelcontextprotocol.io/docs/tutorials/security/authorization)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices)
- [MCP Authorization Extensions Repository](https://github.com/modelcontextprotocol/ext-auth)
- [Enterprise-Managed Authorization Extension](https://modelcontextprotocol.io/extensions/auth/enterprise-managed-authorization)
- [OAuth Client Credentials Extension](https://modelcontextprotocol.io/extensions/auth/oauth-client-credentials)

### MCP 2026-07-28 SEPs Referenced
- SEP-2575: Remove `initialize`/`initialized` handshake
- SEP-2567: Remove `Mcp-Session-Id` and protocol-level session
- SEP-2243: Require `Mcp-Method` and `Mcp-Name` headers
- SEP-2549: `ttlMs` and `cacheScope` for response caching
- SEP-414: W3C Trace Context propagation in `_meta`
- SEP-2322: Multi Round-Trip Requests (`InputRequiredResult`)
- SEP-2260: Server-initiated requests only during active client request
- SEP-2468: Validate `iss` on auth responses (RFC 9207)
- SEP-837: Declare `application_type` during DCR
- SEP-2352: Bind credentials to issuer
- SEP-2207: Request refresh tokens from OIDC AS
- SEP-2350: Scope accumulation during step-up
- SEP-2351: `.well-known` discovery suffix
- SEP-2106: JSON Schema 2020-12 for tools
- SEP-2164: Error code `-32002` → `-32602`

### Standards Referenced in MCP Auth Spec
- [OAuth 2.1 (draft-ietf-oauth-v2-1-13)](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13) — Core auth framework
- [RFC 8414 — OAuth 2.0 Authorization Server Metadata](https://datatracker.ietf.org/doc/html/rfc8414) — AS discovery
- [RFC 7591 — OAuth 2.0 Dynamic Client Registration](https://datatracker.ietf.org/doc/html/rfc7591) — DCR
- [RFC 9728 — OAuth 2.0 Protected Resource Metadata](https://datatracker.ietf.org/doc/html/rfc9728) — PRM (MUST implement)
- [RFC 8707 — Resource Indicators for OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc8707) — `resource` parameter
- [RFC 8693 — OAuth 2.0 Token Exchange](https://datatracker.ietf.org/doc/html/rfc8693) — Token exchange
- [RFC 6750 — OAuth 2.0 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750) — Bearer token format, §3 scope challenge
- [RFC 9068 — JSON Web Token (JWT) Profile for OAuth 2.0 Access Tokens](https://datatracker.ietf.org/doc/html/rfc9068) — `aud` claim
- [OAuth Client ID Metadata Documents (draft-00)](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-client-id-metadata-document-00) — CIMD
- [OpenID Connect Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0.html) — OIDC Discovery

### DeepSecure Implementation Files Audited

**Gateway — Deep Dive (2026-05-28 update):**
- `deeptrail-gateway/app/main.py` — Gateway entry point: MCP endpoint handler, CORS config, middleware registration, SSE stream, session termination, `Mcp-Session-Id` handling (lines 523-701)
- `deeptrail-gateway/app/mcp/session_manager.py` — In-memory `MCPSessionManager` with `_sessions` dict, `AgentMCPSession`/`BackendMCPSession` dataclasses, not thread-safe, 48-bit session IDs
- `deeptrail-gateway/app/mcp/protocol.py` — JSON-RPC 2.0 handler: `JsonRpcErrorCode.SESSION_INVALID = -32002`, `MCPMethod` enum, request routing, max 1MB request size
- `deeptrail-gateway/app/mcp/handlers/initialize.py` — `handle_initialize`: creates sessions via `session_manager.create_agent_session()`, `SUPPORTED_PROTOCOL_VERSIONS = ["2025-11-25", "2024-11-05", "2024-10-07"]`, `PermissionMapper` integration
- `deeptrail-gateway/app/mcp/handlers/tools_list.py` — `handle_tools_list`: requires agent session for tool lookup
- `deeptrail-gateway/app/mcp/handlers/tools_call.py` — `handle_tools_call`: requires session for credential resolution
- `deeptrail-gateway/app/middleware/jwt_validation.py` — JWT validation: HS256, legacy fallback (disables aud/iss), `AgentContext` extraction, bare `WWW-Authenticate: Bearer`
- `deeptrail-gateway/app/middleware/policy_enforcement.py` — Policy enforcement middleware
- `deeptrail-gateway/app/middleware/secret_injection.py` — Secret injection middleware
- `deeptrail-gateway/app/middleware/credential_injection.py` — Credential injection for backend API calls
- `deeptrail-gateway/app/security/token_exchange.py` — RFC 8693 token exchange with Keycloak

**Control Plane:**
- `deeptrail-control/app/api/v1/endpoints/agent_auth.py` — Ed25519 challenge-response authentication
- `deeptrail-control/app/api/v1/endpoints/oauth.py` — Backend OAuth endpoints (Notion, Slack, etc.)
- `deeptrail-control/app/core/security.py` — JWT creation (HS256) and Ed25519 signature verification
- `deeptrail-control/app/core/oauth_config.py` — OAuth provider configuration with PKCE
- `deeptrail-control/app/services/oauth_service.py` — OAuth service with PKCE (S256), state params
- `deeptrail-control/app/services/agent_session_service.py` — Agent session/JWT issuance service

**SDK:**
- `deepsecure/_core/identity_manager.py` — SDK identity management (Ed25519 key operations)
- `deepsecure/_core/base_client.py` — SDK base HTTP client (Authorization header handling)
