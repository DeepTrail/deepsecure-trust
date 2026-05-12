# MCP Authorization Specification vs DeepSecure Implementation: Gap Analysis Audit

**Date:** 2026-04-30 (Updated: 2026-05-01)
**Auditor:** AI Security Audit Agent
**Scope:** MCP Authorization Spec (2025-11-25, formal normative spec) + Tutorial + Security Best Practices + Extensions vs DeepSecure (deeptrail-control, deeptrail-gateway, deepsecure SDK)
**Severity Scale:** CRITICAL | HIGH | MEDIUM | LOW | INFO
**Spec Source:** https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization

---

## Executive Summary

DeepSecure implements a **fundamentally different authorization architecture** than what the MCP Authorization specification prescribes. The MCP spec mandates **OAuth 2.1 with Protected Resource Metadata (RFC 9728)** for HTTP-based transports, where the MCP server acts as a standard OAuth 2.1 Resource Server. DeepSecure instead implements a **custom Ed25519 challenge-response authentication system** with proprietary JWT issuance via a Control Plane, where the Gateway acts as a "Virtual MCP Server."

This is not inherently wrong — the MCP spec states authorization is **OPTIONAL** — but it means DeepSecure's Gateway is **not interoperable with standard MCP clients** (like VS Code, Claude Desktop, or any client implementing the MCP auth spec). A standard MCP client connecting to the DeepSecure Gateway would fail at the first `401 Unauthorized` because it would expect a `WWW-Authenticate` header with `resource_metadata` pointing to a Protected Resource Metadata document, which DeepSecure does not serve.

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

**Recommendation:** Audit all paths where `agent_jwt_token` flows to ensure it is never sent to external services. Add explicit documentation/guardrails.

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
Uses a custom permission model with URN-like strings (`notion:pages:search`, `slack:messages:read`) stored in the JWT's `delegated_permissions` array. This is semantically richer but:

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

The Control Plane's OAuth implementation for connecting to **backend services** (Notion, Slack, HubSpot) is **well-implemented** relative to OAuth best practices:

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

### 13.3 No Correlation IDs (LOW)

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

---

## 16. Prioritized Remediation Roadmap

### Phase 0: Quick Wins (HIGH — 1-2 days)

**Goal:** Improve spec alignment with minimal architectural change.

1. **Remove legacy JWT fallback** that bypasses `aud`/`iss` verification in `jwt_validation.py` — this is a single code change with immediate security benefit
2. **Restrict CORS** from `allow_origins=["*"]` to specific allowed origins
3. **Reduce JWT TTL** from 8 hours to 15-30 minutes
4. **Increase session ID entropy** from `uuid4().hex[:12]` (48 bits) to full UUID (128 bits)
5. **Enhance 401 responses** with structured `WWW-Authenticate` headers (even if pointing to non-standard auth, the structure helps clients)

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
3. **Split-Key Architecture**: Secrets are split between Control Plane and Gateway, requiring both to reconstruct
4. **Backend OAuth with PKCE**: Properly implements PKCE for backend service connections (Notion, Google)
5. **RFC 8693 Token Exchange**: Uses standard token exchange for backend access tokens instead of token passthrough
6. **Middleware Pipeline**: Layered security with JWT validation → Policy enforcement → Secret injection
7. **Fail-Closed Design**: Gateway denies access on any validation failure
8. **Audit Logging**: Comprehensive audit trail for security events

---

## 18. MUST vs SHOULD vs MAY Summary

Understanding the spec's normative language is critical for prioritization:

| Keyword | Meaning | Count in MCP Auth Spec | DeepSecure Compliance |
|---|---|---|---|
| **MUST** | Absolute requirement | ~40+ occurrences | ~3 of ~40+ met |
| **MUST NOT** | Absolute prohibition | ~8 occurrences | ~5 of ~8 met |
| **SHOULD** | Recommended, strong reason to deviate | ~20+ occurrences | ~5 of ~20+ met |
| **MAY** | Optional | ~10 occurrences | Few applicable |

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

