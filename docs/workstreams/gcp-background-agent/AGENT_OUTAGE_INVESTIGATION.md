# Agent Outage Investigation: May 29 → June 3, 2026

## Executive Summary

All three production agents (Thunderbolt, Engineering Audit, Debugging) stopped showing as "active" after May 29, 2026. Investigation revealed **four layered infrastructure failures** plus a **design limitation** that collectively prevented agent activity — none of which existed when the agents were originally deployed on May 20. Each failure was introduced by infrastructure changes made between May 20–29 that silently broke assumptions the working system relied on.

**Root causes (in order of discovery):**

| # | Failure | Impact | When Introduced |
|---|---------|--------|-----------------|
| 1 | `LifecycleService` filtered by `is_active=True` | Agents showed "authenticated" even with recent activity | Pre-existing bug, masked while agents had open sessions |
| 2 | Gateway `env_prefix` mismatch | 0 MCP backends loaded → agents had no tools | Exposed by Terraform cloud_run.tf refactoring |
| 3 | Load balancer `/mcp` path not routed | MCP requests hit frontend → 307 redirect to /login | Exposed by switching agent from direct URL to LB URL |
| 4 | JWT secret mismatch between control plane and gateway | Gateway rejected all agent JWTs as invalid signature | Exposed by adding `SECRET_KEY` to gateway without matching control plane |
| 5 | Single-owner JWT with merged permissions | Multi-user delegation non-functional — vault only resolves one user's tokens | Design limitation discovered post-fix |

**Resolution:** Issues 1–4 fixed and deployed. Thunderbolt Agent confirmed **active** at `2026-06-03T10:48:41Z`. Issue 5 resolved with per-delegation JWT and round-robin execution (see Lesson 6).

---

## Timeline: What Worked Before (May 20–29)

On May 20, 2026, the first agent (Debugging Agent) was deployed as a Cloud Run Job after a 10-attempt debugging process to get Gemini CLI working with the MCP Streamable HTTP protocol (documented in `MCP_DEBUGGING_LOG.md`). By May 29, three agents were running successfully on a Cloud Scheduler cadence.

### Why It Worked Then

The original deployment had these characteristics:

1. **Direct Cloud Run URL for MCP**: Agents connected to `https://deeptrail-gateway-flhiwg2wfa-uc.a.run.app/mcp` — bypassing the load balancer entirely
2. **`JWT_SECRET` env var on control plane**: The Terraform originally passed `JWT_SECRET` from Secret Manager to the control plane
3. **Gateway had no `SECRET_KEY` env var**: The gateway's `proxy_config.py` loaded `jwt_secret_key` with a hardcoded default — but it happened to work because agents were talking directly to the gateway using the direct Cloud Run URL, and the JWT validation used the same default as the control plane's Dockerfile `ENV SECRET_KEY`
4. **Sessions stayed open**: Cloud Run Jobs didn't always cleanly close sessions, so `AgentSession.is_active` remained `True` for some rows, causing `LifecycleService` to count them as "active"

### What Changed Between May 20–29

Several infrastructure changes were made during this period:

| Change | Effect |
|--------|--------|
| Terraform refactored `JWT_SECRET` → `SECRET_KEY` on control plane | Control plane now reads `SECRET_KEY` from Secret Manager, but Dockerfile `ENV SECRET_KEY` was already set to a different default |
| Agent `GATEWAY_URL` changed from direct Cloud Run URL to `https://app.deepsecure.one/mcp` | MCP traffic now routes through the load balancer |
| Gateway `SECRET_KEY` added from Secret Manager | Gateway now validates JWTs with the real secret, not the hardcoded default |
| Delegation tokens created on May 20 expired (8h TTL) | Agents had no permissions; new 30d/90d delegations were created on June 3 |
| Agent sessions ended naturally | `is_active=False` on all sessions → `LifecycleService` stopped counting them |

---

## Investigation Deep Dive

### Problem 1: Agents Showing "Authenticated" Instead of "Active"

**Symptom:** Admin Fleet UI showed all agents as `status: "authenticated"` and `last_active_at: null`, even though `agent_sessions` table had records showing Thunderbolt Agent was active as recently as May 29 with 670+ sessions.

**Root Cause:** `LifecycleService` had two bugs in its database queries:

```python
# lifecycle_service.py — BEFORE fix
# compute_state_bulk: only counted OPEN sessions as "active"
active_agents = set(
    row[0]
    for row in self._db.query(AgentSession.agent_id)
    .filter(
        AgentSession.agent_id.in_(agent_ids),
        AgentSession.last_activity_at >= cutoff,
        AgentSession.is_active.is_(True),    # ← BUG: excluded ended sessions
    )
    .distinct().all()
)

# get_last_active_at: only looked at open sessions
row = (
    self._db.query(AgentSession.last_activity_at)
    .filter(
        AgentSession.agent_id == agent_id,
        AgentSession.last_activity_at.isnot(None),
        AgentSession.is_active.is_(True),    # ← BUG: excluded ended sessions
    )
    .order_by(AgentSession.last_activity_at.desc())
    .first()
)
```

