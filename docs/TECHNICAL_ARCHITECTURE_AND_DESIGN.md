# DeepSecure: Technical Architecture, System Design & Decision Record

> **Version:** 1.0 | **Last Updated:** May 27, 2026  
> **Audience:** Engineers, architects, investors, and technical evaluators  
> **Scope:** Complete technical architecture, design decisions, tradeoffs, and problem-solving approaches

---

## Table of Contents

1. [Problem Statement & Threat Model](#1-problem-statement--threat-model)
2. [Architectural Vision: The Virtual MCP Server](#2-architectural-vision-the-virtual-mcp-server)
3. [System Architecture](#3-system-architecture)
4. [Security Architecture](#4-security-architecture)
5. [Identity & Authentication](#5-identity--authentication)
6. [Permission & Authorization Model](#6-permission--authorization-model)
7. [Credential Management & Split-Key Architecture](#7-credential-management--split-key-architecture)
8. [Gateway (Data Plane) Design](#8-gateway-data-plane-design)
9. [Control Plane Design](#9-control-plane-design)
10. [Data Flow & Token Hierarchy](#10-data-flow--token-hierarchy)
11. [Frontend Architecture](#11-frontend-architecture)
12. [Deployment & Infrastructure](#12-deployment--infrastructure)
13. [Key Design Decisions & Tradeoffs](#13-key-design-decisions--tradeoffs)
14. [Problem-Solving Record](#14-problem-solving-record)
15. [Evolution & Maturity Model](#15-evolution--maturity-model)
16. [Appendix: Architecture Decision Records](#appendix-architecture-decision-records)

---

## 1. Problem Statement & Threat Model

### 1.1 The Core Problem

AI agents are being deployed with static, long-lived API keys embedded in environment variables or config files. When agents can act autonomously, delegate tasks to other agents, and handle sensitive data, this creates a new class of catastrophic security risks:

- **Credential Exfiltration**: A compromised agent exposes all API keys it holds
- **Lateral Movement**: An agent with database credentials pivots to access unrelated tables
- **Over-Privileged Tokens**: OAuth tokens granted broad scopes are stolen and used from anywhere
- **No Attribution**: When an agent acts on behalf of a user, there is no auditable chain of custody
- **No Revocation**: Static keys have no expiry; compromise is permanent until manual rotation

### 1.2 Threat Scenarios Driving the Architecture

| Scenario | Threat | Architectural Mitigation |
|----------|--------|--------------------------|
| **Rogue Trading Agent** | Compromised agent uses static brokerage API key for fraudulent trades | Gateway holds the real key; agent gets ephemeral, scoped JWT |
| **Pivoting Data Analyst** | Agent passes its database credential to a sub-agent, which pivots to unauthorized tables | Delegation tokens with monotonic attenuation; permissions can only narrow |
| **Over-Privileged OAuth** | Stolen long-lived OAuth token grants access to all Google services | Split-key architecture; no single component holds the complete secret |
| **Shadow Agent Activity** | Agent performs unauthorized actions with no visibility | Complete audit trail with human attribution on every action |

### 1.3 Design Principles

The architecture answers four fundamental security questions for every agent action:

1. **Who?** — Verifiable, unique cryptographic identity for every agent (Ed25519)
2. **What?** — Fine-grained, permission-scoped access to specific tools and resources
3. **How?** — Conditions under which access is granted (rate limits, data masking, constraints)
4. **When?** — Time-bound access through ephemeral, automatically-expiring credentials

---

## 2. Architectural Vision: The Virtual MCP Server

### 2.1 The Core Innovation

DeepSecure implements a **Virtual MCP Server** pattern — a security-aware proxy that presents itself as a single MCP (Model Context Protocol) server to AI agents, while internally aggregating, filtering, and securing access to multiple backend MCP servers.

```
Agent sees:     ONE MCP server endpoint (the Gateway)
Reality:        Gateway multiplexes across N backend services (Notion, Slack, HubSpot, ...)
Security:       Every tool call is permission-checked, credential-injected, and audit-logged
```

### 2.2 Value Propositions Proven in MVP

| Value Proposition | How MVP Demonstrates It |
|-------------------|------------------------|
| **Unified MCP Connection** | Agent connects to ONE gateway, sees tools from 2-3 backends |
| **Delegation-Based Consent** | User (Sarah) consents once in browser; agent uses her credentials safely |
| **Tool Filtering** | Agent sees only tools the user delegated (4 tools, not 37+) |
| **Namespace Resolution** | `notion.search_pages` and `slack.search` are unambiguous |
| **Audit Trail** | Every action logged as "agent-X on behalf of Sarah" |
| **Fail-Closed Security** | Agent denied when gateway can't reach control plane |

### 2.3 The "Sarah's Journey" Validation

The architecture is validated through a concrete end-to-end persona flow:

1. **Enterprise Registration** — IT admin configures IdP federation (Okta/Keycloak → DeepTrail)
2. **User Authentication** — Sarah logs in via SSO, gets User Session JWT
3. **Service Connection** — Sarah connects Notion & Slack via OAuth consent in her browser
4. **Agent Delegation** — Sarah delegates specific permissions to her SDR-Assistant agent
5. **Agent Authentication** — Agent authenticates via Ed25519 challenge-response
6. **MCP Session** — Agent connects to Virtual MCP Server, session created per backend
7. **Tool Discovery** — Agent calls `tools/list`, sees only 4 delegated tools (not 37+)
8. **Tool Execution** — Agent calls `notion.search_pages` with Sarah's credentials (injected by gateway)
9. **Permission Denial** — Agent tries `notion.create_page` → blocked (not delegated)
10. **Audit Review** — Sarah reviews complete agent activity trail in console

---

## 3. System Architecture

### 3.1 Dual-Service Architecture

The system is composed of two primary services that implement a separation of concerns between management and enforcement:

| Service | Role | Port | Technology |
|---------|------|------|------------|
| **Control Plane** (`deeptrail-control`) | Policy Decision Point (PDP) — identity, authentication, token management, policy storage, audit | 8000 (→8001 internal) | FastAPI, PostgreSQL |
| **Gateway** (`deeptrail-gateway`) | Policy Enforcement Point (PEP) — MCP protocol handling, permission filtering, credential injection | 8002 (→8001 internal) | FastAPI, Redis |

Supporting services:

| Service | Port | Purpose |
|---------|------|---------|
| **PostgreSQL** | 5434 (→5432) | Persistent storage (users, agents, delegations, connected services, audit events) |
| **Redis** | 6380 (→6379) | Session caching, rate limiting, gateway-side key storage |
| **Keycloak** | 8080 | Identity Provider for SSO (OIDC) |
| **Frontend** | 3000 | Next.js dashboard for user management |

### 3.2 Dual-Flow Architecture

The architecture implements two distinct operational flows:

#### Management Flow (Direct to Control Plane)
- **Operations**: Agent creation, policy management, authentication, credential issuance, service connection
- **Routing**: CLI/SDK/Frontend → `deeptrail-control` directly
- **Rationale**: Admin operations need immediate consistency and don't require gateway policy enforcement

#### Runtime Flow (Through Gateway)
- **Operations**: AI agent tool calls, external API access with secret injection
- **Routing**: Agent SDK → `deeptrail-gateway` → External APIs
- **Rationale**: Runtime operations require policy enforcement, credential injection, and audit logging

This separation provides:
- **Performance**: Management operations avoid gateway latency
- **Security**: Runtime operations get full policy enforcement and secret protection
- **Observability**: Complete audit trails for all agent actions
- **Scalability**: Gateway can scale independently for high-throughput agent workloads

### 3.3 Component Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USER / ADMIN                                     │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐       │
│  │   CLI    │  │  Frontend    │  │  SDK Client    │  │  Agent Code  │       │
│  └────┬─────┘  └──────┬───────┘  └───────┬────────┘  └──────┬───────┘       │
└───────┼───────────────┼──────────────────┼───────────────────┼───────────────┘
        │               │                  │                   │
        │  Management   │   Management     │  Management       │  Runtime
        │  Flow         │   Flow           │  Flow             │  Flow
        ▼               ▼                  ▼                   ▼
┌───────────────────────────────────────────────┐  ┌───────────────────────────┐
│       CONTROL PLANE (deeptrail-control)        │  │  GATEWAY (deeptrail-gw)  │
│                                                │  │                          │
│  ┌─────────────────────────────────────────┐  │  │  ┌────────────────────┐  │
│  │            API Layer (FastAPI)           │  │  │  │  MCP Endpoint      │  │
│  │  /auth/login      /auth/delegate        │  │  │  │  (/mcp)            │  │
│  │  /auth/sso/*      /auth/agent/challenge │  │  │  │                    │  │
│  │  /agents/         /auth/agent/verify    │  │  │  │  initialize        │  │
│  │  /policies/       /vault/tokens/*       │  │  │  │  tools/list        │  │
│  │  /tasks/          /audit/events         │  │  │  │  tools/call        │  │
│  │  /users/me/*      /oauth/*              │  │  │  └────────────────────┘  │
│  └─────────────────────────────────────────┘  │  │           │              │
│                      │                         │  │  ┌────────▼───────────┐  │
│  ┌───────────────────┼─────────────────────┐  │  │  │  Security Pipeline │  │
│  │                   │                      │  │  │  │  1. JWT Validation │  │
│  ▼                   ▼                      │  │  │  │  2. Fail-Closed   │  │
│  PostgreSQL     In-Memory Vault    OAuth    │  │  │  │  3. Namespace     │  │
│  (persistent)   (encrypted)        Service  │  │  │  │  4. Permission    │  │
│                                             │  │  │  │  5. Constraints   │  │
│  • users         • Fernet AES-128  • Token  │  │  │  │  6. Prompt Scan   │  │
│  • agents        • Encrypted       refresh  │  │  │  │  7. Cred Inject   │  │
│  • delegations     tokens          • OAuth  │  │  │  │  8. Backend Call   │  │
│  • connected_svc                    flow    │  │  │  │  9. PII Filter    │  │
│  • vault_tokens                             │  │  │  │  10. Audit Log    │  │
│  • audit_events                             │  │  │  └──────────────────┘  │
│  • policies                                 │  │  │           │              │
│  • tasks                                    │  │  │           ▼              │
│  • idp_sessions                             │  │  │  Backend API Clients    │
└─────────────────────────────────────────────┘  │  │  (Notion, Slack, etc.)  │
                                                  │  └───────────────────────────┘
                                                  │           │
                                                  │           ▼
                                                  │  ┌───────────────────────┐
                                                  │  │  External APIs        │
                                                  │  │  (Notion, Slack,      │
                                                  │  │   HubSpot, Google)    │
                                                  │  └───────────────────────┘
```

---

## 4. Security Architecture

### 4.1 Defense-in-Depth Model

Security is enforced at multiple layers, each independently verifiable:

| Layer | Component | Enforcement Point | What It Protects Against |
|-------|-----------|-------------------|--------------------------|
| **L1** | Cryptographic Identity (Ed25519) | Agent authentication | Agent impersonation |
| **L2** | Monotonic Attenuation | Delegation creation | Privilege escalation |
| **L3** | Permission Mapper | Gateway (every tool call) | Unauthorized tool access |
| **L4** | Credential Injection | Gateway (server-side) | Credential exposure to agents |
| **L5** | Fail-Closed Policy | Gateway (every request) | Access during outages |
| **L6** | Audit Trail | Gateway + Control Plane | Non-repudiation, forensics |

### 4.2 Fail-Closed Security

A critical architectural invariant: **if the Control Plane is unreachable, the Gateway denies ALL requests** rather than failing open. This ensures that an outage in the control plane never leads to a security failure.

```
Control Plane Status    Gateway Behavior
────────────────────    ──────────────────
Available               Normal operation: validate, enforce, audit
Unavailable             DENY all requests: -32000 "Policy service unavailable"
Recovered               Resume normal operation
```

### 4.3 Security Invariants

These invariants are maintained across the entire system:

1. **No hardcoded identity data** — `organization_id`, user email, and permissions all originate from the IdP or user actions, never from hardcoded values
2. **Monotonic attenuation** — Permissions can only narrow as they flow through each layer: OAuth scopes ⊇ delegation permissions ⊇ agent permissions ⊇ task permissions
3. **Agent never sees credentials** — OAuth tokens are resolved server-side by the Credential Injector and injected into backend requests
4. **Complete audit attribution** — Every audit event traces back to a human (`on_behalf_of`), an organization (`organization_id`), and the delegation chain
5. **Single-use challenges** — Agent authentication challenges are deleted after use, preventing replay attacks
6. **Token passthrough prevention** — Gateway MUST NOT forward agent tokens to backends (per MCP Authorization Spec)

---

## 5. Identity & Authentication

### 5.1 Identity Layer Stack

DeepSecure implements a multi-layer identity model:

| Layer | Identity Type | Token Format | Lifetime | Purpose |
|-------|---------------|-------------|----------|---------|
| **L0** | User ID-Token | OIDC JWT from IdP | ~1 hour | Proves user is who they say (from Okta/Keycloak) |
| **L2** | User Session JWT | DeepSecure JWT | 8 hours | User session for console/API operations |
| **L3** | Agent Session JWT | DeepSecure JWT | 8 hours | Agent session with delegated permissions |
| **L4** | Task Token JWT | DeepSecure JWT | min(deadline, 1h) | Per-task scoped permissions (narrowest) |
| **L5** | Delegation Token | Macaroon-style JWT | 7 days (configurable) | Binds user permissions to agent |

### 5.2 Agent Identity: Ed25519 Challenge-Response

Each agent has a persistent, verifiable cryptographic identity:

1. **Registration**: Agent is created with an Ed25519 public key registered in the Control Plane
2. **Challenge**: Agent requests a 256-bit random nonce from `/auth/agent/challenge`
3. **Signing**: Agent signs the nonce with its Ed25519 private key
4. **Verification**: Control Plane verifies the signature against the registered public key
5. **JWT Issuance**: On success, an Agent Session JWT is issued containing the agent's delegated permissions

```
Agent                              Control Plane
─────                              ─────────────
POST /auth/agent/challenge         → Returns 256-bit nonce
{ agent_id }                         Stored in _pending_challenges

Sign(nonce, private_key)           → Agent signs with Ed25519

POST /auth/agent/verify            → Verifies signature against
{ agent_id, challenge,               registered public key
  signature }                          │
                                       ▼
                                  Agent Session JWT:
                                    sub: agent-id
                                    owner: sarah@acme.com
                                    organization_id: acme-org
                                    delegated_permissions: [...]
                                    exp: <now + 8h>
```

### 5.3 Identity Bootstrapping (Attestor Model)

For Day 0 trust establishment, DeepSecure uses a pluggable Attestor Model:

| Platform | Attestation Mechanism | Verification Method |
|----------|----------------------|---------------------|
| **Kubernetes** | Projected Service Account Token (SAT) | Verify against K8s API server |
| **AWS** | IAM Role ARN | `sts:GetCallerIdentity` API call |
| **GCP** | Google Service Account identity token | Validate against Google OAuth2 certs |
| **Local (MVP)** | Ed25519 key pair stored in OS keyring | Challenge-response verification |

### 5.4 SSO Integration (IdP-Enhanced)

The platform supports enterprise SSO through OIDC:

```
Keycloak (IdP)                     Control Plane
──────────                         ─────────────
ID Token (OIDC)                    POST /api/v1/auth/sso/{idp}/callback
  ├─ sub: "sarah-uuid"
  ├─ email: "sarah@acme.com"       provision_user_from_claims()
  ├─ groups: ["acme-org"]            ├─ Maps IdP groups → roles
  └─ roles: ["user"]                 ├─ Derives organization_id
                                     └─ Returns User Session JWT
```

The `organization_id` is derived from the first IdP group membership, providing multi-tenant data isolation throughout the system.

---

## 6. Permission & Authorization Model

### 6.1 Four-Layer Permission Architecture

Permissions flow through four distinct layers, each providing a different control point:

```
Layer 1: Backend Capabilities (External)
         Notion: read_content, update_content, insert_content
         What the OAuth integration actually allows
                    │
                    ▼
Layer 2: Connected Service Scopes (DeepSecure)
         Sarah connects with: "read_content", "search"
         Self-declared by user during OAuth consent
                    │
                    ▼  ScopeMapper expands
Layer 3: Delegated Permissions (DeepSecure)
         notion:pages:search, notion:pages:read, slack:channels:list
         Fine-grained permission strings embedded in Agent JWT
                    │
                    ▼  PermissionMapper enforces
Layer 4: Tool Access (Gateway)
         notion.search_pages, notion.read_page, slack.list_channels
         Runtime enforcement at every tool call
```

### 6.2 The Two-Mapper Architecture

Two distinct mappers serve complementary purposes:

| Aspect | ScopeMapper (Control Plane) | PermissionMapper (Gateway) |
|--------|----------------------------|---------------------------|
| **Location** | `deeptrail-control/app/services/scope_mapper.py` | `deeptrail-gateway/app/mcp/permission_mapper.py` |
| **Purpose** | Validate delegation at creation time | Enforce tool access at runtime |
| **Timing** | Delegation creation (one-time) | Every tool call (hot path) |
| **Maps** | OAuth Scope → Permission strings | Tool name → Permission string |
| **Example** | `read_pages` → `["notion:pages:read", "notion:pages:search"]` | `notion.search_pages` → `notion:pages:search` |

Both mappers use the same permission string vocabulary (`<service>:<resource>:<action>`) and must stay in sync. This provides **defense in depth**: even if the ScopeMapper has a bug, the PermissionMapper still enforces at runtime.

### 6.3 Permission String Format

```
<service>:<resource>:<action>

Examples:
  notion:pages:search       → Can search Notion pages
  notion:pages:read         → Can read a specific Notion page
  slack:messages:send       → Can send Slack messages
  hubspot:contacts:update   → Can update HubSpot contacts
```

### 6.4 Monotonic Attenuation

Permissions can only narrow as they flow through the system:

```
OAuth Scopes (broadest)
  ├─ read_content → notion:pages:read, notion:pages:search, notion:databases:query, ...
  │
  ▼
Delegation (subset of user's permissions)
  ├─ notion:pages:search, notion:pages:read, slack:channels:list
  │
  ▼
Agent JWT (same as delegation)
  ├─ notion:pages:search, notion:pages:read, slack:channels:list
  │
  ▼
Task Token (narrowest — single task)
  └─ notion:pages:search only
```

A delegation can NEVER exceed the user's OAuth scopes. An agent can NEVER exceed its delegation.

### 6.5 Macaroon-Based Delegation

For agent-to-agent delegation in multi-agent workflows, DeepSecure uses Macaroons — bearer credentials that support contextual, chain-of-custody confinement:

1. **Issuance**: Control Plane issues a root macaroon to a parent agent
2. **Attenuation**: Parent agent adds caveats (restrictions) without contacting Control Plane
3. **Delegation**: Parent passes the attenuated macaroon to a child agent
4. **Verification**: Gateway verifies the macaroon chain without calling back to Control Plane

```
Senior Agent → Macaroon(finance_tasks, 30min, rate_limit:20/min)
    │
    ├── Attenuate: Add caveat "ticker_symbol = NVDA"
    │
    ▼
Junior Agent → Macaroon(finance_tasks, 30min, rate_limit:20/min, ticker=NVDA)
    │
    └── Cannot remove any caveat → Only NVDA, only finance, only 30min
```

---

## 7. Credential Management & Split-Key Architecture

### 7.1 Split-Key Secret Storage

DeepSecure employs Shamir's Secret Sharing (or deterministic XOR) to ensure no single component ever holds a complete secret:

```
Original Secret (API Key)
        │
        ▼
   Shamir Splitter
    ┌────┴────┐
    │         │
    ▼         ▼
 Share A    Share B
    │         │
    ▼         ▼
Control    Gateway
Plane      (Redis)
(Vault)
    │         │
    └────┬────┘
         │
         ▼
   JIT Reassembly
   (in memory only)
         │
         ▼
   Outbound API Call
         │
         ▼
   Memory Cleared
```

### 7.2 Credential Lifecycle

| Phase | Action | Where | Security Property |
|-------|--------|-------|-------------------|
| **Registration** | Admin registers API key via CLI/UI | Control Plane | Key split immediately; original never stored |
| **Storage** | Share A encrypted with Fernet (AES-128) | Control Plane vault | At-rest encryption |
| **Storage** | Share B stored | Gateway Redis | Isolated from Control Plane |
| **Runtime** | Gateway receives validated request | Gateway | JWT already verified |
| **Retrieval** | Gateway fetches Share A from Control Plane | Internal API call | Internal token auth |
| **Reassembly** | Shares combined in memory | Gateway (ephemeral) | JIT, never persisted |
| **Usage** | Real API key injected into outbound request | Gateway → External API | Agent never sees key |
| **Cleanup** | Reconstructed secret cleared from memory | Gateway | No persistent exposure |

### 7.3 Credential Injection Flow

The Credential Injector sits in the Gateway's security pipeline and transparently injects the real API credentials:

```
Agent calls:  tools/call("notion.search_pages", {"query": "test"})
    │
    ▼
Gateway:  Permission validated ✓
    │
    ▼
Credential Injector:
  1. Look up MCP Session → credential_ref: "vault://sarah-notion-xyz"
  2. Check token cache (60s TTL)
  3. If miss: GET /vault/tokens/notion (to Control Plane)
  4. Decrypt and resolve OAuth token
    │
    ▼
Backend Client:
  POST https://api.notion.com/v1/search
  Authorization: Bearer {sarah's-real-notion-token}
    │
    ▼
Response returned to agent (credentials stripped)
```

### 7.4 OAuth Proxy Pattern

For OAuth-protected services, the Gateway acts as a transparent OAuth proxy:

1. **Admin Setup**: OAuth `client_id` and `client_secret` registered in Control Plane
2. **User Consent**: User completes OAuth consent flow in their browser (agent never does OAuth)
3. **Token Storage**: Access token + refresh token stored in vault (encrypted)
4. **Runtime**: Gateway retrieves stored tokens, injects into backend requests
5. **Auto-Refresh**: Gateway automatically handles token refresh using refresh tokens

### 7.5 Performance Metrics

| Operation | Measured Latency | Target |
|-----------|-----------------|--------|
| JIT Secret Reassembly | ~2.1ms average | <10ms |
| Delegation Validation | ~1.8ms average | <5ms |
| Credential Cache Hit | <1ms | <5ms |
| Concurrent Operations | 100+ agents | 1000+ |

---

## 8. Gateway (Data Plane) Design

### 8.1 MCP Protocol Implementation

The Gateway implements the MCP (Model Context Protocol) specification, handling three primary JSON-RPC 2.0 methods:

| Method | Purpose | Security Checks |
|--------|---------|-----------------|
| `initialize` | Create agent MCP session, establish backend connections | JWT validation, session creation |
| `tools/list` | Return filtered list of tools agent can access | Permission filtering via delegation |
| `tools/call` | Execute a tool on a backend service | Full security pipeline (10 stages) |

### 8.2 Ten-Stage Security Pipeline

Every `tools/call` request passes through a 10-stage security pipeline:

| # | Stage | Purpose | Failure Mode |
|---|-------|---------|--------------|
| 1 | **JWT Validation** | Verify token signature, expiry, claims | Reject with 401 |
| 2 | **Fail-Closed Check** | Verify Control Plane reachability | Reject with -32000 |
| 3 | **Namespace Parsing** | Split `notion.search_pages` → backend + tool | Reject if malformed |
| 4 | **Permission Validation** | Check tool → required permission ∈ delegation | Reject with -32001 |
| 5 | **Constraint Check** | Rate limits, quotas, time bounds | Reject if violated |
| 6 | **Prompt Injection Scan** | Scan arguments for injection patterns | Block if threat=high |
| 7 | **Credential Injection** | Resolve vault ref → OAuth token, inject | Error if vault unreachable |
| 8 | **Backend Forwarding** | Forward to Notion/Slack/HubSpot API | Handle backend errors |
| 9 | **PII Result Filter** | Mask sensitive data in response (email, phone) | Pass-through in MVP |
| 10 | **Audit Log** | Log success/failure with full attribution | Async, non-blocking |

### 8.3 Tool Namespace Resolution

Backend tools are namespaced to avoid collisions when aggregating from multiple services:

```
Backend Tool Name    →    Namespaced Tool Name    →    Permission String
─────────────────         ────────────────────         ─────────────────
search_pages              notion.search_pages          notion:pages:search
read_page                 notion.read_page             notion:pages:read
search_messages           slack.search_messages        slack:messages:search
list_channels             slack.list_channels          slack:channels:list
```

### 8.4 Session Management

```
Agent Connection to Gateway
  │
  ├── AgentMCPSession (1 per agent)
  │     ├── agent_session_id     (from JWT session_id)
  │     ├── delegator            (from JWT owner)
  │     └── delegated_permissions (from JWT)
  │
  ├── BackendMCPSession: Notion (1 per connected backend)
  │     ├── mcp_session_id      (generated: mcpsess-notion-<uuid>)
  │     ├── credential_ref      (vault://sarah-notion-xyz)
  │     └── available_tools     (mapped from permissions)
  │
  └── BackendMCPSession: Slack
        ├── mcp_session_id      (generated: mcpsess-slack-<uuid>)
        ├── credential_ref      (vault://sarah-slack-abc)
        └── available_tools     (mapped from permissions)
```

### 8.5 Caching Architecture

| Cache | Location | TTL | Purpose |
|-------|----------|-----|---------|
| **Tool Cache** | Gateway in-memory | 5 minutes | Cache tool schemas to avoid repeated backend calls |
| **Credential Cache** | Credential Injector | 60 seconds | Avoid repeated vault lookups |
| **MCP Sessions** | Session Manager | Session lifetime | Track agent sessions and tools |

---

## 9. Control Plane Design

### 9.1 API Surface

The Control Plane exposes a comprehensive REST API organized by domain:

| Domain | Endpoints | Purpose |
|--------|-----------|---------|
| **Auth** | `/auth/login`, `/auth/sso/*`, `/auth/delegate` | User authentication, delegation |
| **Agent Auth** | `/auth/agent/challenge`, `/auth/agent/verify` | Agent Ed25519 authentication |
| **Agents** | `/agents/` (CRUD) | Agent lifecycle management |
| **Policies** | `/policies/` (CRUD) | Policy management |
| **Tasks** | `/tasks/` (CRUD), `/tasks/{id}/token` | Task-scoped tokens |
| **Vault** | `/vault/tokens/{svc}`, `/vault/tokens/{svc}/refresh` | Credential retrieval and refresh |
| **OAuth** | `/oauth/{serviceId}/authorize`, `/oauth/{serviceId}/callback` | OAuth consent flows |
| **Users** | `/users/me/*`, `/users/me/services/*`, `/users/me/available-permissions` | User profile, service connections |
| **Audit** | `/audit/events` | Audit log query |

### 9.2 Database Schema (16 Tables)

| Table | Migration Status | Purpose |
|-------|-----------------|---------|
| `users` | ✅ | User accounts with onboarding state |
| `agents` | ✅ | Agent identities with Ed25519 public keys |
| `credentials` | ✅ | Agent credential records |
| `secrets` | ✅ | Split-key secret storage |
| `nonces` | ✅ | Challenge-response nonces |
| `policies` | ✅ | Authorization policies |
| `attestation_policies` | ✅ | Platform attestation configs |
| `connected_services` | ✅ | User's OAuth-connected services |
| `vault_tokens` | ✅ | Encrypted token storage |
| `idp_sessions` | ✅ | SSO session tracking |
| `tasks` | ✅ | Task records for task-scoped tokens |
| `scoped_permissions` | ✅ | Per-task permission grants |
| `delegation_tokens` | ⚠️ Model exists, migration pending | Persistent delegation storage |
| `agent_sessions` | ⚠️ Model exists, migration pending | Agent session tracking |
| `audit_events` | ⚠️ Model exists, migration pending | Persistent audit trail |
| `user_sessions` | ⚠️ Model exists, deferred | User session tracking |

### 9.3 Decentralized Policy Architecture

The Control Plane acts as the PDP (Policy Decision Point) but does NOT participate in the runtime request path:

1. **PDP (Control Plane)**: Source of truth for policies — creates, updates, and signs policy documents
2. **PEP (Gateway)**: Enforces policies locally using cached, signed policy objects
3. **Sync**: Gateway periodically syncs signed policies from the Control Plane

This provides resilience: the Gateway can enforce policies even during brief Control Plane outages (for cached policies), while new policy checks fail-closed.

---

## 10. Data Flow & Token Hierarchy

### 10.1 Complete Token Flow

```
IdP (Keycloak/Okta)
  │
  │  OIDC ID Token (groups, email, roles)
  ▼
User Session JWT (L2)
  │  sub: sarah@acme.com
  │  organization_id: acme-org (from IdP groups)
  │  session_id: usess-<uuid>
  │  exp: +8h
  ▼
Delegation Token (L5)
  │  user_id: sarah@acme.com
  │  agent_id: sdr-assistant-001
  │  permissions: [notion:pages:search, notion:pages:read, ...]
  │  organization_id: acme-org
  │  constraints: {rate_limit: 100, expires_in_hours: 8}
  ▼
Agent Session JWT (L3)
  │  sub: sdr-assistant-001 (agent identity)
  │  owner: sarah@acme.com (human accountability)
  │  organization_id: acme-org (unchanged)
  │  delegated_permissions: [notion:pages:search, ...]
  │  delegation_id: del-<uuid>
  │  exp: +8h
  ▼
Task Token JWT (L4)  [optional, for per-task scoping]
  │  task_id: task-<uuid>
  │  agent_id: sdr-assistant-001
  │  owner: sarah@acme.com
  │  scoped_permissions: [notion:pages:search]  (narrowest)
  │  deadline: 2026-04-16T17:00:00Z
  │  auto_revoke_on_complete: true
  │  exp: min(deadline, now + 1h)
```

### 10.2 Organization Identity Lineage

The `organization_id` flows from the IdP through every token and into audit events:

```
IdP claims (groups[0])
  → User JWT (organization_id)
    → Delegation (organization_id)
      → Agent JWT (organization_id)
        → Task Token (organization_id)
          → Gateway AgentContext (organization_id)
            → AuditEvent (organization_id)
              → Queryable by organization in audit store
```

### 10.3 Audit Event Structure

Every action through the Gateway generates an audit event with complete attribution:

```json
{
    "event_type": "mcp_tool_call",
    "success": true,
    "agent_id": "sdr-assistant-001",
    "on_behalf_of": "sarah@acme.com",
    "organization_id": "acme-org",
    "tool": "notion.search_pages",
    "arguments": {"query": "competitor analysis"},
    "result_summary": "3 pages found",
    "delegation_id": "del-sarah-sdr-001",
    "agent_session_id": "asess-408c...",
    "mcp_session_id": "mcpsess-notion-6c9b...",
    "duration_ms": 430
}
```

---

## 11. Frontend Architecture

### 11.1 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Framework | Next.js 15 (App Router) | Server-side rendering, API routes |
| UI Components | shadcn/ui + Radix UI | Accessible, composable component library |
| Styling | Tailwind CSS | Utility-first CSS |
| State Management | React hooks + server components | Minimal client-side state |
| Authentication | NextAuth.js (Keycloak provider) | SSO session management |
| API Communication | Custom `apiClient` with proxy | Backend API proxy through Next.js API routes |

### 11.2 Dashboard Pages

| Page | Purpose | Backend Dependencies |
|------|---------|---------------------|
| `/dashboard` | Overview with agent counts, recent audit events | agents, policies, audit |
| `/dashboard/agents` | Agent CRUD management | agents API |
| `/dashboard/agents/[id]/activity` | Agent activity stream with delegation tools | agents, audit, delegation |
| `/dashboard/services` | OAuth service connection management | connected_services, OAuth flow |
| `/dashboard/delegation` | View and create delegations | delegation, available-permissions |
| `/dashboard/policies` | Policy CRUD | policies API |
| `/dashboard/audit` | Audit log viewer with filters | audit events |
| `/dashboard/vault` | Secret management | vault API |
| `/dashboard/tasks` | Task-scoped token management | tasks API |
| `/dashboard/analytics` | Usage analytics and charts | audit events (aggregated) |

### 11.3 API Proxy Architecture

The frontend proxies all API calls through Next.js API routes to avoid CORS issues and attach session tokens:

```
Frontend Component
  │
  apiClient("agents/")
  │
  ▼
/api/proxy/agents/              (Next.js API route)
  │
  Forwards: Authorization: Bearer <user-jwt>
  │
  ▼
http://localhost:8000/api/v1/agents/  (Control Plane)
```

---

## 12. Deployment & Infrastructure

### 12.1 Local Development (Docker Compose)

```yaml
services:
  db:           PostgreSQL (port 5434 → 5432)
  redis:        Redis (port 6380 → 6379)
  keycloak:     Identity Provider (port 8080)
  control:      deeptrail-control (port 8000 → 8001)
  gateway:      deeptrail-gateway (port 8002 → 8001)
  frontend:     Next.js dashboard (port 3000)
```

### 12.2 Production Deployment (GCP Cloud Run)

The production deployment targets GCP Cloud Run with Cloud SQL:

| Component | GCP Service | Configuration |
|-----------|-------------|---------------|
| Control Plane | Cloud Run | Min 1 instance, Cloud SQL connection |
| Gateway | Cloud Run | Min 1 instance, Cloud SQL connection |
| Database | Cloud SQL (PostgreSQL) | `db-f1-micro` (MVP) |
| Redis | Memorystore | Basic tier |
| Frontend | Cloud Run | Static build serving |
| Identity | Keycloak on Cloud Run | Separate Cloud SQL instance |
| DNS | Cloud DNS | `deeptrail.io` domain |
| Load Balancing | Cloud Load Balancer | HTTPS termination |
| Secrets | Google Secret Manager | Environment variable injection |

### 12.3 Infrastructure as Code

Deployment infrastructure is managed through:
- **Terraform**: GCP resource provisioning (Cloud Run, Cloud SQL, networking)
- **Docker**: Container images for all services
- **Build scripts**: `infra/build-and-push.sh` for container image builds
- **Migration scripts**: `infra/migrate.sh` for database migrations on Cloud Run

### 12.4 Background Agent Architecture (GCP)

For long-running agent workloads, the platform supports background execution:

| Component | Purpose |
|-----------|---------|
| **Agent Runner Service** | Cloud Run service that executes agent tasks |
| **Task Queue** | Cloud Tasks for async job dispatch |
| **Event Bus** | Pub/Sub for inter-service events |
| **GCP Identity Integration** | Service account → DeepSecure agent identity mapping |

---

## 13. Key Design Decisions & Tradeoffs

### 13.1 Gateway-Centric vs. Smart SDK

**Decision: Gateway-Centric Model (chosen)**

| Aspect | Smart SDK (rejected) | Gateway-Centric (chosen) |
|--------|---------------------|--------------------------|
| Security | Bypassable — agent could extract keys | Non-bypassable — gateway holds all keys |
| Language Support | Full port per language | Thin SDK per language (just auth) |
| Policy Updates | Requires agent restart | Reflected instantly for all agents |
| Operational Overhead | Lower (fewer services) | Higher (gateway service required) |
| Credential Exposure | SDK holds secrets in memory | Secrets never leave gateway |

**Rationale**: The security benefits of non-bypassable enforcement outweigh the operational complexity. A compromised agent in the Smart SDK model exposes all credentials; in the Gateway model, it exposes nothing.

### 13.2 Split-Key vs. Centralized Vault

**Decision: Split-Key Architecture (chosen)**

| Aspect | Centralized Vault | Split-Key (chosen) |
|--------|-------------------|---------------------|
| Single Point of Compromise | Yes — vault breach exposes all secrets | No — need both components |
| Latency | Single lookup | Two lookups + reassembly (~2.1ms) |
| Operational Complexity | Simpler | More complex |
| Defense in Depth | Single layer | Two layers |

**Rationale**: The ~2ms latency penalty is negligible compared to the security benefit of requiring compromise of two independent components to extract any secret.

### 13.3 Macaroons vs. Standard JWTs for Delegation

**Decision: Macaroon-style JWTs (chosen)**

| Aspect | Standard JWTs | Macaroons (chosen) |
|--------|---------------|---------------------|
| Attenuation | Not possible — fixed claims | Caveats can be added by holder |
| Delegation | Requires Control Plane roundtrip | Client-side, offline attenuation |
| Verification | Centralized or shared key | Any party with root key |
| Complexity | Simpler | More complex token structure |

**Rationale**: Multi-agent workflows require agents to delegate subsets of their authority to child agents without calling the Control Plane. Macaroons uniquely support this with cryptographic guarantees.

### 13.4 MCP vs. REST for Agent-Gateway Communication

**Decision: MCP Protocol (chosen)**

| Aspect | REST API | MCP (chosen) |
|--------|----------|--------------|
| Ecosystem Fit | Generic | Native AI agent protocol |
| Tool Discovery | Custom implementation | Built-in `tools/list` |
| Session Management | Stateless (per request) | Stateful MCP sessions |
| Framework Integration | Manual | LangChain, CrewAI, Claude native |

**Rationale**: MCP is the emerging standard for agent-to-tool communication. Building on MCP means agents can connect to DeepSecure using any MCP-compatible client without custom integration code.

### 13.5 In-Memory vs. Persistent Storage (MVP Tradeoff)

**Decision: In-memory for MVP with persistent migration path**

Several components use in-memory storage in the MVP for development velocity:

| Component | MVP Storage | Target Storage | Migration Priority |
|-----------|------------|----------------|-------------------|
| Delegations | Python dict | PostgreSQL `delegation_tokens` | P1 (data lost on restart) |
| Audit Events | Python list | PostgreSQL `audit_events` | P1 (data lost on restart) |
| Agent Sessions | Python dict | PostgreSQL `agent_sessions` | P1 |
| OAuth Tokens | In-memory vault (Fernet-encrypted) | PostgreSQL `vault_tokens` | Already migrated |
| MCP Sessions | Gateway memory | Redis | P2 (acceptable for single instance) |

**Rationale**: Moving fast for MVP validation while maintaining clear migration paths. The SQLAlchemy models already exist for all persistent tables; only Alembic migrations need to be created.

### 13.6 Token Passthrough Prevention

**Decision: Strict token isolation (per MCP Authorization Spec)**

The Gateway MUST NOT forward agent tokens to backends. Even in MVP, this is non-negotiable:

```
Agent Token → Gateway: Used ONLY for authentication/authorization
Backend Token → External API: Fetched from vault, never exposed to agent
```

**Rationale**: If agent tokens were forwarded, a compromised backend could harvest agent identities. Token isolation ensures each boundary is independently secure.

### 13.7 Fail-Closed vs. Fail-Open

**Decision: Fail-Closed (chosen)**

When the Control Plane is unreachable:
- **Fail-Open** would allow requests without policy checks (dangerous)
- **Fail-Closed** denies all requests (safe but impacts availability)

**Rationale**: For a security platform, availability is secondary to security. An outage that denies agent requests is far preferable to an outage that allows unauthorized access.

### 13.8 Intent-Based vs. Explicit Permissions

**Research Phase**: Two competing approaches were evaluated for permission architecture:

| Approach | Model | Tradeoff |
|----------|-------|----------|
| **Explicit Permissions** | `notion:pages:search` — exact string matching | Simple, predictable, but brittle when backends change |
| **Intent-Based Permissions** | `research:competitor-analysis` — task-level intents mapped to capabilities | More flexible, harder to audit, requires semantic mapping |

**Synthesis Decision**: Start with explicit permissions for MVP (auditable, debuggable), with intent-based permissions as a future layer that maps intents to explicit permission sets. The ScopeMapper already hints at this direction (scope names like `read_pages` are intent-like).

### 13.9 Open Source vs. Enterprise Split Strategy

The platform is designed with a clear open-source/enterprise boundary:

| Component | License | Rationale |
|-----------|---------|-----------|
| **SDK + CLI** | Open Source | Developer adoption, ecosystem growth |
| **Gateway (basic)** | Open Source | Core enforcement, community trust |
| **Control Plane** | Enterprise | Policy management, audit, SSO |
| **Dashboard** | Enterprise | Management UI, analytics |
| **Advanced features** | Enterprise | PII filtering, advanced policies, RBAC |

---

## 14. Problem-Solving Record

### 14.1 Tool Name Derivation Mismatch

**Problem**: The MCP `initialize` handler derived tool names by string-manipulating permission strings (`notion:pages:read` → `read_pages`), but the Permission Mapper expected singular forms (`read_page`).

**Impact**: Tools appeared invisible to agents despite being properly delegated.

**Solution**: Use `PermissionMapper.get_all_tools_for_permission()` as the single source of truth for tool name derivation instead of ad-hoc string manipulation.

**Lesson**: Never derive canonical names through string manipulation when an authoritative mapping exists.

### 14.2 In-Memory Data Loss on Container Restart

**Problem**: Delegations, audit events, and agent sessions stored in Python dicts were lost on every container restart.

**Impact**: Users had to re-create delegations; audit history was ephemeral.

**Solution**: Create Alembic migrations for the existing SQLAlchemy models (`delegation_tokens`, `agent_sessions`, `audit_events`) and update service code to persist to PostgreSQL.

**Lesson**: Even for MVPs, identify which data MUST survive restarts and persist it from day one.

### 14.3 Scope-Permission Sync Problem

**Problem**: `ScopeMapper` (Control Plane) and `PermissionMapper` (Gateway) both use the same permission string vocabulary but are maintained in separate files in separate services with no automated consistency check.

**Impact**: Adding a new permission to one mapper without updating the other causes silent mismatches.

**Solution**: 
- **Short-term**: Cross-mapper consistency test
- **Long-term**: Shared `PERMISSION_DEFINITIONS` registry from which both mappers are derived

**Lesson**: When two components share a vocabulary, enforce consistency through automated tests, not code comments.

### 14.4 OAuth Token Type Confusion

**Problem**: Different API endpoints require different token types (User Token vs. Agent JWT vs. Internal API Token). Using the wrong token type causes cryptic 401 errors.

**Impact**: Validation scripts and tests frequently failed due to token type confusion.

**Solution**: Documented comprehensive token type reference table with endpoint-to-token mapping. Login API returns `token` field (not `access_token`).

**Lesson**: Document token types and their use cases prominently. Naming inconsistencies (`token` vs `access_token`) cause significant debugging overhead.

### 14.5 MCP Gateway Requires Initialize Before Tools/Call

**Problem**: The Gateway requires an `initialize` call to establish an MCP session before any `tools/call` requests. Calling `tools/call` without initialization returns "Session not found."

**Impact**: Integration tests and demos frequently hit this error.

**Solution**: Enforce the MCP session lifecycle: `initialize` → `tools/list` (optional) → `tools/call`. Document the required sequence prominently.

**Lesson**: Stateful protocols require clear lifecycle documentation.

### 14.6 Frontend API Proxy Authentication Mismatch

**Problem**: The frontend proxies API calls with User JWT authentication, but some backend endpoints (e.g., vault) expect API key authentication.

**Impact**: Vault page returned 401 for all operations when accessed through the dashboard.

**Solution**: Update vault endpoints to accept either JWT or API key authentication, with the proxy forwarding the appropriate credential.

### 14.7 Codebase Exploration Before Breakdown

**Problem**: Task breakdowns created from design docs alone assumed ~60% of components were "missing" when they already existed in the codebase.

**Impact**: Over-scoped workstreams with tasks to create components that already existed.

**Solution**: Mandatory codebase exploration (`/explore-codebase`) before any task breakdown. Classify tasks as Create, Modify, Verify, or Skip based on actual codebase state.

**Lesson**: Design docs describe **intent**, not **current state**. Always verify claims against the codebase.

---

## 15. Evolution & Maturity Model

### 15.1 Permission Architecture Evolution

| Level | State | Description |
|-------|-------|-------------|
| **L0 (Current)** | Hardcoded static dicts | Scope and permission mappings in Python source |
| **L1 (Next)** | DB-stored computed permissions | `available_permissions` column on `connected_services` |
| **L2 (Future)** | DB-driven mapping table | Admin-editable `scope_permission_mappings` table |
| **L3 (Future)** | Shared permission registry | Single source of truth for both mappers |

### 15.2 Credential Storage Evolution

| Level | State | Description |
|-------|-------|-------------|
| **L0** | In-memory Python dict | MVP — lost on restart |
| **L1 (Current)** | PostgreSQL `vault_tokens` + Fernet | Persistent, encrypted at rest |
| **L2 (Future)** | External vault integration | HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager |
| **L3 (Future)** | HSM-backed key management | Hardware security module for key operations |

### 15.3 Gateway Scaling Evolution

| Level | State | Description |
|-------|-------|-------------|
| **L0 (Current)** | Single instance, in-memory sessions | Adequate for MVP demo |
| **L1 (Next)** | Redis-backed sessions | Horizontal scaling possible |
| **L2 (Future)** | Connection pooling + circuit breakers | Production reliability |
| **L3 (Future)** | Bloom filter optimization | Performance at 100+ tools |

### 15.4 Feature Roadmap

| Feature | Status | Priority | Scope |
|---------|--------|----------|-------|
| Core MCP Protocol (initialize, tools/list, tools/call) | ✅ Done | — | MVP |
| Ed25519 Agent Authentication | ✅ Done | — | MVP |
| Delegation with Permission Filtering | ✅ Done | — | MVP |
| Credential Injection (Notion, Slack) | ✅ Done | — | MVP |
| Audit Logging | ✅ Done (in-memory) | P1 | MVP |
| SSO via Keycloak | ✅ Done | — | MVP |
| Frontend Dashboard | ✅ Done | — | MVP |
| OAuth Service Connection Flow | ✅ Done | — | MVP |
| ScopeMapper (Scope → Permission) | ✅ Done | — | MVP |
| Persistent Delegations/Audit (DB migration) | ⏳ In Progress | P1 | Post-MVP |
| Delegation Validation Against Scopes (WS-K4) | ⏳ Spec Created | P1 | Post-MVP |
| GCP Cloud Run Deployment | ✅ Done | — | Production |
| Task-Scoped Tokens | ✅ Done | — | MVP |
| HubSpot Backend Integration | ✅ Done | — | Phase 2 |
| SSE Streaming for Audit Events | ⏳ Planned | P2 | Post-MVP |
| PII Result Filtering | ⏳ Planned | P2 | Enterprise |
| Circuit Breakers | ⏳ Planned | P2 | Production |
| Redis Session Persistence | ⏳ Planned | P2 | Scaling |
| Prompt Injection Detection | ⏳ Planned | P2 | Security |
| Cross-Mapper Consistency Tests | ⏳ Recommended | P1 | Quality |
| Intent-Based Permissions | 📋 Research | P3 | Future |
| Federated Virtual Servers | 📋 Research | P3 | Enterprise |
| Non-Python SDK Support | 📋 Planned | P3 | Ecosystem |

### 15.5 Workstreams Completed

| Workstream | Purpose | Status |
|------------|---------|--------|
| **mvp-foundation** | Core Control Plane + Gateway + E2E demo | ✅ Complete |
| **virtual-mcp-server-mvp** | Virtual MCP Server with Notion + Slack | ✅ Complete |
| **frontend-architecture** | Next.js dashboard with shadcn/ui | ✅ Complete |
| **agent-lifecycle** | Agent CRUD, activity tracking, delegation UI | ✅ Complete |
| **idp-enhanced-sso** | Keycloak SSO integration | ✅ Complete |
| **interactive-demo** | E2E demo scripts and validation | ✅ Complete |
| **p3-gcp-ux-alignment** | GCP deployment + UX improvements | ✅ Complete |
| **p4-gcp-identity-agent-registration** | GCP identity + agent registration flow | ✅ Complete |
| **gcp-background-agent** | Background agent execution on GCP | ✅ Complete |
| **idp-selector** | Multi-IdP selection UI | ✅ Complete |
| **ui-improvements-audit-activity** | Audit log viewer + agent activity improvements | ✅ Complete |
| **mvp-production-readiness** | DB persistence, cache fixes, production hardening | 🔄 In Progress |

---

## Appendix: Architecture Decision Records

### ADR-001: Control Plane / Data Plane Separation

- **Status**: Accepted
- **Context**: Need to enforce security policies on agent API calls
- **Decision**: Separate PDP (Control Plane) from PEP (Gateway)
- **Consequence**: Higher operational overhead; non-bypassable security enforcement

### ADR-002: Ed25519 for Agent Identity

- **Status**: Accepted
- **Context**: Need verifiable, persistent agent identities
- **Decision**: Use Ed25519 key pairs with challenge-response authentication
- **Consequence**: Strong cryptographic identity; future compatibility with SPIFFE, mTLS, WebAuthn

### ADR-003: MCP as Agent Communication Protocol

- **Status**: Accepted
- **Context**: Need standardized protocol for agent-to-tool communication
- **Decision**: Implement MCP (Model Context Protocol) JSON-RPC 2.0
- **Consequence**: Native compatibility with LangChain, CrewAI, Claude; stateful sessions

### ADR-004: FastAPI for Both Services

- **Status**: Accepted
- **Context**: Need high-performance async API framework with automatic documentation
- **Decision**: FastAPI with Pydantic models for both Control Plane and Gateway
- **Consequence**: Strong typing, automatic OpenAPI docs, async performance

### ADR-005: Fail-Closed Default

- **Status**: Accepted
- **Context**: Gateway behavior when Control Plane is unreachable
- **Decision**: Deny all requests (fail-closed) rather than allowing them (fail-open)
- **Consequence**: Availability impact during outages; absolute security guarantee

### ADR-006: Next.js Frontend with shadcn/ui

- **Status**: Accepted
- **Context**: Need a modern, accessible management dashboard
- **Decision**: Next.js 15 App Router with shadcn/ui component library
- **Consequence**: Server-side rendering, TypeScript safety, accessible components, API proxy through Next.js routes

### ADR-007: GCP Cloud Run for Production

- **Status**: Accepted
- **Context**: Need serverless, auto-scaling deployment for MVP
- **Decision**: GCP Cloud Run with Cloud SQL PostgreSQL
- **Consequence**: Low operational overhead, auto-scaling, pay-per-use; Cloud Run cold starts

### ADR-008: Explicit Over Intent-Based Permissions (MVP)

- **Status**: Accepted for MVP; intent-based as future layer
- **Context**: Two competing permission models evaluated
- **Decision**: Start with explicit `service:resource:action` permissions
- **Consequence**: Auditable and debuggable; more brittle when backends change; intent layer planned for future

### ADR-009: Token Passthrough Prevention

- **Status**: Accepted (non-negotiable)
- **Context**: MCP Authorization Spec requires token isolation
- **Decision**: Gateway MUST NOT forward agent tokens to backends
- **Consequence**: Separate credential resolution path; agent identity never exposed to backends

### ADR-010: Merge Point Tag Naming Convention

- **Status**: Accepted
- **Context**: Bare merge point tags collided across workstreams
- **Decision**: Tags include feature branch suffix: `{base-tag}-{feature-branch}`
- **Consequence**: Unique tags; traceability to specific workstream

---

> **Document maintained by**: DeepSecure Engineering  
> **Sources**: 25 internal design markdowns, 12 top-level design docs, 7 spec documents, 4 architecture deep-dives, 12 workstream records  
> **Next review**: When architectural changes are made to any core component
