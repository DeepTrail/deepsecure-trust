# Multi-User Agent Delegation: Future Capabilities

> **Related plan:** [multi-user-delegation-roundrobin](../../plans/multi-user-delegation-roundrobin_0fca7fec.plan.md) — the foundational per-delegation JWT with round-robin execution plan that these capabilities build on top of.

> **Related docs:** [PRIORITY_MASTER §5.3 — tracking tables](../../plans/PRIORITY_MASTER.md) (implementation status + UI phase sequence), [Technical Architecture §5.1 Identity Layer Stack](../TECHNICAL_ARCHITECTURE_AND_DESIGN.md#51-identity-layer-stack)

## Overview

The round-robin plan solves the immediate problem: 1 agent with N delegations from N users can cycle through each delegation, get a scoped JWT, and call tools on each user's behalf. This document describes four future capabilities that extend that foundation for more advanced multi-user scenarios.

It also tracks **current P5.3 implementation gaps** (runtime + UI) and proposes a phased UI plan to close them.

---

## P5.3 Implementation Status (June 2026)

> **Updated June 4, 2026:** Phase 0 (per-delegation JWT with round-robin execution), Phase 1 (fleet user→services mapping), and Phase 2 (identity stack panel) are **complete and deployed to production**. The runtime gap ("1 JWT → 1 owner") is resolved. Admin Agent Fleet now shows cross-user service mapping, enriched delegations with service badges, foldable sessions with lazy-loaded tool call detail, and a 5-layer identity stack panel. Remaining gaps are **UI clarity** (Phases 3–4) and the `_meta.user_id` per-call path (future interactive agents).

### Gap Analysis: Runtime & Data Model

| Item | Status | What exists today | What's still missing |
|------|--------|-------------------|----------------------|
| **Multi-user delegation support** | **Done** | N users can delegate to the same agent. **Per-delegation round-robin deployed (June 4).** New endpoints: `GET /auth/agent/delegations` + `POST /auth/agent/delegation-token`. Entrypoint cycles through delegations with scoped JWTs and service-matched prompts. | UI does not yet surface which delegation is "active now" or show per-round execution status. |
| **User-scoped token selection in gateway** | **Done (via round-robin)** | Each delegation-scoped JWT has a single `owner` → vault resolves that owner's OAuth tokens. Gateway handles this natively — no code changes needed. | `_meta.user_id` **per-call** path still incomplete (not needed for round-robin; future path for interactive multi-user agents). |
| **Per-user permission levels** | **Done** | Each delegation-scoped JWT carries only that delegation's permissions. Gateway enforces per-JWT. User B's github-only delegation → agent gets github-only JWT → gateway shows only github tools. Smart prompt selection in entrypoint matches prompts to permissions. | — |
| **Admin registers agent, users self-delegate** | **Done** | Admin registers agents; users create their own delegations independently. | — |
| **Agent → Users → Tokens mapping UI** | **Done (Phase 1+2)** | Fleet shows cross-user mapping with connected services per user, enriched delegations with service badges, foldable sessions with lazy-loaded tool call detail, 5-layer identity stack panel. Details section redesigned with two-column grid. | OAuth token contribution mapping (Phase 4), Vault tab clarification (Phase 3). |
| **`user_id` in `tools/call`** | Partial (infra only) | `_meta.user_id` hook exists in gateway. Round-robin uses per-delegation JWT (different approach, same outcome). | No agent runtime uses `_meta.user_id` yet. Vault `_meta` path incomplete. |
| **Multi-user demo** | **Done (production)** | Round-robin entrypoint **is** the multi-user demo — runs in production on 3 agent jobs (gemini-deepsecure-agent, thunderbolt-deepsecure-agent, engineering-audit). | Standalone `demos/demo_admin_multi_user.py` not updated for round-robin flow yet. |
| **One SA per customer** | Partial (pattern) | GCP agents use one SA per agent (`agents.selector` = SA email). | Not documented/enforced as a company-level pattern in UI. |

### What Cloud Agents Actually Receive (Credential Confusion)

A common question: "We run 3 GCP Cloud Run agents — why is Vault → Agent Credentials empty?"

Three different credential concepts exist in the platform. They are **not interchangeable**:

| Credential type | Layer | Used by GCP cloud agents? | Stored in DB? | Shown in Vault UI? |
|-----------------|-------|---------------------------|---------------|-------------------|
| **GCP OIDC token** | Platform attestation | Yes — once per bootstrap | No | No |
| **Agent Session JWT** | L3 | Yes — every bootstrap (~1h TTL) | Metadata only (`agent_sessions`); JWT string **not persisted** | No (by design — secret) |
| **Delegation record** | L5 | Yes — permission grant | Yes (`delegation_tokens`) | Partially — as "Delegations" in Agent Fleet |
| **User OAuth tokens** | Vault | Yes — per delegator, via gateway | Yes (`vault_tokens` + `connected_services`) | Yes — **OAuth Tokens** tab (per logged-in user) |
| **Split-key credentials** | Legacy Ed25519 flow | **No** — SDK/challenge-response agents only | Yes (`credentials` table) | Yes — **Agent Credentials** tab |

**Why Agent Credentials is empty for GCP agents:** That tab reads `GET /vault/user-credentials`, which queries the `credentials` table (ephemeral Ed25519/X25519 split-key credentials from `POST /vault/credentials`). GCP workload-identity agents bootstrap via `POST /auth/bootstrap/gcp` and receive an **Agent Session JWT (L3)** — a different credential path entirely. Empty is **expected**, not a bug.

**Bootstrap flow for cloud agents (round-robin, deployed June 4):**

```
Cloud Scheduler → Cloud Run Job
  Phase 1: Bootstrap
    → GCP OIDC token (Google SA)              ← one-time platform proof, not stored
    → POST /auth/bootstrap/gcp
    → Discovery JWT (L3)                      ← scoped to newest delegation's owner
  Phase 2: Discover delegations
    → GET /auth/agent/delegations             ← returns all active delegations
  Phase 3: Round-robin loop (per round, per delegation)
    → POST /auth/agent/delegation-token       ← exchange delegation_id for scoped JWT
    → Delegation-scoped JWT (L3)              ← owner=this delegator, perms=this delegation
    → AgentSession row in DB                  ← new session per delegation exchange
    → configure MCP client with scoped JWT
    → warm gateway (initialize MCP session)
    → select prompts matching delegation's services
    → MCP tools/call with scoped JWT
    → Gateway fetches USER OAuth tokens from vault_tokens (keyed by JWT owner)
    → (next delegation...)
  → sleep(interval)
  → (next round... re-fetch delegations to pick up changes)
```

---

## Identity Layer Stack — Backend vs UI

From [Technical Architecture §5.1](../TECHNICAL_ARCHITECTURE_AND_DESIGN.md#51-identity-layer-stack). The architecture describes a multi-layer identity model; the UI only partially reflects delegations and sessions.

| Layer | What it is | Backend | UI today |
|-------|-----------|---------|----------|
| **L0** User ID-Token | Google/OIDC login | IdP flow | Not shown |
| ~~**L1**~~ ~~Organization Key~~ | Never implemented — see [§5.1 note](../TECHNICAL_ARCHITECTURE_AND_DESIGN.md#51-identity-layer-stack) | — | — |
| **L2** User Session JWT | Console/API session | Issued on login | Not shown |
| **L3** Agent Session JWT | Agent MCP session token | `create_access_token()` on bootstrap; `agent_sessions` metadata | Sessions listed in Fleet (IDs/timestamps only), **not the JWT** |
| **L4** Task Token JWT | Per-task scoped token | `task_service.issue_task_token()` | No UI |
| **L5** Delegation Token | User → agent permission grant | `delegation_tokens` table | Shown as delegations (permissions, expiry), **not labeled as L5 / no JWT view** |

**Security principle:** Raw JWT strings and OAuth access tokens must **never** be displayed in the UI. The gap is **metadata visibility** (layer, type, status, issued/expiry, delegator, linked services) — not token inspection.

---

## Agent → Users → Tokens UI Gaps

The P5.3 item `agent-user-token-ui` requires: *"UI shows one agent with multiple delegating users, each with their own connected services and permission levels."*

### Implemented (Agent Fleet today)

- Multiple delegating users per agent
- Delegation list with permission counts and expiry status
- Session count and recent session IDs/timestamps
- Lifecycle state (Registered → Delegated → Authenticated → Active)

### Implemented (Phase 1 + Phase 2 — June 4, 2026)

| Item | Status | Delivered in |
|------|--------|--------------|
| **Per-user connected services** | ✅ Done | Phase 1 — `CrossUserMappingTable` with per-user connected services and scopes |
| **Active Agent JWT metadata** | ✅ Done | Phase 1+2 — sessions show delegator, delegation_id, tool_calls, status; identity stack shows Agent Session layer |
| **Cross-user token mapping** | ✅ Done | Phase 1 — `DelegatorSummary` with `connected_services[]` per delegator |
| **Identity layer stack view** | ✅ Done | Phase 2 — `IdentityStackPanel` showing all 5 layers (User ID-Token, User Session, Delegation, Agent Session, Task Token) |
| **Workload identity display** | ✅ Done | Phase 1 — `platform`, `selector` (renamed to "Service Account" in UI), `auth_method` in fleet response + Details section |

### Not yet implemented

| Gap | Detail | Plan Phase |
|-----|--------|------------|
| **OAuth token contribution mapping** | Which user's vault tokens the agent can reach for each service (token_ref, status, scopes — metadata only) | Phase 4 |
| **Vault tab clarification** | Rename "Agent Credentials" tab for GCP agents; add Agent Sessions link | Phase 3 |

### API gaps blocking UI

Current `GET /api/v1/admin/agents` (`admin_fleet.py`) returns:

- `delegating_users`, `delegations[]`, `sessions[]`, `public_key`, lifecycle state

Missing fields needed for full mapping UI:

- `platform` (e.g., `gcp`, `aws`, `local`)
- `selector` (e.g., `debugging-agent-sa@deepsecure-saas.iam.gserviceaccount.com`)
- Per-delegator: `connected_services[]` (service name, status, scopes_granted, token_ref prefix)
- Per-session: `delegator`, `delegation_id`, `expires_at`, `is_active`

---

## UI Design & Implementation Plan

> **Goal:** Close `agent-user-token-ui` and identity-stack visibility gaps without exposing secrets. Depends on round-robin runtime (Phase 0) for accurate per-delegation session metadata.

### Design Principles

1. **Metadata only** — Show token *existence*, *layer*, *status*, *expiry*, *owner* — never raw JWT or OAuth access token values.
2. **Agent-centric admin view** — Admin sees `Agent → Users → Services → Permissions` in one expandable panel.
3. **User-centric vault view** — Non-admin users see their own OAuth tokens (existing) plus which agents have active delegations using those tokens.
4. **Clarify credential types** — Rename or annotate Vault tabs so "Agent Credentials" vs "Agent Sessions" is unambiguous.

### Phase 0: Runtime prerequisite (backend, not UI) — ✅ COMPLETE (June 4, 2026)

Implemented [round-robin plan](../../plans/multi-user-delegation-roundrobin_0fca7fec.plan.md). Each delegation gets its own scoped JWT and session. Deployed to all 3 production agent jobs.

| Task | File(s) | Status |
|------|---------|--------|
| Revert merged permissions in bootstrap | `bootstrap_service.py` | ✅ Discovery JWT scoped to single newest delegation |
| Add `AgentIdentityDep` | `deps.py` | ✅ Lightweight JWT validation without requiring owner claims |
| Add `GET /auth/agent/delegations` | `agent_auth.py` | ✅ Agent lists active delegations |
| Add `POST /auth/agent/delegation-token` | `agent_auth.py` | ✅ Exchange delegation_id for scoped JWT + AgentSession |
| Round-robin entrypoint | `agents/gemini/entrypoint.sh` | ✅ Two-phase bootstrap, delegation cycling, smart prompt selection, discovery JWT refresh |
| Problem 5 in outage doc | `AGENT_OUTAGE_INVESTIGATION.md` | ✅ Documented single-delegation JWT root cause and fix |

### Phase 1: Agent Fleet — User → Services mapping (M) — ✅ COMPLETE (June 4, 2026)

> **Implemented:** Backend API extended with `platform`, `selector`, `auth_method`, `delegators[]` with `connected_services[]`, enriched `sessions[]` with `delegator`, `delegation_id`, `tool_calls`, `status`. New endpoint `GET /agents/{id}/sessions/{sid}/events` for lazy-loaded session detail. Frontend: `CrossUserMappingTable`, `DelegationsTable`, `SessionsTable` components. Details section redesigned with two-column grid, merged Auth/Auth Method field, Service Account full-width display. Plan: [`fleet-user-services-mapping_2c53a09e.plan.md`](../../plans/fleet-user-services-mapping_2c53a09e.plan.md).

**API:** Extend `AgentFleetEntry` in `admin_fleet.py`:

```python
class ConnectedServiceSummary(BaseModel):
    service_id: str
    display_name: str         # "Notion", "Slack", "GitHub"
    status: str               # "connected" | "token_expired" | "not_connected"
    scopes_granted: List[str] # OAuth scopes the user granted

class DelegatorSummary(BaseModel):
    email: str
    connected_services: List[ConnectedServiceSummary]
    active_delegation: Optional[DelegationSummary]
    delegation_count: int

class SessionSummary(BaseModel):
    session_id: str
    created_at: Optional[str]
    last_activity_at: Optional[str]
    delegator: Optional[str]       # which user's delegation this session was for
    delegation_id: Optional[str]   # which delegation triggered this session
    tool_calls: int                # count of tool calls in this session
    status: str                    # "active" | "expired"

class AgentFleetEntry(BaseModel):
    ...
    platform: Optional[str]
    selector: Optional[str]  # GCP SA email or AWS role ARN
    auth_method: str  # "workload_identity" | "ed25519"
    delegators: List[DelegatorSummary]  # replaces flat delegating_users list
```

**UI:** `frontend/.../admin/agents/page.tsx`

The expanded agent panel has three table sections below the Details/Delegating Users header. All three use a **fold/expand** pattern consistent with the Activity Feed's expandable rows.

#### Table 1: Cross-User Mapping (replaces flat "Delegating Users" badges)

Replaces the current flat `Badge` list (`mahendra@deeptrail.com`, `demo@deeptrail.com`) with a structured table. Each user row is **expandable** — click the chevron to reveal per-service detail.

**Collapsed view (default):**

| | User | Services | Permissions | Active Delegation |
|---|------|----------|-------------|-------------------|
| ▶ | mahendra@deeptrail.com | `Notion` `Slack` `GitHub` `GCal` | 24 permissions | Active (expires 7/3) |
| ▶ | demo@deeptrail.com | `Notion` `Slack` `GitHub` `GCal` | 24 permissions | Active (expires 7/3) |

**Expanded view (click ▶ on mahendra row):**

| | User | Services | Permissions | Active Delegation |
|---|------|----------|-------------|-------------------|
| ▼ | **mahendra@deeptrail.com** | `Notion` `Slack` `GitHub` `GCal` | 24 permissions | Active (expires 7/3) |
| | | `Notion` | notion:pages:read, notion:pages:search, notion:pages:create, notion:databases:read | ● connected |
| | | `Slack` | slack:channels:list, slack:channels:read, slack:messages:send, slack:messages:read | ● connected |
| | | `GitHub` | github:repos:read, github:repos:list, github:pulls:read, github:pulls:create | ● connected |
| | | `GCal` | gcalendar:events:list, gcalendar:events:read | ● token expired |
| ▶ | demo@deeptrail.com | `Notion` `Slack` `GitHub` `GCal` | 24 permissions | Active (expires 7/3) |

Service status badges are color-coded: green dot = connected, amber dot = token expired, gray dot = not connected. This tells the admin at a glance whether the agent can actually use each service for each user.

#### Table 2: Delegations — enriched with service context

Same table structure as today (Delegator | Permissions | Created | Expires | Status), but the Permissions column adds **service badges** next to the count, and each row is **expandable** to show the full permission list grouped by service.

**Collapsed view (default — same density as today plus service badges):**

| | Delegator | Permissions | Created | Expires | Status |
|---|-----------|-------------|---------|---------|--------|
| ▶ | demo@deeptrail.com | 24 permissions · `Notion` `Slack` `GitHub` `GCal` | 6/3/2026 | 7/3/2026 | Active |
| ▶ | mahendra@deeptrail.com | 24 permissions · `Notion` `Slack` `GitHub` `GCal` | 6/3/2026 | 7/3/2026 | Active |
| ▶ | mahendra@deeptrail.com | 5 permissions · `Notion` | 5/16/2026 | 5/17/2026 | Expired |

**Expanded view (click ▶ on first row):**

Shows the full permission list grouped by service, with each permission on its own line:

```
▼ demo@deeptrail.com | 24 permissions | 6/3/2026 | 7/3/2026 | Active
  ┌─────────────────────────────────────────────────┐
  │ Notion (6)                                      │
  │  notion:pages:read  notion:pages:search         │
  │  notion:pages:create  notion:databases:read     │
  │  notion:databases:query  notion:blocks:read     │
  │                                                 │
  │ Slack (6)                                       │
  │  slack:channels:list  slack:channels:read        │
  │  slack:messages:send  slack:messages:read        │
  │  slack:users:list  slack:users:read             │
  │                                                 │
  │ GitHub (8)                                      │
  │  github:repos:read  github:repos:list           │
  │  github:pulls:read  github:pulls:create         │
  │  github:issues:read  github:issues:create       │
  │  github:actions:read  github:actions:trigger     │
  │                                                 │
  │ Google Calendar (4)                              │
  │  gcalendar:events:list  gcalendar:events:read   │
  │  gcalendar:events:create  gcalendar:freebusy:read│
  └─────────────────────────────────────────────────┘
```

#### Table 3: Sessions — folded by default, expandable per row

The current sessions table shows 149 rows flat — overwhelming and not actionable. The new design **folds the table by default** (showing only the header with count), and when opened, each session row is individually expandable to show detail.

**Folded view (default):**

```
▶ Sessions (149)                                    [View All]
  Latest: asess-cfea4544e756417d — 6/4/2026, 2:02 PM — mahendra@deeptrail.com
```

Shows only the section header with count and the most recent session as a preview line. Clicking the chevron opens the table.

**Opened view (click ▶ on section header):**

| | Session ID | Delegator | Created | Last Activity | Tool Calls | Status |
|---|------------|-----------|---------|---------------|------------|--------|
| ▶ | asess-cfea4544e756417d | mahendra@deeptrail.com | 6/4, 2:02 PM | 6/4, 2:08 PM | 12 calls | Active |
| ▶ | asess-9e58420247d84751 | demo@deeptrail.com | 6/4, 12:03 PM | 6/4, 12:09 PM | 8 calls | Expired |
| ▶ | asess-f37f462fb2d34ab1 | mahendra@deeptrail.com | 6/4, 10:01 AM | 6/4, 10:07 AM | 15 calls | Expired |

New columns vs today: **Delegator** (which user's delegation triggered this session), **Tool Calls** (count), **Status** (active/expired based on JWT TTL).

**Expanded view (click ▶ on a session row):**

Shows the session's activity timeline — tool calls made during this session, similar to the Activity Feed component pattern:

```
▼ asess-cfea4544e756417d | mahendra@ | 6/4, 2:02 PM | 12 calls | Active
  ┌─────────────────────────────────────────────────┐
  │ Delegation: del-abc123 (24 permissions)          │
  │ JWT issued: 6/4/2026 2:02:28 PM                 │
  │ JWT expires: 6/4/2026 3:02:28 PM                │
  │                                                  │
  │ Tool calls:                                      │
  │  ✓ notion.search_pages        2:03:01 PM         │
  │  ✓ notion.read_page           2:03:14 PM         │
  │  ✓ slack.list_channels        2:04:02 PM         │
  │  ✓ slack.post_message         2:04:18 PM         │
  │  ✗ github.create_issue        2:05:01 PM  denied │
  │  ... 7 more                                      │
  └─────────────────────────────────────────────────┘
```

This reuses the Activity Feed's `statusIcon()` and `statusBadgeVariant()` patterns from `ActivityFeed.tsx`, applied inline per tool call.

#### Fold/Expand Pattern — Implementation

All three tables use the **same accordion pattern** already used for the agent list in `page.tsx` (line 57): a `string | null` state where clicking one row closes the previously expanded one. This is consistent across every level of nesting.

**Existing pattern (agent-level accordion — no change):**

```typescript
const [expandedId, setExpandedId] = useState<string | null>(null);
// Click Debugging Agent → expands. Click Thunderbolt Agent → Debugging closes, Thunderbolt opens.
```

**Same pattern applied inside each expanded agent panel:**

```typescript
// Within the expanded agent detail, each table section is an accordion:
const [expandedUserRow, setExpandedUserRow] = useState<string | null>(null);
const [expandedDelegationRow, setExpandedDelegationRow] = useState<string | null>(null);
const [expandedSessionRow, setExpandedSessionRow] = useState<string | null>(null);
```

Each uses `ChevronDown`/`ChevronRight` + the `border-t bg-muted/20` reveal pattern. Clicking one row closes the previously expanded row in that table. The three tables are independent — expanding a user row doesn't collapse a delegation row.

**Visual hierarchy (all using the same chevron accordion):**

```
▶ Debugging Agent (agent-494fb...)          ← expandedId (existing, agent-level)
▼ Thunderbolt Agent (agent-7b2a...)         ← expanded agent card
  ┌──────────────────────────────────────────────────────┐
  │ Details: Auth | Platform | Selector | Created | ...  │
  │                                                      │
  │ Cross-User Mapping (2)                               │
  │  ▶ mahendra@deeptrail.com  Notion Slack ...          │ ← expandedUserRow
  │  ▼ demo@deeptrail.com      Notion Slack ...          │
  │    └ Notion: notion:pages:read, notion:pages:search  │
  │    └ Slack: slack:channels:list, slack:messages:read  │
  │                                                      │
  │ Delegations (8)                                      │
  │  ▶ demo@ · 24 perms · Notion Slack GitHub GCal       │ ← expandedDelegationRow
  │  ▶ mahendra@ · 5 perms · Notion                     │
  │                                                      │
  │ ▶ Sessions (149)                                     │ ← folded section header
  └──────────────────────────────────────────────────────┘
```

**Sessions section fold behavior:**

The Sessions section itself is a fold/expand at the section level (not per-row initially). Clicking `▶ Sessions (149)` opens the table. Then within the opened table, each session row follows the same `expandedSessionRow` accordion pattern.

```
  │ ▼ Sessions (149)                                     │ ← section opened
  │  ▶ asess-cfea...  mahendra@  6/4 2:02 PM  12 calls  │ ← expandedSessionRow
  │  ▼ asess-9e58...  demo@      6/4 12:03 PM  8 calls  │
  │    └ Delegation: del-abc123 (24 permissions)          │
  │    └ JWT issued: 6/4/2026 12:03:17 PM                │
  │    └ ✓ notion.search_pages  12:04:01 PM              │
  │    └ ✓ slack.list_channels  12:04:18 PM              │
  │  ▶ asess-f37f...  mahendra@  6/4 10:01 AM  15 calls  │
```

**Default states:**

| Section | Default | Why |
|---------|---------|-----|
| Cross-User Mapping | **Open** (rows collapsed) | Primary view — replaces the flat badges, admin needs to see users at a glance |
| Delegations | **Open** (rows collapsed) | Same as today — already open, rows just gain expand capability |
| Sessions | **Folded** (section collapsed) | 149 rows is overwhelming; admin opens on demand |

#### Details panel — new fields

| Field | Source | Display |
|-------|--------|---------|
| Auth | `public_key` presence | "Workload Identity" or truncated key (existing) |
| **Platform** | `platform` field (new) | "GCP" / "AWS" / "Local" |
| **Selector** | `selector` field (new) | Full SA email or role ARN, monospace font |
| Created | `created_at` | Date (existing) |
| Last Active | `last_active_at` | Date (existing) |

#### API data requirements

The enriched tables need data that doesn't exist in the current `GET /api/v1/admin/agents` response:

| New field | Source | Join required |
|-----------|--------|---------------|
| `platform`, `selector` | `agent_platforms` table | agent_id |
| Per-delegator `connected_services` | `connected_services` + `vault_tokens` | delegation.delegator → user_id → connected_services |
| Per-session `delegator` | `agent_sessions.delegation_id` → `delegation_tokens.delegator` | session → delegation → delegator |
| Per-session `tool_calls` count | `audit_events` where `session_id` matches | session_id |
| Per-session tool call detail (expanded) | `audit_events` where `session_id` matches | session_id (lazy-loaded on expand) |

Tool call details for session expansion should be **lazy-loaded** — only fetch `GET /api/v1/admin/agents/{agent_id}/sessions/{session_id}/events` when the user expands a specific session row, not on initial page load.

**Acceptance:** Admin opens Debugging Agent → sees (1) cross-user mapping with per-user connected services, (2) delegations with service badges and expandable permission details, (3) sessions folded by default with delegator attribution and expandable tool call history.

### Phase 2: Identity Stack panel (M) — ✅ COMPLETE (June 4, 2026)

> **Implemented:** New endpoint `GET /api/v1/admin/agents/{agent_id}/identity-stack` returning 5-layer identity model. Frontend: `IdentityStackPanel` component with color-coded layer badges, accordion-expandable details per layer, pagination for Agent Sessions, and empty states for unused layers. All layers use descriptive names (no L-numbering in UI). Plan: [`identity-stack-panel_c00d4161.plan.md`](../../plans/identity-stack-panel_c00d4161.plan.md).

**API:** New endpoint `GET /api/v1/admin/agents/{agent_id}/identity-stack`:

```json
{
  "agent_id": "agent-494fb073-...",
  "layers": [
    {"layer": "L5", "type": "Delegation", "count": 2, "active": 1, "items": [
      {"id": "del-...", "delegator": "demo@...", "expires_at": "...", "status": "active"}
    ]},
    {"layer": "L3", "type": "Agent Session", "count": 137, "active": 1, "items": [
      {"session_id": "asess-...", "delegator": "demo@...", "created_at": "...", "expires_at": "...", "status": "active"}
    ]},
    {"layer": "L4", "type": "Task Token", "count": 0, "active": 0, "items": []}
  ]
}
```

**UI:** Collapsible "Identity Stack" section in Agent Fleet expanded panel. Each layer shows count, active status, and expandable item list (metadata only).

**Acceptance:** ✅ Admin sees all 5 identity layers (User ID-Token, User Session JWT, Delegation Token, Agent Session JWT, Task Token JWT) labeled by name — not by L-number. Each layer shows count, active status, and expandable item list (metadata only). No JWT strings displayed.

### Phase 3: Vault tab clarification + session metadata (S)

**UI changes:**

| Tab | Current label | Proposed change |
|-----|--------------|-----------------|
| Agent Credentials | "No agent credentials" | Rename to **"Split-Key Credentials"** with subtitle: "Ed25519 agents only. GCP/AWS workload-identity agents use Agent Sessions — see Agent Fleet." |
| (new sub-section or tab) | — | **"Agent Sessions"** under Vault or link from Agent Fleet: lists L3 session metadata for agents the user has delegated to |

**API:** Reuse extended fleet endpoint or add `GET /vault/agent-sessions` scoped to current user's delegated agents.

**Acceptance:** Admin no longer confused why Agent Credentials is empty for GCP agents.

### Phase 4: OAuth token ↔ agent linkage (S)

**UI:** On Vault → OAuth Tokens tab, add column or badge: "Used by agents: Debugging Agent, Thunderbolt Agent" (agents with active delegations from this user that include permissions for that service).

**API:** Join `delegation_tokens` + `delegated_permissions` + `connected_services` for current user.

**Acceptance:** User sees which agents can access each of their OAuth-connected services.

### Phase 5: Task Token UI (L, optional)

When Tasks feature is in active use, add L4 to Identity Stack panel and a Tasks page section showing active task tokens (metadata: task_id, scoped_permissions, expires_at).

Deferred until Task Token usage is production-relevant.

### Implementation Sequence

```mermaid
flowchart LR
  P0["Phase 0<br/>Round-robin runtime"]
  P1["Phase 1<br/>Fleet user→services"]
  P2["Phase 2<br/>Identity stack panel"]
  P3["Phase 3<br/>Vault clarification"]
  P4["Phase 4<br/>OAuth↔agent linkage"]

  P0 --> P1
  P0 --> P2
  P1 --> P4
  P2 --> P3
```

| Phase | Complexity | Depends on | Delivers | Status |
|-------|------------|------------|----------|--------|
| 0 | L | — | Correct per-delegation runtime | ✅ Done — June 4, 2026 |
| 1 | L | Phase 0 | `agent-user-token-ui` core: cross-user mapping, enriched delegations, foldable sessions | ✅ Done — June 4, 2026 |
| 2 | M | Phase 0 | Identity layer visibility | ✅ Done — June 4, 2026 |
| 3 | S | Phase 2 | Vault confusion resolved | 🔲 Not started |
| 4 | S | Phase 1 | User-side agent linkage | 🔲 Not started |
| 5 | L | Tasks in prod | L4 Task Token UI | 🔲 Deferred |

### Files to Create/Modify (UI plan)

| File | Action | Phase |
|------|--------|-------|
| `deeptrail-control/app/api/v1/endpoints/admin_fleet.py` | Extend `AgentFleetEntry` response: add `platform`, `selector`, `delegators[]` with `connected_services[]`; enrich `sessions[]` with `delegator`, `delegation_id`, `tool_calls`, `status`; add service badges to delegations | 1 |
| `deeptrail-control/app/api/v1/endpoints/admin_fleet.py` | Add `GET /agents/{id}/sessions/{session_id}/events` for lazy-loaded session tool call detail | 1 |
| `deeptrail-control/app/api/v1/endpoints/admin_fleet.py` | Add `GET /agents/{id}/identity-stack` | 2 |
| `frontend/src/lib/types/admin.ts` | Add `ConnectedServiceSummary`, `DelegatorSummary` types; extend `SessionSummary` with `delegator`, `delegation_id`, `tool_calls`, `status`; add `IdentityStackLayer` | 1–2 |
| `frontend/src/components/agents/CrossUserMappingTable.tsx` | **New component**: expandable per-user rows with service badges, permission detail, delegation status | 1 |
| `frontend/src/components/agents/DelegationsTable.tsx` | **New component**: enriched delegations with service badges + expandable permission groups | 1 |
| `frontend/src/components/agents/SessionsTable.tsx` | **New component**: folded-by-default section, expandable rows with delegator attribution + lazy-loaded tool call detail | 1 |
| `frontend/src/app/(dashboard)/dashboard/admin/agents/page.tsx` | Replace flat badges + flat tables with the three new components; add `expandedSections`/`expandedRows` state | 1 |
| `frontend/src/app/(dashboard)/dashboard/vault/page.tsx` | Rename Agent Credentials tab, add sessions link | 3 |
| `deeptrail-control/app/api/v1/endpoints/vault.py` | Add agent-session metadata endpoint for delegators | 3–4 |

---

## 1. `_meta.user_id` Per-Call Switching

### What It Is

Instead of getting a new JWT per delegation (round-robin), a single long-running agent process sends `_meta.user_id` on each `tools/call` request to specify which user's tokens to use. The agent holds one merged-permission JWT and switches user context per call.

### How It Helps

SDK-based agents (Python/Node processes, not Gemini CLI) that manage multiple users in memory. A Slack bot that responds to messages from different users in real-time can't stop, re-bootstrap, and re-initialize MCP for each message. It needs to switch user context within a single process.

### Example

```
User A posts in Slack: "What's on my calendar today?"
Agent (single process) → tools/call gcalendar.list_events {_meta: {user_id: "userA@company.com"}}
  → Gateway fetches User A's Google Calendar OAuth token
  → Returns User A's events

User B posts in Slack: "Search my Notion for project plans"  
Agent (same process) → tools/call notion.search_pages {_meta: {user_id: "userB@company.com"}}
  → Gateway fetches User B's Notion OAuth token
  → Returns User B's results
```

### Why It's Separate from Round-Robin

Round-robin is for **batch/scheduled agents** (Cloud Run Jobs) that run, do work, and exit. `_meta.user_id` is for **always-on agents** that serve requests as they arrive. Different execution models, same multi-user need.

### Current State

The gateway already parses `_meta.user_id` and overrides `agent_context.owner` (in `tools_call.py` lines 287-299), but the vault GET path still authenticates with the original JWT's `owner` claim. The vault would need an internal API that accepts an `X-User-ID` header (like the refresh path already does) instead of relying on the JWT's `owner`.

### Implementation Gap

| Component | Current Behavior | Required Change |
|-----------|-----------------|-----------------|
| Gateway `tools_call.py` | Parses `_meta.user_id`, overrides `agent_context.owner` | Already done (partial) |
| Gateway `credential_injection.py` | Vault GET uses Agent JWT's `owner` claim | Use internal API with `X-User-ID` header instead of Agent JWT auth |
| Control plane `vault.py` | Resolves user from JWT `owner` claim | Add internal-auth vault endpoint that accepts `X-User-ID` |
| Permission filtering | Uses merged permissions (no per-user scoping) | Filter `delegated_permissions` to the specific user's delegation |
| Audit logging | `on_behalf_of` uses session-level delegator | Use per-call `_meta.user_id` for audit trail |

### When to Implement

When you build an SDK-based always-on agent (not a batch Gemini CLI agent).

### Deep Dive: Merged-Permission JWT and Per-Call User Switching

A common question: if the agent has ONE JWT with all users' permissions merged, how does it switch user context per call? The answer is that the user context lives **outside the JWT**, on each `tools/call` request.

#### How the Merged JWT Differs from a Per-Delegation JWT

**Round-robin (per-delegation JWT):** One JWT per user, one user per call window.

```
JWT_A: {owner: "mahendra", permissions: [notion, slack]}
  → all calls use mahendra's tokens
  → then discard JWT_A

JWT_B: {owner: "demo", permissions: [github]}
  → all calls use demo's tokens
  → then discard JWT_B
```

**`_meta.user_id` (merged JWT):** One JWT for the agent, user specified per call.

```
MERGED_JWT: {sub: "debugging-agent", permissions: [notion, slack, github]}
  → no meaningful "owner" — the agent is the identity, not any single user

tools/call notion.search {_meta: {user_id: "mahendra@deeptrail.com"}}
  → gateway sees _meta.user_id → fetches mahendra's Notion token

tools/call github.list_repos {_meta: {user_id: "demo@deeptrail.com"}}
  → gateway sees _meta.user_id → fetches demo's GitHub token
```

The JWT does **not** contain user_ids for all users as the `owner` claim. Instead, it carries an `authorized_users` list that the gateway uses to validate the per-call `_meta.user_id`:

```json
{
  "sub": "debugging-agent",
  "type": "agent",
  "delegation_ids": ["del_A_id", "del_B_id"],
  "delegated_permissions": ["notion:pages:read", "slack:channels:list", "github:repos:read"],
  "authorized_users": ["mahendra@deeptrail.com", "demo@deeptrail.com"],
  "exp": 1748900000
}
```

#### Why This Requires Vault API Changes

The current vault token retrieval uses the JWT's `owner` claim to determine whose tokens to fetch:

```
Agent → Gateway → Vault GET /internal/tokens/{service}
                   Auth: Agent JWT
                   Vault reads JWT → extracts "owner" claim → returns that user's token
```

With a merged JWT, the `owner` claim is either absent, set to the agent ID, or set to an arbitrary user. The vault can't know which user's token to return from the JWT alone.

The fix requires switching from JWT-auth to internal-auth for the vault lookup:

```
Agent → Gateway → Vault GET /internal/tokens/{service}
                   Auth: Internal API Token (gateway-to-control)
                   Header: X-User-ID: mahendra@deeptrail.com
                   Vault reads X-User-ID header → returns that user's token
```

This internal-auth path already exists for token **refresh** (the gateway sends `X-User-ID` when refreshing expired tokens in `credential_injection.py`). It does not exist for the initial token **fetch**.

#### The Permission Escalation Problem

With round-robin, the JWT itself enforces scope: JWT_A can only access mahendra's tokens because `owner=mahendra`. The gateway needs no extra validation.

With `_meta.user_id`, the **agent** chooses which user to act as on each call. The gateway must validate two things:

1. **Identity check:** Is `_meta.user_id` in the JWT's `authorized_users` list? (prevents impersonation of non-delegating users)
2. **Permission scoping:** Does the specified user's delegation include the requested permission? (prevents permission escalation)

The second check is critical. Consider: mahendra delegated `notion:*` and `slack:*`, but demo only delegated `github:*`. The merged permissions list includes all three. Without per-user scoping, an agent could call `notion.search_pages` with `_meta.user_id=demo` — using demo's identity to access Notion, even though demo never delegated Notion access.

This means the gateway needs per-user permission maps instead of a flat merged list:

```json
{
  "permission_map": {
    "mahendra@deeptrail.com": ["notion:pages:read", "slack:channels:list"],
    "demo@deeptrail.com": ["github:repos:read"]
  }
}
```

#### Why Round-Robin Was Chosen First

| Concern | Round-Robin | `_meta.user_id` |
|---------|-------------|-----------------|
| JWT semantics | Clean: 1 owner, 1 delegation | Ambiguous: merged identity |
| Vault changes needed | None | Yes (internal-auth GET path) |
| Permission validation | JWT carries correct scope | Gateway must cross-check per-user maps |
| Security surface | JWT is self-contained proof | Agent can choose user identity per call |
| Audit trail | JWT tells you who the call is for | Must log `_meta.user_id` separately |
| Complexity | Simple loop in bash entrypoint | Gateway middleware changes |

Round-robin works with zero gateway changes. `_meta.user_id` requires changes to vault endpoints, gateway permission checking, JWT structure, and audit logging. The right sequencing is: build round-robin first (works for batch agents), then add `_meta.user_id` when an always-on SDK agent can't afford the stop-rebootstrap-reinitialize cycle between users.

---

## 2. Delegation-Scoped Constraints

### What It Is

The `DelegationToken` model has a `constraints` JSON field that can express fine-grained limits beyond just permissions. The gateway currently passes `constraints: {}` (empty) and never evaluates them.

### How It Helps

Lets delegators control **how** their delegation is used, not just **what** it can do. Different users have different risk tolerances. User A might trust the agent fully. User B might say "you can read my email but never send on my behalf." Without constraints, the permission list is binary (has permission or doesn't). Constraints add nuance.

### Example Constraints

| Constraint | Use Case |
|-----------|----------|
| `{"max_calls_per_hour": 100}` | User delegates Notion access but doesn't want the agent hammering the API |
| `{"time_window": {"start": "09:00", "end": "17:00", "tz": "America/Los_Angeles"}}` | Agent can only use my tokens during business hours |
| `{"read_only": true}` | I delegate Slack access but the agent can only read channels, not send messages (even if `slack:messages:send` is in the delegation) |
| `{"ip_allowlist": ["35.x.x.x/24"]}` | My tokens can only be used from known agent infrastructure IPs |
| `{"require_approval": ["slack:messages:send"]}` | Agent can read freely but needs human approval before posting |

### Why It Matters for Multi-User

Different users have different risk profiles for the same agent:

```
Delegation from CEO:
  permissions: [notion:*, slack:*, gmail:*]
  constraints: {"time_window": "business_hours", "require_approval": ["slack:messages:send"]}

Delegation from Intern:
  permissions: [notion:pages:read, slack:channels:list]
  constraints: {}  (no restrictions beyond the limited permissions)
```

### Current State

- `DelegationToken.constraints` column exists in the database (JSON field)
- Bootstrap includes constraints in the JWT context
- Gateway receives `constraints` in MCP handler context (`main.py` line 648: `"constraints": {}`)
- No constraint evaluation logic exists anywhere

### Implementation

Add a `ConstraintEvaluator` in the gateway that runs between permission check and tool execution:

```
Permission Check (exists) → Constraint Evaluation (new) → Credential Injection (exists) → Tool Call
```

The evaluator would:
1. Read constraints from the JWT context (or fetch from control plane if not in JWT)
2. Evaluate each constraint type against the current request
3. Reject the call with a clear error if any constraint is violated

### When to Implement

When users request "read-only" or "business hours only" or "rate-limited" delegations.

---

## 3. Cross-Delegation Prompt Orchestration

### What It Is

The agent makes intelligent decisions about **what to do** based on information gathered across multiple users' delegations, synthesizing results from different user contexts.

### How It Helps

Today with round-robin, each delegation runs independently with isolated prompts. The agent searches User A's Notion, then separately searches User B's Notion. It doesn't combine or reason across results from different users.

### Example

```
Round-robin (current plan):
  Delegation A (mahendra): "Search Notion for strategy docs" → 3 results
  Delegation B (demo): "Search Notion for strategy docs" → 5 results
  (Results are independent, never combined)

Cross-delegation orchestration (future):
  Agent: "Find strategy docs across ALL delegated users' Notion workspaces,
          deduplicate, and post a summary to the #strategy Slack channel
          using whichever user has slack:messages:send permission"
```

### Why It's Infrastructure vs. Intelligence

Round-robin is **infrastructure** — cycling through JWTs, making API calls. Cross-delegation orchestration is **agent intelligence** — deciding what information from User A's context is relevant to User B's workflow.

This requires:
- **Prompt engineering** — the agent needs prompts that reference multi-user context
- **Memory across delegation rounds** — results from User A's round must persist into User B's round
- **Agent framework** — LangGraph, CrewAI, or similar stateful agent framework instead of Gemini CLI's stateless `-p` mode
- **Privacy boundaries** — careful design about what data from User A is visible when acting as User B

### Architecture Sketch

```
┌─────────────────────────────────────────────────────────┐
│  Orchestration Agent (LangGraph / CrewAI)               │
│                                                         │
│  Shared Memory:                                         │
│    user_a_results: [{title: "Q3 Strategy", ...}]        │
│    user_b_results: [{title: "Product Roadmap", ...}]    │
│                                                         │
│  Decision Logic:                                        │
│    "user_a has overlapping docs with user_b"             │
│    "post combined summary to #strategy via user_a's     │
│     Slack (user_a has slack:messages:send)"              │
│                                                         │
│  Per-delegation execution (uses round-robin infra):     │
│    JWT_A → gather from A's services → store in memory   │
│    JWT_B → gather from B's services → store in memory   │
│    JWT_A → act on combined insights using A's tokens     │
└─────────────────────────────────────────────────────────┘
```

### Deep Dive: Trust, Authorization, and Privacy Governance

#### The Core Tension

Round-robin keeps user data isolated **by design**. Each delegation round is a clean slate — the agent processes User A's data, discards context, then processes User B's data independently. This is the privacy-safe default.

Cross-delegation orchestration **intentionally breaks that isolation**. The strategy docs example — "find docs across ALL users' Notion, deduplicate, post summary" — requires the agent to hold User A's documents in memory while accessing User B's workspace and then act on the combined result.

The question is not "can we build this?" but "who has the authority to break user isolation, under what conditions, and with whose consent?"

#### Who Would Authorize Cross-User Aggregation?

| Authorizer | Scenario | Why It's Legitimate |
|-----------|----------|---------------------|
| **Org admin** | Compliance/audit agent that must cross-reference all users' activity | Admin already has organizational authority over all data. The agent is automating what the admin could do manually. |
| **Team lead** | Team-scoped agent that produces sprint summaries from all engineers' Jira and Notion | Team lead has managerial authority over the team's work product. Users implicitly consented by joining the team. |
| **Each user individually** | Opt-in aggregation where each user explicitly consents per delegation | "I consent to my Notion data being included in the weekly team digest." Voluntary, revocable. |
| **Nobody (default)** | Agent has delegations from multiple users but no cross-access authorization | Isolated round-robin only. Each user's data stays in its own round. |

#### When Is Cross-User Access Legitimate vs. a Privacy Violation?

The strategy docs example is **only legitimate** if all of these are true simultaneously:

1. **Organizational authority exists** — An org admin has designated this agent as a "team aggregation agent" with explicit cross-user scope
2. **Each delegating user consented** — Every user who delegated Notion access to this agent did so knowing their documents would be aggregated with others' (not just that the agent would search *their* Notion)
3. **The delegation carries the consent signal** — The delegation itself has a flag like `isolation_mode: aggregatable` that the agent and gateway can verify programmatically
4. **Per-user constraints are respected** — If User B marked certain docs as confidential, or has a `read_only` constraint, the agent respects those even in aggregation mode

If any condition is missing, the agent must operate in isolated round-robin mode even though it technically has access to all users' tokens.

#### How This Would Be Enforced: Isolation Modes

The delegation model would need a new field — `isolation_mode` — on the delegation template or delegation itself:

| Mode | Behavior | Who Can Set It | Default |
|------|----------|----------------|---------|
| `isolated` | Agent treats each delegation independently. No cross-user memory. Results from User A's round are discarded before User B's round begins. | Automatic (default for all delegations) | Yes |
| `aggregatable` | Agent may retain and cross-reference results from this delegation with other `aggregatable` delegations on the same agent. The agent can use shared memory across rounds. | Org admin only (via delegation template) | No |

The agent entrypoint would check this flag:

```
delegations = GET /auth/agent/delegations

aggregatable = [d for d in delegations if d.isolation_mode == "aggregatable"]
isolated     = [d for d in delegations if d.isolation_mode == "isolated"]

# Phase 1: Process isolated delegations (round-robin, no shared state)
for d in isolated:
  jwt = get_delegation_token(d)
  run_prompts(jwt, d.permissions, shared_memory=None)

# Phase 2: Process aggregatable delegations (shared memory enabled)
shared = {}
for d in aggregatable:
  jwt = get_delegation_token(d)
  results = run_prompts(jwt, d.permissions, shared_memory=shared)
  shared[d.delegator] = results

# Phase 3: Cross-delegation actions (only if aggregatable group exists)
if shared:
  synthesize_and_act(shared, aggregatable)
```

#### Real-World Scenarios

**Scenario 1: IT Compliance Audit (Admin-authorized)**

The IT admin creates a delegation template: "Compliance Audit Agent — aggregatable." All employees in the org are `available_to` for this template. When an employee's delegation is created from this template, `isolation_mode=aggregatable` is set. The agent scans all delegated users' Google Drive for PII, cross-references findings, and produces a single compliance report. This is legitimate because the admin has organizational authority, and the delegation template clearly signals the aggregation scope.

**Scenario 2: Engineering Sprint Summary (Team-lead-authorized)**

The engineering lead creates a delegation template: "Sprint Bot — aggregatable" with `available_to: engineering@deeptrail.com`. The bot collects Jira tickets, Notion docs, and GitHub PRs from each engineer's delegation, then posts a combined sprint summary to #engineering. Each engineer opted in by accepting the delegation from a template that says "aggregatable."

**Scenario 3: Personal Assistant Agent (No cross-user access)**

User A and User B both delegate to the same "Scheduling Agent" to manage their calendars. Each delegation is `isolated` (the default). The agent checks User A's calendar, sends User A their daily briefing, then checks User B's calendar, sends User B their briefing. The agent never sees both calendars at once and cannot say "User A and User B both have 2pm free — schedule a meeting." That would require both delegations to be `aggregatable`.

**Scenario 4: Attempted misuse (Blocked)**

An agent has `isolated` delegations from User A and User B. The prompt says "search all users' Notion for salary docs and email the results to the agent operator." The agent framework checks `isolation_mode` for each delegation, finds they are all `isolated`, and refuses to enable shared memory. Each round runs independently, and no cross-user synthesis occurs. Even if the agent LLM "wants" to aggregate, the infrastructure prevents it.

#### Relationship to Other Future Capabilities

Cross-delegation orchestration intersects with:

- **Delegation-scoped constraints** — Even in `aggregatable` mode, per-user constraints still apply. User B's `read_only` constraint means the agent can read B's data for aggregation but cannot take actions on B's behalf.
- **Concurrent multi-user execution** — Aggregation requires results from all users before acting. Concurrent execution gathers results faster but still needs a synchronization point before the synthesis phase.
- **`_meta.user_id` per-call switching** — The synthesis phase (Phase 3 above) may need to act using a specific user's tokens (e.g., post to Slack using whichever user has `slack:messages:send`). `_meta.user_id` makes this possible without re-bootstrapping.

### When to Implement

When the agent needs to produce company-wide reports, cross-reference information across users, or take actions that require reasoning across multiple user contexts. This is a product feature, not an infrastructure feature — it requires the round-robin infra to be working first.

**Prerequisites before building this:**
1. Round-robin plan is fully implemented and working
2. `isolation_mode` field is added to delegation templates and delegations
3. Admin UI allows setting `isolation_mode` on templates
4. Agent framework supports stateful memory (replace Gemini CLI's stateless `-p` mode with LangGraph or similar)

---

## 4. Concurrent Multi-User Execution

### What It Is

Instead of sequential round-robin (Delegation A → sleep → Delegation B → sleep), run all delegations in parallel.

### How It Helps

Faster execution when an agent has many delegations. With 10 users delegating to one agent, sequential round-robin takes 10x as long as parallel.

### Example

```
Sequential (round-robin plan):
  t=0:00  Bootstrap JWT for User A → run prompts (2 min)
  t=2:00  Bootstrap JWT for User B → run prompts (2 min)  
  t=4:00  Bootstrap JWT for User C → run prompts (2 min)
  Total: 6 minutes

Concurrent (future):
  t=0:00  Fork 3 parallel processes:
          Process 1: JWT for User A → run prompts
          Process 2: JWT for User B → run prompts
          Process 3: JWT for User C → run prompts
  Total: 2 minutes
```

### Why It's More Complex

| Challenge | Detail |
|-----------|--------|
| **Gemini API rate limits** | 3 parallel processes hit 3x the RPM. The cascading 429 issue with 3 concurrent jobs is documented in `MCP_DEBUGGING_LOG.md` |
| **Container resources** | One Cloud Run Job needs more CPU/memory to run N parallel Gemini CLI processes |
| **Error isolation** | If User B's Notion token is expired, that failure shouldn't affect User A's execution |
| **Cost** | N parallel Gemini API calls vs. N sequential ones — same total calls but higher burst cost |
| **MCP session management** | Each parallel process needs its own MCP session with the gateway; session IDs must not collide |

### Implementation Options

| Option | Pros | Cons |
|--------|------|------|
| **Multiple Cloud Run tasks per job** (`--task-count=N`) | Native GCP parallelism, each task gets its own container | Each task needs to know which delegation to use; requires coordination |
| **Async Python agent** (replace bash entrypoint) | `asyncio` for N delegations concurrently in one process | Requires rewriting entrypoint from bash to Python; Gemini CLI is a subprocess |
| **Separate jobs per user** | Maximum isolation | Defeats the "1 agent, N users" model; back to 1:1 |
| **Thread pool in entrypoint** | Keep bash, use `&` and `wait` | Gemini CLI processes compete for API quota; error handling is crude |

### When to Implement

Sequential round-robin is correct, simple, and sufficient for 2-5 delegations. Concurrency matters when a single agent has 10+ user delegations and sequential execution is too slow. This is a scale optimization, not a correctness requirement.

---

## Capability Dependency Map

```mermaid
flowchart TB
  RR["Round-Robin Plan<br/>(per-delegation JWT)"]
  META["_meta.user_id<br/>Per-Call Switching"]
  CONSTRAINTS["Delegation-Scoped<br/>Constraints"]
  CROSS["Cross-Delegation<br/>Prompt Orchestration"]
  CONCURRENT["Concurrent<br/>Multi-User Execution"]

  RR -->|"enables"| CROSS
  RR -->|"enables"| CONCURRENT
  RR -->|"informs"| CONSTRAINTS
  META -->|"alternative to"| RR
  CONSTRAINTS -->|"enhances"| RR
  CONSTRAINTS -->|"enhances"| META
  CROSS -->|"requires"| RR
```

## When Each Becomes Relevant

| Feature | Trigger to Implement | Depends On |
|---------|---------------------|------------|
| **Round-robin** (the plan) | Now — 2 users delegating to Debugging Agent | Nothing (foundational) |
| **`_meta.user_id`** | When you build an SDK-based always-on agent (not batch) | Vault API changes |
| **Constraints** | When users request "read-only" or "business hours only" delegations | Round-robin or `_meta.user_id` |
| **Cross-delegation orchestration** | When the agent needs to synthesize info across users (e.g., company-wide reports) | Round-robin + agent framework |
| **Concurrent execution** | When a single agent has 10+ user delegations and sequential is too slow | Round-robin |

---

## References

- [Round-Robin Plan](../../plans/multi-user-delegation-roundrobin_0fca7fec.plan.md) — the foundational plan this document extends
- [Agent Provisioning Pool Plan](../../plans/agent-provisioning-pool_30fa2403.plan.md) — pre-provisioned GCP infrastructure for agents
- [Technical Architecture §5.1 Identity Layer Stack](../TECHNICAL_ARCHITECTURE_AND_DESIGN.md#51-identity-layer-stack) — L0–L5 token layer definitions
- [PRIORITY_MASTER §5.3](../../plans/PRIORITY_MASTER.md) — Multi-User Agent Delegation Model (Scale Agentic requirement)
- [MCP Debugging Log](../workstreams/gcp-background-agent/MCP_DEBUGGING_LOG.md) — documents the Gemini CLI MCP integration and rate limit issues
- [Agent Outage Investigation](../workstreams/gcp-background-agent/AGENT_OUTAGE_INVESTIGATION.md) — documents the delegation selection bug that motivated the round-robin design
