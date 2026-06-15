# DeepSecure: End-to-End Product Use Cases by Persona

> **Product Use Cases Guide** | Version 1.3 | May 2026
>
> This document describes how different enterprise personas interact with the DeepSecure platform, from initial setup through daily operations.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Top 5 Core Features](#2-top-5-core-features)
3. [Persona Overview](#3-persona-overview)
4. [IT Administrator](#4-it-administrator)
5. [Employee (End User)](#5-employee-end-user)
6. [Security Team](#6-security-team)
7. [Engineering Team](#7-engineering-team)
8. [Vendor Admin (Multi-User Agent Model)](#8-vendor-admin-multi-user-agent-model)
9. [Cross-Persona Workflows](#9-cross-persona-workflows)
10. [Appendix: Quick Reference](#10-appendix-quick-reference)

---

## 1. Executive Summary

DeepSecure enables enterprises to securely deploy AI agents while maintaining control, compliance, and accountability. Each persona interacts with the platform differently:

| Persona | Primary Interactions | Key Value |
|---------|---------------------|-----------|
| **IT Administrator** | Setup, governance, emergency controls | Control without blocking productivity |
| **Employee** | Connect services, delegate to agents, monitor activity | Self-service with guardrails |
| **Security Team** | Policy definition, threat monitoring, incident response | Zero-trust enforcement, complete audit |
| **Engineering Team** | Build agents, integrate SDK, test & deploy | Simple integration, no credential handling |
| **Vendor Admin** | Register agents for customers, manage multi-user delegations, monitor fleet | One agent serving multiple users across organizations |

---

## 2. Top 5 Core Features

DeepSecure is built on five core features that work together to enable secure AI agent deployments. Each feature provides value to multiple personas.

### 2.1 Feature 1: Virtual MCP Server (Gateway)

**Single connection to multiple backends with automatic credential injection**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VIRTUAL MCP SERVER ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   AI Agent                           DeepSecure Gateway                      │
│  ┌──────────┐                       ┌─────────────────────┐                 │
│  │          │   ONE Connection      │                     │                 │
│  │  Agent   │ ────────────────────> │  Virtual MCP Server │                 │
│  │          │   (MCP Protocol)      │                     │                 │
│  └──────────┘                       │  • Namespace prefix │                 │
│                                     │  • Permission filter│                 │
│                                     │  • Credential inject│                 │
│                                     └─────────┬───────────┘                 │
│                                               │                             │
│                          ┌────────────────────┼────────────────────┐        │
│                          │                    │                    │        │
│                          ▼                    ▼                    ▼        │
│                    ┌──────────┐         ┌──────────┐         ┌──────────┐   │
│                    │  Notion  │         │  Slack   │         │  Gmail   │   │
│                    │   MCP    │         │   MCP    │         │   MCP    │   │
│                    └──────────┘         └──────────┘         └──────────┘   │
│                                                                              │
│   RESULT: Agent sees unified tools like notion.search_pages,                │
│           slack.send_message, gmail.search_messages                          │
│           All with automatic credential injection                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Capabilities:**

| Capability | Description |
|------------|-------------|
| **Single Endpoint** | Agents connect to ONE gateway URL, access tools from multiple backends |
| **Namespace Prefixing** | Tools automatically namespaced (`notion.search_pages`, `slack.send_message`) |
| **Permission Filtering** | `tools/list` returns ONLY tools the agent has permission to use |
| **Credential Injection** | User's OAuth tokens injected at runtime - agent never sees them |
| **Backend Abstraction** | Add new backends without changing agent code |

**Persona Interactions:**

| Persona | How They Interact with This Feature |
|---------|-------------------------------------|
| **IT Admin** | Approves which backend MCP servers are available in the registry |
| **Employee** | Connects their services (Notion, Slack, etc.) via OAuth in the console |
| **Security** | Monitors tool usage patterns across all backends in unified audit |
| **Engineering** | Writes agent code that calls ONE endpoint, gets tools from multiple backends |

**Engineering Example:**

```python
# Agent connects to ONE gateway - sees tools from ALL backends
async with httpx.AsyncClient() as client:
    # List tools - returns notion.*, slack.*, gmail.* (filtered by permissions)
    tools = await client.post("http://gateway:8002/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}
    }, headers={"Authorization": f"Bearer {agent_jwt}"})
    
    # Call any backend tool - credentials automatically injected
    result = await client.post("http://gateway:8002/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "notion.search_pages", "arguments": {"query": "Q1 plans"}}
    }, headers={"Authorization": f"Bearer {agent_jwt}"})
    # Agent NEVER sees the Notion OAuth token - Gateway injects it
```

---

### 2.2 Feature 2: Delegation-Based Authorization

**Users delegate scoped, time-bounded permissions to agents**

| Property | Description |
|----------|-------------|
| **Macaroon Tokens** | Cryptographically signed delegation tokens with embedded constraints |
| **Monotonic Attenuation** | Delegations can only narrow permissions, never widen them |
| **Fine-Grained** | Permissions like `notion:pages:read`, `slack:messages:send` |
| **Time-Bounded** | Automatic expiration (hours to days) with instant revocation |
| **Auditable** | Full delegation chain tracked for compliance |

**Permission Hierarchy:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MONOTONIC ATTENUATION                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Role Permissions (defined by IT Admin)                                     │
│  └── notion:*, slack:*, gmail:*, github:*                                   │
│      │                                                                       │
│      │  User can only delegate permissions they have                        │
│      ▼                                                                       │
│  User's Connected Scopes (from OAuth consent)                               │
│  └── notion:pages:*, slack:messages:search, gmail:messages:read             │
│      │                                                                       │
│      │  User chooses subset to delegate                                     │
│      ▼                                                                       │
│  Delegation to Agent                                                         │
│  └── notion:pages:read, slack:messages:search                               │
│      │                                                                       │
│      │  Each level can ONLY narrow, NEVER widen                             │
│      ▼                                                                       │
│  Agent's Effective Permissions                                               │
│  └── notion:pages:read, slack:messages:search                               │
│                                                                              │
│  ✓ Agent cannot access gmail:* (user didn't delegate it)                   │
│  ✓ Agent cannot write to notion (only read delegated)                      │
│  ✓ Agent cannot exceed user's permissions                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Persona Interactions:**

| Persona | How They Interact with This Feature |
|---------|-------------------------------------|
| **IT Admin** | Sets maximum delegable permissions per role |
| **Employee** | Creates delegations, choosing which permissions to grant agents |
| **Security** | Audits delegation chains, reviews permission grants |
| **Engineering** | Agent code receives JWT with embedded permissions |

---

### 2.3 Feature 3: Split-Key Credential Architecture

**Defense-in-depth secret protection using Shamir Secret Sharing**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SPLIT-KEY ARCHITECTURE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STORAGE (At Rest):                                                         │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Control Plane (PostgreSQL)         Gateway (Redis)                         │
│  ┌────────────────────────┐         ┌────────────────────────┐              │
│  │  Share 1 (encrypted)   │         │  Share 2 (encrypted)   │              │
│  │  ████████████████████  │         │  ████████████████████  │              │
│  │                        │         │                        │              │
│  │  CANNOT reconstruct    │         │  CANNOT reconstruct    │              │
│  │  secret alone          │         │  secret alone          │              │
│  └────────────────────────┘         └────────────────────────┘              │
│                                                                              │
│  RUNTIME (Just-In-Time Reassembly):                                         │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  1. Agent calls notion.search_pages                                         │
│  2. Gateway requests Share 1 from Control Plane                             │
│  3. Gateway retrieves Share 2 from local Redis                              │
│  4. Shares combined in memory (~2ms)                                        │
│  5. Secret used for API call                                                │
│  6. Secret CLEARED from memory immediately                                  │
│                                                                              │
│  SECURITY PROPERTIES:                                                       │
│  ✓ No single component ever holds complete secret                          │
│  ✓ Compromise of Control Plane alone = no secrets                          │
│  ✓ Compromise of Gateway alone = no secrets                                │
│  ✓ Secret exists in memory only during active API call                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Persona Interactions:**

| Persona | How They Interact with This Feature |
|---------|-------------------------------------|
| **IT Admin** | Deploys both Control Plane and Gateway; understands neither alone has secrets |
| **Employee** | Connects services via OAuth; tokens automatically split and stored securely |
| **Security** | Audits secret access; verifies defense-in-depth architecture |
| **Engineering** | No interaction - completely transparent; agent code unchanged |

---

### 2.4 Feature 4: Complete Audit Trail with Human Attribution

**Every action traced to a responsible human**

| Audit Property | Description |
|----------------|-------------|
| **Human Attribution** | All actions logged as "agent X on behalf of user Y" |
| **Delegation Chain** | Full chain: user → delegation → agent → action |
| **Complete Context** | Tool name, arguments, result, timestamps, session IDs |
| **Queryable** | Filter by agent, user, time, event type, tool |
| **Compliance Ready** | SOC2/HIPAA-ready with export capability |

**Audit Event Example:**

```json
{
  "timestamp": "2026-02-15T10:15:32Z",
  "event_type": "tool_call",
  "agent_id": "agent-sarah-salesassist-001",
  "on_behalf_of": "sarah@acme.com",
  "delegation_id": "del-abc123-xyz789",
  "tool": "notion.search_pages",
  "arguments": {"query": "competitor analysis", "limit": 5},
  "result": "success",
  "result_summary": "3 pages found",
  "session_id": "asess-001-ghi789",
  "mcp_session_id": "mcpsess-notion-jkl012"
}
```

**Persona Interactions:**

| Persona | How They Interact with This Feature |
|---------|-------------------------------------|
| **IT Admin** | Reviews agent activity summaries; responds to unusual patterns |
| **Employee** | Views their own agent's activity in personal dashboard |
| **Security** | Queries audit logs for investigations; generates compliance reports |
| **Engineering** | Debugs agent behavior using audit trail |

---

### 2.5 Feature 5: Fail-Closed Security with Emergency Controls

**Zero-trust enforcement with instant response capability**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FAIL-CLOSED SECURITY MODEL                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  NORMAL OPERATION:                                                          │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Agent Request → Gateway → Control Plane Health ✓ → Process Request        │
│                                                                              │
│  CONTROL PLANE UNREACHABLE:                                                 │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Agent Request → Gateway → Control Plane Health ✗ → DENY ALL REQUESTS      │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  🔴 FAIL-CLOSED: When in doubt, DENY                              │     │
│  │                                                                     │     │
│  │  • Cannot verify permissions? DENY                                 │     │
│  │  • Cannot reach credential vault? DENY                            │     │
│  │  • Cannot log audit event? DENY                                   │     │
│  │                                                                     │     │
│  │  Security is NEVER bypassed due to system issues                  │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  EMERGENCY CONTROLS:                                                        │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  CONTROL                      │  EFFECT                    │ TIME   │    │
│  │  ─────────────────────────────┼────────────────────────────┼────────│    │
│  │  Suspend Single Agent         │  Agent's requests denied   │ <1 sec │    │
│  │  Revoke Delegation            │  Specific delegation void  │ <1 sec │    │
│  │  Suspend All Vendor Agents    │  All vendor agents blocked │ <1 sec │    │
│  │  Global Circuit Breaker       │  ALL agents blocked        │ <1 sec │    │
│  │  User Offboarding (IdP sync)  │  All user delegations void │ <1 sec │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Emergency Control Commands:**

```bash
# Suspend a specific agent immediately
POST /api/v1/admin/agents/{agent_id}/suspend
{
  "reason": "Suspected anomalous behavior",
  "notify_owner": true
}

# Revoke all delegations for an agent
POST /api/v1/admin/delegations/revoke-all?agent_id={agent_id}

# Global circuit breaker (organization-wide lockdown)
POST /api/v1/admin/emergency/lockdown
{
  "reason": "Security incident",
  "duration_minutes": 60
}
```

**Persona Interactions:**

| Persona | How They Interact with This Feature |
|---------|-------------------------------------|
| **IT Admin** | Executes emergency controls; manages circuit breakers |
| **Employee** | Can revoke their own delegations instantly |
| **Security** | Monitors fail-closed events; triggers emergency response |
| **Engineering** | Handles graceful degradation when requests are denied |

**Automatic Revocation Triggers:**

| Trigger | Effect |
|---------|--------|
| Delegation TTL expires | Agent loses access automatically |
| User deactivated in IdP (Okta/Azure AD) | ALL user's delegations invalidated instantly |
| User's role changes | Delegations re-evaluated against new permissions |
| Service OAuth token revoked | Agent can't use that service's tools |
| IT admin suspends agent | Immediate effect, all sessions terminated |

---

### 2.6 Feature Summary by Persona

| Feature | IT Admin | Employee | Security | Engineering |
|---------|:--------:|:--------:|:--------:|:-----------:|
| **1. Virtual MCP Server** | Approves backends | Connects services | Monitors usage | Single integration point |
| **2. Delegation Auth** | Sets role limits | Creates delegations | Audits chains | Receives JWT permissions |
| **3. Split-Key Secrets** | Deploys services | OAuth flow (auto) | Verifies architecture | Transparent |
| **4. Audit Trail** | Reviews summaries | Views own activity | Queries & reports | Debugs behavior |
| **5. Fail-Closed** | Emergency controls | Revokes delegations | Incident response | Handles denials |

---

## 3. Persona Overview

### 3.1 Persona Definitions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEEPSECURE PERSONA MAP                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐       │
│  │  IT ADMINISTRATOR│    │     EMPLOYEE     │    │  SECURITY TEAM   │       │
│  │                  │    │                  │    │                  │       │
│  │  • Platform setup│    │  • Service conn. │    │  • Policy design │       │
│  │  • IdP config    │    │  • Agent setup   │    │  • Threat monitor│       │
│  │  • Service apprvl│    │  • Delegation    │    │  • Incident resp.│       │
│  │  • Emergency ctrl│    │  • Activity view │    │  • Compliance    │       │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘       │
│           │                       │                       │                 │
│           │                       │                       │                 │
│           └───────────────────────┼───────────────────────┘                 │
│                                   │                                         │
│          ┌────────────────────────┼────────────────────────┐                │
│          │                        │                        │                │
│  ┌──────────────────────────┐    │    ┌──────────────────────────┐          │
│  │    ENGINEERING TEAM      │    │    │     VENDOR ADMIN         │          │
│  │                          │    │    │                          │          │
│  │  • Agent development     │    │    │  • Agent registration    │          │
│  │  • SDK integration       │    │    │  • Multi-user management │          │
│  │  • MCP server creation   │    │    │  • Fleet monitoring      │          │
│  │  • Testing & deployment  │    │    │  • Cross-user audit view │          │
│  └──────────────────────────┘    │    └──────────────────────────┘          │
│                                  │                                          │
│                    ┌─────────────────────────────┐                          │
│                    │   MULTI-USER DELEGATION     │                          │
│                    │                             │                          │
│                    │  1 Agent → N Users          │                          │
│                    │  Each user: own OAuth +     │                          │
│                    │  own permissions + own TTL  │                          │
│                    └─────────────────────────────┘                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Interaction Timeline

```
PHASE 1: INITIAL SETUP (Day 0)
├── IT Admin: Platform deployment, IdP integration
├── Security: Policy definition
└── Engineering: SDK setup, agent framework selection

PHASE 2: CONFIGURATION (Day 1-7)
├── IT Admin: Service approval, role configuration
├── Security: Policy testing in sandbox
└── Engineering: Agent development, testing

PHASE 3: ROLLOUT (Day 7+)
├── IT Admin: Enable employee access
├── Employee: Connect services, delegate to agents
└── Engineering: Deploy production agents

PHASE 4: OPERATIONS (Ongoing)
├── Employee: Daily agent interactions
├── Security: Continuous monitoring
├── IT Admin: Periodic reviews, emergency response
└── Engineering: Maintenance, new features
```

---

## 4. IT Administrator

### 4.1 Role Overview

| Aspect | Description |
|--------|-------------|
| **Primary Goal** | Enable AI agent adoption while maintaining security and control |
| **Key Concerns** | Shadow AI, compliance, emergency response, operational overhead |
| **Access Level** | Organization administrator with full platform control |

### 4.2 Initial Platform Setup

#### 3.2.1 Deploy DeepSecure Infrastructure

```bash
# IT Admin deploys DeepSecure services
docker compose up -d db redis deeptrail-control deeptrail-gateway

# Verify services are running
curl http://localhost:8000/health  # Control Plane
curl http://localhost:8002/health  # Gateway
```

**Expected Output:**
```json
{
  "service": "DeepSecure Control Plane",
  "status": "ok",
  "dependencies": {
    "database": "connected"
  }
}
```

#### 3.2.2 Configure Identity Provider Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IT ADMIN: CONFIGURE IDP INTEGRATION                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: Register Organization                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  POST /api/v1/organizations                                                 │
│  {                                                                          │
│    "name": "Acme Corp",                                                     │
│    "domain": "acme.com",                                                    │
│    "idp_type": "okta",                                                      │
│    "idp_issuer": "https://acme.okta.com",                                   │
│    "idp_client_id": "0oa1234567890abcdef",                                  │
│    "allowed_domains": ["acme.com", "acme.io"]                               │
│  }                                                                          │
│                                                                             │
│  STEP 2: Configure Group-to-Role Mapping                                    │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Okta Group "Sales"        → DeepSecure Role "sales-rep"                    │
│  Okta Group "Engineering"  → DeepSecure Role "developer"                    │
│  Okta Group "Finance"      → DeepSecure Role "finance-analyst"              │
│  Okta Group "IT-Admins"    → DeepSecure Role "platform-admin"               │
│                                                                             │
│  STEP 3: Enable Auto-Provisioning                                           │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  • Users auto-created on first SSO login                                    │
│  • Roles assigned based on group membership                                 │
│  • Deactivation in Okta → immediate revocation in DeepSecure                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Service and Agent Governance

#### 3.3.1 Configure Approved Services Registry

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              IT ADMIN CONSOLE: APPROVED SERVICES REGISTRY                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  SERVICE REGISTRY FOR "ACME CORP"                                   │    │
│  │                                                                     │    │
│  │  Service          │ Status   │ Available To        │ Data Class     │    │
│  │  ─────────────────┼──────────┼─────────────────────┼─────────────── │    │
│  │  notion-mcp       │ ✅ Active │ All Employees       │ Internal      |    │
│  │  slack-mcp        │ ✅ Active │ All Employees       │ Internal      │    │
│  │  gmail-mcp        │ ✅ Active │ All Employees       │ Internal      │    │
│  │  calendar-mcp     │ ✅ Active │ All Employees       │ Internal      │    │
│  │  salesforce-mcp   │ ✅ Active │ Sales               │ Confidential  │    │
│  │  financial-api    │ ✅ Active │ Finance Only        │ Restricted    │    │
│  │  hr-records-mcp   │ ⚠️ Review │ HR Only             │ Restricted    │    │
│  │  github-mcp       │ ✅ Active │ Engineering         │ Confidential  │    │
│  │                                                                     │    │
│  │  [+ Add Service]  [Import from Catalog]  [Bulk Update]              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ADDING A NEW SERVICE:                                                      │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  POST /api/v1/admin/services                                                │
│  {                                                                          │
│    "service_id": "jira-mcp",                                                │
│    "display_name": "Jira Issue Tracker",                                    │
│    "endpoint": "https://mcp.atlassian.com/jira",                            │
│    "transport": "streamable-http",                                          │
│    "data_classification": "confidential",                                   │
│    "available_to_roles": ["developer", "product-manager"],                  │
│    "requires_approval": false,                                              │
│    "status": "sandbox"                                                      │
│  }                                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 Configure Role-Based Permission Limits

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   IT ADMIN: ROLE PERMISSION CONFIGURATION                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ROLE: "sales-rep"                                                          │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Maximum Delegable Permissions:                                             │
│  ┌───────────────────────────────────────────────────────────────────┐      │
│  │  slack:messages:search          ✅ Allowed                         │      │
│  │  slack:messages:send           ✅ Allowed                         │      │
│  │  slack:channels:list           ✅ Allowed                         │      │
│  │  gmail:messages:read           ✅ Allowed                         │      │
│  │  gmail:messages:search         ✅ Allowed                         │      │
│  │  github:repos:list             ✅ Allowed                         │      │
│  │  github:issues:read            ✅ Allowed                         │      │
│  │  slack:admin:*                 ❌ Blocked (admin-only)            │      │
│  │  notion:pages:read             ✅ Allowed                         │      │
│  │  notion:pages:create           ✅ Allowed                         │      │
│  │  financial:*                   ❌ Not available for role          │      │
│  └───────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  Default Constraints:                                                       │
│  • Maximum delegation TTL: 7 days                                           │
│  • Maximum actions per day: 500                                             │
│  • Working hours only: 06:00-22:00 local time                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.3.3 Manage Approved Vendor Agents

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  IT ADMIN: APPROVED VENDOR AGENTS                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  APPROVED VENDOR REGISTRY:                                                  │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Vendor            │ Agent Type        │ Status   │ Employees      │     │
│  │  ──────────────────┼───────────────────┼──────────┼─────────────── │     │
│  │  SalesBot Inc      │ Sales Assistant   │ ✅ Active │ 47 using      │     │
│  │  CodeAssist AI     │ Code Helper       │ ✅ Active │ 123 using     │     │
│  │  DataAnalytics Co  │ BI Assistant      │ ⚠️ Review │ 0 using       │     │
│  │  CustomAgent Inc   │ General Purpose   │ ❌ Denied │ N/A           │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  VENDOR APPROVAL WORKFLOW:                                                  │
│                                                                             │
│  1. Security team reviews vendor's security posture                         │
│  2. IT admin approves vendor in registry                                    │
│  3. Vendor agent ID pattern registered: vendor-salesbot-*                   │
│  4. Employees can select vendor from approved list                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Emergency Controls

#### 4.4.1 Agent Suspension

```bash
# Suspend a specific agent immediately
POST /api/v1/admin/agents/{agent_id}/suspend
{
  "reason": "Suspected anomalous behavior",
  "suspended_by": "admin@acme.com",
  "notify_owner": true
}

# Response
{
  "agent_id": "agent-sarah-salesassist-001",
  "status": "suspended",
  "suspended_at": "2026-02-15T10:30:00Z",
  "all_delegations_revoked": true,
  "active_sessions_terminated": 3
}
```

#### 4.4.2 Global Circuit Breaker

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IT ADMIN: EMERGENCY CONTROLS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ⚠️  EMERGENCY CONTROLS - USE WITH CAUTION                                  │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                    │     │
│  │  [ 🔴 SUSPEND ALL VENDOR AGENTS ]                                  │     │
│  │  Immediately terminates all vendor agent sessions                  │     │
│  │  Affects: 47 active agents across 312 employees                    │     │
│  │                                                                    │     │
│  │  [ 🔴 DISABLE ALL DELEGATIONS ]                                    │     │
│  │  Revokes all active delegation tokens organization-wide            │     │
│  │  Affects: 1,247 active delegations                                 │     │
│  │                                                                    │     │
│  │  [ 🔴 LOCKDOWN MODE ]                                              │     │
│  │  Blocks all agent activity until manually re-enabled               │     │
│  │  Affects: All agents, all users                                    │     │
│  │                                                                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  Recent Emergency Actions:                                                  │
│  • 2026-02-10 14:32 - Suspended agent-vendor-xyz (admin@acme.com)           │
│  • 2026-01-28 09:15 - Revoked delegation del-abc123 (security@acme.com)     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 4.4.3 Gateway Operations Dashboard

IT Administrators use the Gateway Operations Dashboard to monitor system health, backend connectivity, and debug issues.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              IT ADMIN: GATEWAY OPERATIONS DASHBOARD                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  System Status: ✅ All Systems Operational        Last Updated: 10:20:01    │
│                                                                              │
│  ┌─ Gateway Metrics (Last 24h) ──────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  Total MCP Requests: 12,458      Success Rate: 99.2%                  │  │
│  │  Active Sessions: 47             Unique Agents: 23                    │  │
│  │  Unique Users: 156               Delegations Active: 312              │  │
│  │                                                                        │  │
│  │  Request Latency:                                                      │  │
│  │    initialize:  p50: 45ms  │ p95: 120ms │ p99: 340ms                  │  │
│  │    tools/list:  p50: 23ms  │ p95:  67ms │ p99: 150ms                  │  │
│  │    tools/call:  p50: 89ms  │ p95: 234ms │ p99: 890ms                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Backend MCP Server Status ───────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  Backend    │ Status │ Latency │ Errors (24h) │ Active Conns │ Health │  │
│  │ ────────────├────────├─────────├──────────────├──────────────├─────── │  │
│  │  notion     │ ✅ UP  │   89ms  │      3       │     12       │  100%  │  │
│  │  slack      │ ✅ UP  │   45ms  │      0       │      8       │  100%  │  │
│  │  gmail      │ ✅ UP  │  120ms  │      1       │      4       │   99%  │  │
│  │  salesforce │ ❌ DOWN│    -    │     47       │      0       │    0%  │  │
│  │                                                                        │  │
│  │  [ Test Connection ] [ Refresh ] [ View Backend Logs ]                │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Recent Errors (Last Hour) ───────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  Time     │ Agent           │ Error Type           │ Backend │ User   │  │
│  │ ──────────├─────────────────├──────────────────────├─────────├─────── │  │
│  │  10:18:45 │ agent-hr-003    │ Vault token expired  │ notion  │ sarah  │  │
│  │  10:15:22 │ agent-sdr-001   │ Backend timeout      │ gmail   │ mike   │  │
│  │  10:12:03 │ agent-sales-007 │ Connection refused   │ salesforce│ jane │  │
│  │  10:08:17 │ agent-hr-003    │ Permission denied    │ slack   │ sarah  │  │
│  │                                                                        │  │
│  │  [ View Full Logs ] [ Export ] [ Create Alert Rule ]                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Credential Vault Status ─────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  Total Stored Tokens: 234      Expiring Soon (7d): 12                 │  │
│  │  Cache Hit Rate: 94.2%         Last Refresh: 10:15:00                 │  │
│  │                                                                        │  │
│  │  Tokens Requiring Attention:                                          │  │
│  │  • sarah@acme.com - notion - Expires in 2 days                        │  │
│  │  • mike@acme.com - gmail - Refresh failed (re-auth needed)             │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Gateway Health Check Commands:**

```bash
# Check overall gateway health
curl -s http://localhost:8002/health | jq .

# Check backend connectivity
curl -s http://localhost:8002/admin/backends/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

# Get gateway metrics
curl -s http://localhost:8002/admin/metrics \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

# Test specific backend connection
curl -s -X POST http://localhost:8002/admin/backends/notion/test \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
```

### 4.5 IT Admin Daily Operations

| Task | Frequency | Actions |
|------|-----------|---------|
| **Review new agent registrations** | Daily | Approve/deny pending registrations |
| **Check service health** | Daily | Monitor Control Plane and Gateway status |
| **Review security alerts** | Daily | Address flagged anomalies |
| **Audit dormant agents** | Weekly | Identify and disable inactive agents |
| **Role permission review** | Monthly | Ensure roles align with business needs |
| **Vendor compliance check** | Quarterly | Verify approved vendors remain compliant |

### 4.6 Admin Agent View (Multi-User Lifecycle)

> **Note:** For the multi-user model (1 agent → N users), IT Admin needs a different view than the employee's single-user Agents page. The admin view shows the agent's relationship to ALL delegating users.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│               IT ADMIN: AGENT FLEET VIEW (MULTI-USER)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  AGENT: Sales Assistant (agent-xxx-yyy-zzz)                                 │
│  Status: ● Active | Platform: GCP Workload Identity                         │
│  SA: sales-agent-sa@company.iam.gserviceaccount.com                         │
│                                                                             │
│  LIFECYCLE:                                                                  │
│  ●─────────────●───────────────────────●────────────────●                   │
│  Reg           Del (3 users)           Auth (1×)       Active               │
│  (admin)       (user self-service)     (bootstrap)     (heartbeat)          │
│                                                                             │
│  WHY 1 AUTH, NOT N:                                                          │
│  The agent has ONE workload identity (one service account).                  │
│  It bootstraps ONCE → gets 1 Agent JWT.                                      │
│  N users create N independent delegations to the SAME agent.                 │
│  On each tool call, agent specifies which user's context (user_id).          │
│                                                                             │
│  DELEGATING USERS (3):                                                       │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  User           │ Services        │ Permissions       │ Expires   │     │
│  │  ────────────── │ ─────────────── │ ──────────────── │ ───────── │     │
│  │  sarah@acme.com │ Notion, Slack,  │ Full access       │ 6 days   │     │
│  │                 │ Gmail, Cal      │ (8 permissions)   │           │     │
│  │  victor@acme.   │ Notion, Gmail   │ Read-only         │ 4 days   │     │
│  │                 │                 │ ⚠️ No send email  │           │     │
│  │  priya@acme.com │ Slack only      │ messages:read     │ 2 days   │     │
│  │                 │                 │ (2 permissions)   │           │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  RECENT ACTIVITY (by user context):                                          │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  10:15  │ sarah  │ notion.search_pages │ ✅ 3 results  │ 473ms   │     │
│  │  10:16  │ victor │ gcalendar.list      │ ✅ 5 events   │ 320ms   │     │
│  │  10:17  │ priya  │ slack.list_channels │ ✅ 12 chans   │ 210ms   │     │
│  │  10:18  │ victor │ gmail.send_message  │ ❌ Denied     │ —       │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Architectural Point:**
- **1 Registration** (by admin)
- **N Delegations** (by users independently — self-service)
- **1 Authentication** (agent bootstrap — NOT per user)
- **Active** status based on agent heartbeat (any user's tool call updates it)

This differs from the current single-employee view where each user sees only their own agents and delegations. The admin view aggregates across all users for a single agent.

### 4.7 Admin Delegation Management

> IT Admin creates default delegation templates that users inherit. Users can narrow (remove permissions) but cannot exceed admin-set limits. This enables "admin sets policy once, N users self-onboard" pattern.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│            IT ADMIN: DELEGATION MANAGEMENT                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DELEGATION TEMPLATES:                                                       │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Agent               │ Default Permissions    │ Max TTL │ Users   │     │
│  │  ──────────────────── │ ────────────────────── │ ─────── │ ─────── │     │
│  │  Sales Assistant      │ notion:read, slack:*,  │ 7 days  │ 5/10   │     │
│  │                       │ gmail:read, cal:read   │         │ active  │     │
│  │  Engineering Audit    │ notion:*, slack:*,     │ 7 days  │ 3/3    │     │
│  │                       │ github:read            │         │ active  │     │
│  │  Thunderbolt Agent    │ notion:*, slack:*,     │ 7 days  │ 1/∞    │     │
│  │                       │ gmail:*, gdrive:*      │         │ active  │     │
│  │                                                                    │     │
│  │  [+ Create Template]  [Edit]  [Clone]                              │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ALL ACTIVE DELEGATIONS (across all users):                                  │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  User           │ Agent              │ Permissions │ Status │ TTL  │     │
│  │  ────────────── │ ────────────────── │ ─────────── │ ────── │ ──── │     │
│  │  sarah@acme     │ Sales Assistant    │ 12 (full)   │ Active │ 6d   │     │
│  │  victor@acme    │ Sales Assistant    │ 5 (narrowed)│ Active │ 4d   │     │
│  │  priya@acme     │ Sales Assistant    │ 4 (narrowed)│ Active │ 2d   │     │
│  │  mahendra@      │ Engineering Audit  │ 12 (full)   │ Active │ 7d   │     │
│  │  sarah@acme     │ Thunderbolt Agent  │ 15 (full)   │ Active │ 7d   │     │
│  │  victor@acme    │ Engineering Audit  │ — (pending) │ Invite │ —    │     │
│  │                                                                    │     │
│  │  [Create Delegation]  [Bulk Revoke]  [Export CSV]                  │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  DELEGATION FLOW:                                                            │
│  ─────────────────                                                           │
│                                                                             │
│  Admin creates template:                                                     │
│    → Sets max permissions per agent (ceiling)                                │
│    → Sets default TTL                                                        │
│    → Optionally invites users                                                │
│                                                                             │
│  User self-service:                                                          │
│    → User logs in, sees agents available to them                             │
│    → User "accepts" delegation (inherits admin template)                     │
│    → User can REMOVE permissions they don't want (narrow)                    │
│    → User CANNOT ADD permissions beyond admin template (ceiling)             │
│    → User can set shorter TTL (but not longer than admin max)                │
│                                                                             │
│  Admin override:                                                             │
│    → Admin can revoke any user's delegation                                  │
│    → Admin can create delegation on behalf of user                           │
│    → Admin can update template (existing delegations NOT auto-changed)       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**API Endpoints:**
```
# Admin: Create delegation template for an agent
POST /api/v1/admin/delegation-templates
{
  "agent_id": "agent-xxx",
  "max_permissions": ["notion:pages:read", "slack:messages:*", ...],
  "default_ttl_days": 7,
  "available_to_roles": ["sales-rep", "product-manager"]
}

# Admin: View all delegations across all users
GET /api/v1/admin/delegations?agent_id=...&user=...&status=active

# Admin: Create delegation on behalf of a user
POST /api/v1/admin/delegations
{
  "agent_id": "agent-xxx",
  "user_email": "sarah@acme.com",
  "permissions": [...],   // must be subset of template max
  "ttl_days": 7
}

# User: Accept/customize their delegation (narrow only)
PATCH /api/v1/delegations/{delegation_id}
{
  "permissions": [...]    // can only REMOVE, not add beyond template
}
```

---

## 5. Employee (End User)

### 5.1 Role Overview

| Aspect | Description |
|--------|-------------|
| **Primary Goal** | Use AI agents to automate tasks and increase productivity |
| **Key Concerns** | Easy setup, reliable operation, confidence in security |
| **Access Level** | Self-service within IT-defined guardrails |

### 5.2 Initial Onboarding

#### 5.2.1 First-Time Login

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EMPLOYEE: FIRST-TIME LOGIN FLOW                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: Access DeepSecure Console                                          │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Sarah navigates to: https://console.deeptrail.io                           │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                     │    │
│  │           🔐 DeepSecure Console                                    │     │
│  │                                                                     │    │
│  │           Welcome! Sign in to continue.                            │     │
│  │                                                                     │    │
│  │           [ Sign in with Okta ]  ← SSO Button                     │      │
│  │                                                                     │    │
│  │           Or enter your email:                                     │     │
│  │           [sarah@acme.com_____________]                            │     │
│  │                                                                     │    │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  STEP 2: SSO Authentication                                                 │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  → Redirected to Okta login                                                 │
│  → Sarah enters credentials + MFA                                           │
│  → Okta returns ID token to DeepSecure                                      │
│  → DeepSecure creates user session                                          │
│                                                                             │
│  STEP 3: Welcome Dashboard                                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  👋 Welcome, Sarah Chen!                                           │     │
│  │                                                                    │     │
│  │  Your Role: Sales Representative                                   │     │
│  │  Organization: Acme Corp                                           │     │
│  │                                                                    │     │
│  │  Quick Actions:                                                    │     │
│  │  • Connect your first service                                      │     │           
      Register an Agent                                                 │     │
│  │  • View available tools                                            │     │
│  │                                                                    │     │
│  │  Connected Services: 0                                             │     │
│  │  Active Agents: 0                                                  │     │
│  │  Active Delegations: 0                                             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Connecting Services

#### 5.3.1 Connect to External Services via OAuth

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMPLOYEE: CONNECT SERVICES                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  AVAILABLE SERVICES FOR YOUR ROLE (Sales Representative):                   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                     │     │
│  │  📊 GitHub                                                          │     │
│  │  Access repositories, issues, and pull requests                   │     │
│  │  Status: Not Connected                                             │     │
│  │  [ Connect GitHub ]                                                │     │
│  │                                                                     │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                     │     │
│  │  💬 Slack                                                          │     │
│  │  Search messages, send notifications                              │     │
│  │  Status: Not Connected                                             │     │
│  │  [ Connect Slack ]                                                 │     │
│  │                                                                     │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                     │     │
│  │  📝 Notion                                                         │     │
│  │  Access company wiki and documents                                │     │
│  │  Status: Not Connected                                             │     │
│  │  [ Connect Notion ]                                                │     │
│  │                                                                     │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                     │     │
│  │  🔒 Financial Data API                                             │     │
│  │  Not available for your role                                      │     │
│  │  Contact IT for access                                            │     │
│  │                                                                     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  OAUTH CONSENT FLOW (When clicking "Connect GitHub"):                       │
│                                                                              │
│  1. Browser redirects to GitHub OAuth                                       │
│  2. Sarah sees GitHub consent screen:                                       │
│     "DeepSecure wants to access your GitHub data"                          │
│     ☑ View repos   ☑ Read issues   ☑ Read pull requests                    │
│  3. Sarah clicks "Authorize"                                                │
│  4. GitHub returns OAuth tokens to DeepSecure                              │
│  5. Tokens stored securely in DeepSecure vault                             │
│  6. Sarah NEVER sees or handles the OAuth tokens                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**CLI/API Alternative:**

```bash
# Connect Notion service
curl -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "'"$NOTION_API_KEY"'",
      "token_type": "bearer",
      "scope": "read_pages search_content"
    }
  }'
```

**Response:**
```json
{
  "service_id": "notion",
  "status": "connected",
  "scopes_granted": ["read_pages", "search_content"],
  "connected_at": "2026-02-15T10:00:00Z"
}
```

### 5.4 Registering an Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMPLOYEE: REGISTER AN AI AGENT                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: Choose Agent Type                                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Register New Agent                                                 │     │
│  │                                                                     │     │
│  │  Agent Type:                                                       │     │
│  │  ○ My Own Agent (I built it)                                      │     │
│  │  ● Vendor Agent (From approved vendor)                            │     │
│  │  ○ Shared Team Agent (Managed by my team)                         │     │
│  │                                                                     │     │
│  │  Select Vendor: [SalesBot Inc ▼]                                  │     │
│  │                                                                     │     │
│  │  Agent Name: [My Sales Assistant____________]                      │     │
│  │                                                                     │     │
│  │  Purpose: [Automate lead follow-up and scheduling_______]         │     │
│  │                                                                     │     │
│  │  [ Register Agent ]                                                │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  STEP 2: Agent Registered                                                   │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  ✅ Agent Successfully Registered!                                          │
│                                                                              │
│  Agent ID: agent-sarah-salesassist-001                                      │
│  Owner: sarah@acme.com                                                      │
│  Status: Registered (No delegations yet)                                    │
│                                                                              │
│  Next Step: Delegate permissions to this agent                             │
│  [ Configure Delegation ]                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.5 Creating a Delegation

#### 5.5.1 Delegate Permissions to Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMPLOYEE: CREATE DELEGATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DELEGATE PERMISSIONS TO: My Sales Assistant                                │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  SLACK PERMISSIONS:                                                │     │
│  │                                                                    │     │
│  │  ☑ Search messages (slack:messages:search)                         │     │
│  │  ☐ Send messages (slack:messages:send)                             │     │
│  │  ☑ List channels (slack:channels:list)                             │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │ 
│  │  NOTION PERMISSIONS:                                               │     │
│  │                                                                    │     │
│  │  ☑ Search pages (notion:pages:search)                              │     │
│  │  ☑ Read pages (notion:pages:read)                                  │     │
│  │  ☐ Create pages (notion:pages:create)                              │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │
│  │  DELEGATION SETTINGS:                                              │     │
│  │                                                                    │     │
│  │  Expires in: [7 days ▼]                                            │     │
│  │  Max actions/day: [100____]                                        │     │
│  │                                                                    │     │
│  │  [ Create Delegation ]                                             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**CLI/API:**

```bash
# Create delegation
curl -X POST http://localhost:8000/api/v1/delegations/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-sarah-salesassist-001",
    "permissions": [
      "notion:pages:search",
      "notion:pages:read",
      "slack:messages:search",
      "slack:channels:list"
    ],
    "constraints": {
      "expires_in_hours": 168
    }
  }'
```

**Response:**
```json
{
  "delegation_token": "MDAxY2xv...[macaroon token]",
  "delegation_id": "del-abc123-xyz789",
  "permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "expires_in": 604800
}
```

### 5.6 Monitoring Agent Activity

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMPLOYEE: MY AGENT ACTIVITY                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  AGENT: My Sales Assistant (agent-sarah-salesassist-001)                    │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  TODAY'S ACTIVITY SUMMARY                                          │     │
│  │                                                                    │     │
│  │  Actions Today: 47 of 100 allowed                                  │     │
│  │  Delegation Expires: 6 days, 14 hours                              │     │
│  │  Status: ● Active                                                  │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │
│  │  RECENT ACTIVITY:                                                  │     │
│  │                                                                    │     │
│  │  Time        │ Tool                   │ Result    │ Details        │     │
│  │  ────────────┼────────────────────────┼───────────┼──────────────  │     │
│  │  10:15:32    │ notion.search_pages    │ ✅ Success │ 3 pages found │     │
│  │  10:16:45    │ notion.read_page       │ ✅ Success │ Read "Q1 Plan"│     │
│  │  10:17:12    │ slack.search_messages  │ ✅ Success │ 12 messages   │     │
│  │  10:18:03    │ gmail.search_messages  │ ✅ Success │ 5 messages    │     │
│  │  10:19:22    │ notion.create_page     │ ❌ Denied  │ Not delegated │     │
│  │                                                                    │     │
│  │  [View Full Audit Log]  [Export Activity]                          │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │
│  │  QUICK ACTIONS:                                                    │     │
│  │                                                                    │     │
│  │  [ Adjust Permissions ]  [ Revoke Delegation ]  [ Contact Support ]│     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.7 Employee Daily Workflow

| Time | Action | Description |
|------|--------|-------------|
| **Morning** | Check agent status | Verify agent is active, review overnight activity |
| **Throughout Day** | Agent operates | Agent performs delegated tasks automatically |
| **As Needed** | Review activity | Check what agent has done, verify results |
| **If Issues** | Adjust/revoke | Modify permissions or revoke delegation |
| **Weekly** | Renew delegation | Extend or recreate expiring delegations |

---

## 6. Security Team

### 6.1 Role Overview

| Aspect | Description |
|--------|-------------|
| **Primary Goal** | Ensure AI agent deployments meet security and compliance requirements |
| **Key Concerns** | Threat detection, policy enforcement, incident response, compliance |
| **Access Level** | Security administrator with audit and policy access |

### 6.2 Policy Definition

#### 6.2.1 Create Security Policies

```yaml
# policy-sales-agents.yaml
# Security policy for sales department AI agents

policy:
  name: "Sales Agent Security Policy"
  description: "Defines security constraints for sales department agents"
  version: "1.0"
  
rules:
  # Rate limiting
  - name: "rate-limit-api-calls"
    description: "Limit API calls per agent per day"
    constraint:
      type: "rate_limit"
      max_calls_per_day: 500
      max_calls_per_hour: 100
      
  # Time-based restrictions
  - name: "business-hours-only"
    description: "Restrict agent operations to business hours"
    constraint:
      type: "time_window"
      allowed_hours: "06:00-22:00"
      timezone: "America/New_York"
      
  # Data access restrictions
  - name: "no-bulk-export"
    description: "Prevent bulk data exports"
    constraint:
      type: "data_limit"
      max_records_per_request: 100
      max_records_per_day: 1000
      
  # Sensitive operations
  - name: "destructive-action-block"
    description: "Block all destructive actions"
    deny:
      - "*:*:delete"
      - "*:*:purge"
      - "*:admin:*"
```

#### 6.2.2 Apply Policies to Roles

```bash
# Apply policy to sales-rep role
POST /api/v1/admin/policies/apply
{
  "policy_id": "sales-agent-security",
  "target_type": "role",
  "target_id": "sales-rep",
  "enforcement_mode": "enforce"  # or "audit" for testing
}
```

### 6.3 Threat Monitoring

#### 6.3.1 Security Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SECURITY TEAM: THREAT MONITORING                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  🔒 SECURITY OVERVIEW - LAST 24 HOURS                                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                     │     │
│  │  Total Agent Actions: 12,847                                       │     │
│  │  Unique Active Agents: 147                                         │     │
│  │  Permission Denials: 23                                            │     │
│  │  Policy Violations: 2 ⚠️                                           │     │
│  │  Anomalies Detected: 1 🚨                                          │     │
│  │                                                                     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ⚠️  ALERTS REQUIRING ATTENTION:                                            │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  🚨 HIGH: Unusual data access pattern                              │     │
│  │  Agent: agent-john-databot-002                                    │     │
│  │  Issue: Accessed 2,847 unique contact records (normal: 50-100)   │     │
│  │  Time: 2026-02-15 03:42 AM (outside normal hours)                │     │
│  │  [ Investigate ]  [ Suspend Agent ]  [ Contact Owner ]           │     │
│  │                                                                     │     │
│  │  ──────────────────────────────────────────────────────────────── │     │
│  │                                                                     │     │
│  │  ⚠️ MEDIUM: Rate limit approached                                  │     │
│  │  Agent: agent-marketing-assistant-001                             │     │
│  │  Issue: 450 of 500 daily actions used by 10 AM                   │     │
│  │  [ Set Alert ]  [ Increase Limit ]  [ Contact Owner ]            │     │
│  │                                                                     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  PERMISSION DENIALS (Last 24h):                                             │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Permission               │ Denials │ Top Agents                  │     │
│  │  ─────────────────────────┼─────────┼─────────────────────────────│     │
│  │  notion:pages:create      │    8    │ agent-sarah-*, agent-bob-* │     │
│  │  slack:messages:send      │    6    │ agent-marketing-*           │     │
│  │  gmail:messages:read      │    5    │ agent-sales-*               │     │
│  │  financial:reports:read   │    4    │ agent-analyst-*             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.3.2 Anomaly Detection Rules

```yaml
# anomaly-rules.yaml
anomaly_detection:
  - name: "unusual-volume"
    description: "Detect unusual data access volume"
    condition:
      metric: "records_accessed"
      threshold: "3x normal"
      window: "1 hour"
    action: "alert_security"
    
  - name: "off-hours-activity"
    description: "Detect activity outside business hours"
    condition:
      time_outside: "06:00-22:00"
      action_count: ">10"
    action: "alert_security"
    
  - name: "new-permission-usage"
    description: "Alert on first use of sensitive permissions"
    condition:
      permission_pattern: "*:*:delete|*:admin:*"
      first_time: true
    action: "alert_and_log"
```

#### 6.3.3 Tool Call Analytics Dashboard

The Tool Call Analytics Dashboard provides visual insights into MCP tool usage patterns, enabling proactive threat detection.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              SECURITY: TOOL CALL ANALYTICS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  📊 MCP TOOL USAGE ANALYSIS - LAST 7 DAYS                                   │
│                                                                              │
│  ┌─ Tool Call Volume by Backend ─────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  notion     ████████████████████████████████████████  68%  (8,234)   │  │
│  │  slack      ██████████████████                       28%  (3,412)   │  │
│  │  gmail      ████                                      4%    (487)   │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Top 10 Tools Called ─────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  Rank │ Tool                    │ Calls  │ Success │ Denials │ Users │  │
│  │ ──────├─────────────────────────├────────├─────────├─────────├────── │  │
│  │   1   │ notion.search_pages     │  4,521 │  99.8%  │    8    │   89  │  │
│  │   2   │ slack.list_channels     │  2,103 │ 100.0%  │    0    │   67  │  │
│  │   3   │ notion.read_page        │  1,892 │  99.9%  │    2    │   54  │  │
│  │   4   │ slack.search_messages   │  1,309 │ 100.0%  │    0    │   45  │  │
│  │   5   │ gmail.search_messages   │    412 │  98.5%  │    6    │   23  │  │
│  │   6   │ notion.create_page      │    234 │  95.3%  │   11    │   12  │  │
│  │   7   │ slack.send_message      │    198 │  91.4%  │   17    │   28  │  │
│  │   8   │ gmail.list_messages     │     75 │  89.3%  │    8    │    8  │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Permission Denial Analysis ──────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  Total Denials: 52         Denial Rate: 0.43%                         │  │
│  │                                                                        │  │
│  │  By Permission Required:                                               │  │
│  │  • slack:messages:write     (17 denials) - 6 agents, 4 users          │  │
│  │  • notion:pages:create      (11 denials) - 3 agents, 3 users          │  │
│  │  • gmail:messages:read      ( 8 denials) - 2 agents, 2 users          │  │
│  │  • notion:pages:delete      ( 6 denials) - 4 agents, 4 users          │  │
│  │                                                                        │  │
│  │  💡 Insight: 65% of denials are write operations agents weren't       │  │
│  │              delegated. Consider reviewing delegation templates.      │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Delegation Chain Visualization ──────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  Select Agent: [agent-sdr-001            ▼]                           │  │
│  │                                                                        │  │
│  │  sarah@acme.com                                                        │  │
│  │       │                                                                │  │
│  │       ├─ Connected Services                                           │  │
│  │       │   ├─ notion (pages:read, pages:search)                        │  │
│  │       │   └─ slack  (messages:search, channels:list)                   │  │
│  │       │                                                                │  │
│  │       └─ Delegated to: agent-sdr-001                                  │  │
│  │           ├─ notion:pages:read    ✅ Used 234 times                   │  │
│  │           ├─ notion:pages:search  ✅ Used 1,021 times                 │  │
│  │           ├─ slack:messages:search ✅ Used 89 times                    │  │
│  │           └─ slack:channels:list  ⚪ Never used                       │  │
│  │                                                                        │  │
│  │  📊 Permission Utilization: 75% (3 of 4 permissions used)             │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  [ Export Report ] [ Schedule Weekly Digest ] [ Create Alert Rule ]         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Tool Call Analytics API:**

```bash
# Get tool usage summary
curl -s "http://localhost:8000/api/v1/audit/analytics/tools?period=7d" \
  -H "Authorization: Bearer $SECURITY_TOKEN" | jq .

# Get permission denial breakdown
curl -s "http://localhost:8000/api/v1/audit/analytics/denials?group_by=permission" \
  -H "Authorization: Bearer $SECURITY_TOKEN" | jq .

# Get delegation utilization for a user
curl -s "http://localhost:8000/api/v1/audit/analytics/delegations?user_id=sarah@acme.com" \
  -H "Authorization: Bearer $SECURITY_TOKEN" | jq .

# Export compliance report
curl -s "http://localhost:8000/api/v1/audit/reports/generate" \
  -H "Authorization: Bearer $SECURITY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "soc2", "period": "2026-Q1", "format": "pdf"}' \
  -o compliance_report_q1.pdf
```

### 6.4 Audit and Compliance

#### 6.4.1 Audit Queries

```bash
# Query all actions by a specific user's agents
curl -X GET "http://localhost:8000/api/v1/audit/events?user_id=sarah@acme.com&limit=100" \
  -H "Authorization: Bearer $SECURITY_TOKEN"

# Query permission denials for compliance report
curl -X GET "http://localhost:8000/api/v1/audit/events?event_type=permission_denied&start_date=2026-01-01" \
  -H "Authorization: Bearer $SECURITY_TOKEN"

# Query all actions on sensitive data
curl -X GET "http://localhost:8000/api/v1/audit/events?tool_pattern=financial.*&limit=500" \
  -H "Authorization: Bearer $SECURITY_TOKEN"
```

**Response:**
```json
{
  "events": [
    {
      "id": "evt-abc123",
      "timestamp": "2026-02-15T10:15:32Z",
      "event_type": "tool_call",
      "agent_id": "agent-sarah-salesassist-001",
      "on_behalf_of": "sarah@acme.com",
      "delegation_id": "del-xyz789",
      "tool": "notion.search_pages",
      "arguments": {"query": "competitor analysis"},
      "result": "success",
      "result_summary": "3 pages found"
    }
  ],
  "total": 47,
  "page": 1
}
```

#### 6.4.2 Compliance Reports

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SECURITY TEAM: COMPLIANCE REPORTS                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  AVAILABLE REPORTS:                                                         │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                    │     │
│  │  📊 SOC2 Agent Activity Report                                     │     │
│  │  Period: Q1 2026                                                   │     │
│  │  Contents: All agent actions with human attribution                │     │
│  │  [ Generate ]  [ Schedule Monthly ]                                │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │
│  │  📊 PII Access Report                                              │     │
│  │  Period: Last 30 Days                                              │     │
│  │  Contents: All access to customer PII data                         │     │
│  │  [ Generate ]  [ Schedule Weekly ]                                 │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │
│  │  📊 Permission Denial Analysis                                     │     │
│  │  Period: Last 90 Days                                              │     │
│  │  Contents: All blocked actions with reasons                        │     │
│  │  [ Generate ]                                                      │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │
│  │  📊 Delegation Chain Audit                                         │     │
│  │  Period: Last 30 Days                                              │     │
│  │  Contents: Full delegation hierarchy for all actions               │     │
│  │  [ Generate ]                                                      │     │
│  │                                                                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.5 Incident Response

#### 6.5.1 Incident Response Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SECURITY TEAM: INCIDENT RESPONSE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INCIDENT: Suspected Data Exfiltration                                      │
│  Agent: agent-john-databot-002                                              │
│  Severity: HIGH                                                             │
│                                                                              │
│  RESPONSE TIMELINE:                                                         │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 1: CONTAIN (Immediate)                                        │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │                                                                      │    │
│  │  [ ✅ DONE ] Suspend agent                                          │    │
│  │  POST /api/v1/admin/agents/agent-john-databot-002/suspend           │    │
│  │                                                                      │    │
│  │  [ ✅ DONE ] Revoke all delegations                                 │    │
│  │  POST /api/v1/admin/delegations/revoke-all?agent_id=agent-john-*    │    │
│  │                                                                      │    │
│  │  [ ✅ DONE ] Notify agent owner                                     │    │
│  │  Automated email sent to john@acme.com                              │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 2: INVESTIGATE                                                │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │                                                                      │    │
│  │  [ IN PROGRESS ] Pull complete audit trail                         │    │
│  │  GET /api/v1/audit/events?agent_id=agent-john-databot-002          │    │
│  │                                                                      │    │
│  │  [ PENDING ] Analyze data access patterns                          │    │
│  │  [ PENDING ] Identify scope of potential breach                    │    │
│  │  [ PENDING ] Determine root cause                                  │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 3: REMEDIATE                                                  │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │                                                                      │    │
│  │  [ PENDING ] Rotate affected credentials                           │    │
│  │  [ PENDING ] Update policies to prevent recurrence                 │    │
│  │  [ PENDING ] Document findings                                     │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.6 Security Team Daily Operations

| Task | Frequency | Actions |
|------|-----------|---------|
| **Review security alerts** | Daily | Investigate and resolve flagged anomalies |
| **Check policy violations** | Daily | Review denied actions for policy gaps |
| **Update anomaly rules** | Weekly | Tune detection based on new patterns |
| **Audit random samples** | Weekly | Spot-check agent activity for compliance |
| **Generate compliance reports** | Monthly | SOC2, HIPAA, internal audit reports |
| **Policy review** | Quarterly | Ensure policies align with security requirements |

---

## 7. Engineering Team

### 7.1 Role Overview

| Aspect | Description |
|--------|-------------|
| **Primary Goal** | Build and deploy AI agents that integrate with enterprise tools |
| **Key Concerns** | Easy integration, reliable operation, no credential handling |
| **Access Level** | Developer access with ability to register and test agents |

### 7.2 SDK Integration

#### 7.2.1 Install DeepSecure SDK

```bash
# Install the SDK
pip install deepsecure

# Or with development dependencies
pip install deepsecure[dev]
```

#### 7.2.2 Initialize Client

```python
import deepsecure

# Initialize the client (automatically handles authentication)
client = deepsecure.Client(
    control_plane_url="http://localhost:8000",
    gateway_url="http://localhost:8002"
)

# Authenticate (for testing/development)
client.configure(
    token="your_agent_jwt_token"
)
```

### 7.3 Agent Development

#### 7.3.1 Register Agent Programmatically

```python
import deepsecure
from deepsecure.crypto import KeyManager

# Generate Ed25519 key pair for agent identity
key_manager = KeyManager()
public_key = key_manager.get_public_key_base64()

# Register agent with control plane
response = client.agents.create(
    name="my-sales-assistant",
    description="Automates sales research and outreach",
    public_key=public_key,
    metadata={
        "team": "sales",
        "version": "1.0.0"
    }
)

agent_id = response.agent_id
print(f"Agent registered: {agent_id}")
```

#### 7.3.2 Agent Authentication Flow

```python
# Agent authenticates using challenge-response
from deepsecure._core.identity_manager import AgentIdentityManager

identity = AgentIdentityManager(agent_id="my-sales-assistant")

# Get challenge from control plane
challenge = client.auth.get_challenge(agent_id=identity.agent_id)

# Sign challenge with private key
signature = identity.sign_challenge(challenge.nonce)

# Verify and get session JWT
session = client.auth.verify_challenge(
    agent_id=identity.agent_id,
    challenge=challenge.nonce,
    signature=signature
)

agent_jwt = session.token
print(f"Agent authenticated, JWT expires in {session.expires_in}s")
```

#### 7.3.3 MCP Tool Calls

```python
import httpx

# Agent connects to Virtual MCP Server
async def call_mcp_tool():
    async with httpx.AsyncClient() as client:
        # Initialize MCP session
        init_response = await client.post(
            "http://localhost:8002/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "MySalesAgent", "version": "1.0.0"}
                }
            }
        )
        print(f"MCP initialized: {init_response.json()}")
        
        # List available tools (filtered by delegation)
        tools_response = await client.post(
            "http://localhost:8002/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
        )
        tools = tools_response.json()["result"]["tools"]
        print(f"Available tools: {[t['name'] for t in tools]}")
        
        # Call a tool
        result = await client.post(
            "http://localhost:8002/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "notion.search_pages",
                    "arguments": {"query": "competitor analysis", "limit": 5}
                }
            }
        )
        print(f"Tool result: {result.json()}")
```

### 7.4 Framework Integrations

#### 7.4.1 LangChain Integration

```python
from langchain.agents import AgentExecutor
from deepsecure.integrations.langchain import DeepSecureMCPToolkit

# Initialize DeepSecure toolkit
toolkit = DeepSecureMCPToolkit(
    gateway_url="http://localhost:8002",
    agent_jwt=agent_jwt
)

# Get LangChain-compatible tools
tools = toolkit.get_tools()

# Use with LangChain agent
agent = AgentExecutor.from_agent_and_tools(
    agent=your_agent,
    tools=tools,
    verbose=True
)

# Tools automatically use DeepSecure for credential injection
result = agent.run("Find competitor analysis documents in Notion")
```

#### 7.4.2 CrewAI Integration

```python
from crewai import Agent, Task, Crew
from deepsecure.integrations.crewai import DeepSecureCrewTools

# Initialize DeepSecure tools for CrewAI
ds_tools = DeepSecureCrewTools(
    gateway_url="http://localhost:8002",
    agent_jwt=agent_jwt
)

# Create CrewAI agent with DeepSecure tools
researcher = Agent(
    role="Sales Researcher",
    goal="Find competitive intelligence",
    tools=ds_tools.get_tools(),
    verbose=True
)

# Tools handle authentication and credential injection automatically
```

### 7.5 Building Custom MCP Servers

#### 7.5.1 Create Internal MCP Server

```python
# internal_api_mcp_server.py
from mcp.server import Server
from mcp.server.models import Tool, TextContent

app = Server("internal-api")

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_employee_info",
            description="Get employee information by email",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string"}
                },
                "required": ["email"]
            }
        ),
        Tool(
            name="search_internal_docs",
            description="Search internal documentation",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_employee_info":
        # Implement your internal API call
        employee = await internal_hr_api.get_employee(arguments["email"])
        return [TextContent(type="text", text=str(employee))]
    elif name == "search_internal_docs":
        results = await internal_docs_api.search(arguments["query"])
        return [TextContent(type="text", text=str(results))]
```

#### 7.5.2 Register with DeepSecure Gateway

```bash
# Register MCP server with gateway
POST /api/v1/admin/mcp-registry/servers
{
  "id": "internal-api",
  "display_name": "Internal API Server",
  "endpoint": "http://internal-mcp:8080",
  "transport": "streamable-http",
  "data_classification": "confidential",
  "available_to_roles": ["employee"],
  "status": "sandbox"
}
```

### 7.6 Testing and Deployment

#### 7.6.1 Local Development Testing

```bash
# Start local DeepSecure services
docker compose up -d db redis deeptrail-control deeptrail-gateway

# Run integration tests
pytest tests/integration/ -v

# Test MCP flow manually
python scripts/test_mcp_flow.py
```

#### 7.6.2 CI/CD Integration

```yaml
# .github/workflows/agent-deploy.yml
name: Deploy Agent

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install deepsecure[dev]
          
      - name: Run tests
        env:
          DEEPSECURE_CONTROL_URL: ${{ secrets.DEEPSECURE_CONTROL_URL }}
        run: pytest tests/ -v
        
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy agent
        run: |
          # Agent deployment logic
          echo "Deploying agent..."
```

#### 7.6.3 MCP Debug Console

Engineers can use the MCP Debug Console to inspect sessions, trace tool calls, and debug issues.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              ENGINEERING: MCP DEBUG CONSOLE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Agent: agent-sdr-001                Session: mcpsess-abc123                │
│  Status: ✅ Connected                 Backends: notion, slack               │
│  Delegation: del-xyz789              Expires: 2026-02-16 10:00:00           │
│                                                                              │
│  ┌─ Session Details ─────────────────────────────────────────────────────┐  │
│  │  Protocol Version: 2024-11-05                                         │  │
│  │  Client Info: MySalesAgent v1.0.0                                     │  │
│  │  Initialized: 2026-02-15 10:15:01                                     │  │
│  │  Allowed Permissions: notion:pages:read, slack:messages:search        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ MCP Call Trace ──────────────────────────────────────────────────────┐  │
│  │  #  │ Method        │ Tool               │ Status │ Latency │ Time   │  │
│  │ ────├───────────────├────────────────────├────────├─────────├─────── │  │
│  │  1  │ initialize    │ -                  │ ✅ 200 │   45ms  │ 10:15:01│ │
│  │  2  │ tools/list    │ -                  │ ✅ 200 │   23ms  │ 10:15:02│ │
│  │  3  │ tools/call    │ notion.search_pages│ ✅ 200 │  234ms  │ 10:15:05│ │
│  │  4  │ tools/call    │ slack.send_message │ ❌ 403 │   12ms  │ 10:15:08│ │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Call #4 Details (Click to expand) ───────────────────────────────────┐  │
│  │                                                                        │  │
│  │  ❌ PERMISSION DENIED                                                  │  │
│  │                                                                        │  │
│  │  Required Permission: slack:messages:write                            │  │
│  │  Agent Has: [slack:messages:search, slack:channels:list]              │  │
│  │                                                                        │  │
│  │  Request:                                                              │  │
│  │  {                                                                     │  │
│  │    "method": "tools/call",                                             │  │
│  │    "params": {                                                         │  │
│  │      "name": "slack.send_message",                                     │  │
│  │      "arguments": {"channel": "#sales", "text": "Hello"}              │  │
│  │    }                                                                   │  │
│  │  }                                                                     │  │
│  │                                                                        │  │
│  │  Response:                                                             │  │
│  │  {                                                                     │  │
│  │    "error": {                                                          │  │
│  │      "code": -32001,                                                   │  │
│  │      "message": "Permission denied: slack:messages:write required"    │  │
│  │    }                                                                   │  │
│  │  }                                                                     │  │
│  │                                                                        │  │
│  │  💡 Fix: Ask user to add slack:messages:write to delegation           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  [ Copy cURL ] [ Replay Call ] [ View Audit Log ] [ Export Trace ]          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Debug Console API (for programmatic access):**

```bash
# Get active sessions for an agent
curl -s "http://localhost:8002/debug/sessions?agent_id=agent-sdr-001" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

# Get call trace for a session
curl -s "http://localhost:8002/debug/sessions/mcpsess-abc123/trace" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

# Replay a specific call (dry-run)
curl -s "http://localhost:8002/debug/replay/call-id-xyz" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "X-Debug-DryRun: true" | jq .
```

### 7.7 Engineering Team Workflow

| Phase | Tasks | Tools/Commands |
|-------|-------|----------------|
| **Setup** | Install SDK, configure environment | `pip install deepsecure` |
| **Development** | Build agent, integrate MCP | Python + DeepSecure SDK |
| **Testing** | Test locally, integration tests | `pytest`, manual MCP calls |
| **Registration** | Register agent with Control Plane | `client.agents.create()` |
| **Deployment** | Deploy to production | CI/CD pipeline |
| **Monitoring** | Monitor agent health, logs | Audit API, logs |

---

## 8. Vendor Admin (Multi-User Agent Model)

> **Added May 2026** — Based on customer conversation with Scale Agentic (Victor). This persona manages agents that serve multiple human users within a customer organization.

### 8.1 Role Overview

| Aspect | Description |
|--------|-------------|
| **Primary Goal** | Deploy one agent per customer that serves multiple human users, each with their own delegated permissions |
| **Key Concerns** | Multi-user isolation, per-user token management, company-level agent identity, scalable onboarding |
| **Access Level** | Admin-level agent registration + monitoring; delegates per-user permission management to individual users |

### 8.2 Multi-User Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│            VENDOR ADMIN: MULTI-USER AGENT MODEL                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CURRENT MODEL (Single-User):          MULTI-USER MODEL (Scale Agentic):   │
│  ─────────────────────────────          ───────────────────────────────     │
│                                                                             │
│  1 User → 1 Agent → 1 Token Set        1 Agent → N Users → N Token Sets   │
│                                                                             │
│  ┌────────┐    ┌────────┐              ┌────────────────────┐              │
│  │ Sarah  │───▶│ Agent  │              │    Sales Agent     │              │
│  │        │    │        │              │  (1 SA / 1 WI)     │              │
│  │ tokens │    │ tools  │              └─────────┬──────────┘              │
│  └────────┘    └────────┘                        │                         │
│                                         ┌────────┼────────┐                │
│                                         ▼        ▼        ▼                │
│                                    ┌────────┐┌────────┐┌────────┐          │
│                                    │ User A ││ User B ││ User C │          │
│                                    │        ││        ││        │          │
│                                    │ Notion ││ Notion ││ Notion │          │
│                                    │ Slack  ││ Slack  ││ Gmail  │          │
│                                    │ Gmail  ││ (read) ││ Cal    │          │
│                                    │ (full) ││        ││(read)  │          │
│                                    └────────┘└────────┘└────────┘          │
│                                                                             │
│  KEY: Each user has their own OAuth tokens + permission scope.              │
│       Agent dynamically selects user context per tool call.                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Vendor Admin: Register Agent for Company

```
┌─────────────────────────────────────────────────────────────────────────────┐
│            VENDOR ADMIN: REGISTER COMPANY AGENT                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: Register Agent (Admin)                                            │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Register Company Agent                                            │     │
│  │                                                                    │     │
│  │  Agent Name: [Scale Sales Agent_______________]                   │     │
│  │  Company: [Deep Trail Inc ▼]                                      │     │
│  │  Identity Method: ● GCP Workload Identity                         │     │
│  │  SA Email: [scale-sales-sa@customer-project.iam.gserviceaccount.com]│    │
│  │                                                                    │     │
│  │  ⚠️ One service account per customer (company-level identity)     │     │
│  │                                                                    │     │
│  │  [ Register Agent ]                                                │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  STEP 2: Agent Registered — Users Onboard Independently                    │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  ✅ Agent Registered: scale-sales-agent (agent-xxx-yyy-zzz)                │
│  ✅ Attestation Policy Created (GCP WI + SA email)                          │
│  📋 Deploy Instructions: [View GCP Setup Commands]                          │
│                                                                             │
│  Next: Individual users log in and delegate their own permissions.          │
│  Agent will access each user's services based on their delegation.          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.4 User Self-Service Delegation (Per-User)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│            USER: SELF-SERVICE DELEGATION TO COMPANY AGENT                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Welcome, Victor! Your admin has registered "Scale Sales Agent"             │
│  for your company. Delegate your permissions below.                         │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  DELEGATE YOUR PERMISSIONS TO: Scale Sales Agent                   │     │
│  │                                                                    │     │
│  │  YOUR CONNECTED SERVICES:                                         │     │
│  │  ✅ Google Calendar (victor@deeptrail.com)                         │     │
│  │  ✅ Gmail (victor@deeptrail.com)                                   │     │
│  │  ✅ Notion (Victor's workspace)                                    │     │
│  │  ⚠️ Slack (not connected) [Connect Now]                           │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │
│  │  GOOGLE CALENDAR:                                                  │     │
│  │  ☑ List events (gcalendar:events:list)                             │     │
│  │  ☐ Create events (gcalendar:events:create)                         │     │
│  │                                                                    │     │
│  │  GMAIL:                                                            │     │
│  │  ☑ Search messages (gmail:messages:search)                         │     │
│  │  ☐ Send messages (gmail:messages:send) ← Victor opts out          │     │
│  │                                                                    │     │
│  │  NOTION:                                                           │     │
│  │  ☑ Search pages (notion:pages:search)                              │     │
│  │  ☑ Read pages (notion:pages:read)                                  │     │
│  │                                                                    │     │
│  │  Expires in: [7 days ▼]                                            │     │
│  │                                                                    │     │
│  │  [ Create Delegation ]                                             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ℹ️ Other users in your company can grant different permissions.            │
│  The agent will only access YOUR data with YOUR permission level.           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.5 Agent → Users → Tokens Mapping (Admin View)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│            VENDOR ADMIN: AGENT USER MAPPING VIEW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  AGENT: Scale Sales Agent (agent-xxx-yyy-zzz)                              │
│  Status: ● Active | Last Activity: 2 min ago                               │
│  Identity: GCP WI (scale-sales-sa@customer-project.iam...)                 │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  DELEGATING USERS (3)                                              │     │
│  │                                                                    │     │
│  │  User           │ Services        │ Permissions       │ Expires   │     │
│  │  ────────────── │ ─────────────── │ ──────────────── │ ───────── │     │
│  │  mahendra@      │ Notion, Slack,  │ Full access       │ 6 days   │     │
│  │  deeptrail.com  │ Gmail, Cal      │ (8 permissions)   │           │     │
│  │                 │                 │                    │           │     │
│  │  victor@        │ Notion, Gmail,  │ Read-only         │ 4 days   │     │
│  │  deeptrail.com  │ Calendar        │ (5 permissions)   │           │     │
│  │                 │                 │ ⚠️ No send email  │           │     │
│  │                 │                 │                    │           │     │
│  │  priya@         │ Slack, Notion   │ Slack full,       │ 2 days   │     │
│  │  deeptrail.com  │                 │ Notion read       │           │     │
│  │                 │                 │ (4 permissions)   │           │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │
│  │  RECENT TOOL CALLS (by user context):                             │     │
│  │                                                                    │     │
│  │  Time     │ User     │ Tool                │ Result               │     │
│  │  ──────── │ ──────── │ ─────────────────── │ ──────────────────── │     │
│  │  10:15:32 │ mahendra │ notion.search_pages │ ✅ 3 pages found     │     │
│  │  10:16:01 │ victor   │ gcalendar.list      │ ✅ 5 events          │     │
│  │  10:16:45 │ priya    │ slack.send_message  │ ✅ Sent to #general  │     │
│  │  10:17:12 │ victor   │ gmail.send_message  │ ❌ Denied (not dele) │     │
│  │                                                                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.6 Multi-User Tool Call Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│            HOW MULTI-USER TOOL CALLS WORK                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Agent bootstraps (gets Agent JWT via GCP Workload Identity)             │
│                                                                             │
│  2. Agent has a task: "Check Victor's calendar for conflicts"               │
│                                                                             │
│  3. Agent makes MCP tool call WITH user context:                            │
│     POST /mcp                                                               │
│     {                                                                       │
│       "method": "tools/call",                                               │
│       "params": {                                                           │
│         "name": "gcalendar.events_list",                                    │
│         "arguments": { "date": "2026-05-27" },                              │
│         "meta": { "user_id": "victor@deeptrail.com" }   ← WHO              │
│       }                                                                     │
│     }                                                                       │
│                                                                             │
│  4. Gateway resolves:                                                       │
│     a. Agent JWT valid? ✅                                                   │
│     b. Find delegation for victor@deeptrail.com + this agent ✅              │
│     c. Does delegation include gcalendar:events:list? ✅                     │
│     d. Get Victor's OAuth token from vault ✅                                │
│     e. Call Google Calendar API with Victor's token                          │
│                                                                             │
│  5. If agent next asks "Send email as Mahendra":                            │
│     a. Find delegation for mahendra@deeptrail.com + this agent ✅            │
│     b. Does delegation include gmail:messages:send? ✅                       │
│     c. Get Mahendra's OAuth token from vault ✅                              │
│     d. Call Gmail API with Mahendra's token                                 │
│                                                                             │
│  KEY: Same agent, same JWT, but different user tokens per call.             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.7 Vendor Admin Daily Workflow

| Time | Action | Description |
|------|--------|-------------|
| **Morning** | Check agent fleet | Verify all customer agents are Active, review any failures |
| **As Needed** | User onboarding | New users log in and delegate; no admin action needed |
| **If Issues** | Token conflicts | Check which user's tokens expired; notify user to re-authorize |
| **Weekly** | Delegation review | Review expiring delegations; remind users to renew |
| **Monthly** | Usage report | Per-user tool call stats, permission utilization |

### 8.8 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| SA per customer (not per user) | 1 SA = 1 company | Prevents data mixing across tenants; simpler identity model |
| Users self-delegate | No admin action per user | Scales to N users without admin bottleneck |
| `user_id` in tool call | Agent specifies per-call | Agent decides whose context to use based on task |
| Per-user permission levels | Different scopes per user | Victor: read-only email; Mahendra: full email access |
| Delegation renewal | Per-user, independent | Each user manages their own TTL |

---

## 9. Cross-Persona Workflows

### 9.1 New Agent Rollout (All Personas)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CROSS-PERSONA: NEW AGENT ROLLOUT                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: PLANNING                                                          │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Engineering: "We want to deploy a new Sales AI Agent"                      │
│       │                                                                      │
│       ▼                                                                      │
│  Security: Reviews requirements, defines policies                           │
│       │                                                                      │
│       ▼                                                                      │
│  IT Admin: Approves vendor, configures service access                       │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│  PHASE 2: DEVELOPMENT                                                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Engineering: Builds agent using DeepSecure SDK                             │
│       │                                                                      │
│       ▼                                                                      │
│  Security: Reviews agent code, tests in sandbox                             │
│       │                                                                      │
│       ▼                                                                      │
│  IT Admin: Registers agent in approved vendor list                          │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│  PHASE 3: DEPLOYMENT                                                        │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  IT Admin: Enables agent for employee self-service                          │
│       │                                                                      │
│       ▼                                                                      │
│  Employee: Registers agent, connects services, creates delegation           │
│       │                                                                      │
│       ▼                                                                      │
│  Engineering: Monitors deployment, addresses issues                         │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│  PHASE 4: OPERATIONS                                                        │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Employee: Uses agent daily, monitors activity                              │
│       │                                                                      │
│       ▼                                                                      │
│  Security: Monitors for anomalies, reviews audit logs                       │
│       │                                                                      │
│       ▼                                                                      │
│  IT Admin: Handles escalations, periodic reviews                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Security Incident Response (Security + IT Admin)

| Step | Security Team | IT Admin |
|------|---------------|----------|
| **1. Detection** | Anomaly detected in monitoring | Receives alert notification |
| **2. Containment** | Requests agent suspension | Executes suspension in console |
| **3. Investigation** | Pulls audit logs, analyzes patterns | Contacts agent owner |
| **4. Remediation** | Updates policies | Revokes credentials, updates config |
| **5. Recovery** | Verifies fixes | Re-enables agent if appropriate |
| **6. Post-Mortem** | Documents findings | Updates procedures |

### 9.3 Employee Offboarding (IT Admin + Security)

```
OFFBOARDING TRIGGER: Employee deactivated in IdP (Okta/Azure AD)

AUTOMATIC ACTIONS (via IdP integration):
1. User session invalidated in DeepSecure
2. All active delegations revoked immediately
3. All agent sessions terminated
4. Audit event logged

IT ADMIN VERIFICATION:
1. Confirm user no longer appears in active users
2. Verify no orphaned agents remain
3. Review audit trail for last actions

SECURITY TEAM REVIEW:
1. Spot-check audit logs for offboarded user
2. Verify no data exfiltration in final days
3. Document in compliance records
```

---

## 10. Appendix: Quick Reference

### 10.1 Persona Capabilities Matrix

| Capability | IT Admin | Employee | Security | Engineering | Vendor Admin |
|------------|:--------:|:--------:|:--------:|:-----------:|:------------:|
| Deploy/configure platform | ✅ | ❌ | ❌ | ❌ | ❌ |
| Configure IdP integration | ✅ | ❌ | ❌ | ❌ | ❌ |
| Approve services | ✅ | ❌ | ✅ | ❌ | ❌ |
| Approve vendor agents | ✅ | ❌ | ✅ | ❌ | ❌ |
| Define security policies | ❌ | ❌ | ✅ | ❌ | ❌ |
| Emergency suspension | ✅ | ❌ | ✅ | ❌ | ❌ |
| Connect personal services | ❌ | ✅ | ❌ | ❌ | ❌ |
| Create delegations | ❌ | ✅ | ❌ | ❌ | ❌ |
| View own agent activity | ❌ | ✅ | ❌ | ❌ | ✅ |
| View all audit logs | ✅ | ❌ | ✅ | ❌ | ❌ |
| Build/deploy agents | ❌ | ❌ | ❌ | ✅ | ✅ |
| Register MCP servers | ✅ | ❌ | ❌ | ✅ | ❌ |
| Register agents for customers | ❌ | ❌ | ❌ | ❌ | ✅ |
| View multi-user agent mapping | ❌ | ❌ | ❌ | ❌ | ✅ |
| Manage fleet across customers | ❌ | ❌ | ❌ | ❌ | ✅ |

### 10.2 Key API Endpoints by Persona

| Persona | Endpoint | Purpose |
|---------|----------|---------|
| **IT Admin** | `POST /api/v1/admin/organizations` | Register organization |
| **IT Admin** | `POST /api/v1/admin/services` | Approve services |
| **IT Admin** | `POST /api/v1/admin/agents/{id}/suspend` | Suspend agent |
| **Employee** | `POST /api/v1/users/me/services/connect` | Connect service |
| **Employee** | `POST /api/v1/delegations/delegate` | Create delegation |
| **Employee** | `GET /api/v1/audit/events?agent_id=X` | View agent activity |
| **Security** | `POST /api/v1/admin/policies` | Create policy |
| **Security** | `GET /api/v1/audit/events` | Query audit logs |
| **Engineering** | `POST /api/v1/agents` | Register agent |
| **Engineering** | `POST /api/v1/auth/agent/challenge` | Agent auth |
| **Engineering** | `POST /mcp` | MCP tool calls |
| **Vendor Admin** | `POST /api/v1/agents` | Register agent for customer |
| **Vendor Admin** | `GET /api/v1/agents/{id}/delegations` | View all user delegations |
| **Vendor Admin** | `POST /mcp` (with `meta.user_id`) | Multi-user tool calls |

### 10.3 Common Commands

```bash
# IT Admin: Check system health
curl http://localhost:8000/health
curl http://localhost:8002/health

# Employee: Login and get token
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@acme.com", "password": "password"}' | jq -r '.token')

# Employee: Connect service
curl -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service_id": "notion", "oauth_token": {...}}'

# Security: Query audit events
curl -X GET "http://localhost:8000/api/v1/audit/events?limit=100" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Engineering: Test MCP tool call
curl -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | February 2026 | Initial comprehensive use case document |