**Why this wasn't an issue before:** Cloud Run Job containers don't always cleanly close sessions (the process exits before the session cleanup runs). So some `AgentSession` rows retained `is_active=True`, and the filter happened to include them. Once all sessions were properly closed (or aged out), the filter excluded everything.

**Fix:** Removed the `is_active.is_(True)` filter from both methods. An agent that ran 1 hour ago should show as "active" regardless of whether it cleanly closed its session.

```python
# lifecycle_service.py — AFTER fix
# compute_state_bulk: counts ANY recent session activity
active_agents = set(
    row[0]
    for row in self._db.query(AgentSession.agent_id)
    .filter(
        AgentSession.agent_id.in_(agent_ids),
        AgentSession.last_activity_at >= cutoff,
        # No is_active filter — recent activity = active
    )
    .distinct().all()
)
```

**File:** `deeptrail-control/app/services/lifecycle_service.py`

---

### Problem 2: Gateway Dynamic Registry — 0 Backends Loaded

**Symptom:** Gateway logs showed continuous failures every 60 seconds:

```
Registry initial load failed (will rely on hardcoded backends): All connection attempts failed
Dynamic registry: 0 backends loaded from Control Plane
```

Zero backends means zero MCP tools. When an agent calls `tools/list`, it gets an empty array. The agent literally has nothing to do.

**How the Dynamic Registry works:**

At startup, the gateway creates a `DynamicBackendLoader` that fetches the service catalog from the control plane:

```
Gateway startup
  → GatewaySettings() created
  → DynamicBackendLoader(
        control_plane_url=gw_settings.control_plane_url,
        internal_api_token=gw_settings.gateway_internal_api_token,
    )
  → loader.initial_load()
      → GET {control_plane_url}/api/v1/internal/services/registry
      → Parse response → Register backends → Cache tools
  → loader.run_refresh_loop() (every 60s)
```

**Root Cause:** The gateway has **two separate configuration systems** that resolve environment variables differently:

| Config Class | Used By | How It Reads Env Vars | Result in Production |
|-------------|---------|----------------------|---------------------|
| `ProxyConfig` (proxy_config.py) | JWT validation middleware | `os.getenv("CONTROL_PLANE_URL", ...)` — reads env var directly | **Correct**: `https://deeptrail-control-flhiwg2wfa-uc.a.run.app` |
| `GatewaySettings` (config.py) | Dynamic registry loader | Pydantic `env_prefix="GATEWAY_"` — expects `GATEWAY_CONTROL_PLANE_URL` | **Wrong**: falls back to `http://localhost:8000` |

Cloud Run provides the env var as `CONTROL_PLANE_URL` (no prefix). But Pydantic's `env_prefix="GATEWAY_"` prepends `GATEWAY_` to all field names when scanning the environment, so it looks for `GATEWAY_CONTROL_PLANE_URL` — which doesn't exist. The field falls back to its default: `http://localhost:8000`.

The gateway was making HTTP requests to `http://localhost:8000/api/v1/internal/services/registry` inside a Cloud Run container where nothing listens on port 8000. Every attempt failed with a connection error.

Same issue for `gateway_internal_api_token`: Pydantic expected `GATEWAY_GATEWAY_INTERNAL_API_TOKEN`, but the env var is `GATEWAY_INTERNAL_TOKEN`.

**Why this wasn't an issue before:** The env_prefix configuration existed from the beginning, but it was masked because:
- The hardcoded backend configs (Notion, Slack, etc.) in `GatewaySettings` provided fallback tool definitions
- The `ProxyConfig` (which reads env vars correctly) handled JWT validation and request routing
- The dynamic registry was added later as an enhancement, and its failure was logged as a warning rather than a fatal error

**Fix:** Added `os.getenv()` fallbacks that bypass Pydantic's prefix:

```python
# config.py — AFTER fix
class GatewaySettings(BaseSettings):
    control_plane_url: str = Field(
        default_factory=lambda: os.getenv("CONTROL_PLANE_URL", "http://localhost:8000"),
    )
    gateway_internal_api_token: str = Field(
        default_factory=lambda: os.getenv(
            "GATEWAY_INTERNAL_API_TOKEN",
            os.getenv("GATEWAY_INTERNAL_TOKEN", "gateway-internal-secret-token"),
        ),
    )

    model_config = {
        "env_prefix": "GATEWAY_",
        "env_nested_delimiter": "__",
    }
```

**File:** `deeptrail-gateway/app/core/config.py`

---

### Problem 3: Load Balancer `/mcp` Path Not Routed to Gateway

**Symptom:** After fixing the registry, agents could discover tools when connecting directly to the gateway's Cloud Run URL. But agents configured with `GATEWAY_URL=https://app.deepsecure.one/mcp` received a `307 Redirect → /login` response.

**Root Cause:** The GCP URL map's `path_rule` for the gateway used a glob pattern:

```yaml
# BEFORE fix — lb.tf / URL map
path_rule:
  paths: ["/mcp/*"]          # Matches /mcp/anything but NOT /mcp alone
  service: backend-gateway
```

