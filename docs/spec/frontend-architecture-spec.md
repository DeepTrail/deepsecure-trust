# Spec: DeepSecure Frontend — Product Dashboard & Interactive Demo

## 1. Objective

Add a Next.js frontend to the `deepsecure-mvp` monorepo that serves two purposes: (1) a production dashboard for managing agents, policies, service connections, audit trails, vault, and tasks, and (2) a public interactive console demo embeddable on the deeptrail.com marketing site.

The frontend uses a BFF (Backend-for-Frontend) auth pattern where the browser never sees raw JWTs — all authentication flows through httpOnly cookies translated to `Authorization: Bearer` headers server-side.

### Personas

Four enterprise personas interact with the frontend. See [`docs/PRODUCT_USE_CASES_BY_PERSONA.md`](../PRODUCT_USE_CASES_BY_PERSONA.md) for full use case details.

| Persona | Primary Interactions | Key Frontend Surfaces |
|---------|---------------------|----------------------|
| **Employee (End User)** | Onboarding, connect services, register agents, delegate permissions, monitor activity | Welcome wizard, service connection, agent registration, delegation builder, my-agent activity |
| **Security Team** | Policy definition, threat monitoring, audit, compliance, incident response | Security dashboard, alerts, tool analytics, compliance reports, incident response workflow |
| **Engineering Team** | Build agents, debug MCP sessions, test tool calls | MCP Debug Console, SDK reference, agent testing sandbox |
| **IT Administrator** | Platform setup, service/agent governance, emergency controls | Admin settings, service registry, role permissions, vendor agents, emergency controls, gateway ops |

### User Stories / Acceptance Criteria

**Employee (End User) — Priority 1:**
- As a **new employee**, I want a guided onboarding flow that walks me through connecting my first service, registering an agent, and creating a delegation
- As an **employee**, I want to see a welcome dashboard with quick actions (connect service, register agent, view tools) when I have no agents yet
- As an **employee**, I want to register an agent by choosing type (my own / vendor / shared team), selecting a vendor from the approved list, naming it, and describing its purpose
- As an **employee**, I want to create a delegation using a permission checklist grouped by service, where role-restricted permissions are locked with explanatory text
- As an **employee**, I want to monitor my agent's activity: today's action count vs. limit, delegation expiry, recent tool calls with success/denied status, and quick actions to adjust or revoke

**Security Team — Priority 2:**
- As a **security analyst**, I want a security dashboard showing total agent actions, active agents, permission denials, policy violations, and anomalies with severity-ranked alerts
- As a **security analyst**, I want to see permission denial analysis grouped by permission and agent, with actionable insights
- As a **security analyst**, I want tool call analytics: usage by backend, top tools, success/denial rates, and delegation chain visualization
- As a **security analyst**, I want to generate compliance reports (SOC2, PII access, permission denials, delegation chain audit) and schedule recurring reports
- As a **security analyst**, I want an incident response workflow view: Contain → Investigate → Remediate with checklist progress tracking

**Engineering Team — Priority 3:**
- As a **developer**, I want an MCP Debug Console showing active sessions, call traces, permission denied details with fix suggestions, and ability to copy cURL commands
- As a **developer**, I want an SDK reference page built into the dashboard with code snippets for agent registration, authentication, and MCP tool calls

**IT Administrator — Priority 4:**
- As an **IT admin**, I want to manage an Approved Services Registry: service list with status, availability by role, data classification, and add/import/bulk-update actions
- As an **IT admin**, I want to configure role-based permission limits: per-role maximum delegable permissions, default constraints (TTL, max actions/day, working hours)
- As an **IT admin**, I want to manage approved vendor agents: vendor list with status, employee count, and approval workflow
- As an **IT admin**, I want emergency controls: suspend agent, suspend all vendor agents, disable all delegations, and organization-wide lockdown mode
- As an **IT admin**, I want a Gateway Operations Dashboard: metrics (requests, latency, sessions), backend MCP server status, recent errors, and credential vault health

**Prospect / Marketing:**
- As a **prospect evaluating DeepTrail**, I want to see an animated interactive demo at `/demo` showing the platform's governance capabilities without logging in
- As a **marketing team member**, I want to embed the `/demo` page on deeptrail.com via iframe

### Success Criteria

- [ ] SSO login via Keycloak (dev) and Google Workspace (production) works end-to-end
- [ ] New user sees welcome dashboard with guided onboarding flow
- [ ] Employee can: connect service → register agent → create delegation → monitor activity (full self-service loop)
- [ ] Security team can: view security dashboard → investigate alert → generate compliance report
- [ ] IT admin can: manage service registry → configure role permissions → trigger emergency controls
- [ ] Developer can: view MCP Debug Console → trace tool calls → copy cURL commands
- [ ] All dashboard pages render with real data from the control plane
- [ ] CRUD operations work through the BFF
- [ ] `/demo` route loads in <1s with SSG, no auth required, embeddable via iframe
- [ ] All 6 demo scenes auto-rotate and match the [console demo spec](../design/deeptrail-console-interactive-demo.md)
- [ ] `docker compose up` starts the frontend alongside existing services
- [ ] Browser never stores or has JavaScript access to JWTs

---

## 2. Technical Design

### Services Affected

| Service | Impact | Changes |
|---------|--------|---------|
| `frontend/` (NEW) | **New** | Entire Next.js application — all phases |
| `deeptrail-control` | **Low** (Ph 1) | Add `POST /api/v1/auth/refresh` endpoint |
| `deeptrail-control` | **Medium** (Ph 5) | Add `/api/v1/audit/analytics/*`, `/api/v1/audit/reports/generate` endpoints |
| `deeptrail-control` | **Medium** (Ph 7) | Add `/api/v1/admin/services`, `/admin/roles`, `/admin/vendor-agents`, `/admin/emergency/*` endpoints |
| `deeptrail-control` | **Low** (Ph 4) | Modify `POST /api/v1/agents/` for backend-generated Ed25519 keypair; add `GET /api/v1/agents/{id}/tools` |
| `deeptrail-gateway` | **None** (Ph 1–4) | No changes — frontend proxies through control plane |
| `deeptrail-gateway` | **Low** (Ph 6) | Add `/debug/sessions`, `/debug/sessions/{id}/trace`, `/debug/replay/{id}` endpoints |
| `deeptrail-gateway` | **Low** (Ph 7) | Add `/admin/metrics`, `/admin/backends/status` endpoints |
| `deepsecure` (SDK) | **None** | No changes |
| `docker-compose.yml` | **Low** | Add `frontend` service definition |

### Architecture: BFF Auth Pattern

```
Browser (localhost:3000)
  │
  │  httpOnly cookie (__session)
  │  + X-CSRF-Token header
  ▼
Next.js Server (frontend container :3000)
  │
  │  middleware.ts → validates cookie exists
  │  app/api/proxy/[...path]/route.ts → decrypts cookie → extracts JWT
  │                                   → checks exp (refresh if <5min)
  │                                   → adds Authorization: Bearer header
  │                                   → forwards to backend
  ▼
deeptrail-control (container :8001, host :8000)
deeptrail-gateway  (container :8001, host :8002)
```

### API Contracts

