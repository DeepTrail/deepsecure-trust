# Comprehensive Architecture vs. MVP Implementation: Coverage Matrix

> **Coverage Analysis Document** | Version 1.0 | February 2026
>
> Detailed breakdown of what the MVP implementation covers and what it does not

---

## Table of Contents

- [Part I: Token Architecture Coverage](#part-i-token-architecture-coverage)
- [Part II: MCP Gateway Coverage](#part-ii-mcp-gateway-coverage)
- [Part III: OAuth Authorization Layer Coverage](#part-iii-oauth-authorization-layer-coverage)
- [Part IV: Session Hierarchy Coverage](#part-iv-session-hierarchy-coverage)
- [Part V: Per-Task Scoped Permissions Coverage](#part-v-per-task-scoped-permissions-coverage)
- [Part VI: Audit & Security Coverage](#part-vi-audit--security-coverage)
- [Part VII: Implementation Challenges Coverage](#part-vii-implementation-challenges-coverage)
- [Use Case Coverage Analysis](#use-case-coverage-analysis)
- [Summary: What the MVP Proves](#summary-what-the-mvp-proves)
- [Critical Gaps for Production](#critical-gaps-for-production)
- [Recommended Next Steps](#recommended-next-steps)

---

## Part I: Token Architecture Coverage

The comprehensive architecture defines a **6-layer token hierarchy** with monotonic attenuation. Here's how the MVP covers each layer:

### Layer-by-Layer Coverage

| Layer | Token Type | Full Architecture | MVP Status | Coverage |
|-------|------------|-------------------|------------|----------|
| **0** | User ID-Token | Okta/Entra ID OIDC token with MFA, SSO | ❌ **Not Implemented** - Hardcoded config | 0% |
| **1** | Agent-ID Token | IdP-issued with `owner` claim binding | ❌ **Not Implemented** - No IdP | 0% |
| **2** | Delegation Token | Macaroon with cryptographic attenuation | ⚠️ **Partial** - Basic grants, no attenuation | 30% |
| **3** | Agent Session JWT | Ed25519 challenge-response, permissions embedded | ✅ **Implemented** - Working | 90% |
| **4** | Task Token | Per-task scoped, auto-revoke, specific permissions | ❌ **Not Implemented** - Session-level only | 0% |
| **5** | MCP OAuth Token | Keycloak RFC 8693 exchange, audience-bound | ❌ **Not Implemented** - Static tokens | 0% |

### Token Hierarchy: Visual Comparison

```
FULL ARCHITECTURE                          MVP IMPLEMENTATION
═══════════════════════════════════════════════════════════════════════════════

Layer 0: User ID-Token                     [NOT IMPLEMENTED]
├── Source: Okta/Entra ID OIDC             ├── Hardcoded organization config
├── Contains: sub, email, groups, mfa      ├── No user identity provider
└── Used for: Human authentication         └── Simulated in tests

         ▼                                          │
                                                    │ (skipped)
Layer 1: Agent-ID Token                             ▼
├── Source: Enterprise IdP                 [NOT IMPLEMENTED]
├── Contains: agent_id, owner claim        ├── Agent created via API directly
├── Binding: Cryptographic to user         ├── No IdP binding
└── Used for: Agent identity               └── Agent identity stored locally

         ▼                                          ▼

Layer 2: Delegation Token                  [PARTIAL IMPLEMENTATION]
├── Type: Macaroon with caveats            ├── Basic delegation grants
├── Features: Attenuation, refinement      ├── No macaroon caveats
├── Caveats: Time, scope, context          ├── Simple allowed_tools array
└── Chaining: Third-party delegation       └── No delegation chaining

         ▼                                          ▼

Layer 3: Agent Session JWT                 [FULLY IMPLEMENTED] ✅
├── Auth: Ed25519 challenge-response       ├── Ed25519 challenge-response
├── Contains: permissions, session_id      ├── permissions, session_id
├── Validation: Gateway middleware         ├── JWT validation middleware
└── Expiry: Configurable TTL               └── Configurable TTL

         ▼                                          │
                                                    │ (skipped)
Layer 4: Task Token                                 ▼
├── Scope: Per-task minimum permissions    [NOT IMPLEMENTED]
├── Features: Auto-revoke on completion    ├── Session-level permissions only
├── Request: Agent requests per task       ├── No per-task scoping
└── Grant: Control Plane evaluates         └── No dynamic scoping

         ▼                                          │
                                                    │ (skipped)
Layer 5: MCP OAuth Token                            ▼
├── Source: Keycloak token exchange        [NOT IMPLEMENTED]
├── Standard: RFC 8693                     ├── Static OAuth tokens
├── Features: Audience-bound, scoped       ├── Hardcoded in backend clients
└── Used for: Backend API calls            └── Mock implementations
```

### Layer 2 Delegation Token: Detailed Gap Analysis

| Feature | Full Architecture | MVP | Gap |
|---------|-------------------|-----|-----|
| Token Format | Macaroon with HMAC | Simple JSON struct | No cryptographic binding |
| Caveats | Time, tool, context, rate | allowed_tools array | No caveat system |
| Attenuation | Third-party can further restrict | N/A | No attenuation chain |
| Revocation | Immediate via caveat | Delete from DB | Simpler model |
| Verification | Cryptographic chain | DB lookup | Less secure |

### Layer 3 Agent Session JWT: Implementation Details

| Feature | Full Architecture | MVP | Status |
|---------|-------------------|-----|--------|
| Challenge Generation | Random nonce | ✅ Implemented | Complete |
| Ed25519 Verification | Signature check | ✅ Implemented | Complete |
| JWT Generation | HS256/RS256 | ✅ Implemented | Complete |
| Claims: agent_id | Required | ✅ Included | Complete |
| Claims: permissions | Embedded list | ✅ Included | Complete |
| Claims: delegation_id | Reference | ✅ Included | Complete |
| Claims: session_id | Unique ID | ✅ Included | Complete |
| Claims: user_id | Attribution | ✅ Included | Complete |
| Middleware Validation | Gateway intercepts | ✅ Implemented | Complete |

**Layer 3 Coverage: 90%** (missing only advanced claims like `task_context`)

---

## Part II: MCP Gateway Coverage

The Gateway is the heart of the Virtual MCP Server architecture. Here's the component-by-component coverage:

### Gateway Component Matrix

| Component | Full Architecture | MVP Implementation | Coverage |
|-----------|-------------------|-------------------|----------|
| **MCP Protocol Handler** | JSON-RPC 2.0 over HTTP, SSE | JSON-RPC 2.0 over HTTP | 80% |
| **Namespace Prefixer** | `{backend}.{tool}` format | ✅ Implemented | 95% |
| **Tool Aggregator** | Merge from N backends | ✅ Implemented | 90% |
| **Static Permission Filter** | Filter by delegation | ✅ Implemented | 90% |
| **Backend Connection Manager** | Pool, lifecycle, health | ✅ Implemented | 85% |
| **Credential Injection** | Secret substitution | ✅ Implemented | 90% |
| **Audit Logger** | All actions logged | ✅ Implemented | 90% |
| **Token Exchange Service** | RFC 8693 exchange | ❌ Not Implemented | 0% |
| **Result Filtering** | PII masking | ❌ Not Implemented | 0% |
| **Prompt Injection Detection** | Argument validation | ❌ Not Implemented | 0% |
| **Dynamic Scoping Engine** | Runtime attenuation | ❌ Not Implemented | 0% |

### MCP Protocol Handler: Detailed Coverage

| Feature | Specification | MVP | Status |
|---------|---------------|-----|--------|
| `initialize` method | Version negotiation | ✅ | Complete |
| `tools/list` method | Return available tools | ✅ | Complete |
| `tools/call` method | Execute tool | ✅ | Complete |
| `prompts/list` method | List prompts | ❌ | Not in scope |
| `prompts/get` method | Get prompt | ❌ | Not in scope |
| `resources/list` method | List resources | ❌ | Not in scope |
| `resources/read` method | Read resource | ❌ | Not in scope |
| `sampling/` methods | LLM sampling | ❌ | Not in scope |
| SSE streaming | Server-sent events | ⚠️ | Basic support |
| `Mcp-Session-Id` header | Session tracking | ✅ | Complete |
| JSON-RPC 2.0 | Request/response | ✅ | Complete |
| Batch requests | Multiple in one | ⚠️ | Partial |

**MCP Protocol Coverage: ~60%** (tools scope fully covered)

### Backend Clients: Coverage

| Backend | Full Architecture | MVP Implementation | Status |
|---------|-------------------|-------------------|--------|
| **Notion** | Real OAuth + MCP server | Mock client | ⚠️ Mock |
| **Slack** | Real OAuth + MCP server | Mock client | ⚠️ Mock |
| **HubSpot** | Real OAuth + MCP server | Mock client | ⚠️ Mock |
| **Google Calendar** | Phase 2 | Not implemented | ❌ |
| **GitHub** | Phase 2 | Not implemented | ❌ |

### Backend Client Implementation Details

```
FULL ARCHITECTURE BACKEND FLOW
══════════════════════════════════════════════════════════════════════════════

Agent Request → Gateway → Token Exchange → Real Backend MCP Server → Response
                          (RFC 8693)       (OAuth-protected)

MVP IMPLEMENTATION BACKEND FLOW
══════════════════════════════════════════════════════════════════════════════

Agent Request → Gateway → Mock Client → Synthetic Response
                          (Static token)  (Hardcoded data)
```

| Backend | Mock Tools Implemented | Sample Responses |
|---------|----------------------|------------------|
| Notion | `notion.search_pages`, `notion.create_page`, `notion.get_database` | ✅ |
| Slack | `slack.post_message`, `slack.list_channels`, `slack.read_messages` | ✅ |
| HubSpot | `hubspot.create_contact`, `hubspot.search_contacts`, `hubspot.update_deal` | ✅ |

---

## Part III: OAuth Authorization Layer Coverage

The comprehensive architecture specifies a sophisticated OAuth Authorization Layer with Keycloak integration. This is the largest gap in the MVP.

### OAuth Authorization Layer Components

| Component | Full Architecture | MVP | Coverage |
|-----------|-------------------|-----|----------|
| **OAuth 2.0 Authorization Server** | Keycloak with custom extensions | ❌ None | 0% |
| **RFC 8693 Token Exchange** | Token-for-token exchange | ❌ None | 0% |
| **PKCE Flow** | Code verifier/challenge | ❌ None | 0% |
| **Client Credentials Flow** | Service-to-service | ✅ Agent JWT | 30% |
| **Refresh Token Rotation** | Automatic refresh | ❌ None | 0% |
| **Audience-Bound Tokens** | Per-backend tokens | ❌ Static tokens | 0% |
| **Scope Management** | Dynamic scopes | ❌ Static allowed_tools | 10% |

### Keycloak Integration: Full Architecture Vision

```
FULL ARCHITECTURE OAUTH FLOW
══════════════════════════════════════════════════════════════════════════════

                    ┌───────────────────┐
                    │     Keycloak      │
                    │  (Auth Server)    │
                    ├───────────────────┤
                    │ • Custom SPI      │
                    │ • Token Exchange  │
                    │ • Delegation      │
                    └───────┬───────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ User ID-Token │   │ Agent Token   │   │ MCP OAuth     │
│ (Layer 0)     │   │ (Layer 1)     │   │ (Layer 5)     │
└───────────────┘   └───────────────┘   └───────────────┘

MVP: No Keycloak integration. Static tokens throughout.
```

### Token Exchange: What's Missing

| Exchange Type | RFC 8693 Flow | MVP Alternative |
|---------------|---------------|-----------------|
| Delegation → Agent JWT | `urn:ietf:params:oauth:grant-type:token-exchange` | Ed25519 challenge-response (works) |
| Agent JWT → Backend Token | `urn:ietf:params:oauth:grant-type:token-exchange` | Static hardcoded token (gap) |
| User Token → Delegation | Custom grant | Direct API call (works) |

---

## Part IV: Session Hierarchy Coverage

The architecture defines a three-layer session model with lazy initialization.

### Session Layers

| Layer | Session Type | Full Architecture | MVP | Coverage |
|-------|--------------|-------------------|-----|----------|
| **1** | User Session | SSO-backed, IdP refresh | DB-stored, no IdP | 40% |
| **2** | Agent Session | Ed25519 authenticated | ✅ Implemented | 85% |
| **3** | MCP Session | Per-connection state | ✅ Implemented | 80% |

### User Session: Gap Analysis

| Feature | Full Architecture | MVP | Status |
|---------|-------------------|-----|--------|
| Creation | SSO login callback | Direct API | ⚠️ Different |
| Identity binding | IdP user_id | Simulated | ⚠️ Mock |
| Connected services | Real OAuth tokens | Stored but not real | ⚠️ Mock |
| Token refresh | Background refresh | N/A | ❌ Missing |
| MFA verification | IdP enforced | N/A | ❌ Missing |

### Agent Session: Implementation Status

| Feature | Full Architecture | MVP | Status |
|---------|-------------------|-----|--------|
| Ed25519 auth | Challenge-response | ✅ | Complete |
| Session JWT | Signed, expiring | ✅ | Complete |
| Delegation binding | References delegation | ✅ | Complete |
| User attribution | user_id in JWT | ✅ | Complete |
| Permission snapshot | Embedded in JWT | ✅ | Complete |

### MCP Session: Implementation Status

| Feature | Full Architecture | MVP | Status |
|---------|-------------------|-----|--------|
| Session tracking | Mcp-Session-Id header | ✅ | Complete |
| Backend connections | Per-session pools | ✅ | Complete |
| Tool cache | Session-scoped | ✅ | Complete |
| State isolation | Per-agent separation | ✅ | Complete |

---

## Part V: Per-Task Scoped Permissions Coverage

The full architecture implements per-task permission scoping for true least privilege. This is entirely missing from the MVP.

### Task Token System

| Component | Full Architecture | MVP | Coverage |
|-----------|-------------------|-----|----------|
| **Task Token Model** | Scoped to single task | ❌ | 0% |
| **Task Lifecycle** | Create → Execute → Revoke | ❌ | 0% |
| **Permission Request** | Agent requests per task | ❌ | 0% |
| **Dynamic Scoping** | Minimum required permissions | ❌ | 0% |
| **Auto-Revocation** | On task completion | ❌ | 0% |

### Permission Model Comparison

```
FULL ARCHITECTURE: Per-Task Permissions
══════════════════════════════════════════════════════════════════════════════

Agent Delegation: [notion.*, slack.post_message]
                            │
                            ▼
Task 1: "Search Notion"    Task 2: "Post to Slack"    Task 3: "Read Slack"
├── Task Token             ├── Task Token             ├── Task Token
├── Scope: [notion.search] ├── Scope: [slack.post]    ├── Scope: [slack.read]
├── TTL: 5 minutes         ├── TTL: 5 minutes         ├── DENIED (not in delegation)
└── Auto-revoke            └── Auto-revoke            └── ──

MVP: Session-Level Permissions Only
══════════════════════════════════════════════════════════════════════════════

Agent JWT: [notion.search_pages, notion.create_page, slack.post_message]
           │
           └── All permissions available for entire session
               No per-task scoping
               No auto-revocation
```

### Why This Matters

| Risk | With Task Tokens | MVP (Without) |
|------|------------------|---------------|
| Credential exposure window | 5 minutes per task | Session lifetime |
| Blast radius of compromise | Single task | All permitted tools |
| Least privilege | True minimum | Delegation maximum |
| Audit granularity | Per-task actions | Session-level |

---

## Part VI: Audit & Security Coverage

### Audit System Coverage

| Feature | Full Architecture | MVP | Coverage |
|---------|-------------------|-----|----------|
| **Event Logging** | All tool calls | ✅ Implemented | 90% |
| **User Attribution** | delegating_user_id | ✅ Implemented | 90% |
| **Agent Attribution** | agent_id | ✅ Implemented | 90% |
| **Tool Details** | tool, params (sanitized) | ✅ Implemented | 85% |
| **Result Logging** | Success/failure, sanitized | ✅ Implemented | 80% |
| **Query API** | Filter, paginate | ✅ Implemented | 85% |
| **PII Masking** | Sensitive field redaction | ❌ Not Implemented | 0% |
| **Streaming Audit** | Real-time export | ❌ Not Implemented | 0% |
| **Compliance Reports** | SOC2, GDPR | ❌ Not Implemented | 0% |

### Security Controls Coverage

| Control | Full Architecture | MVP | Coverage |
|---------|-------------------|-----|----------|
| **Fail-Closed** | Deny on policy error | ✅ Implemented | 95% |
| **Constraint Checker** | Rate limits, quotas | ⚠️ Basic | 40% |
| **Permission Filter** | Block unpermitted tools | ✅ Implemented | 90% |
| **Credential Isolation** | Agent never sees secrets | ✅ Implemented | 90% |
| **JWT Validation** | Signature, expiry, claims | ✅ Implemented | 90% |
| **Prompt Injection Detection** | Malicious argument blocking | ❌ Not Implemented | 0% |
| **Result Filtering** | Sensitive data removal | ❌ Not Implemented | 0% |
| **DNS Rebinding Protection** | Origin header validation | ⚠️ Partial | 30% |

### Fail-Closed Implementation Details

```python
# Implemented in app/security/fail_closed.py

FAIL-CLOSED SCENARIOS (ALL IMPLEMENTED):
├── Policy service unavailable    → DENY
├── JWT validation fails          → DENY
├── Permission check fails        → DENY
├── Backend unreachable           → DENY
├── Delegation expired            → DENY
├── Unknown tool requested        → DENY
└── Any exception in auth path    → DENY
```

---

## Part VII: Implementation Challenges Coverage

The comprehensive architecture identifies key implementation challenges. Here's how the MVP addresses them:

### Connection Management

| Challenge | Full Architecture Solution | MVP Approach | Addressed? |
|-----------|---------------------------|--------------|------------|
| Backend pool sizing | Dynamic based on load | Fixed pool size | ⚠️ Partial |
| Connection lifecycle | Health checks, reconnect | Basic lifecycle | ⚠️ Partial |
| Lazy initialization | Connect on first use | Eager + lazy hybrid | ✅ Yes |
| Cross-agent isolation | Separate connections | Shared with filtering | ⚠️ Partial |

### Caching Strategy

| Challenge | Full Architecture Solution | MVP Approach | Addressed? |
|-----------|---------------------------|--------------|------------|
| Tool schema caching | TTL + event invalidation | TTL-based | ⚠️ Partial |
| Permission matrix | Precomputed, cached | Per-request lookup | ⚠️ Partial |
| Bloom filter | Fast negative lookup | N/A | ❌ No |
| Cache invalidation | Event-driven | TTL-based only | ⚠️ Partial |

### Performance Requirements

| Requirement | Full Architecture Target | MVP Status | Gap |
|-------------|-------------------------|------------|-----|
| Latency overhead | < 50ms | Not measured | Unknown |
| Concurrent agents | 1000+ | Not tested | Unknown |
| Backend connections | Pool per backend | Implemented | ✅ |
| Cache hit ratio | > 90% | Not measured | Unknown |

### Open Problems from Architecture

| Problem | Full Architecture Notes | MVP Status |
|---------|------------------------|------------|
| Streaming through virtual server | Complex governance | ❌ Not addressed |
| Cross-server transactions | SAGA pattern proposed | ❌ Not addressed |
| Tool schema evolution | Version negotiation | ❌ Not addressed |
| Federated virtual servers | Multi-org routing | ❌ Not addressed |
| Hot-reloading config | Zero-downtime changes | ❌ Not addressed |

---

## Use Case Coverage Analysis

### Use Case 1: AI Agent Vendor Integration

> *Scenario: Third-party AI agent provider (e.g., AI coding assistant) needs access to customer's enterprise tools*

| Requirement | Full Architecture | MVP | Coverage |
|-------------|-------------------|-----|----------|
| Agent identity via IdP | IdP-issued Agent-ID Token | ❌ API-registered | 20% |
| Customer-controlled delegation | Delegation with constraints | ✅ Basic delegation | 70% |
| Tool filtering | Static permission filter | ✅ Implemented | 90% |
| Credential isolation | Agent never sees tokens | ✅ Implemented | 90% |
| Audit for vendor actions | Full attribution | ✅ Implemented | 85% |
| Revocation | Immediate via IdP | ⚠️ DB delete | 50% |

**Use Case 1 Overall Coverage: ~65%**

### Use Case 2: Enterprise Agent Onboarding

> *Scenario: Enterprise IT onboards internal AI agents with existing IdP*

| Requirement | Full Architecture | MVP | Coverage |
|-------------|-------------------|-----|----------|
| SSO integration | Okta/Entra ID federation | ❌ Hardcoded | 0% |
| Agent identity in IdP | Service accounts with owner | ❌ API-only | 0% |
| Group-based policies | IdP groups → permissions | ❌ Per-delegation | 10% |
| MFA enforcement | IdP-enforced | ❌ None | 0% |
| Compliance reporting | SOC2/GDPR reports | ❌ Basic audit | 20% |
| Self-service portal | User manages delegations | ⚠️ API-only | 30% |

**Use Case 2 Overall Coverage: ~10%**

### Use Case 3: MCP Server Rollout

> *Scenario: Organization rolling out MCP to standardize agent-tool interactions*

| Requirement | Full Architecture | MVP | Coverage |
|-------------|-------------------|-----|----------|
| Protocol compliance | Full MCP spec | ⚠️ Tools scope | 60% |
| Multi-backend aggregation | N backends → 1 gateway | ✅ Implemented | 90% |
| Namespace management | Collision-free prefixing | ✅ Implemented | 95% |
| Schema caching | Performance optimization | ✅ Implemented | 80% |
| Version negotiation | MCP version handling | ✅ Implemented | 85% |
| Streaming support | SSE governance | ⚠️ Basic | 40% |

**Use Case 3 Overall Coverage: ~75%**

### Use Case Coverage Summary

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          USE CASE COVERAGE SUMMARY                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Use Case 1: AI Agent Vendor Integration                                         │
│  ████████████████████░░░░░░░░░░  65%                                             │
│  ├── Strengths: Tool filtering, credential isolation, audit                      │
│  └── Gaps: IdP integration, advanced revocation                                  │
│                                                                                  │
│  Use Case 2: Enterprise Agent Onboarding                                         │
│  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10%                                             │
│  ├── Strengths: Basic delegation exists                                          │
│  └── Gaps: No IdP, no SSO, no MFA, no group policies                             │
│                                                                                  │
│  Use Case 3: MCP Server Rollout                                                  │
│  ███████████████████████░░░░░░░  75%                                             │
│  ├── Strengths: Protocol handling, aggregation, namespacing                      │
│  └── Gaps: Full MCP spec, streaming governance                                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary: What the MVP Proves

The MVP successfully validates **6 core value propositions**:

### 1. Unified MCP Connection

> **Validated**: Single gateway handles multiple backend MCP servers

- Agent connects to one endpoint: `POST /mcp`
- Gateway aggregates tools from Notion, Slack, HubSpot
- Namespace prefixing prevents collisions

**Evidence**: `demos/demo_unified_connection.py` passes ✅

### 2. Filtered Tool Visibility

> **Validated**: Agents only see tools they're authorized to use

- Delegation specifies `allowed_tools`
- Permission filter removes unauthorized tools from `tools/list`
- 90%+ attack surface reduction possible

**Evidence**: `demos/demo_filtered_visibility.py` passes ✅

### 3. Zero Credential Exposure

> **Validated**: AI agents never see backend OAuth tokens

- Credential injection happens at gateway
- Agent JWT contains no backend secrets
- Tokens stored server-side only

**Evidence**: `demos/demo_delegation_execution.py` passes ✅

### 4. Permission Enforcement

> **Validated**: Unauthorized tool calls are blocked

- `tools/call` validates against delegation
- Fail-closed on any permission error
- Clear error messages for debugging

**Evidence**: `demos/demo_permission_enforcement.py` passes ✅

### 5. Complete Audit Trail

> **Validated**: All actions logged with user attribution

- Every tool call creates audit event
- Attribution to delegating user
- Queryable via API

**Evidence**: `demos/demo_unified_audit.py` passes ✅

### 6. Fail-Closed Security

> **Validated**: System denies all during outages

- Policy service unavailable → DENY
- Any auth error → DENY
- Exception in auth path → DENY

**Evidence**: `demos/demo_fail_closed.py` passes ✅

---

## Critical Gaps for Production

### Priority 0 (P0): Required for E2E Tests

| Gap | Description | Effort | Files Affected |
|-----|-------------|--------|----------------|
| **User Login Endpoint** | `POST /api/v1/auth/login` for human auth | S | `deeptrail-control/app/api/v1/endpoints/auth.py` |
| **Service Connection Endpoint** | `POST /api/v1/users/me/services/connect` | M | New endpoint file |
| **Test Path Fixes** | Correct endpoint paths in tests | S | `tests/e2e/test_sarah_journey.py` |

### Priority 1 (P1): Required for Demo to Real Customers

| Gap | Description | Effort | Components |
|-----|-------------|--------|------------|
| **Real Backend OAuth** | Actual Notion/Slack OAuth tokens | L | Backend clients, OAuth flow |
| **Token Refresh** | Background token refresh | M | Token manager service |
| **Error Messages** | User-friendly error responses | S | All error handlers |
| **Health Monitoring** | Backend health dashboard | M | Health check endpoints |

### Priority 2 (P2): Required for Production

| Gap | Description | Effort | Components |
|-----|-------------|--------|------------|
| **Keycloak Integration** | RFC 8693 token exchange | XL | New OAuth service |
| **Enterprise IdP** | Okta/Entra ID federation | XL | IdP integration module |
| **Task Token System** | Per-task permissions | L | New token layer |
| **Result Filtering** | PII masking | M | Response filter middleware |
| **Prompt Injection Detection** | Argument validation | M | Security middleware |
| **Macaroon Delegation** | Cryptographic attenuation | L | Delegation service rewrite |
| **Compliance Reporting** | SOC2/GDPR exports | M | Audit reporting service |

### Gap Impact Analysis

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            GAP IMPACT MATRIX                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  GAP                           │ SECURITY │ COMPLIANCE │ UX │ DEMO │ PROD │     │
│  ─────────────────────────────────────────────────────────────────────────────   │
│  No IdP integration            │   HIGH   │    HIGH    │ MED│  LOW │ HIGH │     │
│  No Keycloak                   │   HIGH   │    MED     │ LOW│  LOW │ HIGH │     │
│  No Task Tokens                │   MED    │    MED     │ LOW│  LOW │  MED │     │
│  No Result Filtering           │   MED    │    HIGH    │ LOW│  LOW │ HIGH │     │
│  Missing User Endpoints        │   LOW    │    LOW     │ HIGH│ HIGH│  MED │     │
│  Mock Backend Clients          │   LOW    │    LOW     │ MED│  MED │ HIGH │     │
│  No Prompt Injection Detection │   HIGH   │    LOW     │ LOW│  LOW │  MED │     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Recommended Next Steps

### Phase 1: Enable E2E Tests (Effort: 1-2 days)

1. **Add minimal user login endpoint**
   - `POST /api/v1/auth/login` returning mock user token
   - Store in user_session table

2. **Add service connection endpoint**
   - `POST /api/v1/users/me/services/connect`
   - Store OAuth tokens in connected_services table

3. **Fix test endpoint paths**
   - Update `tests/e2e/test_sarah_journey.py`
   - Use actual endpoint paths from implementation

### Phase 2: Real Backend Integration (Effort: 1-2 weeks)

1. **Implement real Notion OAuth flow**
   - Authorization URL generation
   - Callback handling
   - Token storage and refresh

2. **Implement real Slack OAuth flow**
   - Same as above

3. **Replace mock clients with real implementations**
   - HTTP calls to actual APIs
   - Error handling for real-world scenarios

### Phase 3: Production Hardening (Effort: 2-4 weeks)

1. **Keycloak deployment and integration**
2. **Enterprise IdP federation (Okta first)**
3. **Result filtering for PII**
4. **Prompt injection detection**
5. **Compliance reporting**

### Phase 4: Advanced Features (Effort: 4-8 weeks)

1. **Task Token system**
2. **Macaroon-based delegation**
3. **Cross-service workflows**
4. **Federated virtual servers**

---

## Coverage Summary Table

| Architecture Area | Full Scope | MVP Implemented | Coverage % |
|-------------------|------------|-----------------|------------|
| Token Hierarchy (6 layers) | All 6 layers | Layer 3 fully, Layer 2 partial | ~25% |
| MCP Gateway | Full protocol + OAuth | Tools scope only | ~70% |
| OAuth Authorization Layer | Keycloak + RFC 8693 | None | 0% |
| Session Hierarchy | User → Agent → MCP | Agent + MCP only | ~55% |
| Per-Task Permissions | Full scoping | None | 0% |
| Audit & Security | Full compliance | Basic audit + fail-closed | ~60% |
| Use Case 1 (Vendor) | Full integration | Basic flow | ~65% |
| Use Case 2 (Enterprise) | Full IdP | Almost none | ~10% |
| Use Case 3 (MCP Rollout) | Full spec | Tools scope | ~75% |

### Overall MVP Coverage: **~40%** of comprehensive architecture

The MVP strategically implements the most demonstrable components (Gateway, tool aggregation, basic auth) while deferring complex enterprise features (IdP, Keycloak, Task Tokens) that require significant infrastructure.

---

*Document generated: February 2026*
*Based on: deepsecure-comprehensive-architecture-consolidated.md, deepsecure-virtual-mcp-server-mvp.md, deepsecure-virtual-mcp-server-use-cases.md, and codebase analysis*