The MCP Streamable HTTP protocol sends all requests to a single endpoint (`POST /mcp`). The glob `/mcp/*` matches `/mcp/initialize`, `/mcp/anything`, but **does not match** `/mcp` (no trailing path). Requests to `/mcp` fell through to the `default_service` (frontend), which redirected unauthenticated requests to `/login`.

```
Agent: POST https://app.deepsecure.one/mcp  (MCP initialize)
  → URL map: /mcp does NOT match /mcp/*
  → Falls through to default_service → frontend
  → Next.js middleware: no session → 307 → /login
  → Agent sees redirect, MCP handshake fails
```

**Why this wasn't an issue before:** The original agent deployment used the **direct Cloud Run URL** (`https://deeptrail-gateway-flhiwg2wfa-uc.a.run.app/mcp`) which bypasses the load balancer entirely. When the agent configuration was later changed to use `https://app.deepsecure.one/mcp` (the production domain), the load balancer routing gap was exposed.

**Fix:** Added `/mcp` (without wildcard) to the path rule:

```terraform
# AFTER fix — lb.tf
path_rule {
  paths   = ["/mcp", "/mcp/*"]    # Now matches both /mcp and /mcp/*
  service = google_compute_backend_service.gateway.id
}
```

**File:** `infra/terraform/lb.tf`

---

### Problem 4: JWT Secret Mismatch — "Invalid JWT Signature"

**Symptom:** After fixing routing, MCP requests reached the gateway but were rejected:

```
JWT validation failed: Invalid JWT signature
```

The agent gets a JWT from the control plane (which signs it), then sends that JWT to the gateway (which validates the signature). If they use different secrets, every JWT is invalid.

**Root Cause:** A three-way misconfiguration of the JWT signing secret:

```
Control Plane signing key:
  Code reads:    os.getenv("SECRET_KEY", os.getenv("JWT_SECRET", "insecure_default"))
  Dockerfile:    ENV SECRET_KEY="your-secret-key-please-change-in-compose"
  Cloud Run:     JWT_SECRET=<real secret from Secret Manager>
  
  Resolution: Dockerfile ENV sets SECRET_KEY → os.getenv("SECRET_KEY") returns the
  Dockerfile value → never falls through to JWT_SECRET → signs with WRONG key

Gateway validation key:
  Code reads:    os.getenv("SECRET_KEY", os.getenv("JWT_SECRET", "your-secret-key-for-jwt"))
  Cloud Run:     SECRET_KEY=<real secret from Secret Manager>

  Resolution: os.getenv("SECRET_KEY") returns real secret → validates with CORRECT key

  Result: Control plane signs with "your-secret-key-please-change-in-compose"
          Gateway validates with <real jwt-secret from Secret Manager>
          → MISMATCH → "Invalid JWT signature"
```

The Dockerfile's `ENV SECRET_KEY="your-secret-key-please-change-in-compose"` acts as a default that Docker sets in the container environment. In Cloud Run, environment variables from the service configuration override Dockerfile `ENV` values — but only if they use the **same name**. The Terraform was passing `JWT_SECRET` (not `SECRET_KEY`), so the Dockerfile default for `SECRET_KEY` remained in effect.

**Why this wasn't an issue before:** Before the Terraform refactoring, the control plane had `JWT_SECRET` from Secret Manager and the code's `SECRET_KEY` field defaulted to a different value. But the gateway was also using its own hardcoded default, and since agents connected via the direct Cloud Run URL (bypassing the LB), the JWT validation used a different code path. The system worked by coincidence — both sides used their respective defaults, which happened to be compatible in the original deployment configuration.

**Fix (two parts):**

1. **Terraform:** Changed the control plane's env var from `JWT_SECRET` to `SECRET_KEY` so it overrides the Dockerfile default:

```terraform
# cloud_run.tf — AFTER fix (control plane)
env {
  name = "SECRET_KEY"           # Was: JWT_SECRET
  value_source {
    secret_key_ref {
      secret  = google_secret_manager_secret.auto["jwt-secret"].secret_id
      version = "latest"
    }
  }
}
```

2. **Code:** Updated both services to fall back from `SECRET_KEY` → `JWT_SECRET`:

```python
# deeptrail-control/app/core/config.py
SECRET_KEY: str = os.getenv("SECRET_KEY", os.getenv("JWT_SECRET", "insecure_default"))

# deeptrail-gateway/app/core/proxy_config.py (in load_config)
'jwt_secret_key': os.getenv('SECRET_KEY', os.getenv('JWT_SECRET', 'your-secret-key-for-jwt')),
```

**Files:** `infra/terraform/cloud_run.tf`, `deeptrail-control/app/core/config.py`, `deeptrail-gateway/app/core/proxy_config.py`

---

## Architecture Diagrams

### BEFORE: How the System Was Broken (May 29 → June 3)

