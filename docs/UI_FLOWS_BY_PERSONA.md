# DeepSecure: End-to-End UI Flows by Persona

> **Version:** 1.0 | May 2026
>
> This document describes the correct end-to-end UI flows for the two primary personas that interact
> with the DeepSecure console. It reflects both the intended product design and the gaps between the
> current implementation and that design.

---

## Table of Contents

1. [Employee (End User) Flow](#1-employee-end-user-flow)
2. [IT Administrator Flow](#2-it-administrator-flow)
3. [How the Two Flows Intersect](#3-how-the-two-flows-intersect)
4. [Current UI Gaps vs Correct Behavior](#4-current-ui-gaps-vs-correct-behavior)

---

## 1. Employee (End User) Flow

### Persona Summary

| Aspect | Description |
|--------|-------------|
| **Example** | Sarah Chen, Sales Representative at Acme Corp |
| **Primary Goal** | Use AI agents to automate tasks and increase productivity |
| **Key Concerns** | Easy setup, reliable operation, confidence in security |
| **Access Level** | Self-service within IT-defined guardrails |
| **Technical Level** | Non-technical — should never see private keys, JWTs, or crypto operations |

---

### Phase 1: Onboarding (First Login — One-Time)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Log in                                                               │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  → Navigate to https://console.deepsecure.io                                 │
│  → Click "Sign in with Google" (or Okta SSO)                                 │
│  → Complete MFA if required                                                   │
│  → DeepSecure creates user session, detects first-time login                 │
│  → Onboarding wizard launches automatically                                  │
│                                                                               │
│  STEP 2: Connect Services (Wizard — one service at a time)                   │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  Wizard shows services approved for the user's role (e.g., "Sales Rep"):    │
│                                                                               │
│    ① Notion        [ Connect → ]   ← opens real OAuth popup                 │
│    ② Slack         [ Connect → ]   ← opens real OAuth popup                 │
│    ③ Gmail         [ Connect → ]   ← opens real OAuth popup                 │
│    ④ Google Drive  [ Connect → ]   ← opens real OAuth popup                 │
│    ⑤ Google Cal    [ Connect → ]   ← opens real OAuth popup                 │
│                                                                               │
│  Each OAuth flow:                                                             │
│    Browser → Service consent screen → "Allow" → tokens stored in vault      │
│    Sarah never sees or handles OAuth tokens                                  │
│                                                                               │
│  After each connect: wizard step marked ✅, progress to next                 │
│                                                                               │
│  STEP 3: Wizard Complete                                                      │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  → Dashboard overview shown                                                  │
│  → Status: "23 permissions available across 5 connected services"            │
│  → Quick actions: [Register an Agent] [View Permissions]                     │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Why this matters:** The permissions shown in the delegation step (Phase 3) are derived
from the OAuth scopes granted in this step. If Sarah only connects Notion and Slack, she
can only delegate Notion and Slack tools — HubSpot tools do not appear.

---

### Phase 2: Register an Agent

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Agents → Register Agent                                                   │
│                                                                               │
│  STEP 1: Choose Agent Type                                                   │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  ┌─────────────────────────────────┐  ┌────────────────────────────────────┐ │
│  │  👤 Own Agent                    │  │  🏢 Vendor Agent                   │ │
│  │  An agent I build and control.   │  │  A third-party agent from an IT-  │ │
│  │  I manage its deployment.        │  │  approved vendor (e.g., SalesBot) │ │
│  └─────────────────────────────────┘  └────────────────────────────────────┘ │
│                                                                               │
│  STEP 2: Fill in Details                                                     │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  Name:        [Sales Agent for Lead Gen___________]                          │
│  Description: [Automates lead follow-up and CRM updates]                     │
│                                                                               │
│  ℹ️  Agent ID will be auto-generated (e.g., agent-9e38ab05-...)              │
│  ℹ️  Ed25519 keypair will be generated by the server                         │
│                                                                               │
│  [ Register Agent ]                                                           │
│                                                                               │
│  STEP 3: Registration Success — Private Key Modal                            │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  ✅ Agent Registered!                                                         │
│                                                                               │
│  ⚠️  Private Key (shown ONCE — copy and store securely):                     │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  base64:AbCdEfGh1234...==                                              │  │
│  │  [ Copy ]  [ Download .env snippet ]                                   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  "This key is never stored by DeepSecure. If lost, you must re-register."   │
│                                                                               │
│  Agent Status: [● Registered]  ← gray badge                                 │
│                                                                               │
│  Next Step: → [ Create Delegation for this Agent ]                           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Key design decision (two flows, not one):**

There are two valid keypair flows depending on who is registering the agent:

| Flow | Who | How | When |
|------|-----|-----|------|
| **Console flow** (this doc) | Non-technical employee | Server generates keypair; private key shown once in browser modal | MVP and Priority 2 |
| **API/SDK flow** (QUICKSTART.md Step 3a) | Engineer | Client generates keypair with `nacl`; uploads only the public key | Already supported |

**Why the private key is shown in the browser rather than pushed to AWS/GCP/Vault directly:**

The console has no cloud credentials. Writing to AWS Secrets Manager requires IAM
credentials in the browser, which is a worse security problem than the key download.
The employee might also be deploying to GCP, Azure, HashiCorp Vault, or plain Kubernetes
— the console cannot know which.

**This approach is interim.** Priority 4 (AWS AgentCore integration) eliminates the
private key problem entirely: instead of generating a keypair, the employee registers
the agent's IAM role ARN. The agent authenticates using its AWS workload identity
(ECS task role, Lambda ARN) — no key is generated, stored, or deployed anywhere.
See `docs/design/aws-agentcore-identity-integration.md` and `plans/PRIORITY_MASTER.md`
Priority 4 for the roadmap.

```
MVP (now)       →  Private key shown once, employee copies to secrets manager
Priority 2      →  Deploy Config tab with copy-paste snippets per platform
Priority 4      →  Register IAM role ARN instead — no key exists to deploy
```

---

### Phase 3: Delegate Permissions

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Delegation → Create Delegation                                            │
│    (or via the "Next Step" prompt on the registration success screen)        │
│                                                                               │
│  STEP 1: Select Agent                                                        │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  Select agent: [Sales Agent for Lead Gen ▼]                                  │
│                                                                               │
│  STEP 2: Choose Permissions                                                  │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  Available permissions come from Sarah's connected services:                 │
│                                                                               │
│  📝 Notion (8 permissions)                                                   │
│    ☑ notion:pages:search    ☑ notion:pages:read    ☐ notion:pages:create     │
│    ☐ notion:pages:update    ☐ notion:pages:delete  ☐ notion:blocks:read      │
│    ☐ notion:databases:list  ☐ notion:databases:query                         │
│                                                                               │
│  💬 Slack (5 permissions)                                                    │
│    ☑ slack:messages:send    ☑ slack:channels:list  ☐ slack:messages:search   │
│    ☐ slack:channels:history ☐ slack:users:list                               │
│                                                                               │
│  📅 Google Calendar (3 permissions)                                          │
│    ☑ gcalendar:calendars:list  ☐ gcalendar:events:read  ☐ gcalendar:events:create │
│                                                                               │
│  ✉️  Gmail  (4 permissions)      📄 Google Drive (3 permissions)             │
│    ☐ ...                           ☐ ...                                     │
│                                                                               │
│  Note: HubSpot does NOT appear — Sarah has not connected HubSpot.            │
│                                                                               │
│  STEP 3: Set TTL                                                             │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  Expires after: ( ) 1 hour  ( ) 8 hours  (●) 24 hours  ( ) 7 days           │
│                                                                               │
│  [ Create Delegation ]                                                        │
│                                                                               │
│  Result:                                                                     │
│  ✅ Delegation created: del-9585d285-e64b-425e-8c83-50bd70ae465c             │
│  → Agent status badge updates to: [● Delegated]  ← amber                    │
│  → "Awaiting agent connection from runtime"                                  │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 4: Deploy the Agent (Hand Off to Engineering or Self-Deploy)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Agents → Sales Agent for Lead Gen → Deploy Config tab                    │
│                                                                               │
│  ┌─ Copy-paste setup for your deployment environment ────────────────────┐   │
│  │                                                                         │  │
│  │  Option A: Environment Variables                                        │  │
│  │  ──────────────────────────────────────────────────                     │  │
│  │  DEEPSECURE_AGENT_ID=agent-9e38ab05-4643-4bfa-9cac-b99982bbd903        │  │
│  │  DEEPSECURE_PRIVATE_KEY=<the key you saved at registration>             │  │
│  │  DEEPSECURE_CONTROL_URL=https://control.deepsecure.io                   │  │
│  │  DEEPSECURE_GATEWAY_URL=https://gateway.deepsecure.io                   │  │
│  │                                                                         │  │
│  │  Option B: AWS Secrets Manager                                          │  │
│  │  ──────────────────────────────────────────────────                     │  │
│  │  aws secretsmanager create-secret \                                     │  │
│  │    --name deepsecure/sales-agent \                                      │  │
│  │    --secret-string '{"agent_id":"agent-9e38ab05-...","private_key":"…}' │  │
│  │                                                                         │  │
│  │  Option C: Kubernetes Secret                                            │  │
│  │  ──────────────────────────────────────────────────                     │  │
│  │  kubectl create secret generic deepsecure-sales-agent \                 │  │
│  │    --from-literal=agent_id=agent-9e38ab05-... \                         │  │
│  │    --from-literal=private_key=<key>                                     │  │
│  │                                                                         │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  Share these values with your engineering team or paste into your AI         │
│  agent's deployment configuration.                                           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 5: Agent Authenticates Itself (Fully Automated — No Employee Action)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  This phase happens in the agent's runtime environment (AWS, K8s, local).    │
│  Sarah takes no action. She watches the status badge change.                 │
│                                                                               │
│  Agent startup sequence (DeepSecure SDK):                                    │
│                                                                               │
│  1. SDK reads DEEPSECURE_AGENT_ID + DEEPSECURE_PRIVATE_KEY from env          │
│  2. SDK → POST /api/v1/auth/agent/challenge                                  │
│     ← { "challenge": "abc123..." }                                           │
│  3. SDK signs challenge with Ed25519 private key                             │
│  4. SDK → POST /api/v1/auth/agent/verify                                     │
│     ← { "access_token": "<Agent Session JWT>" }                              │
│     JWT contains: agent_id, delegated_permissions, user_id, expiry           │
│  5. SDK stores JWT in memory, uses it for all MCP gateway requests           │
│                                                                               │
│  Employee sees in the console:                                               │
│  → Agent status badge: [● Authenticated]  ← blue                            │
│  → "Last authentication: 2 minutes ago from 52.14.x.x"                      │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Critical design note:** The "Authenticate Agent" button currently shown in the UI is
for developer testing only. For a deployed agent, authentication is fully automatic via
the SDK. The button should be relabeled: "Test Authentication (Developer)" and hidden
from non-technical employees, or removed from the main agent detail view entirely.

**SDK vs manual:** `QUICKSTART.md` Step 4 shows the challenge-response flow as manual
curl commands — this is for understanding the protocol. In production, the DeepSecure
SDK handles this automatically at agent startup. Engineers do not write challenge-response
code; they initialise the SDK with the agent credentials and it handles authentication.

---

### Phase 6: Agent is Active (Ongoing — Daily Operations)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Agent is running and calling tools through the MCP Gateway.                 │
│                                                                               │
│  Agent status badge: [● Active]  ← green                                    │
│                                                                               │
│  Agent Detail Page shows:                                                    │
│                                                                               │
│  ┌─ Delegations ──────────────────────────────────────────────────────────┐  │
│  │  del-9585d285-...   TTL: 23h 45m remaining   3 permissions   [Revoke]  │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Tools (available to this agent based on delegation) ─────────────────┐  │
│  │  ✅ notion.search_pages     notion:pages:search    In delegation        │  │
│  │  ✅ notion.get_page         notion:pages:read      In delegation        │  │
│  │  ✅ slack.send_message      slack:messages:send    In delegation        │  │
│  │  ✅ gcalendar.list_events   gcalendar:events:read  In delegation        │  │
│  │  ─────────────────────────────────────────────────────────────────     │  │
│  │  ❌ notion.create_page      notion:pages:create    Connected, not delegated │
│  │  ─────────────────────────────────────────────────────────────────     │  │
│  │  (HubSpot tools not shown — HubSpot not connected by this user)        │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Recent Activity ──────────────────────────────────────────────────────┐  │
│  │  10:14:03  notion.search_pages  query="Q2 leads"         ✅ success     │  │
│  │  10:14:05  slack.send_message   channel=#sales-team       ✅ success    │  │
│  │  10:13:58  gcalendar.list_events  date=today              ✅ success    │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Employee Four-State Agent Lifecycle (Summary)

```
  [● Registered]  →  [● Delegated]  →  [● Authenticated]  →  [● Active]
       gray               amber               blue                green

  What triggered it:        What Sarah did / what happened:
  ─────────────────────     ─────────────────────────────────────────────────
  Registered         →      Sarah clicked "Register Agent" in the console
  Delegated          →      Sarah created a delegation with specific permissions
  Authenticated      →      Agent runtime started, SDK performed challenge-response
  Active             →      Agent called its first MCP tool through the gateway
```

---

### Employee Daily Operations (After Setup)

| Task | Where in UI | Frequency |
|------|------------|-----------|
| Check agent activity | Agents → Agent Detail → Activity tab | Daily |
| Renew expiring delegation | Delegation → Create new delegation | Per TTL cycle |
| Revoke a delegation | Agent Detail → Delegations → Revoke | On demand |
| Re-connect expired service | Services → Connect | When notified |
| View audit trail | Audit Trail → filter by agent_id | As needed |

---

## 2. IT Administrator Flow

### Persona Summary

| Aspect | Description |
|--------|-------------|
| **Example** | Alex Torres, IT Platform Admin at Acme Corp |
| **Primary Goal** | Enable AI agent adoption while maintaining security and control |
| **Key Concerns** | Shadow AI, compliance, emergency response, operational overhead |
| **Access Level** | Organization administrator with full platform control |
| **Technical Level** | Technical — infrastructure-focused, not building agents |

---

### Phase 1: Initial Platform Setup (Day 0)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Deploy DeepSecure Infrastructure                                    │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  docker compose up -d db redis deeptrail-control deeptrail-gateway           │
│                                                                               │
│  Verify:                                                                     │
│    curl http://localhost:8000/health  →  "status": "ok"  (Control Plane)     │
│    curl http://localhost:8002/health  →  "status": "ok"  (Gateway)           │
│                                                                               │
│  STEP 2: Configure Identity Provider (IdP) Integration                       │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  → Settings → Identity Provider                                              │
│                                                                               │
│  Register Organization:                                                      │
│    Organization Name:  Acme Corp                                             │
│    Domain:             acme.com                                              │
│    IdP Type:           Okta (or Azure AD / Google Workspace)                 │
│    IdP Issuer URL:     https://acme.okta.com                                 │
│    Client ID:          0oa1234567890abcdef                                   │
│    Allowed Domains:    acme.com, acme.io                                     │
│                                                                               │
│  Configure Group → Role Mapping:                                             │
│    Okta Group "Sales"        →  DeepSecure Role "sales-rep"                  │
│    Okta Group "Engineering"  →  DeepSecure Role "developer"                  │
│    Okta Group "Finance"      →  DeepSecure Role "finance-analyst"            │
│    Okta Group "IT-Admins"    →  DeepSecure Role "platform-admin"             │
│                                                                               │
│  Enable Auto-Provisioning:                                                   │
│    ☑ Create users on first SSO login                                         │
│    ☑ Assign roles from group membership                                      │
│    ☑ Deactivate users when removed from IdP                                  │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 2: Configure Services Registry

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Settings → Services Registry                                              │
│                                                                               │
│  This determines which external services employees can connect and which     │
│  roles can access them. Employees can only see services approved here.       │
│                                                                               │
│  ┌──────────────────┬───────────┬─────────────────────┬───────────────────┐  │
│  │ Service          │ Status    │ Available To         │ Data Class        │  │
│  ├──────────────────┼───────────┼─────────────────────┼───────────────────┤  │
│  │ notion-mcp       │ ✅ Active  │ All Employees        │ Internal          │  │
│  │ slack-mcp        │ ✅ Active  │ All Employees        │ Internal          │  │
│  │ hubspot-mcp      │ ✅ Active  │ Sales, Marketing     │ Confidential      │  │
│  │ google-workspace │ ✅ Active  │ All Employees        │ Internal          │  │
│  │ salesforce-mcp   │ ✅ Active  │ Sales only           │ Confidential      │  │
│  │ financial-api    │ ✅ Active  │ Finance only         │ Restricted        │  │
│  │ hr-records-mcp   │ ⚠️ Review  │ HR only              │ Restricted        │  │
│  │ github-mcp       │ ✅ Active  │ Engineering          │ Confidential      │  │
│  └──────────────────┴───────────┴─────────────────────┴───────────────────┘  │
│                                                                               │
│  [ + Add Service ]  [ Import from Catalog ]                                  │
│                                                                               │
│  Adding a new service:                                                       │
│    Service ID:         jira-mcp                                              │
│    Display Name:       Jira Issue Tracker                                    │
│    MCP Endpoint:       https://mcp.atlassian.com/jira                        │
│    Transport:          streamable-http                                       │
│    Data Classification: confidential                                         │
│    Available To Roles: developer, product-manager                            │
│    Requires Approval:  ☐                                                     │
│    Status:             sandbox                                               │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 3: Configure Role-Based Permission Limits

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Settings → Roles & Permissions                                            │
│                                                                               │
│  These limits are the ceiling for what employees of a given role can         │
│  delegate to their agents. An employee cannot grant more than their role     │
│  allows, regardless of what OAuth scopes they hold.                          │
│                                                                               │
│  Role: "sales-rep"                                                           │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  Maximum Delegable Permissions:                                              │
│    hubspot:contacts:read         ✅ Allowed                                  │
│    hubspot:contacts:create       ✅ Allowed                                  │
│    hubspot:contacts:delete       ❌ Blocked (destructive — requires approval) │
│    hubspot:deals:read            ✅ Allowed                                  │
│    hubspot:deals:update          ✅ Allowed                                  │
│    hubspot:settings:*            ❌ Blocked (admin-only)                     │
│    slack:messages:read           ✅ Allowed                                  │
│    slack:messages:send           ✅ Allowed                                  │
│    slack:admin:*                 ❌ Blocked (admin-only)                     │
│    notion:pages:read             ✅ Allowed                                  │
│    notion:pages:create           ✅ Allowed                                  │
│    financial:*                   ❌ Not available for this role              │
│                                                                               │
│  Delegation Constraints:                                                     │
│    Maximum delegation TTL:       7 days                                      │
│    Maximum actions per day:      500                                         │
│    Working hours enforcement:    06:00–22:00 local time                      │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 4: Configure Approved Vendor Agents (Optional)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Settings → Vendor Agents                                                  │
│                                                                               │
│  Approved vendors whose agents employees can register without custom         │
│  development. Employees see only vendors approved here.                      │
│                                                                               │
│  ┌──────────────────┬──────────────────┬──────────┬────────────────────┐     │
│  │ Vendor           │ Agent Type       │ Status   │ Employees Using    │     │
│  ├──────────────────┼──────────────────┼──────────┼────────────────────┤     │
│  │ SalesBot Inc     │ Sales Assistant  │ ✅ Active │ 47                 │     │
│  │ CodeAssist AI    │ Code Helper      │ ✅ Active │ 123                │     │
│  │ DataAnalytics Co │ BI Assistant     │ ⚠️ Review │ 0 (pending)        │     │
│  │ CustomAgent Inc  │ General Purpose  │ ❌ Denied │ N/A                │     │
│  └──────────────────┴──────────────────┴──────────┴────────────────────┘     │
│                                                                               │
│  Vendor Approval Workflow:                                                   │
│  1. Security team reviews vendor's security posture                          │
│  2. IT admin approves vendor in registry                                     │
│  3. Vendor agent ID pattern registered: vendor-salesbot-*                   │
│  4. Employees can now select this vendor when registering an agent           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 5: Daily Operations — Monitor Agent Activity

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Overview Dashboard (Admin View)                                           │
│                                                                               │
│  ┌─ Platform Summary ────────────────────────────────────────────────────┐   │
│  │  Active Agents:       47      Active Delegations:  312                │   │
│  │  Connected Services:  234     MCP Requests (24h):  12,458             │   │
│  │  Unique Users:        156     Success Rate:         99.2%             │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌─ Backend MCP Server Status ────────────────────────────────────────────┐  │
│  │  notion      ✅ UP     89ms     3 errors                               │  │
│  │  slack       ✅ UP     45ms     0 errors                               │  │
│  │  hubspot     ⚠️ SLOW   850ms   12 errors   (investigate)              │  │
│  │  salesforce  ❌ DOWN   —        47 errors   (action required)         │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Credential Vault Status ──────────────────────────────────────────────┐  │
│  │  Total Stored Tokens:   234    Cache Hit Rate: 94.2%                   │  │
│  │  Expiring Soon (7d):    12     Last Refresh: 10:15:00                  │  │
│  │                                                                         │  │
│  │  Tokens Requiring Attention:                                            │  │
│  │  • sarah@acme.com - notion  - Expires in 2 days                        │  │
│  │  • mike@acme.com  - hubspot - Refresh failed (re-auth needed)          │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 6: Review New Agent Registrations

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Agents → All Agents (Admin View — sees all users' agents)                 │
│                                                                               │
│  ┌──────────────────────┬──────────────┬──────────┬─────────────────────┐    │
│  │ Agent Name           │ Owner        │ Status   │ Last Active         │    │
│  ├──────────────────────┼──────────────┼──────────┼─────────────────────┤    │
│  │ Sales Agent Lead Gen │ sarah@acme   │ Active   │ 2 mins ago          │    │
│  │ Code Review Bot      │ dev@acme     │ Delegated│ never               │    │
│  │ HR Onboarding Agent  │ hr@acme      │ Registered│ never              │    │
│  │ Vendor: SalesBot     │ mike@acme    │ Active   │ 5 mins ago          │    │
│  └──────────────────────┴──────────────┴──────────┴─────────────────────┘    │
│                                                                               │
│  Pending Approval (if approval required by policy):                          │
│    agent-new-001  (alice@acme)  "Marketing automation agent"  [ Approve ✅ ] [ Deny ❌ ] │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 7: Emergency Controls

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Settings → Emergency Controls                                             │
│                                                                               │
│  ⚠️  These actions are immediate and organization-wide. Use with caution.    │
│                                                                               │
│  Targeted Actions:                                                           │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  Suspend a specific agent:                                                   │
│    Agent: [sales-agent-001 ▼]   Reason: [Suspected anomalous behavior]      │
│    ☑ Notify owner               [ Suspend Agent ]                            │
│    Effect: All sessions terminated, all delegations revoked immediately      │
│                                                                               │
│  Revoke all delegations for a user:                                          │
│    User: [sarah@acme.com ▼]     [ Revoke All Delegations ]                  │
│                                                                               │
│  ─────────────────────────────────────────────────────────────────────────   │
│  Organization-Wide Actions:                                                  │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  [ 🔴 Suspend All Vendor Agents ]                                            │
│  Immediately terminates all vendor agent sessions.                           │
│  Currently affects: 47 active agents across 312 employees                   │
│                                                                               │
│  [ 🔴 Disable All Delegations ]                                              │
│  Revokes all active delegation tokens organization-wide.                     │
│  Currently affects: 1,247 active delegations                                 │
│                                                                               │
│  [ 🔴 Lockdown Mode ]                                                        │
│  Blocks all agent activity until manually re-enabled.                        │
│  Duration: [60 minutes ▼]      Reason: [Security incident]                  │
│                                                                               │
│  ─────────────────────────────────────────────────────────────────────────   │
│  Recent Emergency Actions:                                                   │
│  2026-02-10 14:32  Suspended agent-vendor-xyz           (admin@acme.com)     │
│  2026-01-28 09:15  Revoked delegation del-abc123         (security@acme.com) │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Automatic revocation triggers (no IT action required):**

| Trigger | Effect |
|---------|--------|
| Delegation TTL expires | Agent loses access automatically |
| User deactivated in Okta/Azure AD | ALL user's delegations invalidated instantly |
| User's Okta group changes | Delegations re-evaluated against new role |
| Service OAuth token revoked | Agent can no longer use that service's tools |
| IT admin suspends agent | Immediate effect, all sessions terminated |

---

### IT Admin Recurring Tasks

| Task | Frequency | Console Location |
|------|-----------|-----------------|
| Review new agent registrations | Daily | Agents → All Agents |
| Check service health | Daily | Overview → Backend Status |
| Review security alerts | Daily | Audit Trail → Alerts |
| Review expiring credentials | Daily | Overview → Vault Status |
| Audit dormant agents | Weekly | Agents → filter by "last active > 7d" |
| Role permission review | Monthly | Settings → Roles & Permissions |
| Vendor compliance check | Quarterly | Settings → Vendor Agents |

---

## 3. How the Two Flows Intersect

```
IT ADMIN (Alex)                                   EMPLOYEE (Sarah)
─────────────────────────────────────────         ────────────────────────────────────────

Day 0:
Deploys platform ──────────────────────────────── (not yet using it)
Configures IdP (Okta)
Approves services: Notion, Slack, Gmail,
  GDrive, GCal (all users)
  HubSpot (Sales role only)
Configures "sales-rep" role permission limits
  (max TTL: 7 days, 500 actions/day)
Approves vendor: SalesBot Inc

Day 1+ (Employee Onboarding):
                                                  Sarah logs in → onboarding wizard
                                                  Connects Notion, Slack, Gmail, GDrive, GCal
                                                  (HubSpot shown only if Sarah = Sales role)
                                                  Wizard complete

Day 1+ (Agent Setup):
                                                  Registers "Sales Agent for Lead Gen"
                                                  Saves private key
                                                  Creates delegation: 4 permissions, 24h TTL
                                                  Passes key to engineering

Day 1+ (Agent Running):
Sees new agent in "All Agents" view               Agent starts up, authenticates via SDK
                                                  Agent status: Active ✅

Ongoing:
Monitors platform-wide agent activity             Checks agent activity feed daily
Reviews credential vault for expiring tokens      Gets notified when service token expires
                                                  Re-connects service via OAuth
Can revoke Sarah's agent if anomaly detected      Can revoke own delegation at any time
```

---

## 4. Current UI Gaps vs Correct Behavior

These gaps are tracked in `plans/agent_auth_flow_design_66bcb1ec.md` (Priority 2) and
`plans/integration_verification_pipeline.plan.md` (Priority 1).

| Current UI Behavior | Problem | Correct Behavior | Tracking |
|--------------------|---------|--------------------|---------|
| "Authenticate Agent" button visible to employees | Misleads employees into thinking they manually authenticate | Rename to "Test Authentication (Developer Only)" or hide from non-admin users | `frontend-detail-page` |
| Private key paste form shown to employees | Ed25519 challenge-response is an engineering concern | Only show "Agent is authenticated automatically. Check your runtime deployment." | `frontend-detail-page` |
| Tools list shows 17 hardcoded tools including HubSpot (not connected) | Static hardcoded `PERMISSION_TOOL_MAP` in `agents.py` — not filtered by user's connected services | Only show tools from services the user has actually connected; filter by delegation | `part-c4-scope-permissions` |
| No lifecycle state badge on agent cards | Employee cannot tell if agent is Registered/Delegated/Authenticated/Active | Four-state badge: Registered (gray), Delegated (amber), Authenticated (blue), Active (green) | `frontend-lifecycle-badges` |
| No "Next Step" prompt after registration | Disconnect between registration and delegation — employee doesn't know to create a delegation | Registration success screen shows: "Next: Create a delegation for this agent →" | `frontend-detail-page` |
| No Deploy Config tab on agent detail page | Employee has no way to get copy-paste deployment snippets | Add Deploy Config tab with env var / AWS Secrets Manager / K8s snippets | `frontend-deploy-config` |
| Delegation and registration are disconnected pages | Creates workflow gap; employees register then don't know to delegate | Post-registration redirect flow directly to delegation creation | `frontend-detail-page` |
