# Virtual MCP Server MVP: Merge Points & Testing Strategy

> **Workstream:** [WORKSTREAM.md](./WORKSTREAM.md)
>
> **Status:** [STATUS.md](./STATUS.md)
>
> **Last Updated:** January 2026

---

## Overview

This document defines the merge point actions and testing strategy for the Virtual MCP Server MVP implementation. Merge points are synchronization gates where parallel workstreams converge before dependent tasks can begin.

---

## Merge Point Timeline

```
Batch 1 → Batch 2 → Batch 3 → Batch 4 → MP1 → Batch 5 → MP2 → Batch 6 → MP3 → Batch 7 → Batch 8 → MP4 → Batch 9
                                  ↑              ↑              ↑                            ↑
                            First merge    Auth ready    Execution     Complete system
                                          path ready
```

---

## Merge Points Summary

| Point | After Batch | Converging Tasks | Enables | Integration Type |
|-------|-------------|------------------|---------|------------------|
| **MP1** | Batch 4 | A8 + B3 | C1 | Control Plane ↔ Gateway |
| **MP2** | Batch 5 | B8 + C3 | D1 | Full Auth Flow |
| **MP3** | Batch 6 | C7 + D6 | E3 | Full Execution Path |
| **MP4** | Batch 8 | E3 + backends | F1 | Complete System |

---

## MP1: Control Plane ↔ Gateway Integration

### What's Converging

| Worktree | Task | Description |
|----------|------|-------------|
| vmcp-control | A8 | AgentSessionService - challenge/verify/issue JWT |
| vmcp-gateway | B3 | MCP Session tracking - track backend connections |

### Why It's a Merge Point

- Gateway needs to validate Agent Session JWTs issued by Control Plane
- First time both services need to communicate
- Shared JWT signing/verification keys required

### Pre-Merge Checklist

- [ ] A8 (AgentSessionService) complete with tests passing
- [ ] B3 (MCP Session tracking) complete with tests passing
- [ ] JWT signing key configuration aligned between services
- [ ] Agent Session JWT format documented

### Merge Actions

```bash
# 1. Push worktree branches
cd /Users/imaxxs/repositories/vmcp-control
git add -A && git commit -m "Complete A8: AgentSessionService"
git push origin feature/vmcp-control

cd /Users/imaxxs/repositories/vmcp-gateway
git add -A && git commit -m "Complete B3: MCP Session tracking"
git push origin feature/vmcp-gateway

# 2. Create PRs
gh pr create --base dev --head feature/vmcp-control \
  --title "Control Plane: Batch 1-4 (A1-A8, E1)" \
  --body "Implements user sessions, delegation, and agent authentication"

gh pr create --base dev --head feature/vmcp-gateway \
  --title "Gateway: Batch 1-4 (B1-B8)" \
  --body "Implements MCP protocol, session tracking, tool aggregation"

# 3. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-control --no-ff -m "Merge Control Plane: Batch 1-4"
git merge origin/feature/vmcp-gateway --no-ff -m "Merge Gateway: Batch 1-4"
git push origin dev

# 4. Update worktrees
cd /Users/imaxxs/repositories/vmcp-control && git rebase origin/dev
cd /Users/imaxxs/repositories/vmcp-gateway && git rebase origin/dev
```

### Testing Requirements

| Test Type | Description | Command | Required? |
|-----------|-------------|---------|-----------|
| Unit | Both services pass | `pytest deeptrail-control/tests/ deeptrail-gateway/tests/` | ✅ Yes |
| Integration | Agent auth flow | `pytest tests/integration/test_agent_auth.py` | ✅ Yes |
| Container | Services communicate | See below | ✅ Yes |

### Container Deployment

```bash
# Build and start services
docker compose build deeptrail-control deeptrail-gateway
docker compose up -d db redis deeptrail-control deeptrail-gateway

# Wait for health
sleep 10
curl http://localhost:8000/health
curl http://localhost:8002/health

# Run integration tests
DEEPSECURE_CONTROL_URL=http://localhost:8000 \
DEEPSECURE_GATEWAY_URL=http://localhost:8002 \
pytest tests/integration/test_agent_auth.py -v

# Test scenarios
# 1. Agent requests challenge from Control Plane
# 2. Agent signs and verifies, receives JWT
# 3. Agent connects to Gateway with JWT
# 4. Gateway validates JWT and creates MCP sessions
```

### Success Criteria

- [ ] Agent can authenticate with Control Plane
- [ ] Control Plane issues valid Agent Session JWT
- [ ] Gateway accepts and validates JWT
- [ ] MCP sessions created for connected backends
- [ ] Integration tests pass
- [ ] Container deployment works

### Post-Merge Status Update

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

Update WORKSTREAM.md:
```markdown
| **MP1** | A8 + B3 | C1 (agent auth) | ✅ `complete` |
```

---

## MP2: Full Auth Flow Ready

### What's Converging