```
┌──────────────────┐
│  Cloud Scheduler │
│  (every 6 hours) │
└────────┬─────────┘
         │ triggers
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Cloud Run Job (Agent)                                              │
│                                                                      │
│  1. Get GCP OIDC token  ──────────────────────────────────────┐      │
│  2. Bootstrap: POST /api/v1/auth/bootstrap/gcp                │      │
│     └─► JWT signed with ❌ WRONG KEY                          │      │
│  3. Configure Gemini CLI with MCP → app.deepsecure.one/mcp    │      │
│  4. Gemini CLI sends POST /mcp (initialize)                   │      │
│     └─► ❌ PROBLEM 3: LB routes /mcp to frontend (307)       │      │
│                                                                │      │
│  Even if /mcp reached gateway:                                │      │
│  5. Gateway validates JWT signature                           │      │
│     └─► ❌ PROBLEM 4: "Invalid JWT signature"                │      │
│                                                                │      │
│  Even if JWT was valid:                                       │      │
│  6. Gateway has 0 backends loaded                             │      │
│     └─► ❌ PROBLEM 2: tools/list returns []                  │      │
│                                                                │      │
│  Result: No tools, no activity, no heartbeat                  │      │
│  Admin UI: "authenticated" (not "active")                     │      │
│     └─► ❌ PROBLEM 1: LifecycleService filter bug            │      │
└──────────────────────────────────────────────────────────────────────┘
         │                                                │
         │ Bootstrap request                              │ MCP request
         ▼                                                ▼
┌─────────────────────┐                      ┌─────────────────────────┐
│  GCP Load Balancer  │                      │  GCP Load Balancer      │
│  app.deepsecure.one │                      │  app.deepsecure.one     │
│                     │                      │                         │
│  /api/v1/* → ctrl   │                      │  /mcp → ❌ frontend    │
│  /mcp/*   → gw     │                      │  /mcp/* → gw (unused)  │
└────────┬────────────┘                      └────────┬────────────────┘
         │                                            │
         ▼                                            ▼
┌─────────────────────────┐              ┌─────────────────────────────┐
│  Control Plane          │              │  Frontend (Next.js)         │
│  (deeptrail-control)    │              │  307 Redirect → /login      │
│                         │              └─────────────────────────────┘
│  Signs JWT with:        │
│  SECRET_KEY = Dockerfile│
│  default (WRONG)        │
│                         │
│  ┌───────────────────┐  │
│  │ Dockerfile:       │  │
│  │ ENV SECRET_KEY=   │  │
│  │ "your-secret-key  │  │
│  │  -please-change   │  │
│  │  -in-compose"     │  │
│  │                   │  │
│  │ Cloud Run env:    │  │
│  │ JWT_SECRET=<real> │  │
│  │                   │  │
│  │ Code reads:       │  │
│  │ os.getenv(        │  │
│  │  "SECRET_KEY"     │  │
│  │ ) → gets Docker   │  │
│  │   default, never  │  │
│  │   reaches         │  │
│  │   JWT_SECRET      │  │
│  └───────────────────┘  │
│                         │
│  ┌─────────┐            │
│  │ PostgreSQL           │
│  │ agent_sessions:      │
│  │  all is_active=False │
│  │  (sessions ended)    │
│  └─────────┘            │
└─────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Gateway (deeptrail-gateway) — if requests ever reached it      │
│                                                                  │
│  GatewaySettings (config.py):                                    │
│    env_prefix = "GATEWAY_"                                       │
│    Looks for: GATEWAY_CONTROL_PLANE_URL  (doesn't exist)         │
│    Falls back: http://localhost:8000                              │
│                                                                  │
│  DynamicBackendLoader:                                           │
│    GET http://localhost:8000/api/v1/internal/services/registry    │
│    → Connection refused → 0 backends → 0 tools                  │
│                                                                  │
│  ProxyConfig (proxy_config.py):                                  │
│    Reads CONTROL_PLANE_URL directly → CORRECT URL                │
│    But this config is used for middleware, NOT the registry       │
│                                                                  │
│  JWT validation:                                                 │
│    SECRET_KEY = <real secret from Secret Manager>                │
│    ≠ Control plane's signing key (Dockerfile default)            │
│    → "Invalid JWT signature" on every request                    │
│                                                                  │
│  ┌─────────┐                                                     │
│  │  Redis  │  (Memorystore — working fine, not the issue)        │
│  └─────────┘                                                     │
└──────────────────────────────────────────────────────────────────┘
```

### AFTER: How the System Works Now (June 3)

