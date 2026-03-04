# DeepSecure Product Features

> **Comprehensive Feature List** | Version 1.0 | February 2026
>
> DeepSecure provides Identity-as-Code for AI agents, enabling them to fetch their own ephemeral credentials programmatically instead of using static API keys.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Architecture](#2-core-architecture)
3. [Identity & Authentication](#3-identity--authentication)
4. [Authorization & Delegation](#4-authorization--delegation)
5. [Virtual MCP Server (Gateway)](#5-virtual-mcp-server-gateway)
6. [Credential Management](#6-credential-management)
7. [Policy Engine](#7-policy-engine)
8. [Audit & Compliance](#8-audit--compliance)
9. [Security Features](#9-security-features)
10. [Developer Experience](#10-developer-experience)
11. [Enterprise Features](#11-enterprise-features)
12. [Integration Capabilities](#12-integration-capabilities)

---

## 1. Executive Summary

DeepSecure is a security platform designed to solve critical challenges in AI agent deployments:

| Challenge | DeepSecure Solution |
|-----------|---------------------|
| Static API keys exposure | Ephemeral, time-bounded credentials |
| Over-privileged access | Fine-grained, delegated permissions |
| No accountability | Full audit trail with human attribution |
| Credential sprawl | Centralized secret management with split-key architecture |
| N×M integration complexity | Single Virtual MCP Server gateway |

---

## 2. Core Architecture

### 2.1 Dual-Service Architecture

DeepSecure implements a separation between the Control Plane and Data Plane for optimal security and scalability.

| Component | Service | Purpose |
|-----------|---------|---------|
| **Control Plane** | `deeptrail-control` | Policy Decision Point (PDP) - manages identities, policies, credentials, and audit |
| **Data Plane** | `deeptrail-gateway` | Policy Enforcement Point (PEP) - enforces policies, injects credentials, proxies requests |

### 2.2 Dual-Flow Architecture

| Flow Type | Routing | Operations |
|-----------|---------|------------|
| **Management Flow** | Direct to Control Plane | Agent creation, authentication, policy management, credential issuance |
| **Runtime Flow** | Through Gateway | Tool calls, API access, secret injection, policy enforcement |

### 2.3 Component Stack

```
┌──────────────────────────────────────────────────────────────┐
│                     Developer / Admin                         │
│   DeepTrail CLI    │    DeepSecure SDK    │    Console UI    │
├──────────────────────────────────────────────────────────────┤
│                      AI Agent Runtime                         │
│               Agent Code + DeepSecure SDK                     │
├──────────────────────────────────────────────────────────────┤
│                      Control Plane                            │
│   Identity Manager  │  Policy Engine  │  Token Vault         │
│   Delegation Service│  Audit Logger   │  Session Manager     │
├──────────────────────────────────────────────────────────────┤
│                       Data Plane                              │
│   MCP Protocol Handler  │  Permission Filter  │  Audit MW    │
│   Credential Injector   │  Backend Adapter    │  Tool Cache  │
├──────────────────────────────────────────────────────────────┤
│                    External Services                          │
│         Notion   │   Slack   │   HubSpot   │   Custom APIs   │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Identity & Authentication

### 3.1 User Identity

| Feature | Description |
|---------|-------------|
| **SSO Integration** | Enterprise IdP support (Okta, Azure AD, Google Workspace) |
| **User Sessions** | Time-bounded sessions (8 hours default) with JWT tokens |
| **Organization Registry** | Multi-tenant organization support with domain-based routing |
| **Group/Role Mapping** | IdP groups mapped to DeepSecure roles and permissions |

### 3.2 Agent Identity

| Feature | Description |
|---------|-------------|
| **Ed25519 Key Pairs** | Cryptographic identity with long-term key pairs |
| **Challenge-Response Auth** | Secure agent authentication via signed nonce challenges |
| **Agent Registration** | Programmatic agent creation with public key registration |
| **Identity Bootstrapping** | Pluggable attestors (Kubernetes, AWS IAM, GCP Service Accounts) |

### 3.3 Authentication Flows

| Flow | Mechanism | Use Case |
|------|-----------|----------|
| **User Login** | OAuth 2.0 / OIDC with IdP | Human user access to console |
| **Agent Challenge-Response** | Ed25519 signature verification | Agent runtime authentication |
| **Service Connection** | OAuth 2.0 with PKCE | User connecting external services |
| **Inter-Service Auth** | JWT + Internal API Token | Control Plane ↔ Gateway communication |

---

## 4. Authorization & Delegation

### 4.1 Delegation Model

| Feature | Description |
|---------|-------------|
| **User-to-Agent Delegation** | Users delegate specific permissions to agents |
| **Agent-to-Agent Delegation** | Agents can create attenuated delegations to sub-agents |
| **Monotonic Attenuation** | Delegations can only narrow permissions, never widen |
| **Time-Bounded Tokens** | All delegations have configurable expiration (hours to days) |

### 4.2 Macaroon-Based Delegation Tokens

| Feature | Description |
|---------|-------------|
| **Cryptographic Signatures** | Macaroons with tamper-proof signatures |
| **Caveat-Based Constraints** | Embedded restrictions (time, permissions, resources) |
| **Offline Verification** | Gateway can verify without Control Plane roundtrip |
| **Delegation Chains** | Full audit trail of delegation hierarchy |

### 4.3 Permission Model

| Level | Description |
|-------|-------------|
| **Service Scopes** | OAuth scopes from connected services (e.g., `read_pages`, `search`) |
| **DeepSecure Permissions** | Fine-grained permissions (e.g., `notion:pages:read`, `slack:messages:send`) |
| **Tool Permissions** | Tool-level access control (e.g., `notion.search_pages`) |

### 4.4 Scope-to-Permission Mapping

| Feature | Description |
|---------|-------------|
| **ScopeMapper** | Maps broad OAuth scopes to fine-grained DeepSecure permissions |
| **Permission Validation** | Validates requested permissions against user's connected scopes |
| **Available Permissions API** | Endpoint to discover what permissions user can delegate |

---

## 5. Virtual MCP Server (Gateway)

### 5.1 MCP Protocol Support

| Feature | Description |
|---------|-------------|
| **JSON-RPC 2.0** | Full MCP protocol compliance |
| **initialize** | MCP session handshake with capabilities negotiation |
| **tools/list** | Filtered tool discovery based on agent permissions |
| **tools/call** | Tool execution with credential injection |

### 5.2 Tool Aggregation

| Feature | Description |
|---------|-------------|
| **Multi-Backend Support** | Aggregate tools from multiple MCP servers (Notion, Slack, HubSpot, etc.) |
| **Namespace Prefixing** | Automatic tool namespacing (`notion.search_pages`, `slack.send_message`) |
| **Tool Caching** | Cached tool definitions with invalidation |
| **Schema Passthrough** | Tool input schemas preserved for client validation |

### 5.3 Permission Filtering

| Feature | Description |
|---------|-------------|
| **Delegation-Based Filtering** | Agent sees only tools they have permission to use |
| **Real-Time Filtering** | `tools/list` filters based on current delegation state |
| **Permission-to-Tool Mapping** | Maps DeepSecure permissions to backend tool names |

### 5.4 Request Handling

| Feature | Description |
|---------|-------------|
| **Namespace Resolution** | Parse `backend.tool` to route to correct backend |
| **Permission Enforcement** | Validate permission before forwarding |
| **Credential Injection** | Inject user's OAuth token into backend request |
| **Response Passthrough** | Return backend response to agent |

---

## 6. Credential Management

### 6.1 Token Vault

| Feature | Description |
|---------|-------------|
| **Encrypted Storage** | OAuth tokens stored encrypted in PostgreSQL |
| **Token References** | Vault URIs (`vault://sarah-notion-oauth-xyz`) instead of raw tokens |
| **Automatic Refresh** | OAuth token refresh handling (future) |
| **Token Expiration Tracking** | Track and manage token lifecycles |

### 6.2 Split-Key Architecture

| Feature | Description |
|---------|-------------|
| **Shamir Secret Sharing** | Secrets split into multiple shares |
| **Distributed Storage** | Share 1 in Control Plane, Share 2 in Gateway Redis |
| **JIT Reassembly** | Secrets reassembled just-in-time for API calls |
| **Memory Clearing** | Secrets cleared from memory immediately after use |

### 6.3 Credential Injection

| Feature | Description |
|---------|-------------|
| **Transparent Injection** | Agent never sees raw credentials |
| **Service-Specific Tokens** | Correct token selected per service |
| **Cache with TTL** | Credential caching with configurable TTL |
| **Real-Time Invalidation** | Redis Pub/Sub for cross-service cache invalidation |

---

## 7. Policy Engine

### 7.1 Policy Types

| Type | Description |
|------|-------------|
| **Permission Policies** | Define allowed actions per agent/role |
| **Constraint Policies** | Rate limits, quotas, time restrictions |
| **Resource Policies** | Resource-specific access controls |
| **Task Policies** | Multi-resource task-based permissions |

### 7.2 Policy Enforcement

| Feature | Description |
|---------|-------------|
| **Fail-Closed Security** | All requests denied when policy service unavailable |
| **Real-Time Enforcement** | Policies enforced at request time |
| **Pre-Request Validation** | Permission check before forwarding to backend |
| **Constraint Checking** | Rate limits and quotas validated per request |

### 7.3 Policy Management

| Feature | Description |
|---------|-------------|
| **YAML Policy Definitions** | Human-readable policy files |
| **Policy Versioning** | Track policy changes over time |
| **Hot Reload** | Policy updates without service restart |

---

## 8. Audit & Compliance

### 8.1 Audit Logging

| Feature | Description |
|---------|-------------|
| **Complete Event Capture** | Every MCP call logged with full context |
| **Human Attribution** | Actions attributed to "agent on behalf of user" |
| **Delegation Chain Tracking** | Full delegation hierarchy in audit events |
| **Persistence** | Audit events stored in PostgreSQL |

### 8.2 Audit Event Fields

| Field | Description |
|-------|-------------|
| `timestamp` | When the event occurred |
| `event_type` | Type of event (tool_call, permission_denied, etc.) |
| `agent_id` | Agent that performed the action |
| `on_behalf_of` | User who delegated to the agent |
| `delegation_id` | Reference to delegation token |
| `tool` | Tool that was called (with namespace) |
| `arguments` | Tool call arguments |
| `result_summary` | Summarized result |
| `session_ids` | Agent and MCP session identifiers |

### 8.3 Audit Queries

| Feature | Description |
|---------|-------------|
| **Agent Activity Query** | "What did agent X do?" |
| **User Activity Query** | "What actions were performed on behalf of user Y?" |
| **Time-Based Queries** | Filter by date range |
| **Event Type Filtering** | Filter by success/failure/denied |

---

## 9. Security Features

### 9.1 Zero-Trust Principles

| Principle | Implementation |
|-----------|----------------|
| **Never Trust by Default** | All agents must authenticate and get explicit permissions |
| **Least Privilege** | Agents get minimum permissions for minimum time |
| **Verify Continuously** | Every request validated against current state |

### 9.2 Fail-Closed Security

| Feature | Description |
|---------|-------------|
| **Control Plane Health Check** | Gateway monitors Control Plane availability |
| **Circuit Breaker** | Automatic fail-closed when Control Plane unreachable |
| **Request Denial** | All requests denied during outage |
| **Graceful Recovery** | Automatic recovery when Control Plane restored |

### 9.3 Credential Protection

| Feature | Description |
|---------|-------------|
| **Token Passthrough Prevention** | Agent tokens never forwarded to backends (per MCP spec) |
| **Credential Isolation** | Agents never see backend OAuth tokens |
| **Encrypted At-Rest** | All credentials encrypted in storage |
| **Short-Lived Tokens** | JWTs with short expiration (minutes to hours) |

### 9.4 Request Security

| Feature | Description |
|---------|-------------|
| **JWT Validation** | All requests validated via middleware |
| **Request Sanitization** | Input validation and sanitization |
| **CORS Configuration** | Configurable CORS policies |
| **Rate Limiting** | Request rate limiting (production) |

---

## 10. Developer Experience

### 10.1 DeepSecure SDK (Python)

| Feature | Description |
|---------|-------------|
| **Client Initialization** | Simple `deepsecure.Client()` initialization |
| **Automatic Auth** | SDK handles authentication automatically |
| **Agent Management** | `client.agents.create()`, `client.agents.register()` |
| **Credential Renewal** | Automatic token refresh |

### 10.2 DeepTrail CLI

| Command | Description |
|---------|-------------|
| `deepsecure agent create` | Create new agent identity |
| `deepsecure policy create` | Define security policies |
| `deepsecure vault issue` | Issue credentials |
| `deepsecure configure` | Configure SDK/CLI settings |

### 10.3 Framework Integrations

| Framework | Status |
|-----------|--------|
| **LangChain** | Integration available |
| **CrewAI** | Integration available |
| **Custom Agents** | SDK works with any Python agent |

### 10.4 Developer APIs

| API | Description |
|-----|-------------|
| **REST API** | Full HTTP API for all operations |
| **MCP Endpoint** | JSON-RPC 2.0 MCP protocol |
| **Health Endpoints** | `/health`, `/ready` for monitoring |
| **OpenAPI Docs** | Auto-generated API documentation |

---

## 11. Enterprise Features

### 11.1 Multi-Tenancy

| Feature | Description |
|---------|-------------|
| **Organization Isolation** | Complete data isolation per organization |
| **Domain-Based Routing** | Route users to correct organization |
| **Admin Hierarchy** | Organization-level admin roles |

### 11.2 IT Governance

| Feature | Description |
|---------|-------------|
| **Approved Agent Registry** | IT-approved vendor agent list |
| **Approved Service Registry** | IT-approved MCP server list |
| **Role-Based Tool Visibility** | Users see only role-appropriate tools |
| **Maximum Delegable Permissions** | Role-based delegation limits |

### 11.3 Emergency Controls

| Feature | Description |
|---------|-------------|
| **Agent Suspension** | One-click agent suspension |
| **Delegation Revocation** | Immediate delegation invalidation |
| **Global Circuit Breaker** | Suspend all agent access |
| **Incident Response Tools** | Quick response to security incidents |

### 11.4 Compliance Support

| Feature | Description |
|---------|-------------|
| **SOC2 Audit Trail** | Complete audit logs for compliance |
| **HIPAA Support** | PII access logging and controls |
| **Data Classification** | Tag data by sensitivity level |
| **Export Capabilities** | Export audit logs for review |

---

## 12. Integration Capabilities

### 12.1 Supported Backends (MVP)

| Backend | Tools | Status |
|---------|-------|--------|
| **Notion** | search_pages, read_page, create_page | ✅ Implemented |
| **Slack** | search_messages, send_message, list_channels | ✅ Implemented |
| **HubSpot** | get_contact, update_contact, list_deals | ✅ Implemented |

### 12.2 Backend Integration Architecture

| Component | Description |
|-----------|-------------|
| **Backend Adapter** | Unified interface for all backends |
| **Service Clients** | Per-service API clients (NotionClient, SlackClient, etc.) |
| **Connection Manager** | Manage backend connections |
| **Tool Definitions** | Backend-specific tool schemas |

### 12.3 Identity Provider Integrations

| Provider | Status |
|----------|--------|
| **Okta** | Supported |
| **Azure AD** | Supported |
| **Google Workspace** | Supported |
| **Custom OIDC** | Supported |

### 12.4 Infrastructure Integrations

| Integration | Description |
|-------------|-------------|
| **PostgreSQL** | Primary database for all persistent data |
| **Redis** | Cache, session storage, Pub/Sub messaging |
| **Docker** | Container deployment |
| **Kubernetes** | Orchestration support with Helm charts |

### 12.5 Secrets Backend Support (Roadmap)

| Backend | Status |
|---------|--------|
| **Native Vault** | ✅ Implemented (PostgreSQL-backed) |
| **HashiCorp Vault** | 🔜 Planned |
| **AWS Secrets Manager** | 🔜 Planned |
| **Google Secret Manager** | 🔜 Planned |
| **Azure Key Vault** | 🔜 Planned |

---

## Feature Summary by Persona

### For Developers

- ✅ Simple SDK initialization
- ✅ Automatic authentication handling
- ✅ No credential management in code
- ✅ Framework integrations (LangChain, CrewAI)
- ✅ Clear API documentation

### For Security Teams

- ✅ Centralized visibility and control
- ✅ Zero-trust enforcement
- ✅ Complete audit trail
- ✅ Emergency circuit breakers
- ✅ Policy-as-code

### For IT Operations

- ✅ IdP integration
- ✅ Approved agent/service registries
- ✅ Role-based access control
- ✅ Health monitoring endpoints
- ✅ Container/Kubernetes ready

### For Compliance

- ✅ Human accountability for all actions
- ✅ Delegation chain tracking
- ✅ Audit log export
- ✅ Data classification support
- ✅ Access pattern monitoring

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | February 2026 | Initial comprehensive feature list |