DeepSecure has built a **security-first platform** with strong cryptographic foundations, but it operates in a **proprietary authorization silo** that is incompatible with the MCP authorization standard. This audit identified **42 specific gaps** against the normative MCP Authorization Specification (2025-11-25), including approximately **15 MUST-level requirement failures**.

The most critical finding: any standard MCP client (VS Code, Claude Desktop, or clients built with official MCP SDKs) **cannot authenticate** with the DeepSecure Gateway. The entire OAuth 2.1 discovery → registration → authorization → token flow is absent.

The good news is that DeepSecure already has the **infrastructure building blocks** to bridge this gap:
- **Keycloak is deployed** and configured for RFC 8693 token exchange — extending it as the MCP Authorization Server is the shortest path to compliance
- **Keycloak natively provides** OIDC Discovery (`/.well-known/openid-configuration`), `code_challenge_methods_supported`, Dynamic Client Registration, and JWKS endpoints
- **The Gateway already validates Bearer JWTs** — extending validation to accept Keycloak-issued tokens alongside proprietary JWTs is incremental
- **The Control Plane has OAuth endpoints** for backend service connections — the PKCE, state, and redirect handling patterns can be reused
- **SSO/IdP integration exists** for enterprise identity providers — this maps to the enterprise-managed authorization extension
- **RFC 8693 token exchange** for backend access is already the correct pattern per the spec

The primary work is to **expose these capabilities through MCP-standard interfaces** (PRM endpoint, AS metadata, `WWW-Authenticate` headers, `resource` parameter handling) rather than building from scratch.

### Immediate Actions (Before Phase 1)

Phase 0 items require **no architectural change** and should be done immediately:
1. Remove the legacy JWT fallback (single code change, immediate security benefit)
2. Restrict CORS from `allow_origins=["*"]`
3. Reduce JWT TTL from 8 hours
4. Increase session ID entropy

**Priority:** Addressing the CRITICAL gaps in Phase 1 should be the immediate focus, as they are prerequisite for MCP ecosystem interoperability. As MCP adoption accelerates through 2026, interoperability with standard clients will transition from "nice to have" to "table stakes."

---

## Appendix A: References

### MCP Specification Documents
- [MCP Authorization Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) — **Primary source for this audit**
- [MCP Authorization Tutorial](https://modelcontextprotocol.io/docs/tutorials/security/authorization)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices)
- [MCP Authorization Extensions Repository](https://github.com/modelcontextprotocol/ext-auth)
- [Enterprise-Managed Authorization Extension](https://modelcontextprotocol.io/extensions/auth/enterprise-managed-authorization)
- [OAuth Client Credentials Extension](https://modelcontextprotocol.io/extensions/auth/oauth-client-credentials)

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
- `deeptrail-gateway/app/middleware/jwt_validation.py` — JWT validation middleware (HS256, legacy fallback)
- `deeptrail-gateway/app/middleware/security.py` — Security middleware stack
- `deeptrail-gateway/app/security/token_exchange.py` — RFC 8693 token exchange with Keycloak
- `deeptrail-gateway/app/main.py` — Gateway entry point, CORS config, middleware registration
- `deeptrail-gateway/app/mcp/session_manager.py` — In-memory MCP session management
- `deeptrail-control/app/api/v1/endpoints/agent_auth.py` — Ed25519 challenge-response authentication
- `deeptrail-control/app/api/v1/endpoints/oauth.py` — Backend OAuth endpoints (Notion, Slack, etc.)
- `deeptrail-control/app/core/security.py` — JWT creation (HS256) and Ed25519 signature verification
- `deeptrail-control/app/core/oauth_config.py` — OAuth provider configuration with PKCE
- `deeptrail-control/app/services/oauth_service.py` — OAuth service with PKCE (S256), state params
- `deeptrail-control/app/services/agent_session_service.py` — Agent session/JWT issuance service
- `deepsecure/_core/identity_manager.py` — SDK identity management (Ed25519 key operations)
- `deepsecure/_core/base_client.py` — SDK base HTTP client (Authorization header handling)