```
┌──────────────────┐
│  Cloud Scheduler │
│  (every 6 hours) │
└────────┬─────────┘
         │ triggers
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Cloud Run Job (Agent)                                              │
│                                                                      │
│  1. Get GCP OIDC token from metadata server                   ✅    │
│  2. POST /api/v1/auth/bootstrap/gcp → Agent JWT               ✅    │
│  3. Check delegations: GET /api/v1/auth/delegations            ✅    │
│     └─► "Found 2 active delegation(s)"                              │
│  4. gemini mcp add deepsecure https://app.deepsecure.one/mcp   ✅    │
│  5. Warmup: POST /mcp (initialize) → 200                      ✅    │
│  6. gemini -y --sandbox=false -p "Search notion..."            ✅    │
│     └─► Gemini CLI: initialize → tools/list (21 tools)              │
│     └─► tools/call: notion.search_pages → results returned          │
│  7. Activity recorded → agent_sessions.last_activity_at updated ✅   │
│                                                                      │
│  Result: Tools work, activity recorded, agent shows ACTIVE          │
└──────────────────────────────────────────────────────────────────────┘
         │                                                │
         │ Bootstrap + API                                │ MCP protocol
         ▼                                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  GCP Load Balancer — app.deepsecure.one                         │
│                                                                  │
│  Path Rules:                                                     │
│    /api/v1/*    →  backend-control   (Control Plane)             │
│    /mcp         →  backend-gateway   (Gateway)  ← FIX #3        │
│    /mcp/*       →  backend-gateway   (Gateway)                   │
│    /realms/*    →  backend-keycloak  (Keycloak)                  │
│    (default)    →  backend-frontend  (Next.js)                   │
└──────────┬──────────────────────────────────┬────────────────────┘
           │                                  │
           ▼                                  ▼
┌──────────────────────────┐     ┌──────────────────────────────────┐
│  Control Plane           │     │  Gateway                         │
│  (deeptrail-control)     │     │  (deeptrail-gateway)             │
│                          │     │                                  │
│  Cloud Run env:          │     │  Cloud Run env:                  │
│  SECRET_KEY=<jwt-secret> │     │  SECRET_KEY=<jwt-secret>         │
│  ← FIX #4: was           │     │  CONTROL_PLANE_URL=              │
│    JWT_SECRET            │     │   https://deeptrail-control-...  │
│                          │     │  GATEWAY_INTERNAL_TOKEN=<token>  │
│  Code:                   │     │                                  │
│  SECRET_KEY = os.getenv( │     │  GatewaySettings (config.py):    │
│    "SECRET_KEY",         │     │  ← FIX #2: os.getenv() fallback │
│    os.getenv(            │     │    control_plane_url =            │
│      "JWT_SECRET", ...   │     │      os.getenv("CONTROL_PLANE_  │
│    )                     │     │        URL", "localhost:8000")   │
│  )                       │     │    → Correctly resolves to       │
│  → Reads <jwt-secret>   │     │      real Control Plane URL      │
│  → Signs JWT correctly  │     │                                  │
│                          │     │  DynamicBackendLoader:            │
│                          │     │  GET https://deeptrail-control-  │
│  ┌───────────────────┐   │     │    .../api/v1/internal/services  │
│  │    PostgreSQL     │   │     │    /registry                     │
│  │  (Cloud SQL)      │   │     │  → 6 backends loaded ✅         │
│  │                   │   │     │  → 21 MCP tools cached ✅       │
│  │  agents           │   │     │                                  │
│  │  agent_sessions   │   │     │  ProxyConfig:                    │
│  │  delegation_tokens│   │     │  jwt_secret_key =                │
│  │  vault_tokens     │   │     │    os.getenv("SECRET_KEY",       │
│  │  connected_services│  │     │      os.getenv("JWT_SECRET"))    │
│  │  service_registry │   │     │  → Same <jwt-secret> value      │
│  └───────────────────┘   │     │  → JWT signatures MATCH ✅      │
│                          │     │                                  │
└──────────────────────────┘     │  ┌─────────────────────────────┐ │
                                 │  │  Redis (Memorystore)        │ │
                                 │  │  Share storage, sessions    │ │
                                 │  └─────────────────────────────┘ │
                                 └──────────────────────────────────┘
```

---

## MCP Request Flow: Complete Path (Working)

```
Agent Container                    Load Balancer              Gateway                    Control Plane
      │                                 │                         │                            │
      │  POST /mcp                      │                         │                            │
      │  {initialize}                   │                         │                            │
      │  Authorization: Bearer <JWT>    │                         │                            │
      │────────────────────────────────►│                         │                            │
      │                                 │  /mcp matches rule      │                            │
      │                                 │──────────────────────►  │                            │
      │                                 │                         │                            │
      │                                 │                         │  Validate JWT signature     │
      │                                 │                         │  (SECRET_KEY matches ✅)    │
      │                                 │                         │                            │
      │                                 │                         │  Create MCP session         │
      │                                 │  200 + Mcp-Session-Id   │                            │
      │  ◄────────────────────────────────────────────────────────│                            │
      │                                 │                         │                            │
      │  POST /mcp                      │                         │                            │
      │  {tools/list}                   │                         │                            │
      │────────────────────────────────►│──────────────────────►  │                            │
      │                                 │                         │                            │
      │                                 │                         │  DynamicBackendLoader      │
      │                                 │                         │  has 6 backends loaded      │
      │                                 │                         │  from Control Plane registry│
      │                                 │                         │                            │
      │                                 │  200, 21 tools          │                            │
      │  ◄────────────────────────────────────────────────────────│                            │
      │                                 │                         │                            │
      │  POST /mcp                      │                         │                            │
      │  {tools/call:                   │                         │                            │
      │   notion.search_pages}          │                         │                            │
      │────────────────────────────────►│──────────────────────►  │                            │
      │                                 │                         │                            │
      │                                 │                         │  1. Check delegation        │
      │                                 │                         │     permissions             │
      │                                 │                         │                            │
      │                                 │                         │  2. Get vault token         │
      │                                 │                         │─────────────────────────►  │
      │                                 │                         │  ◄─────────────────────────│
      │                                 │                         │   (encrypted OAuth token)   │
      │                                 │                         │                            │
      │                                 │                         │  3. Decrypt token (KMS)     │
      │                                 │                         │                            │
      │                                 │                         │  4. Call Notion API         │
      │                                 │                         │     with OAuth token        │
      │                                 │                         │──────► Notion API           │
      │                                 │                         │  ◄────── Results            │
      │                                 │                         │                            │
      │                                 │                         │  5. Record heartbeat        │
      │                                 │                         │─────────────────────────►  │
      │                                 │                         │   POST /internal/heartbeat  │
      │                                 │                         │                            │
      │                                 │  200, search results    │                            │
      │  ◄────────────────────────────────────────────────────────│                            │
```