| Worktree | Task | Description |
|----------|------|-------------|
| vmcp-gateway | B8 | Tool aggregator - combine tools from backends |
| vmcp-gateway | C3 | JWT validation middleware - validate on every request |

### Why It's a Merge Point

- Complete authentication and authorization pipeline
- tools/list now fully functional with permission filtering
- Ready to implement backend connectors

### Pre-Merge Checklist

- [ ] B8 (Tool aggregator) complete
- [ ] C3 (JWT validation middleware) complete
- [ ] C4 (Tool→permission mapper) complete
- [ ] D3, D4, D5 (Backend clients) complete
- [ ] D6 (Backend router) complete
- [ ] tools/list returns filtered, namespaced tools

### Merge Actions

```bash
# 1. Ensure vmcp-gateway has all Batch 5 commits
cd /Users/imaxxs/repositories/vmcp-gateway
git status
git add -A && git commit -m "Complete Batch 5: C3, C4, D3-D6"
git push origin feature/vmcp-gateway

# 2. Create PR for Batch 5 changes
gh pr create --base dev --head feature/vmcp-gateway \
  --title "Gateway: Batch 5 (C3, C4, D3-D6)" \
  --body "Implements JWT validation, permission mapping, backend clients and router"

# 3. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-gateway --no-ff -m "Merge Gateway: Batch 5"
git push origin dev

# 4. Update worktree
cd /Users/imaxxs/repositories/vmcp-gateway && git rebase origin/dev
```

### Testing Requirements

| Test Type | Description | Command |
|-----------|-------------|---------|
| Unit | Aggregator, middleware | `pytest deeptrail-gateway/tests/` |
| Integration | Auth → tools/list flow | `pytest tests/integration/test_tools_list.py` |
| Container | Full auth with real JWT | Deploy + test |

### Container Test Scenarios

```bash
# 1. Agent authenticates and gets JWT
# 2. Agent calls initialize on Gateway
# 3. Agent calls tools/list
# 4. Verify tools are filtered by delegation
# 5. Verify namespace prefixing works
```

### Success Criteria

- [ ] tools/list returns only delegated tools
- [ ] Tools are namespaced (e.g., `notion.search_pages`)
- [ ] Undelegated tools are hidden
- [ ] JWT validation rejects invalid tokens

### Post-Merge Status Update

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

Update WORKSTREAM.md:
```markdown
| **MP2** | B8 + C3 | D1 (backend connectors) | ✅ `complete` |
```

---

## MP3: Full Execution Path Ready

### What's Converging

| Worktree | Task | Description |
|----------|------|-------------|
| vmcp-gateway | C7 | Credential injection - inject OAuth from vault |
| vmcp-gateway | D6 | Backend router - route to correct backend |

### Why It's a Merge Point

- Complete tools/call execution path
- Credentials injected from vault
- Requests routed to correct backend
- Ready for audit middleware

### Pre-Merge Checklist

- [ ] C5 (Permission filter) complete
- [ ] C6 (Delegation validator) complete
- [ ] C7 (Credential injection) complete
- [ ] D6 (Backend router) complete
- [ ] All backend connectors (D3-D6) complete
- [ ] Vault integration working

### Merge Actions

```bash
# 1. Ensure both worktrees have Batch 6 commits
cd /Users/imaxxs/repositories/vmcp-gateway
git status
git add -A && git commit -m "Complete Batch 6: C5, C6, C7"
git push origin feature/vmcp-gateway

# 2. Create PR for Batch 6 changes
gh pr create --base dev --head feature/vmcp-gateway \
  --title "Gateway: Batch 6 (C5-C7)" \
  --body "Implements permission filter, delegation validator, credential injection"

# 3. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-gateway --no-ff -m "Merge Gateway: Batch 6"
git push origin dev

# 4. Update worktree
cd /Users/imaxxs/repositories/vmcp-gateway && git rebase origin/dev
```

### Testing Requirements

| Test Type | Description | Command |
|-----------|-------------|---------|
| Integration | tools/call with injection | `pytest tests/integration/test_tools_call.py` |
| Container | Gateway → Backend flow | Deploy with mock backend |

### Container Test Scenarios

```bash
# 1. Agent calls tools/call("notion.search_pages", {...})
# 2. Gateway validates permission
# 3. Gateway fetches Sarah's OAuth token from vault
# 4. Gateway injects token into backend request
# 5. Backend receives request with valid OAuth
# 6. Response returned to agent (token not visible)
```

### Success Criteria

- [ ] tools/call reaches correct backend
- [ ] OAuth token injected (agent never sees it)
- [ ] Permission denied for non-delegated tools
- [ ] Backend response returned correctly

### Post-Merge Status Update

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

Update WORKSTREAM.md:
```markdown
| **MP3** | C7 + D6 | E3 (audit middleware) | ✅ `complete` |
```

---

## MP4: Complete System Ready

### What's Converging

