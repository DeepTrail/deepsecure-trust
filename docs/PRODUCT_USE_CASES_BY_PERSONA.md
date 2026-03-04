# DeepSecure: End-to-End Product Use Cases by Persona

> **Product Use Cases Guide** | Version 1.0 | February 2026
>
> This document describes how different enterprise personas interact with the DeepSecure platform, from initial setup through daily operations.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Persona Overview](#2-persona-overview)
3. [IT Administrator](#3-it-administrator)
4. [Employee (End User)](#4-employee-end-user)
5. [Security Team](#5-security-team)
6. [Engineering Team](#6-engineering-team)
7. [Cross-Persona Workflows](#7-cross-persona-workflows)
8. [Appendix: Quick Reference](#8-appendix-quick-reference)

---

## 1. Executive Summary

DeepSecure enables enterprises to securely deploy AI agents while maintaining control, compliance, and accountability. Each persona interacts with the platform differently:

| Persona | Primary Interactions | Key Value |
|---------|---------------------|-----------|
| **IT Administrator** | Setup, governance, emergency controls | Control without blocking productivity |
| **Employee** | Connect services, delegate to agents, monitor activity | Self-service with guardrails |
| **Security Team** | Policy definition, threat monitoring, incident response | Zero-trust enforcement, complete audit |
| **Engineering Team** | Build agents, integrate SDK, test & deploy | Simple integration, no credential handling |

---

## 2. Persona Overview

### 2.1 Persona Definitions

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
│                    ┌──────────────────────────┐                             │
│                    │    ENGINEERING TEAM      │                             │
│                    │                          │                             │
│                    │  • Agent development     │                             │
│                    │  • SDK integration       │                             │
│                    │  • MCP server creation   │                             │
│                    │  • Testing & deployment  │                             │
│                    └──────────────────────────┘                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Interaction Timeline

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

## 3. IT Administrator

### 3.1 Role Overview

| Aspect | Description |
|--------|-------------|
| **Primary Goal** | Enable AI agent adoption while maintaining security and control |
| **Key Concerns** | Shadow AI, compliance, emergency response, operational overhead |
| **Access Level** | Organization administrator with full platform control |

### 3.2 Initial Platform Setup

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

### 3.3 Service and Agent Governance

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
│  │  hubspot-mcp      │ ✅ Active │ Sales, Marketing    │ Confidential  │    │
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
│  │  hubspot:contacts:read         ✅ Allowed                         │      │
│  │  hubspot:contacts:create       ✅ Allowed                         │      │
│  │  hubspot:contacts:update       ✅ Allowed                         │      │
│  │  hubspot:contacts:delete       ❌ Blocked (destructive action)    │      │
│  │  hubspot:deals:read            ✅ Allowed                         │      │
│  │  hubspot:deals:update          ✅ Allowed                         │      │
│  │  hubspot:settings:*            ❌ Blocked (admin-only)            │      │
│  │  slack:messages:read           ✅ Allowed                         │      │
│  │  slack:messages:send           ✅ Allowed                         │      │
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

### 3.4 Emergency Controls

#### 3.4.1 Agent Suspension

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

#### 3.4.2 Global Circuit Breaker

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

### 3.5 IT Admin Daily Operations

| Task | Frequency | Actions |
|------|-----------|---------|
| **Review new agent registrations** | Daily | Approve/deny pending registrations |
| **Check service health** | Daily | Monitor Control Plane and Gateway status |
| **Review security alerts** | Daily | Address flagged anomalies |
| **Audit dormant agents** | Weekly | Identify and disable inactive agents |
| **Role permission review** | Monthly | Ensure roles align with business needs |
| **Vendor compliance check** | Quarterly | Verify approved vendors remain compliant |

---

## 4. Employee (End User)

### 4.1 Role Overview

| Aspect | Description |
|--------|-------------|
| **Primary Goal** | Use AI agents to automate tasks and increase productivity |
| **Key Concerns** | Easy setup, reliable operation, confidence in security |
| **Access Level** | Self-service within IT-defined guardrails |

### 4.2 Initial Onboarding

#### 4.2.1 First-Time Login

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

### 4.3 Connecting Services

#### 4.3.1 Connect to External Services via OAuth

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMPLOYEE: CONNECT SERVICES                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  AVAILABLE SERVICES FOR YOUR ROLE (Sales Representative):                   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                     │     │
│  │  📊 HubSpot CRM                                                    │     │
│  │  Access contacts, deals, and sales data                           │     │
│  │  Status: Not Connected                                             │     │
│  │  [ Connect HubSpot ]                                               │     │
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
│  OAUTH CONSENT FLOW (When clicking "Connect HubSpot"):                      │
│                                                                              │
│  1. Browser redirects to HubSpot OAuth                                      │
│  2. Sarah sees HubSpot consent screen:                                      │
│     "DeepSecure wants to access your HubSpot data"                         │
│     ☑ View contacts   ☑ Edit contacts   ☑ View deals                       │
│  3. Sarah clicks "Allow"                                                    │
│  4. HubSpot returns OAuth tokens to DeepSecure                             │
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

### 4.4 Registering an Agent

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

### 4.5 Creating a Delegation

#### 4.5.1 Delegate Permissions to Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMPLOYEE: CREATE DELEGATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DELEGATE PERMISSIONS TO: My Sales Assistant                                │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  HUBSPOT PERMISSIONS:                                              │     │ 
│  │                                                                    │     │
│  │  ☑ Read contacts (hubspot:contacts:read)                           │     │
│  │  ☑ Create contacts (hubspot:contacts:create)                       │     │
│  │  ☐ Update contacts (hubspot:contacts:update)                       │     │
│  │  🔒 Delete contacts - Not available for your role                  │     │
│  │                                                                    │     │
│  │  ☑ Read deals (hubspot:deals:read)                                 │     │
│  │  ☐ Update deals (hubspot:deals:update)                             │     │
│  │                                                                    │     │
│  │  ────────────────────────────────────────────────────────────────  │     │
│  │                                                                    │     │
│  │  SLACK PERMISSIONS:                                                │     │
│  │                                                                    │     │
│  │  ☑ Read messages (slack:messages:read)                             │     │
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
      "slack:channels:list",
      "hubspot:contacts:read"
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
    "slack:channels:list",
    "hubspot:contacts:read"
  ],
  "expires_in": 604800
}
```

### 4.6 Monitoring Agent Activity

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
│  │  10:18:03    │ hubspot.get_contacts   │ ✅ Success │ 5 contacts    │     │
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

### 4.7 Employee Daily Workflow

| Time | Action | Description |
|------|--------|-------------|
| **Morning** | Check agent status | Verify agent is active, review overnight activity |
| **Throughout Day** | Agent operates | Agent performs delegated tasks automatically |
| **As Needed** | Review activity | Check what agent has done, verify results |
| **If Issues** | Adjust/revoke | Modify permissions or revoke delegation |
| **Weekly** | Renew delegation | Extend or recreate expiring delegations |

---

## 5. Security Team

### 5.1 Role Overview

| Aspect | Description |
|--------|-------------|
| **Primary Goal** | Ensure AI agent deployments meet security and compliance requirements |
| **Key Concerns** | Threat detection, policy enforcement, incident response, compliance |
| **Access Level** | Security administrator with audit and policy access |

### 5.2 Policy Definition

#### 5.2.1 Create Security Policies

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

#### 5.2.2 Apply Policies to Roles

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

### 5.3 Threat Monitoring

#### 5.3.1 Security Dashboard

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
│  │  hubspot:contacts:delete  │    5    │ agent-sales-*               │     │
│  │  financial:reports:read   │    4    │ agent-analyst-*             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.3.2 Anomaly Detection Rules

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

### 5.4 Audit and Compliance

#### 5.4.1 Audit Queries

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

#### 5.4.2 Compliance Reports

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

### 5.5 Incident Response

#### 5.5.1 Incident Response Workflow

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

### 5.6 Security Team Daily Operations

| Task | Frequency | Actions |
|------|-----------|---------|
| **Review security alerts** | Daily | Investigate and resolve flagged anomalies |
| **Check policy violations** | Daily | Review denied actions for policy gaps |
| **Update anomaly rules** | Weekly | Tune detection based on new patterns |
| **Audit random samples** | Weekly | Spot-check agent activity for compliance |
| **Generate compliance reports** | Monthly | SOC2, HIPAA, internal audit reports |
| **Policy review** | Quarterly | Ensure policies align with security requirements |

---

## 6. Engineering Team

### 6.1 Role Overview

| Aspect | Description |
|--------|-------------|
| **Primary Goal** | Build and deploy AI agents that integrate with enterprise tools |
| **Key Concerns** | Easy integration, reliable operation, no credential handling |
| **Access Level** | Developer access with ability to register and test agents |

### 6.2 SDK Integration

#### 6.2.1 Install DeepSecure SDK

```bash
# Install the SDK
pip install deepsecure

# Or with development dependencies
pip install deepsecure[dev]
```

#### 6.2.2 Initialize Client

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

### 6.3 Agent Development

#### 6.3.1 Register Agent Programmatically

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

#### 6.3.2 Agent Authentication Flow

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

#### 6.3.3 MCP Tool Calls

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

### 6.4 Framework Integrations

#### 6.4.1 LangChain Integration

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

#### 6.4.2 CrewAI Integration

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

### 6.5 Building Custom MCP Servers

#### 6.5.1 Create Internal MCP Server

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

#### 6.5.2 Register with DeepSecure Gateway

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

### 6.6 Testing and Deployment

#### 6.6.1 Local Development Testing

```bash
# Start local DeepSecure services
docker compose up -d db redis deeptrail-control deeptrail-gateway

# Run integration tests
pytest tests/integration/ -v

# Test MCP flow manually
python scripts/test_mcp_flow.py
```

#### 6.6.2 CI/CD Integration

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

### 6.7 Engineering Team Workflow

| Phase | Tasks | Tools/Commands |
|-------|-------|----------------|
| **Setup** | Install SDK, configure environment | `pip install deepsecure` |
| **Development** | Build agent, integrate MCP | Python + DeepSecure SDK |
| **Testing** | Test locally, integration tests | `pytest`, manual MCP calls |
| **Registration** | Register agent with Control Plane | `client.agents.create()` |
| **Deployment** | Deploy to production | CI/CD pipeline |
| **Monitoring** | Monitor agent health, logs | Audit API, logs |

---

## 7. Cross-Persona Workflows

### 7.1 New Agent Rollout (All Personas)

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

### 7.2 Security Incident Response (Security + IT Admin)

| Step | Security Team | IT Admin |
|------|---------------|----------|
| **1. Detection** | Anomaly detected in monitoring | Receives alert notification |
| **2. Containment** | Requests agent suspension | Executes suspension in console |
| **3. Investigation** | Pulls audit logs, analyzes patterns | Contacts agent owner |
| **4. Remediation** | Updates policies | Revokes credentials, updates config |
| **5. Recovery** | Verifies fixes | Re-enables agent if appropriate |
| **6. Post-Mortem** | Documents findings | Updates procedures |

### 7.3 Employee Offboarding (IT Admin + Security)

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

## 8. Appendix: Quick Reference

### 8.1 Persona Capabilities Matrix

| Capability | IT Admin | Employee | Security | Engineering |
|------------|:--------:|:--------:|:--------:|:-----------:|
| Deploy/configure platform | ✅ | ❌ | ❌ | ❌ |
| Configure IdP integration | ✅ | ❌ | ❌ | ❌ |
| Approve services | ✅ | ❌ | ✅ | ❌ |
| Approve vendor agents | ✅ | ❌ | ✅ | ❌ |
| Define security policies | ❌ | ❌ | ✅ | ❌ |
| Emergency suspension | ✅ | ❌ | ✅ | ❌ |
| Connect personal services | ❌ | ✅ | ❌ | ❌ |
| Create delegations | ❌ | ✅ | ❌ | ❌ |
| View own agent activity | ❌ | ✅ | ❌ | ❌ |
| View all audit logs | ✅ | ❌ | ✅ | ❌ |
| Build/deploy agents | ❌ | ❌ | ❌ | ✅ |
| Register MCP servers | ✅ | ❌ | ❌ | ✅ |

### 8.2 Key API Endpoints by Persona

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

### 8.3 Common Commands

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