---

## The Configuration Dual-System Problem

The gateway has two independent configuration systems that resolve environment variables **differently**. This is the architectural root cause of Problems 2 and 4.

```
┌────────────────────────────────────────────────────────────────────┐
│                     Gateway Configuration                         │
│                                                                    │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐ │
│  │  ProxyConfig                │  │  GatewaySettings            │ │
│  │  (proxy_config.py)          │  │  (config.py)                │ │
│  │                             │  │                             │ │
│  │  Reads env vars DIRECTLY:   │  │  Uses Pydantic env_prefix:  │ │
│  │  os.getenv("SECRET_KEY")    │  │  env_prefix = "GATEWAY_"    │ │
│  │  os.getenv("CONTROL_PLANE  │  │                             │ │
│  │    _URL")                   │  │  Expects:                   │ │
│  │                             │  │  GATEWAY_CONTROL_PLANE_URL  │ │
│  │  Used by:                   │  │  GATEWAY_GATEWAY_INTERNAL   │ │
│  │  • JWT validation middleware│  │    _API_TOKEN               │ │
│  │  • Request routing          │  │                             │ │
│  │  • Security checks          │  │  Used by:                   │ │
│  │                             │  │  • DynamicBackendLoader     │ │
│  │  ✅ Always worked correctly │  │  • Registry refresh loop    │ │
│  │                             │  │  • Health reporting         │ │
│  │                             │  │                             │ │
│  │                             │  │  ❌ Silently used defaults  │ │
│  └─────────────────────────────┘  └─────────────────────────────┘ │
│                                                                    │
│  Cloud Run Environment:                                            │
│    CONTROL_PLANE_URL = https://deeptrail-control-...               │
│    GATEWAY_INTERNAL_TOKEN = <from Secret Manager>                  │
│    SECRET_KEY = <from Secret Manager>                              │
│                                                                    │
│  ProxyConfig sees:                                                 │
│    CONTROL_PLANE_URL → ✅ "https://deeptrail-control-..."          │
│    SECRET_KEY → ✅ "<real jwt secret>"                             │
│                                                                    │
│  GatewaySettings sees (with GATEWAY_ prefix):                     │
│    GATEWAY_CONTROL_PLANE_URL → ❌ not set → "http://localhost:8000"│
│    GATEWAY_GATEWAY_INTERNAL_API_TOKEN → ❌ not set → default       │
│                                                                    │
│  FIX: Added os.getenv() fallbacks in GatewaySettings fields        │
│    control_plane_url = Field(                                      │
│      default_factory=lambda: os.getenv("CONTROL_PLANE_URL", ...)   │
│    )                                                               │
└────────────────────────────────────────────────────────────────────┘
```

---

## The JWT Secret Chain Problem

```
                    Secret Manager
                    ┌─────────────┐
                    │ jwt-secret  │
                    │ = "abc123"  │ (actual value)
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
    Terraform (control)          Terraform (gateway)
    ┌──────────────────┐         ┌──────────────────┐
    │ BEFORE:          │         │ SECRET_KEY =      │
    │ JWT_SECRET =     │         │   jwt-secret:     │
    │   jwt-secret:    │         │   latest          │
    │   latest         │         │                   │
    │                  │         │ → os.getenv(      │
    │ AFTER (fix):     │         │   "SECRET_KEY")   │
    │ SECRET_KEY =     │         │ = "abc123" ✅     │
    │   jwt-secret:    │         └──────────────────┘
    │   latest         │
    └────────┬─────────┘
             │
             ▼
    Control Plane Container
    ┌───────────────────────────────────────────────┐
    │ Layer 1: Dockerfile                           │
    │   ENV SECRET_KEY="your-secret-key-please-     │
    │                   change-in-compose"          │
    │                                               │
    │ Layer 2: Cloud Run env (overrides Dockerfile) │
    │   BEFORE: JWT_SECRET="abc123"                 │
    │     → SECRET_KEY NOT overridden               │
    │     → Dockerfile value persists               │
    │     → os.getenv("SECRET_KEY") = "your-sec..." │
    │     → SIGNS WITH WRONG KEY ❌                 │
    │                                               │
    │   AFTER:  SECRET_KEY="abc123"                 │
    │     → Overrides Dockerfile ENV                │
    │     → os.getenv("SECRET_KEY") = "abc123"      │
    │     → SIGNS WITH CORRECT KEY ✅               │
    │                                               │
    │ Layer 3: Code fallback chain                  │
    │   os.getenv("SECRET_KEY",                     │
    │     os.getenv("JWT_SECRET",                   │
    │       "insecure_default"))                    │
    │   → Now correctly resolves to "abc123"        │
    └───────────────────────────────────────────────┘
```

