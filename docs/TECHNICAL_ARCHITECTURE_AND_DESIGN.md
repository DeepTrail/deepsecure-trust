# DeepSecure: Technical Architecture, System Design & Decision Record

> **Version:** 1.1 | **Last Updated:** June 4, 2026  
> **Audience:** Engineers, architects, investors, and technical evaluators  
> **Scope:** Complete technical architecture, design decisions, tradeoffs, and problem-solving approaches  
> **v1.1 changes:** Multi-user delegation with per-delegation JWT and round-robin execution (§5.5, §9.1, §10.1, §12.4, ADR-011)

---

## Table of Contents

1. [Problem Statement & Threat Model](#1-problem-statement--threat-model)
2. [Architectural Vision: The Virtual MCP Server](#2-architectural-vision-the-virtual-mcp-server)
3. [System Architecture](#3-system-architecture)
4. [Security Architecture](#4-security-architecture)
5. [Identity & Authentication](#5-identity--authentication)
   - [5.5 Multi-User Delegation & Round-Robin Bootstrap](#55-multi-user-delegation--round-robin-bootstrap)
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
Reality:        Gateway multiplexes across N backend services (Notion, Slack, Gmail, ...)
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
                                                  │  │   Gmail, Google)      │
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
| ~~**L1**~~ | ~~Organization Key~~ | — | — | *Never implemented — see note below* |
| **L2** | User Session JWT | DeepSecure JWT | 8 hours | User session for console/API operations |
| **L3** | Agent Session JWT | DeepSecure JWT | 8 hours | Agent session with delegated permissions |
| **L4** | Task Token JWT | DeepSecure JWT | min(deadline, 1h) | Per-task scoped permissions (narrowest) |
| **L5** | Delegation Token | Macaroon-style JWT | 7 days (configurable) | Binds user permissions to agent |

**Why is L1 missing?** The original 6-layer hierarchy defined L1 as an "Organization Key" — a platform bootstrap token for multi-tenant onboarding. It was never implemented; GCP Workload Identity (P4, May 2026) replaced it with direct OIDC attestation. L2–L5 were not renumbered because those labels are embedded across JWT claims, database comments, and code. Full history, all three numbering schemes, and a file-by-file audit of old references: [`architecture/IDENTITY_LAYER_NUMBERING_HISTORY.md`](architecture/IDENTITY_LAYER_NUMBERING_HISTORY.md).

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

| Platform | Attestation Mechanism | Verification Method | Production Status |
|----------|----------------------|---------------------|-------------------|
| **GCP** | Google Service Account OIDC identity token | Validate against Google OAuth2 certs (JWKS) | ✅ Production (all 3 agent jobs) |
| **Kubernetes** | Projected Service Account Token (SAT) | Verify against K8s API server | 🔲 Planned |
| **AWS** | IAM Role ARN | `sts:GetCallerIdentity` API call | ⚠️ Exists, security fix needed (P10) |
| **Local (MVP)** | Ed25519 key pair stored in OS keyring | Challenge-response verification | ✅ Production (SDK agents) |

#### GCP Bootstrap Flow (Production)

GCP workload-identity agents authenticate via `POST /auth/bootstrap/gcp`:

```
Cloud Run Job starts
  │
  ├── 1. Agent fetches OIDC token from GCP Metadata Server
  │      GET http://metadata.google.internal/.../identity?audience=<CONTROL_URL>
  │      → Short-lived Google-signed OIDC JWT proving SA identity
  │
  ├── 2. Agent sends OIDC token to Control Plane
  │      POST /api/v1/auth/bootstrap/gcp { "identity_token": "<oidc>" }
  │
  ├── 3. Control Plane validates:
  │      - Google OIDC signature (via JWKS)
  │      - SA email matches a registered agent's selector (1:1 mapping)
  │      - Agent is not suspended
  │
  ├── 4. Control Plane finds the newest active delegation for this agent
  │      (single delegation → single owner for JWT clarity)
  │
  └── 5. Issues Discovery JWT (L3):
         sub: <agent_id>
         owner: <delegation.delegator>
         delegation_id: <delegation.id>
         delegated_permissions: [...]
         exp: +1h
```

The Discovery JWT is scoped to one delegation's owner and permissions — not a merge of all delegations. This is a deliberate design choice (see [ADR-011](#adr-011-per-delegation-jwt-over-merged-permissions)).

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

### 5.5 Multi-User Delegation & Round-Robin Bootstrap

> **Deployed:** June 4, 2026 — all 3 production agent jobs  
> **Design:** [round-robin plan](../plans/multi-user-delegation-roundrobin_0fca7fec.plan.md), [ADR-011](#adr-011-per-delegation-jwt-over-merged-permissions)

#### The Problem: 1 JWT → 1 Owner

A single agent can receive delegations from N users (User A delegates notion+slack, User B delegates github). The original bootstrap merged all permissions into one JWT with a single `owner` claim. Since the vault resolves OAuth tokens by `owner`, the agent could only reach one user's tokens — making multi-user delegation non-functional at runtime.

#### The Solution: Per-Delegation Scoped JWTs

Instead of one merged JWT, the agent gets a separate JWT for each delegation:

```
Agent (1 workload identity)
  │
  ├── Phase 1: Bootstrap → Discovery JWT (scoped to newest delegation)
  │
  ├── Phase 2: GET /auth/agent/delegations → list all active delegations
  │     Returns: [{delegation_id, delegator, permissions, expires_at}, ...]
  │
  └── Phase 3: Round-robin loop
        │
        ├── Round 1:
        │   ├── Delegation A (User A: notion+slack)
        │   │   POST /auth/agent/delegation-token {delegation_id: A}
        │   │   → JWT: {owner: UserA, perms: [notion:*, slack:*]}
        │   │   → Configure MCP, run matching prompts
        │   │
        │   └── Delegation B (User B: github)
        │       POST /auth/agent/delegation-token {delegation_id: B}
        │       → JWT: {owner: UserB, perms: [github:*]}
        │       → Configure MCP, run matching prompts
        │
        ├── sleep(interval)
        ├── Re-fetch delegations (pick up new/dropped)
        └── Round 2: (repeat)
```

#### New Control Plane Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/v1/auth/agent/delegations` | Any Agent JWT (via `AgentIdentityDep`) | List all active, non-revoked, non-expired delegations for the calling agent |
| `POST /api/v1/auth/agent/delegation-token` | Any Agent JWT | Exchange `{delegation_id}` for a new JWT scoped to that delegation's owner and permissions; creates an `AgentSession` |

#### AgentIdentityDep

A lightweight FastAPI dependency that extracts `agent_id` from any valid Agent JWT — discovery or delegation-scoped — without requiring `owner` or full delegation claims. Used by agent-facing endpoints where the agent needs to identify itself (e.g., listing its own delegations) but doesn't need delegation-scoped authorization.

#### Smart Prompt Selection

The agent entrypoint tags each prompt with the services it requires (e.g., `"notion|Search for strategy docs"`). When cycling through a delegation, only prompts whose required services match the delegation's permissions are selected. This prevents the agent from attempting tool calls that would be denied by the gateway.

#### Resilience

- **Discovery JWT refresh:** If the discovery JWT approaches its 1h TTL (checked at 50min), the agent re-bootstraps from the GCP metadata server automatically
- **Client-side expiry check:** Delegations with `expires_at` in the past are skipped before making an API call
- **Dynamic delegation list:** Re-fetched each round to pick up newly created delegations and drop revoked ones

#### Future: Advanced Multi-User Capabilities

The round-robin approach (deployed) solves the batch agent use case. Three planned capabilities extend multi-user delegation for more advanced scenarios. Full design, implementation gaps, and architectural sketches are in [`docs/design/MULTI_USER_DELEGATION_FUTURE.md`](design/MULTI_USER_DELEGATION_FUTURE.md).

| Capability | What it enables | When to build | Key gateway change |
|------------|----------------|---------------|-------------------|
| **`_meta.user_id` Per-Call Switching** | Always-on SDK agents (Slack bots, real-time assistants) switch user context on each `tools/call` without re-bootstrapping. Agent holds one merged-permission JWT and passes `_meta: {user_id: "bob@acme.com"}` per request. | When an always-on agent (not batch) needs real-time multi-user context | Vault token fetch must use internal-auth + `X-User-ID` header instead of JWT `owner`; gateway must validate `_meta.user_id` against JWT's `authorized_users` list and enforce per-user permission maps to prevent escalation |
| **Delegation-Scoped Constraints** | Delegators control *how* their delegation is used beyond just *what* permissions are granted. Constraints like `max_calls_per_hour`, `time_window` (business hours only), `read_only`, `ip_allowlist`, and `require_approval` are evaluated per tool call. | When users request rate-limited, time-bounded, or approval-gated delegations | New `ConstraintEvaluator` stage between permission check and credential injection in the 10-stage security pipeline |
| **Cross-Delegation Prompt Orchestration** | Agent synthesizes information across multiple users' delegations — e.g., search all delegated users' Notion for strategy docs, deduplicate, post a combined summary. Requires an `isolation_mode` field (`isolated` default vs `aggregatable` admin-set) on delegations to govern cross-user data access. | When the agent needs company-wide reports or cross-user reasoning. Requires stateful agent framework (LangGraph/CrewAI, not Gemini CLI) | No gateway change; agent framework manages shared memory across delegation rounds. `isolation_mode` enforcement at entrypoint level |
| **Concurrent Multi-User Execution** | Run delegations in parallel instead of sequential round-robin — reduces wall-clock time from N*T to T for N delegations. Options: Cloud Run `--task-count=N`, async Python, or thread pool. | When a single agent has 10+ delegations and sequential execution is too slow | No gateway change; parallelism is agent-side (multiple MCP sessions with separate JWTs) |

**Dependency chain:** Round-robin (✅ deployed) → Constraints / Concurrent (independent) → `_meta.user_id` (alternative path) → Cross-delegation orchestration (requires round-robin + agent framework + isolation_mode)

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
  gmail:messages:read       → Can read Gmail messages
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
| 8 | **Backend Forwarding** | Forward to Notion/Slack/Gmail API | Handle backend errors |
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
| **Agent Auth** | `/auth/agent/challenge`, `/auth/agent/verify`, `/auth/agent/delegations`, `/auth/agent/delegation-token` | Agent Ed25519 auth, GCP bootstrap, delegation discovery, per-delegation JWT exchange |
| **Agent Bootstrap** | `/auth/bootstrap/gcp` | GCP workload identity OIDC bootstrap |
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
| `delegation_tokens` | ✅ | Persistent delegation storage (multi-user delegation grants) |
| `agent_sessions` | ✅ | Agent session tracking (created per delegation-token exchange) |
| `audit_events` | ✅ | Persistent audit trail |
| `service_registry` | ✅ | IT Admin service catalog (dynamic MCP backend registry) |
| `service_oauth_config` | ✅ | Org-level OAuth credentials per service |
| `delegation_templates` | ✅ | Admin delegation templates with permission ceilings |
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

#### Single-User Flow (Ed25519 / SDK agents)

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

#### Multi-User Flow (GCP Workload Identity / Round-Robin agents)

When an agent has delegations from multiple users, the token hierarchy adds a discovery + exchange phase:

```
GCP Metadata Server
  │
  │  OIDC identity token (Google-signed, SA email as subject)
  ▼
Discovery JWT (L3 — bootstrap)
  │  sub: agent-001
  │  owner: sarah@acme.com (newest delegation's owner)
  │  delegation_id: del-sarah-<uuid>
  │  delegated_permissions: [notion:*, slack:*]
  │  exp: +1h
  │
  │  GET /auth/agent/delegations (using Discovery JWT)
  │  → [{delegation_id: A, delegator: sarah, perms: [notion,slack], expires_at: ...},
  │     {delegation_id: B, delegator: bob, perms: [github], expires_at: ...}]
  │
  ├── POST /auth/agent/delegation-token {delegation_id: A}
  │   ▼
  │   Delegation-Scoped JWT (L3 — for Sarah)
  │     sub: agent-001
  │     owner: sarah@acme.com
  │     delegation_id: del-sarah-<uuid>
  │     delegated_permissions: [notion:pages:search, slack:channels:list, ...]
  │     session_id: asess-<new-uuid>
  │     exp: +1h
  │     → Gateway resolves Sarah's OAuth tokens from vault
  │
  └── POST /auth/agent/delegation-token {delegation_id: B}
      ▼
      Delegation-Scoped JWT (L3 — for Bob)
        sub: agent-001
        owner: bob@acme.com
        delegation_id: del-bob-<uuid>
        delegated_permissions: [github:repos:read, github:issues:list, ...]
        session_id: asess-<new-uuid>
        exp: +1h
        → Gateway resolves Bob's OAuth tokens from vault
```

**Key invariant:** Each JWT has exactly one `owner`. The vault token lookup is always unambiguous — `owner` in the JWT maps to one user's OAuth tokens. Multi-user support is achieved through multiple JWTs, not merged claims in a single token.

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

Background agents run as Cloud Run Jobs triggered by Cloud Scheduler (every 6 hours). Each job bootstraps via GCP Workload Identity, cycles through all delegated users using round-robin execution, and exits cleanly.

| Component | GCP Service | Purpose |
|-----------|-------------|---------|
| **Agent Container** | Cloud Run Job | Gemini CLI with DeepSecure MCP, round-robin entrypoint |
| **Scheduler** | Cloud Scheduler | Triggers job every 6h to keep agents "active" |
| **Identity** | GCP Service Account | 1:1 mapping to DeepSecure agent via `selector` field |
| **Secrets** | Secret Manager | `gemini-api-key` injected as env var |

#### Production Agent Jobs (June 2026)

| Job Name | Agent ID | SA Email | Schedule |
|----------|----------|----------|----------|
| `debugging-deepsecure-agent-job` | `debugging-deepsecure-agent` | `debugging-agent-sa@deepsecure-saas.iam.gserviceaccount.com` | `0 */1 * * *` |
| `engineering-audit-deepsecure-agent-job` | `engineering-audit-deepsecure-agent` | `engineering-audit-sa@deepsecure-saas.iam.gserviceaccount.com` | `0 */1 * * *` |
| `thunderbolt-deepsecure-agent-job` | `thunderbolt-deepsecure-agent` | `thunderbolt-agent-sa@deepsecure-saas.iam.gserviceaccount.com` | `0 */1 * * *` |

#### Round-Robin Execution Model

Each job run:

1. **Bootstrap** — Exchange GCP OIDC token for Discovery JWT (1 API call)
2. **Discover** — `GET /auth/agent/delegations` to list all active delegations
3. **Round-robin** — For `AGENT_MAX_ROUNDS` rounds (default 3):
   - For each delegation: exchange for scoped JWT → configure MCP → run `AGENT_PROMPTS_PER_DELEGATION` (default 2) matching prompts → next delegation
   - Sleep `AGENT_INTERVAL_SECONDS` between rounds
   - Re-fetch delegations to pick up changes
4. **Exit** — Clean exit after all rounds complete

#### Configuration (Environment Variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_MAX_ROUNDS` | `3` | Number of complete passes through all delegations |
| `AGENT_PROMPTS_PER_DELEGATION` | `2` | Max prompts run per delegation per round |
| `AGENT_INTERVAL_SECONDS` | `60` | Sleep between rounds |
| `GEMINI_MODEL` | `gemini-2.5-flash` | LLM model (Flash for 1K RPM vs Pro's 25 RPM) |

#### Deploy Scripts

| Script | Purpose |
|--------|---------|
| `infra/deploy-agent.sh` | Build + push image, create/update Cloud Run Job + Scheduler |
| `infra/build-and-push.sh` | Build + push service images (control, gateway, frontend) |
| `infra/deploy.sh` | Deploy Cloud Run services |
| `infra/migrate.sh` | Run Alembic migrations via Cloud Run Job or local proxy |

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
| Persistent Delegations/Audit (DB migration) | ✅ Done | P1 | Post-MVP |
| Delegation Validation Against Scopes (WS-K4) | ✅ Done | P1 | Post-MVP |
| GCP Cloud Run Deployment | ✅ Done | — | Production |
| Task-Scoped Tokens | ✅ Done | — | MVP |
| Gmail Backend Integration | ✅ Done | — | Phase 2 |
| SSE Streaming for Audit Events | ✅ Done | P2 | Post-MVP |
| GCP Workload Identity Bootstrap | ✅ Done | P4 | Production |
| Agent Lifecycle (4-state) | ✅ Done | P2 | Production |
| IT Admin Service Catalog | ✅ Done | P5.2 | Production |
| Audit Trail + Tool Call Analytics UI | ✅ Done | P5.1 | Production |
| **Multi-User Delegation (Round-Robin)** | ✅ Done | P5.3 | **Production (June 4, 2026)** |
| Per-Delegation Scoped JWTs | ✅ Done | P5.3 | Production |
| Smart Prompt Selection (service-tagged) | ✅ Done | P5.3 | Production |
| Multi-User UI (Fleet → Services mapping) | ⏳ Planned | P5.3 Phase 1 | Post-MVP |
| Identity Stack Panel UI | ⏳ Planned | P5.3 Phase 2 | Post-MVP |
| MCP Auth Spec Compliance (OAuth 2.1) | ⏳ Planned | P5.3 | Pre-July 2026 |
| `_meta.user_id` Per-Call Switching | 📋 Designed | Future | [MULTI_USER_DELEGATION_FUTURE §1](design/MULTI_USER_DELEGATION_FUTURE.md#1-_metauserid-per-call-switching) |
| Delegation-Scoped Constraints | 📋 Designed | Future | [MULTI_USER_DELEGATION_FUTURE §2](design/MULTI_USER_DELEGATION_FUTURE.md#2-delegation-scoped-constraints) |
| Cross-Delegation Orchestration | 📋 Designed | Future | [MULTI_USER_DELEGATION_FUTURE §3](design/MULTI_USER_DELEGATION_FUTURE.md#3-cross-delegation-prompt-orchestration) |
| Concurrent Multi-User Execution | 📋 Designed | Future | [MULTI_USER_DELEGATION_FUTURE §4](design/MULTI_USER_DELEGATION_FUTURE.md#4-concurrent-multi-user-execution) |
| PII Result Filtering | ⏳ Planned | P2 | Enterprise |
| Circuit Breakers | ⏳ Planned | P2 | Production |
| Redis Session Persistence | ⏳ Planned | P2 | Scaling |
| Prompt Injection Detection | ⏳ Planned | P2 | Security |
| Cross-Mapper Consistency Tests | ✅ Done | P1 | Quality |
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
| **ui-improvements-audit-activity** | Audit trail redesign, tool call analytics, delegation chain visualization | ✅ Complete |
| **it-admin-service-catalog-mcp-mgmt** | IT Admin service catalog, OAuth config, delegation templates, admin fleet, multi-user delegation runtime | 🔄 In Progress |

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

### ADR-011: Per-Delegation JWT Over Merged Permissions

- **Status**: Accepted (June 4, 2026)
- **Context**: When an agent has delegations from N users (User A with notion+slack, User B with github), the original bootstrap merged all permissions into a single JWT with one `owner` claim. The vault resolves OAuth tokens by `owner`, so the agent could only reach one user's tokens — making multi-user delegation non-functional at runtime despite having correct data in the database.

- **Decision**: Issue one JWT per delegation via a two-phase bootstrap:
  1. **Discovery JWT** — GCP bootstrap returns a JWT scoped to the newest delegation (not a merge). Used only to call agent-facing API endpoints (`GET /delegations`, `POST /delegation-token`).
  2. **Delegation-Scoped JWT** — Agent exchanges a `delegation_id` for a JWT with that delegation's owner and permissions. One JWT per user, rotated each round.

- **Alternatives considered**:

| Approach | Why rejected |
|----------|-------------|
| Merged JWT with `_meta.user_id` per tool call | Requires vault changes to use `_meta` instead of JWT `owner`; gateway must parse and trust client-supplied user context; increases attack surface |
| Separate MCP sessions per user | Higher complexity; gateway session manager not designed for multi-session agents |
| Single JWT, re-bootstrap per user | Requires re-authenticating to GCP metadata server per delegation; unnecessary latency |

- **Consequence**: Agent entrypoint is more complex (round-robin loop vs flat loop), but each JWT has exactly one `owner` — vault lookup is always unambiguous. Gateway required zero changes (already handles per-JWT owner correctly). New env vars `AGENT_MAX_ROUNDS` and `AGENT_PROMPTS_PER_DELEGATION` replace `AGENT_MAX_ITERATIONS`.

---

> **Document maintained by**: DeepSecure Engineering  
> **Sources**: 25 internal design markdowns, 12 top-level design docs, 7 spec documents, 4 architecture deep-dives, 13 workstream records  
> **Next review**: When architectural changes are made to any core component
