# DeepSecure: End-to-End UI Flows by Persona

> **Version:** 2.0 | May 2026
>
> This document describes the correct end-to-end UI flows for all personas that interact
> with the DeepSecure console. It reflects both the intended product design and the gaps between the
> current implementation and that design.
>
> **Changes in v2.0:** Added Vendor Admin (multi-user agent model), Security Team flows. Updated Agent Registration to reflect GCP Workload Identity as primary path. Added multi-user delegation variant. Added Tool Call Analytics.

---

## Table of Contents

1. [Employee (End User) Flow](#1-employee-end-user-flow)
2. [IT Administrator Flow](#2-it-administrator-flow)
3. [Vendor Admin (Multi-User Agent Model)](#3-vendor-admin-multi-user-agent-model)
4. [Security Team Flow](#4-security-team-flow)
5. [How the Flows Intersect](#5-how-the-flows-intersect)
6. [Current UI Gaps vs Correct Behavior](#6-current-ui-gaps-vs-correct-behavior)

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
can only delegate Notion and Slack tools — Gmail tools do not appear.

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
│  STEP 2: Choose Identity Method                                              │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  ● GCP Workload Identity (recommended)                                       │
│    Agent authenticates via GCP service account — no key to manage             │
│                                                                               │
│  ○ Ed25519 Keypair (legacy/manual)                                           │
│    Server generates keypair; private key shown once                           │
│                                                                               │
│  STEP 3: Fill in Details (GCP WI selected)                                   │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  Name:        [Sales Agent for Lead Gen___________]                          │
│  Description: [Automates lead follow-up and CRM updates]                     │
│  SA Email:    [sales-agent@my-project.iam.gserviceaccount.com]               │
│                                                                               │
│  ℹ️  Agent ID will be auto-generated (e.g., agent-9e38ab05-...)              │
│  ℹ️  Attestation policy will be created for this service account             │
│                                                                               │
│  [ Register Agent ]                                                           │
│                                                                               │
│  STEP 4: Registration Success                                                │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  ✅ Agent Registered!                                                         │
│                                                                               │
│  Agent ID: agent-9e38ab05-4643-4bfa-9cac-b99982bbd903                        │
│  Identity: GCP Workload Identity                                             │
│  SA: sales-agent@my-project.iam.gserviceaccount.com                          │
│  Attestation Policy: Created ✅                                               │
│                                                                               │
│  ┌─ Deploy Instructions ──────────────────────────────────────────────────┐  │
│  │  Set these environment variables in your Cloud Run / GKE deployment:   │  │
│  │                                                                         │  │
│  │  DEEPSECURE_AGENT_ID=agent-9e38ab05-...                                │  │
│  │  DEEPSECURE_CONTROL_URL=https://app.deepsecure.one                     │  │
│  │  DEEPSECURE_GATEWAY_URL=https://app.deepsecure.one/mcp                 │  │
│  │  DEEPSECURE_IDENTITY_PROVIDER=gcp                                      │  │
│  │                                                                         │  │
│  │  ℹ️ No private key needed — agent exchanges GCP OIDC token for JWT     │  │
│  │  [ Copy ]  [ View Full gcloud Setup Commands ]                         │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  Agent Status: [● Registered]  ← gray badge                                 │
│                                                                               │
│  Next Step: → [ Create Delegation for this Agent ]                           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Identity method options:**

| Flow | Who | How | When |
|------|-----|-----|------|
| **GCP Workload Identity** (primary) | Employee or Admin | Register SA email; agent bootstraps via OIDC token exchange. No key exists anywhere | P4+ (current) |
| **Ed25519 Keypair** (legacy) | Non-technical employee | Server generates keypair; private key shown once in browser modal | MVP / P2 |
| **API/SDK flow** | Engineer | Client generates keypair with `nacl`; uploads only the public key | Always supported |

**Why GCP WI is the recommended path:**

No private key is generated, stored, or deployed anywhere. The agent authenticates using
its GCP service account's native OIDC token, which DeepSecure validates against an
attestation policy. This eliminates the key management problem entirely.

```
P4 (current)    →  GCP Workload Identity — no key, OIDC bootstrap
Legacy          →  Ed25519 keypair — shown once, employee stores securely
Future (P10)    →  AWS Identity Provider — IAM role ARN, STS exchange
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
│  Note: Gmail does NOT appear — Sarah has not connected Gmail.                 │
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
│  This phase happens in the agent's runtime environment (GCP, AWS, K8s).      │
│  Sarah takes no action. She watches the status badge change.                 │
│                                                                               │
│  Agent startup sequence — GCP Workload Identity (primary):                   │
│                                                                               │
│  1. SDK reads DEEPSECURE_AGENT_ID + DEEPSECURE_IDENTITY_PROVIDER=gcp         │
│  2. SDK obtains GCP OIDC token from metadata server (automatic in Cloud Run) │
│  3. SDK → POST /api/v1/auth/agent/gcp-identity-token                         │
│     Body: { "agent_id": "...", "identity_token": "<GCP OIDC token>" }        │
│     ← { "access_token": "<Agent Session JWT>" }                              │
│     JWT contains: agent_id, delegated_permissions, user_id, expiry           │
│  4. SDK stores JWT in memory, uses it for all MCP gateway requests           │
│  5. SDK refreshes via heartbeat (background loop every 5 minutes)            │
│                                                                               │
│  Alternative: Ed25519 challenge-response (legacy):                           │
│                                                                               │
│  1. SDK reads DEEPSECURE_AGENT_ID + DEEPSECURE_PRIVATE_KEY from env          │
│  2. SDK → POST /api/v1/auth/agent/challenge                                  │
│     ← { "challenge": "abc123..." }                                           │
│  3. SDK signs challenge with Ed25519 private key                             │
│  4. SDK → POST /api/v1/auth/agent/verify                                     │
│     ← { "access_token": "<Agent Session JWT>" }                              │
│                                                                               │
│  Employee sees in the console:                                               │
│  → Agent status badge: [● Authenticated]  ← blue                            │
│  → "Last authentication: 2 minutes ago from 34.72.x.x (GCP Cloud Run)"      │
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
│  │  (Gmail tools not shown — Gmail not connected by this user)             │  │
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
│  │ gmail-mcp        │ ✅ Active  │ All Employees        │ Internal          │  │
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
│    slack:messages:search         ✅ Allowed                                  │
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
│  │  gmail       ✅ UP     120ms    1 error                               │  │
│  │  salesforce  ❌ DOWN   —        47 errors   (action required)         │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Credential Vault Status ──────────────────────────────────────────────┐  │
│  │  Total Stored Tokens:   234    Cache Hit Rate: 94.2%                   │  │
│  │  Expiring Soon (7d):    12     Last Refresh: 10:15:00                  │  │
│  │                                                                         │  │
│  │  Tokens Requiring Attention:                                            │  │
│  │  • sarah@acme.com - notion  - Expires in 2 days                        │  │
│  │  • mike@acme.com  - gmail   - Refresh failed (re-auth needed)          │  │
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

## 3. Vendor Admin (Multi-User Agent Model)

### Persona Summary

| Aspect | Description |
|--------|-------------|
| **Example** | Victor, Customer Success lead at Scale Agentic |
| **Primary Goal** | Deploy one agent per customer company that serves multiple human users |
| **Key Concerns** | Multi-user isolation, per-user token management, scalable onboarding |
| **Access Level** | Admin-level agent registration; delegates per-user permission management to individual users |

---

### Phase 1: Register Company Agent (Admin Action)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Agents → Register Agent (Admin)                                           │
│                                                                               │
│  STEP 1: Register Agent for Company                                          │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  Agent Name:      [Scale Sales Agent_______________]                         │
│  Company:         [Deep Trail Inc ▼]                                         │
│  Identity Method: ● GCP Workload Identity                                    │
│  SA Email:        [scale-sales-sa@customer-project.iam.gserviceaccount.com]  │
│                                                                               │
│  ⚠️  One service account per customer company (company-level identity)        │
│                                                                               │
│  [ Register Agent ]                                                           │
│                                                                               │
│  STEP 2: Success — Users Onboard Independently                               │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  ✅ Agent Registered: scale-sales-agent (agent-xxx-yyy-zzz)                  │
│  ✅ Attestation Policy Created (GCP WI + SA email)                            │
│  📋 Deploy Instructions: [View GCP Setup Commands]                            │
│                                                                               │
│  Next: Individual users log in and delegate their own permissions.            │
│  Agent accesses each user's services based on their delegation.              │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 2: User Self-Service Delegation (Per-User, No Admin Action)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Delegation (logged in as Victor)                                          │
│                                                                               │
│  Welcome, Victor! Your admin has registered "Scale Sales Agent"              │
│  for your company. Delegate your permissions below.                          │
│                                                                               │
│  DELEGATE YOUR PERMISSIONS TO: Scale Sales Agent                             │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  YOUR CONNECTED SERVICES:                                                    │
│  ✅ Google Calendar (victor@deeptrail.com)                                    │
│  ✅ Gmail (victor@deeptrail.com)                                              │
│  ✅ Notion (Victor's workspace)                                               │
│  ⚠️ Slack (not connected) [Connect Now]                                      │
│                                                                               │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                               │
│  GOOGLE CALENDAR:                                                            │
│  ☑ List events (gcalendar:events:list)                                       │
│  ☐ Create events (gcalendar:events:create)                                   │
│                                                                               │
│  GMAIL:                                                                      │
│  ☑ Search messages (gmail:messages:search)                                   │
│  ☐ Send messages (gmail:messages:send) ← Victor opts out                    │
│                                                                               │
│  NOTION:                                                                     │
│  ☑ Search pages (notion:pages:search)                                        │
│  ☑ Read pages (notion:pages:read)                                            │
│                                                                               │
│  Expires in: [7 days ▼]                                                      │
│                                                                               │
│  [ Create Delegation ]                                                        │
│                                                                               │
│  ℹ️ Other users in your company can grant different permissions.              │
│  The agent will only access YOUR data with YOUR permission level.            │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 3: Admin Multi-User Agent View

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Agents → Scale Sales Agent (Admin View)                                   │
│                                                                               │
│  AGENT: Scale Sales Agent (agent-xxx-yyy-zzz)                                │
│  Status: ● Active | Platform: GCP Workload Identity                          │
│  SA: scale-sales-sa@customer-project.iam.gserviceaccount.com                 │
│                                                                               │
│  LIFECYCLE:                                                                   │
│  ●─────────────●───────────────────────●────────────────●                    │
│  Reg           Del (3 users)           Auth (1×)       Active                │
│  (admin)       (user self-service)     (bootstrap)     (heartbeat)           │
│                                                                               │
│  WHY 1 AUTH, NOT N:                                                           │
│  One workload identity → bootstraps ONCE → gets 1 Agent JWT.                │
│  N users create N independent delegations. On each tool call,                │
│  agent specifies which user's context (user_id).                             │
│                                                                               │
│  ┌─ Delegating Users (3) ───────────────────────────────────────────────┐    │
│  │  User           │ Services        │ Permissions       │ Expires      │    │
│  │  ────────────── │ ─────────────── │ ──────────────── │ ──────────── │    │
│  │  mahendra@      │ Notion, Slack,  │ Full access       │ 6 days       │    │
│  │  deeptrail.com  │ Gmail, Cal      │ (8 permissions)   │              │    │
│  │                 │                 │                    │              │    │
│  │  victor@        │ Notion, Gmail,  │ Read-only         │ 4 days       │    │
│  │  deeptrail.com  │ Calendar        │ (5 permissions)   │              │    │
│  │                 │                 │ ⚠️ No send email  │              │    │
│  │                 │                 │                    │              │    │
│  │  priya@         │ Slack, Notion   │ Slack full,       │ 2 days       │    │
│  │  deeptrail.com  │                 │ Notion read       │              │    │
│  │                 │                 │ (4 permissions)   │              │    │
│  └───────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─ Recent Activity (by user context) ──────────────────────────────────┐    │
│  │  Time     │ User     │ Tool                │ Result                  │    │
│  │  ──────── │ ──────── │ ─────────────────── │ ─────────────────────── │    │
│  │  10:15:32 │ mahendra │ notion.search_pages │ ✅ 3 pages found        │    │
│  │  10:16:01 │ victor   │ gcalendar.list      │ ✅ 5 events             │    │
│  │  10:16:45 │ priya    │ slack.send_message  │ ✅ Sent to #general     │    │
│  │  10:17:12 │ victor   │ gmail.send_message  │ ❌ Denied (not delegated)│   │
│  └───────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 4: Admin Delegation Management

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Settings → Delegation Templates (Admin)                                   │
│                                                                               │
│  DELEGATION TEMPLATES:                                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  Agent               │ Default Permissions    │ Max TTL │ Users       │   │
│  │  ──────────────────── │ ────────────────────── │ ─────── │ ─────────── │   │
│  │  Sales Assistant      │ notion:read, slack:*,  │ 7 days  │ 5/10 active│   │
│  │                       │ gmail:read, cal:read   │         │             │   │
│  │  Engineering Audit    │ notion:*, slack:*,     │ 7 days  │ 3/3 active │   │
│  │                       │ github:read            │         │             │   │
│  │                                                                        │   │
│  │  [+ Create Template]  [Edit]  [Clone]                                 │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ALL ACTIVE DELEGATIONS (across all users):                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  User           │ Agent              │ Permissions │ Status │ TTL     │   │
│  │  ────────────── │ ────────────────── │ ─────────── │ ────── │ ─────── │   │
│  │  sarah@acme     │ Sales Assistant    │ 12 (full)   │ Active │ 6d      │   │
│  │  victor@acme    │ Sales Assistant    │ 5 (narrowed)│ Active │ 4d      │   │
│  │  priya@acme     │ Sales Assistant    │ 4 (narrowed)│ Active │ 2d      │   │
│  │                                                                        │   │
│  │  [Create Delegation]  [Bulk Revoke]  [Export CSV]                     │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  DELEGATION FLOW:                                                             │
│  ─ Admin creates template → sets max permissions (ceiling) + default TTL     │
│  ─ User accepts delegation → inherits template                               │
│  ─ User can REMOVE permissions (narrow) but CANNOT ADD beyond ceiling        │
│  ─ User can set shorter TTL but not longer                                   │
│  ─ Admin can revoke any user's delegation or create on behalf of user        │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Security Team Flow

### Persona Summary

| Aspect | Description |
|--------|-------------|
| **Example** | Jordan, Security Engineer at Acme Corp |
| **Primary Goal** | Ensure AI agent deployments meet security and compliance requirements |
| **Key Concerns** | Threat detection, policy enforcement, incident response, compliance |
| **Access Level** | Security administrator with audit and policy access |

---

### Phase 1: Tool Call Analytics Dashboard

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Analytics → Tool Call Analytics                                            │
│                                                                               │
│  📊 MCP TOOL USAGE ANALYSIS — LAST 7 DAYS                                    │
│                                                                               │
│  ┌─ Tool Call Volume by Backend ──────────────────────────────────────────┐  │
│  │  notion     ████████████████████████████████████████  68%  (8,234)     │  │
│  │  slack      ██████████████████                       28%  (3,412)     │  │
│  │  gmail      ████                                      4%    (487)     │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Top Tools Called ─────────────────────────────────────────────────────┐  │
│  │  Rank │ Tool                    │ Calls  │ Success │ Denials │ Users   │  │
│  │ ──────├─────────────────────────├────────├─────────├─────────├──────── │  │
│  │   1   │ notion.search_pages     │  4,521 │  99.8%  │    8    │   89    │  │
│  │   2   │ slack.list_channels     │  2,103 │ 100.0%  │    0    │   67    │  │
│  │   3   │ notion.read_page        │  1,892 │  99.9%  │    2    │   54    │  │
│  │   4   │ gmail.search_messages   │    412 │  98.5%  │    6    │   23    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Permission Denial Analysis ───────────────────────────────────────────┐  │
│  │  Total Denials: 52         Denial Rate: 0.43%                          │  │
│  │                                                                         │  │
│  │  • slack:messages:write     (17 denials) — 6 agents, 4 users           │  │
│  │  • notion:pages:create      (11 denials) — 3 agents, 3 users           │  │
│  │  • gmail:messages:read      ( 8 denials) — 2 agents, 2 users           │  │
│  │                                                                         │  │
│  │  💡 Insight: 65% of denials are write ops not delegated.                │  │
│  │     Consider reviewing delegation templates.                            │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Delegation Chain Visualization ───────────────────────────────────────┐  │
│  │  Select Agent: [agent-sdr-001            ▼]                            │  │
│  │                                                                         │  │
│  │  sarah@acme.com                                                         │  │
│  │       │                                                                 │  │
│  │       ├─ Connected Services                                             │  │
│  │       │   ├─ notion (pages:read, pages:search)                          │  │
│  │       │   └─ slack  (messages:read, channels:list)                      │  │
│  │       │                                                                 │  │
│  │       └─ Delegated to: agent-sdr-001                                    │  │
│  │           ├─ notion:pages:read    ✅ Used 234 times                     │  │
│  │           ├─ notion:pages:search  ✅ Used 1,021 times                   │  │
│  │           ├─ slack:messages:search ✅ Used 89 times                      │  │
│  │           └─ slack:channels:list  ⚪ Never used                         │  │
│  │                                                                         │  │
│  │  📊 Permission Utilization: 75% (3 of 4 permissions used)              │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  [ Export Report ] [ Schedule Weekly Digest ] [ Create Alert Rule ]           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 2: Threat Monitoring & Alerts

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Security → Threat Monitoring                                              │
│                                                                               │
│  🔒 SECURITY OVERVIEW — LAST 24 HOURS                                        │
│                                                                               │
│  Total Agent Actions: 12,847    Unique Active Agents: 147                    │
│  Permission Denials: 23         Policy Violations: 2 ⚠️                       │
│  Anomalies Detected: 1 🚨                                                    │
│                                                                               │
│  ⚠️  ALERTS REQUIRING ATTENTION:                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  🚨 HIGH: Unusual data access pattern                                  │  │
│  │  Agent: agent-john-databot-002                                         │  │
│  │  Issue: Accessed 2,847 unique records (normal: 50-100)                 │  │
│  │  Time: 2026-02-15 03:42 AM (outside normal hours)                      │  │
│  │  [ Investigate ]  [ Suspend Agent ]  [ Contact Owner ]                 │  │
│  │                                                                         │  │
│  │  ⚠️ MEDIUM: Rate limit approached                                      │  │
│  │  Agent: agent-marketing-assistant-001                                   │  │
│  │  Issue: 450 of 500 daily actions used by 10 AM                         │  │
│  │  [ Set Alert ]  [ Increase Limit ]  [ Contact Owner ]                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 3: Incident Response Workflow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  → Security → Incidents → INC-2026-042                                       │
│                                                                               │
│  INCIDENT: Suspected Data Exfiltration                                       │
│  Agent: agent-john-databot-002 | Severity: HIGH                              │
│                                                                               │
│  ┌─ STEP 1: CONTAIN (Immediate) ─────────────────────────────────────────┐  │
│  │  [ ✅ DONE ] Suspend agent                                             │  │
│  │  [ ✅ DONE ] Revoke all delegations                                    │  │
│  │  [ ✅ DONE ] Notify agent owner                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ STEP 2: INVESTIGATE ──────────────────────────────────────────────────┐  │
│  │  [ IN PROGRESS ] Pull complete audit trail                             │  │
│  │  [ PENDING ] Analyze data access patterns                              │  │
│  │  [ PENDING ] Determine root cause                                      │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ STEP 3: REMEDIATE ───────────────────────────────────────────────────┐  │
│  │  [ PENDING ] Rotate affected credentials                               │  │
│  │  [ PENDING ] Update policies to prevent recurrence                     │  │
│  │  [ PENDING ] Document findings                                         │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Security Team Recurring Tasks

| Task | Frequency | Console Location |
|------|-----------|-----------------|
| Review security alerts | Daily | Security → Threat Monitoring |
| Check policy violations | Daily | Security → Denials |
| Review tool call analytics | Weekly | Analytics → Tool Call Analytics |
| Update anomaly rules | Weekly | Security → Settings → Anomaly Rules |
| Generate compliance reports | Monthly | Reports → Generate |
| Policy review | Quarterly | Settings → Policies |

---

## 5. How the Flows Intersect

```
IT ADMIN (Alex)                                   EMPLOYEE (Sarah)
─────────────────────────────────────────         ────────────────────────────────────────

Day 0:
Deploys platform ──────────────────────────────── (not yet using it)
Configures IdP (Okta)
Approves services: Notion, Slack, Gmail,
  GDrive, GCal (all users)
  GitHub (Engineering role only)
Configures "sales-rep" role permission limits
  (max TTL: 7 days, 500 actions/day)
Approves vendor: SalesBot Inc

Day 1+ (Employee Onboarding):
                                                  Sarah logs in → onboarding wizard
                                                  Connects Notion, Slack, Gmail, GDrive, GCal
                                                  (GitHub shown only if Sarah = Engineering role)
                                                  Wizard complete

Day 1+ (Agent Setup):
                                                  Registers "Sales Agent for Lead Gen"
                                                  Selects GCP Workload Identity method
                                                  Creates delegation: 4 permissions, 7d TTL
                                                  Deploys agent with gcloud commands

Day 1+ (Agent Running):
Sees new agent in "All Agents" view               Agent starts up, bootstraps via GCP OIDC
                                                  Agent status: Active ✅

Ongoing:
Monitors platform-wide agent activity             Checks agent activity feed daily
Reviews credential vault for expiring tokens      Gets notified when service token expires
                                                  Re-connects service via OAuth
Can revoke Sarah's agent if anomaly detected      Can revoke own delegation at any time
```

**Multi-User Model (Vendor Admin):**

```
VENDOR ADMIN (Victor)          USER A (Sarah)          USER B (Priya)
───────────────────────        ────────────────────    ────────────────────

Day 0:
Registers agent for
company (1 SA) ─────────────── (not yet delegated)    (not yet delegated)

Day 1+:
                               Connects services       Connects services
                               Delegates (full access) Delegates (read-only)

Agent bootstraps (1× via GCP WI) ──────────────────────────────────────────

Ongoing:
Views agent + all users        Checks own activity     Checks own activity
Sees per-user tool calls       Can narrow permissions  Can narrow permissions
Can revoke any delegation      Can revoke own only     Can revoke own only
```

---

## 6. Current UI Gaps vs Correct Behavior

These gaps are tracked in `plans/PRIORITY_MASTER.md` P5.1 (UI Improvements) and
`plans/integration_verification_pipeline.plan.md`.

| Current UI Behavior | Problem | Correct Behavior | Priority |
|--------------------|---------|--------------------|---------|
| "Authenticate Agent" button visible to employees | Misleads employees into thinking they manually authenticate | Hide for GCP WI agents; show only for Ed25519 legacy agents in dev mode | P5.1 |
| Audit Trail shows only `mcp_tool_call` badge + agent ID | All detail fields (tool, success, user, duration) are returned by API but not displayed | Show tool name, success/failure badge, user attribution, duration. Expandable detail for arguments | P5.1 |
| Overview "Recent Activity" shows only event type + agent ID | Missing tool name, user context, success indicator | Rich activity rows with tool name + user + success badge | P5.1 |
| No Tool Call Analytics page | Security team has no aggregated view of tool usage patterns | Analytics page: top tools, usage by backend, denial patterns, delegation utilization | P5.1 |
| Tools list shows hardcoded tools (not filtered by delegation) | Static `PERMISSION_TOOL_MAP` — not filtered by user's connected services | Only show tools from services the user has connected; filter by active delegation | Partially fixed (P2) |
| No lifecycle state badge on agent cards | Employee cannot tell if agent is Registered/Delegated/Authenticated/Active | Four-state badge: Registered (gray), Delegated (amber), Authenticated (blue), Active (green) | Partially implemented (P2) |
| No multi-user agent view (admin) | Admin sees same single-user view as employee; cannot see all delegating users for one agent | Admin Agent View: 1 agent with N users, per-user permissions, activity grouped by user | P5.2 |
| No delegation templates (admin) | Admin must create delegations one-by-one; no "set policy once, N users onboard" pattern | Delegation Templates: admin defines max permissions + TTL, users inherit and can narrow | P5.2 |
| No Deploy Config tab showing GCP WI instructions | Employee has no in-UI guidance for deploying to GCP | Deploy Instructions tab with pre-filled gcloud/env vars after registration | P5.4 |
| Agent ID shown instead of agent name in audit trail | Difficult to identify which agent performed actions | Resolve agent_id to display name via client-side lookup | P5.1 |