---

## MCP Bridge History: Why It Existed and Why We Don't Need It Anymore

### The Original Problem (May 19–20, 2026)

When we first attempted to connect Gemini CLI to the DeepSecure gateway, we went through **10 debugging attempts** (documented in `MCP_DEBUGGING_LOG.md`). The gateway's MCP Streamable HTTP implementation had several issues:

1. **Protocol version rejection** — Gateway rejected Gemini CLI's `2025-11-25` version
2. **Wrong status codes** — 204 instead of 202 for notifications
3. **Missing headers** — No `Mcp-Session-Id` on initialize response
4. **Schema violation** — `nextCursor: null` in `tools/list` (Zod requires `string | undefined`)

After fixing these protocol issues, Gemini CLI's `-p` (headless) mode still showed "MCP issues detected." We built `mcp-bridge.mjs` as a stdio-to-HTTP bridge to test whether the issue was in Gemini CLI's HTTP transport or something more fundamental. The bridge didn't help — proving the issue was in Gemini CLI's headless mode, not our HTTP implementation.

The final fix was removing `nextCursor: null` from the `tools/list` response (Attempt 10), after which everything worked.

### Why the Bridge Was Kept

After the protocol fixes landed, `mcp-bridge.mjs` was kept in the codebase as a fallback option but was not actively used. The production entrypoint (`entrypoint.sh`) uses `gemini mcp add` to configure Gemini CLI's native HTTP MCP transport directly.

### Why MCP Tools Stopped Loading (This Outage)