#### New Backend Endpoint (Control Plane)

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/v1/auth/refresh` | Issue a completely new JWT with reset TTL (not extend existing token) | `Authorization: Bearer <current_jwt>` |

**Request:** Empty body. The current (still-valid) JWT is in the Authorization header.

**Behavior:** Validates the current JWT is not expired, then issues a **brand new JWT** with a fresh `exp` claim (full TTL reset). The old JWT remains valid until its original expiry. This is a full token rotation, not an expiry extension.

**Response (200):**
```json
{
  "token": "<completely_new_jwt>",
  "expires_in": 28800
}
```

**Response (401):** JWT expired or invalid — client must re-authenticate via SSO.

**Rationale:** The existing SSO-specific refresh (`POST /api/v1/auth/sso/refresh`) only handles SSO tokens. A general refresh endpoint allows the BFF to transparently extend sessions without the user re-authenticating, regardless of how they originally logged in.

#### Frontend BFF Routes (Next.js API Routes)

| Method | Path | Purpose | Backend Call |
|--------|------|---------|-------------|
| POST | `/api/auth/login` | Authenticate, set httpOnly cookie | `POST /api/v1/auth/login` |
| POST | `/api/auth/logout` | Clear cookies | None (client-only) |
| GET | `/api/auth/sso/[idp]` | Initiate SSO redirect | `GET /api/v1/auth/sso/{idp}/authorize` |
| GET | `/api/auth/sso/[idp]/callback` | SSO callback, set cookie | `GET /api/v1/auth/sso/{idp}/callback` |
| ALL | `/api/proxy/[...path]` | Authenticated proxy to control plane / gateway | Varies — JWT injected from cookie |
| GET | `/api/events/stream` | SSE passthrough (Phase 4) | `GET /api/v1/audit/events/stream` (to be built) |

#### Existing Backend Endpoints Used by Frontend

**Auth & SSO:**

| Page | Method | Endpoint | Notes |
|------|--------|----------|-------|
| SSO Login | GET | `/api/v1/auth/sso/{idp}/authorize` | idp: `keycloak`, `google`, `okta`, `entra` |
| SSO Callback | GET | `/api/v1/auth/sso/{idp}/callback` | Returns JWT in response |
| SSO Refresh | POST | `/api/v1/auth/sso/refresh` | SSO-specific token refresh |

**Employee — Core Pages (Phases 1–2):**

| Page | Method | Endpoint | Notes |
|------|--------|----------|-------|
| Dashboard | GET | `/api/v1/audit/summary` | Metrics cards |
| Dashboard | GET | `/api/v1/audit/events` | Recent activity feed |
| Agents | GET | `/api/v1/agents/` | Agent list |
| Agents | POST | `/api/v1/agents/` | Create agent |
| Agents | GET | `/api/v1/agents/{agent_id}` | Agent detail |
| Agents | PATCH | `/api/v1/agents/{agent_id}` | Update agent |
| Agents | DELETE | `/api/v1/agents/{agent_id}` | Delete agent |
| Delegation | POST | `/api/v1/auth/delegate` | User→agent delegation |
| Policies | GET | `/api/v1/policies/` | Policy list |
| Policies | POST | `/api/v1/policies/` | Create policy |
| Policies | GET | `/api/v1/policies/{policy_id}` | Policy detail |
| Policies | PUT | `/api/v1/policies/{policy_id}` | Update policy |
| Policies | DELETE | `/api/v1/policies/{policy_id}` | Delete policy |
| Services | POST | `/api/v1/users/me/services/connect` | Connect OAuth service |
| Services | GET | `/api/v1/users/me/available-permissions` | Available permissions |
| Services | DELETE | `/api/v1/users/me/services/{service_id}` | Disconnect service |
| OAuth | GET | `/api/v1/oauth/{service_id}/authorize` | Initiate OAuth flow |
| OAuth | GET | `/api/v1/oauth/{service_id}/callback` | OAuth callback |
| Vault | GET | `/api/v1/vault/secrets` | List secrets |
| Vault | POST | `/api/v1/vault/store` | Store secret |
| Vault | GET | `/api/v1/vault/secrets/{name}` | Secret detail |
| Vault | DELETE | `/api/v1/vault/secrets/{name}` | Delete secret |
| Audit | GET | `/api/v1/audit/events` | Filtered event list — returns full chain: `session_id`, `agent_session_id`, `mcp_session_id`, `delegation_id`, `on_behalf_of`, `agent_id`, `event_type`, `tool`, `success`, `duration_ms` |
| Audit | GET | `/api/v1/audit/events/{event_id}` | Event detail — same fields plus `arguments`, `result_summary`, `attempted_tool`, `required_permission`, `reason`, `extra_data` |
| Tasks | GET | `/api/v1/tasks/` | Task list |
| Tasks | POST | `/api/v1/tasks/` | Create task |
| Tasks | GET | `/api/v1/tasks/{task_id}` | Task detail |
| Tasks | POST | `/api/v1/tasks/{task_id}/activate` | Activate task |
| Tasks | POST | `/api/v1/tasks/{task_id}/complete` | Complete task |
| Tasks | POST | `/api/v1/tasks/{task_id}/revoke` | Revoke task |
| Tasks | POST | `/api/v1/tasks/{task_id}/token` | Get task token |
| Health | GET | `/health` | App root (not /api/v1) |

**Employee — Onboarding & Activity Monitoring (Phase 4):**

| Page | Method | Endpoint | Notes |
|------|--------|----------|-------|
| Onboarding | GET | `/api/v1/users/me` | User profile, role, org, `onboarding_completed` flag — drives routing (onboarding vs. dashboard) |
| Onboarding | PATCH | `/api/v1/users/me` | **Modified**: set `onboarding_completed: true` when wizard finishes |
| Onboarding | GET | `/api/v1/users/me/services` | Connected services list |
| Agent Registration | POST | `/api/v1/agents/` | **Modified**: when no `public_key` in body, backend generates Ed25519 keypair and returns `public_key` + one-time `private_key` |
| Agent Tools | GET | `/api/v1/agents/{id}/tools` | **New endpoint**: permission-filtered tool list for agent (User JWT + ownership check, no Agent JWT needed) |
| Agent Activity | GET | `/api/v1/audit/events?agent_id={id}` | Per-agent activity feed |
| Delegation Builder | GET | `/api/v1/users/me/available-permissions` | Role-filtered permissions for checklist |

**Security Team (Phase 5):**

| Page | Method | Endpoint | Notes |
|------|--------|----------|-------|
| Security Dashboard | GET | `/api/v1/audit/summary` | Reused — actions, denials, violations |
| Security Dashboard | GET | `/api/v1/audit/events?event_type=anomaly` | Anomaly alerts |
| Tool Analytics | GET | `/api/v1/audit/analytics/tools?period=7d` | Tool usage by backend (**new endpoint**) |
| Tool Analytics | GET | `/api/v1/audit/analytics/denials?group_by=permission` | Permission denial breakdown (**new endpoint**) |
| Delegation Viz | GET | `/api/v1/audit/analytics/delegations?user_id={id}` | Delegation chain utilization (**new endpoint**) |
| Compliance | POST | `/api/v1/audit/reports/generate` | Queue async report generation — returns job ID (**new endpoint**) |
| Compliance | GET | `/api/v1/audit/reports/{job_id}` | Poll report status + download URL when ready (**new endpoint**) |
| Incident Response | POST | `/api/v1/admin/agents/{agent_id}/suspend` | Suspend agent (**new endpoint**) |
| Incident Response | POST | `/api/v1/admin/delegations/revoke-all?agent_id={id}` | Revoke all delegations (**new endpoint**) |

**Engineering Team (Phase 6):**

| Page | Method | Endpoint | Notes |
|------|--------|----------|-------|
| MCP Debug Console | GET | `/debug/sessions?agent_id={id}` | Active sessions (gateway) (**new endpoint**) |
| MCP Debug Console | GET | `/debug/sessions/{session_id}/trace` | Call trace (gateway) (**new endpoint**) |
| MCP Debug Console | POST | `/debug/replay/{call_id}` | Replay call dry-run (gateway) (**new endpoint**) |

**IT Administrator (Phase 7):**

| Page | Method | Endpoint | Notes |
|------|--------|----------|-------|
| Service Registry | GET | `/api/v1/admin/services` | List approved services (**new endpoint**) |
| Service Registry | POST | `/api/v1/admin/services` | Add/update service (**new endpoint**) |
| Role Permissions | GET | `/api/v1/admin/roles/{role_id}/permissions` | Role permission config (**new endpoint**) |
| Role Permissions | PUT | `/api/v1/admin/roles/{role_id}/permissions` | Update role permissions (**new endpoint**) |
| Vendor Agents | GET | `/api/v1/admin/vendor-agents` | List approved vendors (**new endpoint**) |
| Vendor Agents | POST | `/api/v1/admin/vendor-agents` | Approve/deny vendor (**new endpoint**) |
| Emergency Controls | POST | `/api/v1/admin/emergency/suspend-all-vendors` | Suspend all vendor agents (**new endpoint**) |
| Emergency Controls | POST | `/api/v1/admin/emergency/disable-delegations` | Revoke all delegations org-wide (**new endpoint**) |
| Emergency Controls | POST | `/api/v1/admin/emergency/lockdown` | Organization lockdown (**new endpoint**) |
| Gateway Ops | GET | `/admin/metrics` | Gateway metrics (gateway) (**new endpoint**) |
| Gateway Ops | GET | `/admin/backends/status` | Backend MCP server status (gateway) (**new endpoint**) |

### Data Models

No new database tables. The frontend consumes existing API responses and stores no persistent state. Session state (encrypted JWT) lives in httpOnly cookies.

### Architecture Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|--------------------|--------|-----------|
| Framework | Next.js, Vite+React, Remix | Next.js 15 (App Router) | Public pages need SSR/SSG; BFF auth pattern needs API routes; console demo spec Phase 3 already planned Next.js migration |
| Auth pattern | Client-side JWT (localStorage), httpOnly cookies + BFF | httpOnly cookies + BFF | Security product must not expose JWTs to JavaScript/XSS |
| Component library | Material UI, Ant Design, shadcn/ui | shadcn/ui + Tailwind CSS | Own the components, accessible primitives, utility-first CSS |
| State management | Redux, Zustand, Jotai | TanStack Query (server) + Zustand (client) | TanStack Query handles API caching; Zustand for minimal UI state |
| Real-time transport | WebSocket, SSE, Polling | SSE via BFF (Phase 4), Polling fallback (Phase 2) | Gateway already uses SSE; works with cookies/HTTP; unidirectional sufficient |
| Package manager | npm, pnpm, yarn | npm | Simplicity; no existing preference |
| Token refresh | Redirect on expiry, extend TTL, add refresh endpoint | Add `POST /api/v1/auth/refresh` | Transparent refresh avoids disrupting user sessions; 8hr TTL is too short for all-day dashboard use |
| Demo component sharing | Shared components, separate components | Separate first, extract in Phase 4 | Demo optimizes for animation; product optimizes for interactivity; premature abstraction causes friction |
| Monorepo vs separate repo | Monorepo, separate repo | Monorepo (`frontend/` in deepsecure-mvp) | Existing monorepo pattern; atomic API+frontend changes; single docker-compose |

---

## 3. Project Structure

### Files to Create

| File | Purpose |
|------|---------|
| `frontend/` (entire directory) | Next.js application |
| `frontend/Dockerfile` | Multi-stage build: deps → build → standalone runtime |
| `frontend/next.config.ts` | Standalone output, no rewrites (BFF-only pattern) |
| `frontend/package.json` | Dependencies, scripts (test, e2e, storybook, generate:types, demo:extract) |
| `frontend/tsconfig.json` | TypeScript configuration |
| `frontend/tailwind.config.ts` | Product design system theme extension |
| `frontend/vitest.config.ts` | Vitest test runner configuration |
| `frontend/playwright.config.ts` | Playwright E2E configuration |
| `frontend/components.json` | shadcn/ui configuration |
| `frontend/.storybook/` | Storybook configuration |
| `frontend/.env` | Shared defaults (committed) |
| `frontend/.env.development` | Dev-specific non-secrets (committed) |
| `frontend/.env.production` | Prod-specific non-secrets (committed) |
| `frontend/scripts/generate-env.sh` | Generate `.env.local` with random secrets |
| `frontend/scripts/extract-demo-data.ts` | Extract demo data from live Sarah Journey run |
| `frontend/src/app/(auth)/login/` | Login page (SSO + email) |
| `frontend/src/app/(dashboard)/` | Authenticated layout shell (sidebar, header, user menu) |
| `frontend/src/app/(dashboard)/dashboard/` | Employee welcome dashboard + overview |
| `frontend/src/app/(dashboard)/onboarding/` | Guided onboarding wizard (Ph 4) |
| `frontend/src/app/(dashboard)/agents/` | Agent list, create, detail pages |
| `frontend/src/app/(dashboard)/agents/[id]/activity/` | Per-agent activity monitoring (Ph 4) |
| `frontend/src/app/(dashboard)/delegation/` | Delegation builder with permission checklist (Ph 4) |
| `frontend/src/app/(dashboard)/services/` | Service connections |
| `frontend/src/app/(dashboard)/policies/` | Policy CRUD |
| `frontend/src/app/(dashboard)/audit/` | Audit trail with filters |
| `frontend/src/app/(dashboard)/vault/` | Secret management |
| `frontend/src/app/(dashboard)/tasks/` | Task lifecycle |
| `frontend/src/app/(dashboard)/security/` | Security dashboard + alerts (Ph 5) |
| `frontend/src/app/(dashboard)/security/analytics/` | Tool call analytics (Ph 5) |
| `frontend/src/app/(dashboard)/security/compliance/` | Compliance reports (Ph 5) |
| `frontend/src/app/(dashboard)/security/incidents/` | Incident response workflow (Ph 5) |
| `frontend/src/app/(dashboard)/dev/debug/` | MCP Debug Console (Ph 6) |
| `frontend/src/app/(dashboard)/dev/reference/` | SDK reference + code snippets (Ph 6) |
| `frontend/src/app/(dashboard)/admin/services/` | Approved Services Registry (Ph 7) |
| `frontend/src/app/(dashboard)/admin/roles/` | Role-based permission limits (Ph 7) |
| `frontend/src/app/(dashboard)/admin/vendors/` | Approved vendor agents (Ph 7) |
| `frontend/src/app/(dashboard)/admin/emergency/` | Emergency controls (Ph 7) |
| `frontend/src/app/(dashboard)/admin/gateway/` | Gateway Operations Dashboard (Ph 7) |
| `frontend/src/app/(public)/demo/` | Interactive console demo (SSG, no auth) |
| `frontend/src/app/api/` | BFF API routes (auth, proxy, events) |
| `frontend/src/components/` | UI primitives, layout, feedback, domain, demo |
| `frontend/src/components/audit/` | Attribution chain, token layer badge, event type badge, event detail panel (Ph 2) |
| `frontend/src/components/onboarding/` | Welcome wizard, step indicators, quick-action cards (Ph 4) |
| `frontend/src/components/delegation/` | Permission checklist, service group, constraint form (Ph 4) |
| `frontend/src/components/security/` | Alert cards, denial analysis, delegation tree (Ph 5) |
| `frontend/src/components/debug/` | Session inspector, call trace table, request/response viewer (Ph 6) |
| `frontend/src/components/admin/` | Service registry table, role config, emergency control buttons (Ph 7) |
| `frontend/src/lib/` | API client, auth helpers, utilities |
| `frontend/src/styles/` | Design tokens (product + demo) |
| `frontend/src/middleware.ts` | Auth middleware |
| `frontend/e2e/` | Playwright E2E tests |

### Files to Modify

| File | Changes |
|------|---------|
| `docker-compose.yml` | Add `frontend` service (port 3000, depends_on control+gateway) |
| `.gitignore` | Add `frontend/.env.local`, `frontend/.next/`, `frontend/node_modules/` |
| `deeptrail-control/app/api/v1/endpoints/auth.py` | Add `POST /refresh` endpoint |
| `deeptrail-control/app/api/v1/api.py` | Register refresh route (if separate file) |

---

## 4. Testing Strategy

### Test Levels

| Level | What | Location | Framework |
|-------|------|----------|-----------|
| Unit | Design system components, auth helpers, API client | `frontend/src/**/*.test.{ts,tsx}` | Vitest + React Testing Library |
| Unit (Storybook) | Visual component documentation | `frontend/src/**/*.stories.tsx` | Storybook |
| Integration | Page rendering with mocked APIs | `frontend/src/app/**/*.test.tsx` | Vitest + MSW |
| E2E | Full user flows against running docker-compose | `frontend/e2e/*.spec.ts` | Playwright |
| Backend unit | New `/auth/refresh` endpoint | `deeptrail-control/tests/` | pytest |

### Coverage Requirements

- New frontend code: >80% coverage on `lib/` and `components/ui/`
- Auth flow (cookie encryption, CSRF, middleware): 100% coverage
- Each dashboard page: at least one integration test (happy path + error + empty)
- E2E critical paths:
  - **Employee**: login → onboarding → connect service → register agent → create delegation → view activity → logout
  - **Audit trail**: login → audit page → verify token layer badges → expand event → verify attribution chain (on_behalf_of → delegation_id → agent_id → session → tool) → click agent link → filter by user → filter by session
  - **Security**: login → security dashboard → investigate alert → suspend agent → generate report
  - **Engineering**: login → MCP debug console → view session → expand call trace → copy cURL
  - **IT Admin**: login → service registry → configure role → emergency control (with confirmation) → gateway ops
- Role-based access: verify non-admin users cannot access admin routes, non-security cannot access security routes

---

## 5. Boundaries

### Always Do

- Route ALL authenticated backend calls through BFF proxy (never direct browser→backend)
- Encrypt JWTs in cookies using `SESSION_SECRET` (AES-256-GCM)
- Validate CSRF token on all mutating BFF requests (POST, PUT, DELETE)
- Return standardized `BFFErrorResponse` envelope from all proxy routes
- Implement loading skeleton, error state, and empty state for every data-fetching page
- Use product design system tokens for authenticated routes, demo tokens (scoped to `.demo-console`) for `/demo` only
- Run `npm run test` before marking any task complete

### Ask First

- Changes to control plane API contracts (new fields, changed response shapes)
- New npm dependencies not in the approved stack
- Changes to docker-compose networking or port mappings
- Changes to the design token values (check against [Figma designs](https://bunch-sled-10231777.figma.site/))

### Never Do

- Store JWTs in localStorage, sessionStorage, or JavaScript-accessible cookies
- Use Next.js `rewrites` for authenticated endpoints (bypasses BFF auth)
- Share high-level demo components with product components before Phase 4 extraction
- Commit `.env.local` or any file containing `SESSION_SECRET` / `CSRF_SECRET`
- Hardcode backend URLs in client components (use environment variables via BFF)

---

## 6. Demo Scenarios

### Demo 1: SSO Login → Dashboard (Keycloak)

```
Step 1: Navigate to http://localhost:3000 → Expected: redirected to /login
Step 2: Click "Sign in with Keycloak" → Expected: redirect to Keycloak login
Step 3: Enter sarah@deeptrail.com / password → Expected: redirect back to /dashboard
Step 4: Dashboard shows → Expected: audit summary cards, agent count, recent activity
Step 5: Check browser cookies → Expected: __session (httpOnly), __csrf (readable)
Step 6: Check browser localStorage → Expected: empty (no JWTs stored)
```

### Demo 2: SSO Login → Dashboard (Google Workspace)

```
Step 1: Navigate to http://localhost:3000/login
Step 2: Click "Sign in with Google" → Expected: redirect to Google OAuth consent
Step 3: Complete Google auth → Expected: redirect back to /dashboard
Step 4: Dashboard loads with user's Google identity
```

### Demo 3: Interactive Console Demo (Public)

```
Step 1: Navigate to http://localhost:3000/demo (no login) → Expected: demo loads instantly
Step 2: Wait 8 seconds → Expected: auto-rotates to Scene 2
Step 3: Click "Tasks" in sidebar → Expected: jumps to Scene 4 with permission funnel
Step 4: Hover over demo → Expected: auto-rotation pauses
Step 5: Embed as iframe: <iframe src="http://localhost:3000/demo"> → Expected: renders correctly
```

### Demo 4: Employee Onboarding — Full Self-Service Loop (ACTs 1–5)

```
Step 1: Login as new user (`onboarding_completed: false`) → Expected: redirect to `/onboarding` wizard with quick actions
Step 2: Click "Connect your first service" → Expected: guided service connection page
Step 3: Connect Notion via OAuth → Expected: service appears as connected
Step 4: See "Available Permissions" → Expected: grouped by service, shows maximum delegable scopes
Step 5: Click "Register an Agent" → Expected: agent type selection wizard
Step 6: Select "My Own Agent" → fill name/purpose → Expected: Ed25519 keypair generated, public key shown, private key downloadable with warning
Step 7: Agent registered → Expected: agent detail page shows agent_id, public_key, status: "Never authenticated"
Step 8: Click "Configure Delegation" → Expected: permission checklist grouped by service
Step 9: Try to check "notion:pages:create" → Expected: orange lock with "Your Notion connection doesn't include insert_content scope" (ACT 3 attenuation)
Step 10: Select valid permissions → set TTL to 7 days → submit → Expected: delegation created
Step 11: (Agent authenticates via API) → Refresh agent detail → Expected: status: "Active session", session info displayed
Step 12: Click "Agent Tools" tab → Expected: tools like notion.search_pages, notion.read_page shown; notion.create_page greyed out
Step 13: Navigate to agent activity → Expected: real-time tool call feed with security status icons
Step 14: See a blocked call → Expected: red shield "Prompt injection detected" in activity row
```

### Demo 5: Audit Trail — Full Attribution Chain (ACT 8)

```
Step 1: Login → navigate to /audit → Expected: event list with token layer badges (L2/L3/L4) on each row
Step 2: Filter by "Permission Denials Only" → Expected: only permission_denied events shown, red badges
Step 3: Click a permission_denied event → Expected: detail panel slides open
Step 4: See attribution chain: sarah@deeptrail.com → del-abc123 → sdr-assistant-001 → asess-xyz → notion.create_page → ❌ Denied
Step 5: See red callout: "Attempted: notion.create_page | Required: notion:pages:create | Reason: Not in delegation"
Step 6: Click "sdr-assistant-001" in chain → Expected: navigates to agent detail page
Step 7: Click back → filter by "on_behalf_of: sarah@deeptrail.com" → Expected: all events for Sarah's agents
Step 8: Click an mcp_tool_call event → Expected: chain shows L3 badge, tool arguments (collapsible JSON), result_summary, duration_ms
Step 9: Click "This session only" shortcut → Expected: filters to agent_session_id, shows all events in that session chronologically
```

### Demo 6: Security Team Workflow

```
Step 1: Login as security user → Expected: security dashboard with metrics + alerts
Step 2: Click HIGH severity alert → Expected: expanded detail with Investigate/Suspend buttons
Step 3: Click "Suspend Agent" → confirm → Expected: agent suspended, alert resolved
Step 4: Navigate to Tool Analytics → Expected: charts showing tool usage by backend
Step 5: Navigate to Compliance → Generate SOC2 report → Expected: "Generating..." state → poll → download link appears
```

### Demo 7: IT Admin Emergency Controls

```
Step 1: Login as admin → navigate to /admin/emergency → Expected: emergency control panel
Step 2: Click "Suspend All Vendor Agents" → Expected: confirmation dialog showing blast radius
Step 3: Type "SUSPEND" to confirm → Expected: all vendor agents suspended, audit log entry created
Step 4: Navigate to Gateway Ops → Expected: metrics dashboard with backend status
```

### Demo 8: Error Handling

```
Step 1: Login → stop deeptrail-control container → refresh dashboard
Step 2: Expected: yellow banner "Backend services temporarily unavailable", cached data visible
Step 3: Click "Add Agent" → Expected: button disabled with tooltip
Step 4: Restart deeptrail-control → Expected: banner disappears, data refreshes
```

---

## 7. Dependencies & Risks

### External Dependencies

| Dependency | Risk | Mitigation |
|------------|------|------------|
| deeptrail-control API stability | API changes break frontend | OpenAPI type generation catches drift at build time |
| Keycloak in docker-compose | Adds container startup time | Conditional — skip if `IDP_NAME=google` |
| Google Workspace OAuth | Requires real Google credentials | Development uses Keycloak; Google tested with `IDP_NAME=google` |
| shadcn/ui component updates | Breaking changes in component APIs | Pin versions; own the generated component code |

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| BFF proxy adds latency to every API call | Medium | Low | Next.js server runs in same docker network; sub-1ms overhead |
| Cookie size limit (4KB) exceeds encrypted JWT size | Low | High | JWTs are typically <2KB; monitor with tests |
| SSE passthrough in BFF route has buffering issues | Medium | Medium | Phase 4 concern; polling fallback in Phase 2 |
| Design system diverges from Figma once Figma file is added | Medium | Medium | Add Figma as source of truth; update CSS tokens from Figma exports |
| `POST /api/v1/auth/refresh` introduces security surface | Low | Medium | Validate existing JWT signature; only extend, never change claims; rate-limit |
| Many new backend endpoints needed (Ph 5–7) delays frontend | High | Medium | Frontend phases decouple: use MSW mocks for missing endpoints; backend work runs in parallel |
| Emergency controls executed accidentally | Low | Critical | Require typed confirmation for destructive actions; audit log every emergency action; existing admin role is sufficient (no separate emergency role) |
| Role-based navigation complexity | Medium | Low | Use server-side role claim from JWT; single `useRole()` hook drives sidebar visibility |
| Debug console exposes sensitive session data | Medium | Medium | Restrict to engineering role; redact credential values in call traces; admin-only in production |

---

## 8. Open Questions

- [x] SSO in Phase 1? → **Yes**, Keycloak + Google Workspace already implemented
- [x] Token refresh? → **Add `POST /api/v1/auth/refresh`** to control plane
- [x] SSE for audit? → **Phase 4** new backend work; polling in Phase 2
- [x] Package manager? → **npm**
- [x] Figma? → CSS tokens from plan as code source of truth. Figma design source available at [`https://bunch-sled-10231777.figma.site/`](https://bunch-sled-10231777.figma.site/) for visual fidelity, layout reference, and component patterns.
- [x] Webflow embed? → **Phase 3 requirement**, not nice-to-have
- [x] First user? → Both internal demo/dev AND external users via Google Workspace
- [x] Performance budgets? → Best effort (<100KB gzip, Lighthouse >90)
- [x] Caddy replacement → **Deferred.** TLS termination will be mapped to AWS/GCP constructs (ALB, Cloud Load Balancer) as part of the production deployment architecture. Caddy stays for local dev.
- [x] `POST /api/v1/auth/refresh` implementation → **Issue a completely new JWT (reset TTL).** New JWT with fresh `exp`; do not extend the existing token.
- [x] Role model → **JWT already includes role claims** (e.g., `groups` from Keycloak/Google contain role info). Frontend reads the role from the decrypted JWT in the BFF cookie — no `/api/v1/users/me` call needed for sidebar navigation. Middleware and BFF proxy extract the role to drive route guards.
- [x] Emergency controls authorization → **Existing admin role is sufficient** with typed confirmation as the safeguard. No separate "emergency admin" role needed.
- [x] Agent tools view → **Add `GET /api/v1/agents/{id}/tools` to the control plane.** This endpoint returns the permission-filtered tool list for an agent based on its delegation and registered backends, without requiring the Agent JWT.
- [x] Ed25519 key generation → **Backend generates and returns the keypair**, matching the pattern in `scripts/demo_sarah_journey.sh`. The frontend calls a backend endpoint that generates the Ed25519 keypair and returns both public key (stored server-side) and private key (displayed once for download). The private key is never stored server-side after the response.
- [x] Onboarding state persistence → **Server-side.** An `onboarding_completed` flag on the user model tracks whether the user has completed onboarding. Once completed, the user bypasses the onboarding wizard entirely and lands directly on their dashboard showing registered agents and connected tools. The BFF checks this flag on login and routes accordingly.
- [x] Admin endpoints (Phase 5–7) → **Deferred.** Codebase exploration will be done when Phase 5 begins to determine which admin/analytics/debug endpoints already exist vs. need to be built.
- [x] Compliance report format → **Async.** Report generation queues a job and returns a download URL. The frontend polls or uses a notification to indicate when the report is ready for download.

---

## 9. Implementation Phases

### Phase 1: Scaffold, Design System, Auth, Test Infrastructure

**Deliverables:**
- Next.js project scaffolded in `frontend/`
- Product design system implemented (CSS vars, Tailwind theme, core components with tests + Storybook)
- Feedback components: ErrorCard, EmptyState, PageSkeleton, TableSkeleton
- BFF auth: httpOnly cookies, cookie encryption, CSRF, SSO redirect/callback (Keycloak + Google), `POST /api/v1/auth/refresh` (backend — issues completely new JWT with reset TTL), transparent token refresh in BFF proxy, standardized error envelope
- Auth middleware: validates cookie, extracts role from JWT `groups` claim → drives route guards and sidebar navigation (no `/api/v1/users/me` call needed for role). Login page, authenticated layout shell (sidebar, header, user menu) with role-based navigation visibility
- Error boundaries at public, authenticated, and global levels
- Vitest + RTL + MSW + Storybook + Playwright setup
- Dockerfile + docker-compose integration + env config
- OpenAPI type generation script

**Exit criteria:**
- `docker compose up` starts frontend alongside backend
- SSO login works end-to-end (Keycloak + Google Workspace)
- Unauthenticated `/dashboard` redirects to `/login`
- Public routes (`/`, `/demo` placeholder, `/status`) load without auth
- Design system components have passing tests + Storybook stories
- `npm run test` passes with >80% coverage on `lib/` and `components/ui/`

### Phase 2: Core Dashboard Pages

> **Screen designs:** [`docs/design/deeptrail-dashboard-core-pages.md`](../design/deeptrail-dashboard-core-pages.md) — ASCII wireframes, component breakdowns, API mappings, and state specs for all 7 pages.

**ACT coverage:** ACT 2 (service connections), ACT 3 (basic agent + delegation CRUD), ACT 8 (audit trail with full attribution chain)

**Deliverables:**
- 7 pages, each with loading skeleton, error state, empty state: Dashboard, Agents, Policies, Service Connections, Audit Trail, Vault, Tasks
- Integration tests with MSW-mocked API responses per page
- Playwright E2E: login → dashboard → create agent → view agent → logout

**Audit Trail page — full attribution chain (ACT 8):**

The audit trail is the compliance backbone of DeepSecure. Each event already returns the full chain from the backend (`AuditEventResponse` includes `session_id`, `agent_session_id`, `mcp_session_id`, `delegation_id`, `on_behalf_of`, `agent_id`). The frontend must surface this, not hide it behind a flat table.

*Event list view:*
- Filterable table with columns: Timestamp, Event Type, Tool, Agent, On Behalf Of, Result, Token Layer
- **Token Layer badge** per event row:
  - `L2 User` (blue) — user-direct actions (session_created, delegation_created)
  - `L3 Agent` (green) — agent session actions (mcp_tool_call, permission_denied via agent JWT)
  - `L4 Task` (purple) — task-scoped actions (tool calls made with task token)
  - Badge derived from: if `extra_data.token_type == "task_token"` → L4; elif `agent_session_id` present → L3; else → L2
- **Event type badges**: `mcp_tool_call` (green), `permission_denied` (red), `delegation_created` (blue), `session_created` (grey), `prompt_injection_blocked` (orange)
- Filters: event_type, agent_id, on_behalf_of, date range, tool pattern, success/denied

*Event detail panel (click to expand or slide-over):*
- **Attribution chain visualization** — a vertical breadcrumb showing the full chain for this event:
  ```
  👤 sarah@deeptrail.com          (on_behalf_of — human accountable)
   └─ 📋 del-abc123-xyz789        (delegation_id — permission grant)
       └─ 🤖 sdr-assistant-001    (agent_id — who acted)
           └─ 🔑 asess-xyz-456    (agent_session_id — L3 session)
               └─ 🔌 mcpsess-789  (mcp_session_id — gateway connection)
                   └─ 🔧 notion.search_pages → ✅ success
  ```
- Each node in the chain is a clickable link:
  - `on_behalf_of` → link to user's audit events (`?on_behalf_of=sarah@...`)
  - `delegation_id` → link to delegation detail (agents page)
  - `agent_id` → link to agent detail page
  - `agent_session_id` → link to filtered audit (`?agent_session_id=asess-...`)
- **Event fields**: timestamp, event_type, tool, arguments (collapsible JSON), result_summary, reason (for denials), duration_ms
- **For permission_denied events**: show `attempted_tool`, `required_permission`, and reason in a red callout box

*Compliance query shortcuts (from ACT 8):*
- Quick filter buttons: "All by user", "All by agent", "Permission denials only", "This session only"
- Maps to Sarah Journey ACT 8: "WHO initiated this? WHAT agent? WHICH delegation?"

**Exit criteria:**
- All 7 pages render with real data from running backend
- CRUD operations work end-to-end
- Audit trail shows token layer badges and event type badges on every row
- Audit event detail shows full attribution chain with clickable links
- Permission denied events display attempted_tool, required_permission, and reason
- Audit filters work: by event_type, agent_id, on_behalf_of, date range
- E2E critical path passes

### Phase 3: Interactive Console Demo

**Deliverables:**
- 6 demo scenes per [console demo spec](../design/deeptrail-console-interactive-demo.md) in `src/components/demo/` (separate from product components)
- Auto-rotation, scene navigation, Framer Motion animations
- SSG public `/demo` route, embeddable via iframe on deeptrail.com
- Demo data extracted from live Sarah Journey run

**Exit criteria:**
- `/demo` loads in <1s with no auth
- All 6 scenes render and auto-rotate
- Embeddable via iframe (no CORS, no auth dependency)

### Phase 4: Employee Onboarding, Agent Identity, MCP Gateway & Delegation

> **Screen designs:** [`docs/design/deeptrail-employee-onboarding-screens.md`](../design/deeptrail-employee-onboarding-screens.md) — ASCII wireframes for onboarding wizard, agent registration, delegation builder, tools view, activity monitor, and task lifecycle.

**Persona focus:** Employee (End User)
**ACT coverage:** ACT 2 (available permissions), ACT 3 (agent registration + delegation + attenuation), ACT 4 (agent auth status), ACT 5 (MCP gateway visualization), ACT 6 (task lifecycle enrichment), ACT 7 (injection/PII visibility for employee)

This phase builds the complete employee self-service loop that mirrors the Sarah Journey demo (ACTs 1–8), ensuring the frontend represents the full trust layer — not just CRUD, but the cryptographic identity, delegation attenuation, and MCP gateway flows.

**Deliverables:**

*Onboarding:*
- **Server-side onboarding state**: `onboarding_completed` flag on the user model. The BFF reads this from `GET /api/v1/users/me` on authenticated page load and routes accordingly:
  - `onboarding_completed: false` → redirect to `/onboarding` wizard
  - `onboarding_completed: true` → land directly on `/dashboard` showing registered agents and connected tools
- Once the user completes the wizard, `PATCH /api/v1/users/me` sets `onboarding_completed: true`. The user never sees the onboarding wizard again.
- Welcome dashboard for new users: guided quick-action cards ("Connect your first service", "Register an Agent", "View available tools")
- Guided onboarding wizard: step-by-step flow (connect service → register agent → create delegation) with progress indicator
- Available permissions discovery page: after connecting services, show the monotonic attenuation boundary — "These are the MAXIMUM permissions you can grant to any agent" grouped by service (maps to ACT 2 step 2.N)

*Agent Registration (ACT 3):*
- Agent registration wizard: agent type selector (My Own Agent / Vendor Agent / Shared Team Agent), vendor dropdown, name, purpose
- **Cryptographic identity generation**: when "My Own Agent" is selected, the backend generates the Ed25519 keypair (matching the pattern in `demo_sarah_journey.sh`). The API returns both the public key (stored server-side with the agent record) and the private key (displayed once). The UI shows:
  - Public key (truncated, always visible on agent detail)
  - Private key in a one-time-display modal with copy button and download-as-file button, plus a warning: "This private key will not be shown again. Store it securely — your agent needs it to authenticate."
  - The private key is never stored server-side after the registration response
- For Vendor Agents: public key is provided by the vendor; UI shows read-only public key from vendor registration
- Agent detail page shows: agent_id, public_key (truncated), owner, registration date, auth status

*Delegation Builder (ACT 3):*
- Permission checklist grouped by service, with two lock levels:
  - **Role-locked** (grey lock icon): permissions your role cannot delegate (e.g., `financial:*` for sales role)
  - **OAuth-scope-locked** (orange lock icon): permissions beyond your connected OAuth scopes (monotonic attenuation boundary) — explains "Your Notion connection doesn't include insert_content scope"
- Delegation settings: TTL, max actions/day, rate limit
- **Negative test UI**: if employee tries to check an OAuth-locked permission, show inline explanation of why it's blocked (mirrors ACT 3 step 3.4)

*Agent Auth & Session Status (ACT 4):*
- Agent detail page shows authentication status: "Never authenticated", "Active session (expires in Xh)", "Session expired"
- Session info panel: session_id, delegation_id, authenticated_at, expires_at
- "How agent authentication works" expandable section: visual diagram of challenge → sign → verify flow (educational, not interactive — the agent authenticates via API, not through the frontend)

*MCP Gateway — Virtual Trust Layer (ACT 5):*
- **Agent tools view**: read-only list of tools the agent can access through the MCP Gateway, fetched from `GET /api/v1/agents/{id}/tools` (new control plane endpoint — returns permission-filtered tools without requiring Agent JWT). Shows:
  - Tool name with namespace prefix (e.g., `notion.search_pages`, `slack.list_channels`)
  - Which backend service each tool comes from
  - Permission required for each tool
  - Tools NOT available (greyed out) because they're not in the delegation
- **"How it works" trust layer explainer**: visual showing Agent → Gateway → Backend with callouts: "Credentials injected server-side — agent never sees OAuth tokens"
- Per-agent activity monitoring page: today's action count vs. limit bar, delegation expiry countdown, recent tool calls table (time, tool, result status, details)
- Tool call detail expandable row: shows tool name, arguments, result summary, latency, and **security status** (passed / prompt injection blocked / PII filtered)

*Task Lifecycle Enrichment (ACT 6):*
- Enhanced Tasks page (building on Phase 2 CRUD): task detail view now shows:
  - Task status lifecycle: pending → active → completed/revoked (with visual stepper)
  - Scoped permissions for this task vs. agent's full delegation (visual narrowing)
  - Task token status: "Not issued", "Active (expires at X)", "Revoked (auto-revoke on complete)"
  - "This task has access to 1 of 7 delegated permissions" with bar visualization

*Security Visibility for Employee (ACT 7):*
- In agent activity feed: tool calls blocked by prompt injection detection show a red shield icon with "Blocked: Prompt injection detected" detail
- In agent activity feed: tool call responses where PII was filtered show an info icon with "PII redacted in response"

*Infrastructure:*
- SSE passthrough BFF route + `useSSE` hook for live activity updates
- Shared component extraction (StatusBadge, AnimatedCounter, PermissionLevelColor, TrustLayerDiagram)

**New/modified backend endpoints needed:**
- `GET /api/v1/users/me` — user profile (role, org, `onboarding_completed` flag)
- `PATCH /api/v1/users/me` — update user profile (set `onboarding_completed: true` on wizard completion)
- `GET /api/v1/users/me/services` — list connected services (drives onboarding state)
- `GET /api/v1/admin/vendor-agents` — approved vendor list (read-only for employee)
- `GET /api/v1/agents/{id}/tools` — **new endpoint**: returns permission-filtered tool list for an agent based on its delegation and registered backends (no Agent JWT needed — uses User JWT + ownership check)
- `POST /api/v1/agents/` — **modified**: when no `public_key` is provided in the request body, backend generates Ed25519 keypair and returns both `public_key` and `private_key` in the response (private key returned once, never stored)
- Existing: `GET /api/v1/users/me/available-permissions` — attenuation boundary
- Existing: `GET /api/v1/audit/events?agent_id={id}` — per-agent activity

**Exit criteria:**
- New user (`onboarding_completed: false`) is redirected to `/onboarding` wizard on login
- Returning user (`onboarding_completed: true`) lands directly on `/dashboard` with registered agents and connected tools
- Employee can complete full loop: connect service → see available permissions → register agent (with Ed25519 key display) → create delegation (with attenuation locks) → view agent tools → view agent activity
- Delegation builder shows both role-locked and OAuth-scope-locked permissions with explanations
- Agent detail page shows auth status and session info
- Agent tools view shows permission-filtered tool list from gateway
- Activity feed shows prompt injection blocks and PII filtering events
- Task detail shows scoped permission narrowing and lifecycle
- Integration tests for onboarding flow, agent registration (all 3 types), delegation builder (positive + negative), tools view, activity feed
- Playwright E2E: onboarding → register agent → delegate → view tools → view activity → task lifecycle

### Phase 5: Security Team — Dashboard, Analytics & Compliance

**Persona focus:** Security Team

**Deliverables:**
- Security dashboard: threat monitoring overview with metrics cards (total actions, active agents, permission denials, policy violations, anomalies detected), severity-ranked alert list
- Alert management: alert cards with severity (HIGH/MEDIUM/LOW), details, action buttons (Investigate, Suspend Agent, Contact Owner)
- Permission denial analysis: grouped by permission and by agent, with actionable insights ("65% of denials are write operations — consider reviewing delegation templates")
- Tool call analytics dashboard: usage volume by backend (bar chart), top 10 tools called table (calls, success rate, denial count, unique users), delegation chain visualization (tree view: user → services → permissions → usage stats)
- Compliance report generation (async): report type selector (SOC2, PII Access, Permission Denials, Delegation Chain Audit), period picker, format options (PDF/CSV). `POST /api/v1/audit/reports/generate` queues the job and returns a job ID. Frontend shows a "Report generating..." state and polls `GET /api/v1/audit/reports/{job_id}` until ready, then displays a download link. Reports list page shows past reports with download URLs. Schedule recurring option for auto-generation.
- Incident response workflow view: step-by-step tracker (Contain → Investigate → Remediate) with checklist items, status badges, timestamps
- Policy definition UI: create/edit security policies with rate limiting, time windows, data limits, destructive action blocks

**New backend endpoints needed (control plane):**
- `GET /api/v1/audit/analytics/tools?period={period}` — tool usage summary
- `GET /api/v1/audit/analytics/denials?group_by={field}` — permission denial breakdown
- `GET /api/v1/audit/analytics/delegations?user_id={id}` — delegation chain utilization
- `POST /api/v1/audit/reports/generate` — queue async compliance report (returns job ID)
- `GET /api/v1/audit/reports/{job_id}` — poll report status + get download URL
- `POST /api/v1/admin/agents/{agent_id}/suspend` — suspend agent
- `POST /api/v1/admin/delegations/revoke-all?agent_id={id}` — bulk revoke

**Exit criteria:**
- Security dashboard shows real data: actions, denials, anomalies from running backend
- Alert cards render with correct severity levels and action buttons work (suspend triggers backend call)
- Tool analytics charts render with real audit data
- Delegation chain visualization displays correct tree for a given user
- Compliance report async flow works: generate → "processing" state → poll until ready → download link appears
- Integration tests for each security view (dashboard, alerts, analytics, compliance, incident)
- Playwright E2E: security user views dashboard → investigates alert → suspends agent → generates report

### Phase 6: Engineering Team — MCP Debug Console & SDK Reference

**Persona focus:** Engineering Team

**Deliverables:**
- MCP Debug Console page: session list (agent, status, backends connected, delegation, expiry), expandable call trace table (method, tool, status, latency, timestamp)
- Call detail view: full request/response JSON, permission denied explanation (required permission vs. agent permissions), fix suggestion ("Ask user to add X permission to delegation")
- Action toolbar: Copy cURL, Replay Call (dry-run), View Audit Log, Export Trace
- SDK reference page: built-in documentation with code snippets for Python SDK integration (install, init, register agent, authenticate, MCP tool calls, LangChain/CrewAI integration)
- Agent testing sandbox: test MCP tool calls in-browser against the gateway with selected agent identity

**New backend endpoints needed (gateway):**
- `GET /debug/sessions?agent_id={id}` — list active sessions
- `GET /debug/sessions/{session_id}/trace` — call trace for session
- `POST /debug/replay/{call_id}` — replay call in dry-run mode

**Exit criteria:**
- Debug Console lists active sessions from running gateway
- Call trace shows all MCP calls for a session with expandable details
- Permission denied calls show clear explanation and fix suggestion
- Copy cURL generates valid command that reproduces the call
- SDK reference page renders code snippets with syntax highlighting
- Integration tests for debug console with mocked gateway responses
- Playwright E2E: developer views sessions → expands call trace → copies cURL → views SDK reference

### Phase 7: IT Administrator — Governance, Emergency Controls & Gateway Ops

**Persona focus:** IT Administrator

**Deliverables:**
- Approved Services Registry: sortable/filterable table (service name, status, available-to roles, data classification), add service form, import from catalog, bulk update
- Role-based permission limits: per-role permission configuration (expandable accordion per role, checkboxes for each permission, locked items for admin-only), default constraints form (max TTL, max actions/day, working hours)
- Approved vendor agents: vendor table (vendor, agent type, status, employee count), approval workflow (review → approve/deny), vendor detail with usage stats
- Emergency controls: big-button UI with confirmation dialogs — Suspend All Vendor Agents, Disable All Delegations, Lockdown Mode — each showing blast radius ("Affects: 47 agents, 312 employees") and requiring typed confirmation
- Gateway Operations Dashboard: metrics cards (total requests, success rate, active sessions, unique agents), latency percentiles chart, backend MCP server status table (status, latency, errors, active connections, health %), recent errors table, credential vault health
- Admin audit log: recent emergency actions with timestamps and admin identity

**New backend endpoints needed:**
- Control plane: `GET/POST /api/v1/admin/services`, `GET/PUT /api/v1/admin/roles/{role_id}/permissions`, `GET/POST /api/v1/admin/vendor-agents`, `POST /api/v1/admin/emergency/suspend-all-vendors`, `POST /api/v1/admin/emergency/disable-delegations`, `POST /api/v1/admin/emergency/lockdown`
- Gateway: `GET /admin/metrics`, `GET /admin/backends/status`, `POST /admin/backends/{id}/test`

**Exit criteria:**
- Service registry displays data and supports add/edit/status-toggle
- Role permission page correctly shows locked/unlocked permissions per role
- Emergency controls require typed confirmation and trigger backend calls
- Gateway ops dashboard shows real metrics from running gateway
- All admin pages enforce admin-only access (non-admin users see 403)
- Integration tests for each admin view
- Playwright E2E: admin manages services → configures role → triggers emergency control → views gateway ops

### Phase 8: Polish, Performance & Cross-Cutting Concerns

**ACT coverage:** ACT 9 (token hierarchy visualization)

**Deliverables:**
- Dark/light theme toggle with system preference detection
- Charts and data visualization (recharts or similar) across security analytics and gateway ops
- Responsive design audit across all pages
- Performance optimization: bundle analysis, code splitting by route group, Lighthouse >90 (best effort)
- Accessibility audit (WCAG 2.1 AA for all interactive components)
- Role-based sidebar navigation: show/hide menu items based on user role (employee vs. security vs. engineering vs. admin)
- Notification system for alerts (security team), delegation expiry warnings (employees), and system status changes (admin)
- **Token hierarchy visualization (ACT 9)**: an educational component reusable on agent detail, delegation detail, and task detail pages showing the 6-layer token hierarchy (L1 Org → L2 User → L3 Agent → L4 Task → L5 Delegation → L6 Secret Share) with the current context highlighted and permissions narrowing at each layer. Mirrors the side-by-side comparison from ACT 9 of the Sarah Journey demo.

**Exit criteria:**
- Dark/light toggle works across all pages
- Sidebar navigation adapts to user role
- Token hierarchy component renders correctly on agent detail, task detail, and delegation pages
- Lighthouse performance >90, accessibility >90
- No runtime errors across all persona flows

---

## 10. References

### Design Sources
- **Figma designs**: [`https://bunch-sled-10231777.figma.site/`](https://bunch-sled-10231777.figma.site/) — visual design source of truth for layout, component patterns, colors, typography, and spacing
- **Console demo screen spec**: [`docs/design/deeptrail-console-interactive-demo.md`](../design/deeptrail-console-interactive-demo.md) — 6-scene interactive demo design with ASCII wireframes, animation sequences, and data sources (Phase 3)
- **Dashboard core pages screen spec**: [`docs/design/deeptrail-dashboard-core-pages.md`](../design/deeptrail-dashboard-core-pages.md) — screen designs for the 7 core dashboard pages with wireframes, component breakdowns, API mappings, and state specifications (Phase 2)
- **Employee onboarding screen spec**: [`docs/design/deeptrail-employee-onboarding-screens.md`](../design/deeptrail-employee-onboarding-screens.md) — screen designs for onboarding wizard, agent registration, delegation builder, agent tools, task lifecycle, and security visibility (Phase 4)

### Architecture & Context
- **Product use cases by persona**: [`docs/PRODUCT_USE_CASES_BY_PERSONA.md`](../PRODUCT_USE_CASES_BY_PERSONA.md) — detailed persona definitions, use cases, UI mockups, and API examples for Employee, Security Team, Engineering Team, and IT Administrator
- **Architecture plan**: [`plans/frontend_architecture_plan_26af34d6.md`](../../plans/frontend_architecture_plan_26af34d6.md) — detailed design decisions, auth flow, design system tokens, directory structure, testing strategy, error handling, SSE strategy, demo data pipeline
- **Sarah Journey demo**: [`scripts/demo_sarah_journey.sh`](../../scripts/demo_sarah_journey.sh) — E2E demo covering all 9 ACTs, SSO with Keycloak + Google
- **Existing API surface**: deeptrail-control exposes `/api/v1/auth`, `/agents`, `/policies`, `/audit`, `/vault`, `/oauth`, `/users`, `/tasks`, `/bootstrap` + `/health` at app root
- **OpenAPI spec**: Available at `http://localhost:8000/openapi.json` when control plane is running
- **Docker-compose**: Existing services: db (5434), redis (6380), keycloak (8080), control (8000→8001), gateway (8002→8001), caddy (8443)

---

## Spec Complete

**Saved to:** `docs/spec/frontend-architecture-spec.md`

### Phase Summary

| Phase | Persona Focus | Key Deliverables | ACTs Covered | Backend Impact |
|-------|--------------|------------------|-------------|----------------|
| 1 | All | Scaffold, design system, auth, test infra | ACT 1 | `POST /auth/refresh` |
| 2 | Employee | 7 core dashboard pages with CRUD | ACT 2, 3 (basic), 8 | None (existing endpoints) |
| 3 | Prospect | Interactive console demo (SSG, embeddable) | — | None |
| 4 | Employee | **Onboarding, agent identity (Ed25519), delegation attenuation, MCP gateway trust layer, task lifecycle, security visibility** | **ACT 2–7** | Low–Medium (agent tools endpoint, user profile) |
| 5 | Security Team | Security dashboard, tool analytics, compliance reports, incident response | ACT 7, 8 | Medium (analytics + admin endpoints) |
| 6 | Engineering | MCP Debug Console, SDK reference, agent testing sandbox | ACT 4, 5, 9 | Low (debug endpoints on gateway) |
| 7 | IT Admin | Service registry, role permissions, vendor agents, emergency controls, gateway ops | — | Medium (admin + emergency endpoints) |
| 8 | All | Dark/light theme, role-based nav, performance, accessibility, token hierarchy visualization | ACT 9 | None |

### Next Steps

1. `/explore-codebase` — Verify existing frontend assets and which backend endpoints exist
2. `/breakdown-design docs/spec/frontend-architecture-spec.md` — Create workstreams and tasks
3. `/create-workstream frontend` — Create tracking structure

### Pipeline Position

```
/spec ✅ → /explore-codebase → /breakdown-design → /create-workstream → ...
```