| Component | Tasks | Description |
|-----------|-------|-------------|
| Audit | E3 | Audit middleware logs all tool calls |
| Backends | D3, D4, D5 | Notion, Slack, HubSpot connectors |

### Why It's a Merge Point

- Complete system ready for E2E testing
- All demos can be validated
- Sarah's full journey (Steps 1-10) testable

### Pre-Merge Checklist

- [ ] E2 (Audit logger service) complete
- [ ] E3 (Audit middleware) complete
- [ ] E4 (Fail-closed security) complete
- [ ] E5 (Constraint checker) complete
- [ ] All backend connectors working
- [ ] F1 (Sarah's Journey E2E test) complete

### Merge Actions

```bash
# 1. Ensure both worktrees have Batch 7-8 commits
cd /Users/imaxxs/repositories/vmcp-control
git status
git add -A && git commit -m "Complete Batch 7-8: E2, E6"
git push origin feature/vmcp-control

cd /Users/imaxxs/repositories/vmcp-gateway
git status
git add -A && git commit -m "Complete Batch 7-8: E3, E4, E5, F1-F4"
git push origin feature/vmcp-gateway

# 2. Create PRs for final batches
gh pr create --base dev --head feature/vmcp-control \
  --title "Control Plane: Batch 7-8 (E2, E6)" \
  --body "Implements audit logging and query API"

gh pr create --base dev --head feature/vmcp-gateway \
  --title "Gateway: Batch 7-8 (E3-E5, F1-F4)" \
  --body "Implements audit middleware, fail-closed, demos 1-4"

# 3. Merge to dev (after PR review)
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-control --no-ff -m "Merge Control: Batch 7-8"
git merge origin/feature/vmcp-gateway --no-ff -m "Merge Gateway: Batch 7-8"
git push origin dev

# 4. Update worktrees for final batch
cd /Users/imaxxs/repositories/vmcp-control && git rebase origin/dev
cd /Users/imaxxs/repositories/vmcp-gateway && git rebase origin/dev
```

### Testing Requirements

| Test Type | Description | Command |
|-----------|-------------|---------|
| E2E | Sarah's Journey | `pytest tests/e2e/test_sarah_journey.py` |
| Demos | All 6 demos | `./scripts/run_demos.sh` |
| Load | Basic performance | `pytest tests/performance/` |

### Demo Validation

| Demo | Task | Test Script |
|------|------|-------------|
| Demo 1: Unified Connection | F2 | `examples/demo_01_unified_connection.py` |
| Demo 2: Filtered Visibility | F3 | `examples/demo_02_filtered_visibility.py` |
| Demo 3: Delegation Execution | F4 | `examples/demo_03_delegation_execution.py` |
| Demo 4: Permission Enforcement | F5 | `examples/demo_04_permission_enforcement.py` |
| Demo 5: Unified Audit | F6 | `examples/demo_05_unified_audit.py` |
| Demo 6: Fail-Closed | F7 | `examples/demo_06_fail_closed.py` |

### Success Criteria

- [ ] Sarah's 10-step journey works end-to-end
- [ ] All 6 demos pass
- [ ] Audit logs capture all actions
- [ ] Permission denials logged
- [ ] Fail-closed behavior verified

### Post-Merge Status Update

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

Update WORKSTREAM.md:
```markdown
| **MP4** | E3 + backends | F1 (complete system) | ✅ `complete` |
```

---

## Container Deployment Schedule

| After | Deploy? | Purpose | Services |
|-------|---------|---------|----------|
| Batch 1 | Optional | Verify MCP parser | Gateway only |
| Batch 3 | Optional | Test models/services | Control only |
| **MP1** | **Required** | Control ↔ Gateway | Both services |
| **MP2** | **Required** | Full auth flow | Both services |
| **MP3** | **Required** | Full execution | Both + mock backend |
| **MP4** | **Required** | Complete system | All services + backends |

---

## Quick Reference Commands

### Push and Merge

```bash
# Push worktree
git push origin feature/vmcp-control

# Create PR
gh pr create --base dev --head feature/vmcp-control --title "..."

# Merge to dev
git checkout dev && git pull origin dev
git merge origin/feature/vmcp-control --no-ff
git push origin dev
```

### Container Testing

```bash
# Start services
docker compose up -d

# Health check
curl localhost:8000/health && curl localhost:8002/health

# Run tests
pytest -m integration -v

# Logs
docker compose logs -f deeptrail-control deeptrail-gateway

# Teardown
docker compose down -v
```

### Status Sync

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

---

## Merge Point Status

| Point | Status | Merged At | Notes |
|-------|--------|-----------|-------|
| MP1 | ⏸️ Pending | - | After Batch 4 |
| MP2 | ⏸️ Pending | - | After Batch 5 |
| MP3 | ⏸️ Pending | - | After Batch 6 |
| MP4 | ⏸️ Pending | - | After Batch 8 |

---

## History

| Date | Event |
|------|-------|
| Jan 2026 | Document created |