The "MCP tools NOT loading" symptom during this outage was **not** a repeat of the original Gemini CLI issue. The original issue was at the MCP protocol level (Gemini CLI couldn't parse our responses). This outage was at the infrastructure level:

```
Original issue (May 19):       This outage (May 29+):
Protocol ─── broken             Protocol ─── working ✅
  ↓                               ↓
Gemini CLI can't parse          Gemini CLI parses fine
  ↓                               ↓
Tools not registered            BUT: requests don't reach gateway (LB routing)
                                  OR: JWT rejected (secret mismatch)
                                  OR: gateway has 0 tools (registry failure)
```

---

## Why Were Delegations Expired?

The original delegations created on May 20 used an **8-hour TTL** (the default at the time). By May 21, they had expired. The agents continued running on Cloud Scheduler but failed silently — they could bootstrap (get a JWT) but had no delegated permissions, so every tool call was rejected by the gateway's permission check.

This was partially masked because:
- The `entrypoint.sh` didn't originally check for active delegations before proceeding
- Failed tool calls were logged as warnings, not fatal errors
- The agent job completed with exit code 0 even when all tools failed

**Fix applied:** Added a pre-flight delegation check to `entrypoint.sh` that fails loudly:

```bash
DELEGATION_CHECK=$(curl -sf \
  -H "Authorization: Bearer ${AGENT_JWT}" \
  "${CONTROL_URL}/api/v1/auth/delegations" \
  | jq 'if type == "array" then length else 0 end') || DELEGATION_CHECK="0"

if [ "${DELEGATION_CHECK}" = "0" ]; then
  echo "FATAL: No active delegations for agent ${AGENT_ID}"
  exit 1
fi
```

New delegations were created with 30-day and 90-day TTLs.

---

## Files Modified

| File | Change | Fixes Problem |
|------|--------|---------------|
| `deeptrail-control/app/services/lifecycle_service.py` | Removed `is_active.is_(True)` filter from `get_last_active_at` and `compute_state_bulk` | #1 |
| `deeptrail-gateway/app/core/config.py` | Added `os.getenv()` fallbacks for `control_plane_url` and `gateway_internal_api_token` to bypass Pydantic `env_prefix` | #2 |
| `deeptrail-gateway/app/backends/dynamic_registry.py` | Increased `httpx` timeout from 10s to 30s for cold starts | #2 |
| `infra/terraform/lb.tf` | Added `/mcp` (without wildcard) to gateway path rule | #3 |
| `infra/terraform/cloud_run.tf` | Changed control plane env var from `JWT_SECRET` to `SECRET_KEY` | #4 |
| `deeptrail-control/app/core/config.py` | Added `os.getenv("JWT_SECRET")` fallback for `SECRET_KEY` field | #4 |
| `deeptrail-gateway/app/core/proxy_config.py` | Added `os.getenv("JWT_SECRET")` fallback for `jwt_secret_key` | #4 |
| `agents/gemini/entrypoint.sh` | Added pre-flight delegation check with loud failure | Delegation expiry |

---

## Lessons Learned

### 1. Pydantic `env_prefix` Is a Footgun

When `env_prefix="GATEWAY_"` is set, Pydantic silently prepends the prefix to every field name when scanning environment variables. If the actual Cloud Run env var doesn't have the prefix, the field falls back to its default — **with no warning**. This created a production configuration that looked correct (env vars were set) but was silently ignored.

**Rule:** When using `env_prefix` in Pydantic settings, always add explicit `os.getenv()` fallbacks for critical fields, or don't use `env_prefix` at all for fields that receive env vars from external systems (like Terraform/Cloud Run).

### 2. Dockerfile ENV Defaults Can Override Secret Manager

Docker's `ENV` directive sets environment variables that persist into the running container. Cloud Run service env vars override them — but only if the names match exactly. Passing `JWT_SECRET` from Secret Manager doesn't override `SECRET_KEY` from the Dockerfile. The code reads `SECRET_KEY` first, gets the Dockerfile value, and never falls through to `JWT_SECRET`.

**Rule:** Ensure Terraform env var names match the Dockerfile `ENV` names they're intended to replace. Or better: remove hardcoded defaults from Dockerfiles and require all secrets to come from the runtime environment.

### 3. Load Balancer Path Matching Is Literal

GCP URL map `path_rule` with `/mcp/*` matches `/mcp/anything` but **not** `/mcp` (no trailing path). The MCP Streamable HTTP protocol sends all requests to a single endpoint (`POST /mcp`), not to sub-paths. This is different from REST APIs where `/api/v1/*` naturally matches all endpoints.

**Rule:** For protocols that use a single endpoint path, always include both the exact path and the wildcard: `["/mcp", "/mcp/*"]`.

### 4. Two Configuration Systems = Two Failure Modes

The gateway had `ProxyConfig` (for middleware) and `GatewaySettings` (for the registry) reading the same env vars differently. One worked, the other didn't. Because they serve different subsystems, the failure in one didn't affect the other — the gateway appeared "healthy" (middleware worked, health checks passed) while the registry silently failed.

**Rule:** Consolidate configuration into a single system, or ensure all config classes resolve env vars identically.

### 5. Silent Failures Compound

Each of these four issues would have been easy to diagnose in isolation. But combined, they created a situation where:
- The admin UI showed wrong status (Problem 1) → misleading diagnostics
- The gateway had no tools (Problem 2) → but appeared healthy
- The load balancer routed to the wrong service (Problem 3) → returned valid HTTP responses (307)
- The JWT was rejected (Problem 4) → returned a clear error, but only if requests reached the gateway

**Rule:** Add startup validation that verifies critical assumptions (registry loaded > 0 backends, JWT secret matches expected value, MCP endpoint is reachable). Fail loudly on misconfiguration instead of falling back to defaults.

### 6. Single-Delegation JWT Prevents Multi-User Execution

While investigating agent behavior post-fix, a design limitation was discovered: the GCP bootstrap creates **one JWT with a single `owner` claim**, even when the agent has delegations from multiple users. The bootstrap merges permissions from all active delegations into one token, but the vault can only resolve OAuth tokens for the JWT's `owner` user. An agent with delegations from User A (notion/slack) and User B (github) can only use User A's tokens — User B's services are unreachable despite having permissions in the JWT.

This is not a bug in the outage sense (the agent runs and completes work for one user), but it means multi-user delegation — a core platform feature — was not functional in production.

**Fix:** Implemented per-delegation JWT with round-robin execution:
1. Bootstrap issues a "discovery JWT" scoped to the newest delegation (no more merged permissions)
2. New `GET /auth/agent/delegations` endpoint lets the agent list its active delegations
3. New `POST /auth/agent/delegation-token` endpoint exchanges a delegation_id for a scoped JWT with that delegation's owner and permissions
4. Agent entrypoint rewritten to cycle through delegations: for each, get a scoped JWT, configure the MCP client, run prompts matching that delegation's services, then move to the next

**Rule:** Each JWT must have exactly one `owner` so the vault token lookup is unambiguous. Multi-user support requires multiple JWTs, not merged claims in a single token.

See: [Multi-User Delegation Round-Robin Plan](../../../plans/multi-user-delegation-roundrobin_0fca7fec.plan.md), [Multi-User Delegation Future Capabilities](../../design/MULTI_USER_DELEGATION_FUTURE.md)

---

## Verification

After all fixes were deployed on June 3, 2026:

```bash
# Agent execution log
[2026-06-03T10:47:14] Bootstrap successful. JWT obtained.
[2026-06-03T10:47:19] Gemini CLI configured with MCP server → https://app.deepsecure.one/mcp
[2026-06-03T10:47:19] Gateway warm.
[2026-06-03T10:47:19] Running prompt 0: Search notion...
[2026-06-03T10:47:27] The search for "strategy" in Notion returned no results.

# Admin Fleet API
{
  "name": "Thunderbolt Agent",
  "status": "active",                              ← Was "authenticated"
  "last_active_at": "2026-06-03T10:48:41.763707Z"  ← Was null
}
```
