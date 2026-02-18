# Merge Point Guide: Actions & Testing Strategy

> **Purpose:** Generic guide for handling merge points during parallel workstream execution.
>
> **Applies to:** Any design document broken into workstreams and tasks.
>
> **Last Updated:** February 2026

---

## Table of Contents

1. [What Are Merge Points?](#what-are-merge-points)
2. [Code Dependencies vs Runtime Dependencies](#code-dependencies-vs-runtime-dependencies)
3. [Development Mode vs Integration Mode](#development-mode-vs-integration-mode)
4. [Identifying Merge Points](#identifying-merge-points)
5. [Merge Point Workflow](#merge-point-workflow)
6. [Testing Strategy](#testing-strategy)
7. [Container Deployment](#container-deployment)
8. [Templates](#templates)
9. [Output Verification Checklist](#output-verification-checklist)

---

## What Are Merge Points?

Merge points are **synchronization gates** in parallel development where:

- Multiple independent workstreams converge
- Code from different worktrees must be integrated
- Integration testing validates cross-component behavior
- Dependent tasks become unblocked

### Merge Point Characteristics

| Characteristic | Description |
|----------------|-------------|
| **Convergence** | 2+ parallel tasks must complete before proceeding |
| **Integration** | First time components interact in production context |
| **Testing Gate** | Integration tests must pass before next batch |
| **Branch Merge** | Worktree branches merged to shared dev branch |

### Example Timeline

```
                    Parallel Execution
                    ─────────────────────
Worktree A:   A1 ─→ A2 ─→ A3 ─→ A4 ─┐
                                     ├──→ MP1 ──→ Next batch
Worktree B:   B1 ─→ B2 ─→ B3 ─→ B4 ─┘
```

---

## Code Dependencies vs Runtime Dependencies

Understanding the difference between dependency types is critical for parallel development:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY TYPES IN MERGE POINTS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CODE DEPENDENCY (Worktree-level)                                           │
│  ─────────────────────────────────                                          │
│  • Task needs another task's API/interface to BUILD                         │
│  • Blocks task from STARTING                                                │
│  • Tracked in task tickets and STATUS.md                                    │
│  • Resolved when dependent task is "code complete"                          │
│                                                                              │
│  Example: H1 (credential injector) needs E2 (vault endpoint) to know        │
│           endpoint format: GET /api/v1/vault/tokens/{service_id}            │
│                                                                              │
│  RUNTIME DEPENDENCY (Deployment-level)                                      │
│  ────────────────────────────────────                                       │
│  • Task needs another service RUNNING for integration testing               │
│  • Does NOT block task from starting                                        │
│  • Resolved at MERGE POINTS when services are deployed together             │
│  • Development proceeds with mocks/local fallbacks                          │
│                                                                              │
│  Example: H1 needs Control Plane running to fetch real tokens               │
│           During P0, H1 used mock tokens instead                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Task Lifecycle with Dependencies

```
                              CODE COMPLETE                    INTEGRATION COMPLETE
                                   │                                   │
 ┌──────────┐   ┌──────────┐   ┌──┴───────┐   ┌──────────┐   ┌────────┴─────────┐
 │ Blocked  │ → │  Ready   │ → │   Dev    │ → │  Code    │ → │   Integration    │
 │          │   │          │   │          │   │ Complete │   │     Complete     │
 └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────────────┘
      │              │              │              │                   │
      │              │              │              │                   │
  Waiting for    Code deps      Building      Unit tests         Services
  code deps      satisfied      with mocks    pass, API          deployed,
  to complete                   /local mode   documented         integration
                                                                 tests pass
```

### When Each Dependency Type Matters

| Phase | Code Dependencies | Runtime Dependencies |
|-------|-------------------|----------------------|
| **Task Creation** | Listed in ticket metadata | Listed in ticket metadata |
| **Task Start** | Must be satisfied (✅) | Not required |
| **Development** | Use completed APIs | Use mocks/local fallbacks |
| **Unit Testing** | Against real interfaces | With mocked services |
| **Code Complete** | All satisfied | May be unavailable |
| **Merge Point** | All satisfied | Services deployed |
| **Integration Testing** | All satisfied | All services running |

---

## Development Mode vs Integration Mode

### Development Mode (In Worktree)

During task implementation, you can work WITHOUT all services running:

| Service Down | Fallback Behavior | Tasks Affected |
|--------------|-------------------|----------------|
| Control Plane | Use mock responses | Backend client tasks |
| Gateway | Control Plane works standalone | API endpoint tasks |
| Both down | Unit tests still pass with mocks | All tasks |

**Development Environment:**
```bash
# Control worktree
cd /path/to/control-worktree/[service-dir]
pytest tests/ -v  # Works without Gateway

# Gateway worktree
cd /path/to/gateway-worktree/[service-dir]
pytest tests/ -v  # Works without Control Plane
```

### Integration Mode (At Merge Point)

At merge points, services must be running for integration testing:

| Mode | When | Services Required | Purpose |
|------|------|-------------------|---------|
| Dev | During task work | None required | Unit testing with mocks |
| MP1 | After first batch | Minimal stack | Verify flow works |
| MP2 | After API tasks | Core services | Verify API integration |
| MP3 | After integration | Full stack | Verify end-to-end |
| MP4 | After hardening | Full stack + auth | Production readiness |

### Runtime Dependencies by Merge Point (Template)

| MP | Service A | Service B | Database | Cache | External APIs |
|----|-----------|-----------|----------|-------|---------------|
| MP1 | ✅ Running | ✅ Running | ✅ | ✅ | ❌ Not needed |
| MP2 | ✅ Running | ❌ Not needed | ✅ | ✅ | ❌ Not needed |
| MP3 | ✅ Running | ✅ Running | ✅ | ✅ | ⚠️ Optional |
| MP4 | ✅ Running | ✅ Running | ✅ | ✅ | ✅ Required |

### Runtime Dependencies by Task (Template)

| Task | Service | Needs at Runtime | During Dev Use |
|------|---------|------------------|----------------|
| [Task ID] | [Service] | [Dependency] | Mock/fallback |

---

## Identifying Merge Points

### During Breakdown (`/breakdown-design`)

Look for these patterns in task dependencies:

1. **Cross-service dependencies**: Task in Service A depends on task in Service B
2. **Integration requirements**: "Validate JWT from Control Plane in Gateway"
3. **Shared state**: Both services access same database/cache
4. **End-to-end flows**: User journey step requires multiple services

### Common Merge Point Triggers

| Trigger | Example | Merge Point Type |
|---------|---------|------------------|
| Service integration | Gateway validates Control Plane JWT | Protocol integration |
| Shared contracts | Both services use same API schema | Contract validation |
| Data flow | User data flows through multiple services | Pipeline integration |
| Security boundary | Auth tokens cross service boundaries | Security integration |
| Complete feature | Full user journey testable | Feature integration |

### Documenting Merge Points

In your workstream breakdown, create a Merge Points table:

```markdown
## Merge Points

| Point | Converging Tasks | Enables | Why Merge? |
|-------|------------------|---------|------------|
| **MP1** | [Task A] + [Task B] | [Next Task] | [Reason] |
| **MP2** | [Task C] + [Task D] | [Next Task] | [Reason] |
```

---

## Merge Point Workflow

### Phase 1: Pre-Merge Verification

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRE-MERGE CHECKLIST                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  □ All converging tasks marked complete in STATUS.md            │
│  □ Completion reports exist for all tasks                       │
│  □ Unit tests pass in each worktree                             │
│  □ Linting passes: ruff check, mypy                             │
│  □ No uncommitted changes in worktrees                          │
│  □ Shared contracts/interfaces aligned                          │
│                                                                  │
│  CONTRACT VERIFICATION (CRITICAL - BLOCKING):                   │
│  □ All endpoints match design doc spec exactly                  │
│  □ Test endpoints match implementation endpoints                │
│  □ Request/response schemas match spec                          │
│                                                                  │
│  FILE LOCATION VERIFICATION (CRITICAL - BLOCKING):              │
│  □ E2E tests at root level (tests/e2e/)                        │
│  □ Demos at root level (demos/)                                 │
│  □ Demo tests at root level (tests/demos/)                      │
│                                                                  │
│  TECHNICAL REQUIREMENTS:                                         │
│  □ Async fixtures use @pytest_asyncio.fixture                   │
│  □ HTTP clients use httpx.AsyncClient                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Contract Verification Commands

```bash
# Check implemented endpoints
grep -r "@router\.\(get\|post\|put\|delete\)" [service]/ | grep -o '"/api/v1[^"]*"' | sort -u

# Check test endpoints
grep -r '"/api/v1' tests/ | grep -o '"/api/v1[^"]*"' | sort -u

# Compare - these should match exactly
# If they don't, fix BEFORE merging

# Check for async fixture mistakes (should return nothing)
grep -r "@pytest.fixture" tests/ | grep -B1 "async def"
```

### Phase 2: Push Worktree Changes

```bash
# For each worktree
cd /path/to/worktree-a
git add -A
git commit -m "Complete [tasks]: [description]"
git push origin feature/worktree-a-branch

cd /path/to/worktree-b
git add -A
git commit -m "Complete [tasks]: [description]"
git push origin feature/worktree-b-branch
```

### Phase 3: Create Pull Requests

```bash
# From worktree or main repo
gh pr create \
  --base dev \
  --head feature/worktree-a-branch \
  --title "[Service A]: Batch N Tasks" \
  --body "$(cat <<'EOF'
## Summary
- Task A1: [description]
- Task A2: [description]

## Testing
- [ ] Unit tests pass
- [ ] Integration tests ready

## Merge Point
This PR is part of MP[N]. Requires merging with [other PR].
EOF
)"
```

### Phase 4: Merge to Dev Branch

```bash
# From main repository
cd /path/to/main-repo
git checkout dev
git pull origin dev

# Merge first worktree (order usually doesn't matter)
git merge origin/feature/worktree-a-branch --no-ff \
  -m "Merge [Service A]: [tasks] for MP[N]"

# Merge second worktree
git merge origin/feature/worktree-b-branch --no-ff \
  -m "Merge [Service B]: [tasks] for MP[N]"

# Resolve any conflicts if needed
# git add . && git commit

# Push merged dev
git push origin dev
```

### Phase 5: Run Integration Tests

```bash
# Run integration test suite
pytest tests/integration/ -v

# Or specific merge point tests
pytest tests/integration/test_mp[N]_*.py -v

# With coverage
pytest tests/integration/ --cov=. --cov-report=html
```

### Phase 6: Container Deployment & Verification

```bash
# Build services with merged code
docker compose build [service-a] [service-b]

# Start services
docker compose up -d [dependencies] [service-a] [service-b]

# Wait for health
sleep 10
curl http://localhost:[port-a]/health
curl http://localhost:[port-b]/health

# Run integration tests against containers
[ENV_VARS] pytest tests/integration/ -v

# Teardown
docker compose down
```

### Phase 7: Update Worktrees

```bash
# Critical: Sync worktrees with merged dev
cd /path/to/worktree-a
git fetch origin dev
git rebase origin/dev
# Resolve conflicts if any

cd /path/to/worktree-b
git fetch origin dev
git rebase origin/dev
```

### Phase 8: Update Status Files

```bash
# From main repo
cd /path/to/main-repo
/sync-worktree-status [feature-name]

# Manually update merge point status in WORKSTREAM.md
# | **MP1** | A4 + B4 | C1 | ✅ `complete` |
```

---

## Testing Strategy

### Testing Pyramid at Merge Points

```
                    ┌─────────┐
                    │   E2E   │  ← After final merge point
                    ├─────────┤
                    │Container│  ← At every merge point
                    ├─────────┤
               │  Integration  │  ← At every merge point
               ├───────────────┤
          │        Unit Tests       │  ← Before every merge
          └─────────────────────────┘
```

### Test Types by Merge Point

| Test Type | When | What to Test | Required? |
|-----------|------|--------------|-----------|
| **Unit** | Before merge | Individual components | ✅ Always |
| **Integration** | At merge point | Cross-component flows | ✅ Always |
| **Container** | At merge point | Real service interaction | ✅ At key merges |
| **E2E** | Final merge | Complete user journeys | ✅ Final only |

### Testing Strategy by Phase

#### Phase 0: Contract Verification

```bash
# Endpoints exist and return correct formats
python demos/demo_[feature]_e2e.py
# Success = exit code 0 (mocks OK)
```

#### Phase 1: Mock Replacement Verification

```bash
# Real APIs called, real data returned
python demos/demo_[feature]_e2e.py --verbose

# Verify no mock strings in output
grep -c "Mock" /tmp/demo_output.log
# Success = 0 matches
```

#### Phase 2: Security Verification

```bash
# Security test suite
pytest tests/security/ -v
```

### E2E Test Success Criteria (Final Merge Point)

> **CRITICAL**: E2E tests validate the complete user journey. All must pass.

| Criterion | How to Verify | Common Failures |
|-----------|---------------|-----------------|
| Endpoints match spec | Compare test URLs vs implementation | 404 = endpoint mismatch |
| Services running | `docker compose ps` | Tests skipped = services down |
| Auth flow complete | Check token generation | 401 = auth not implemented |
| Async fixtures correct | No `AttributeError` on fixtures | Use `@pytest_asyncio.fixture` |
| Files at correct location | `ls tests/e2e/` | Tests not found |

### Common E2E Test Failures and Fixes

| Error | Root Cause | Fix |
|-------|------------|-----|
| `404 Not Found` | Test uses wrong endpoint path | Update test to match implementation |
| `AttributeError: 'async_generator'` | Wrong fixture decorator | `@pytest.fixture` → `@pytest_asyncio.fixture` |
| Tests skipped | Services not running | `docker compose up -d` |
| `401 Unauthorized` | Auth flow not implemented | Implement or mock auth endpoint |
| Test file not found | Wrong location | Move to `tests/e2e/` (root) |

### Integration Test Categories

```python
# tests/integration/conftest.py

import pytest

@pytest.fixture
def merge_point_1_ready():
    """Fixture that requires MP1 components."""
    # Verify both services are available
    # Set up test data
    pass

# tests/integration/test_mp1_integration.py

@pytest.mark.integration
@pytest.mark.merge_point_1
def test_service_a_calls_service_b(merge_point_1_ready):
    """Test cross-service communication at MP1."""
    pass
```

### Container Test Template

```python
# tests/integration/test_container_mp1.py

import pytest
import requests
import os

SERVICE_A_URL = os.getenv("SERVICE_A_URL", "http://localhost:8000")
SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://localhost:8002")

@pytest.fixture(scope="module")
def verify_services():
    """Verify services are running."""
    assert requests.get(f"{SERVICE_A_URL}/health").status_code == 200
    assert requests.get(f"{SERVICE_B_URL}/health").status_code == 200

@pytest.mark.integration
@pytest.mark.container
def test_cross_service_flow(verify_services):
    """Test complete flow across services."""
    # 1. Call Service A
    response_a = requests.post(f"{SERVICE_A_URL}/api/action", json={...})
    assert response_a.status_code == 200
    token = response_a.json()["token"]
    
    # 2. Use token with Service B
    response_b = requests.get(
        f"{SERVICE_B_URL}/api/resource",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response_b.status_code == 200
```

---

## Container Deployment

### When to Deploy Containers

| Merge Point Type | Deploy? | Purpose |
|------------------|---------|---------|
| First service integration | ✅ Yes | Verify communication |
| Security boundary crossing | ✅ Yes | Verify auth/authz |
| Data pipeline integration | ✅ Yes | Verify data flow |
| Minor feature addition | ⚠️ Optional | Only if integration-heavy |
| Final system ready | ✅ Yes | Full E2E validation |

### Container Deployment Schedule (Template)

| Merge Point | When to Deploy | Services | Duration |
|-------------|----------------|----------|----------|
| **MP1** | After first batch complete | Core services | ~30 min |
| **MP2** | After API tasks complete | Service A + DB + Cache | ~20 min |
| **MP3** | After integration tasks | Full stack | ~45 min |
| **MP4** | After hardening | Full stack + Auth | ~60 min |

### Container Environment Setup (Template)

```bash
# Environment variables for all merge point testing
export SERVICE_A_URL=http://localhost:8000
export SERVICE_B_URL=http://localhost:8002
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export REDIS_HOST=localhost
export REDIS_PORT=6379

# For production testing (MP4)
export AUTH_URL=http://localhost:8080
export ENVIRONMENT=production
```

### Docker Compose Pattern

```yaml
# docker-compose.yml

services:
  # Dependencies
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: testdb
    healthcheck:
      test: ["CMD", "pg_isready"]
  
  redis:
    image: redis:7
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
  
  # Service A
  service-a:
    build: ./service-a
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://...
      SERVICE_B_URL: http://service-b:8001
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  
  # Service B
  service-b:
    build: ./service-b
    depends_on:
      redis:
        condition: service_healthy
    environment:
      REDIS_URL: redis://redis:6379
      SERVICE_A_URL: http://service-a:8001
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
```

### Container Test Script

```bash
#!/bin/bash
# scripts/test_merge_point.sh

set -e

MERGE_POINT=${1:-"mp1"}

echo "=== Testing Merge Point: $MERGE_POINT ==="

# 1. Build services
echo "Building services..."
docker compose build

# 2. Start services
echo "Starting services..."
docker compose up -d

# 3. Wait for health
echo "Waiting for services..."
sleep 15

# 4. Verify health
echo "Checking health..."
curl -f http://localhost:8000/health || exit 1
curl -f http://localhost:8002/health || exit 1

# 5. Run integration tests
echo "Running integration tests..."
pytest tests/integration/ -m "$MERGE_POINT" -v

# 6. Capture result
RESULT=$?

# 7. Collect logs on failure
if [ $RESULT -ne 0 ]; then
    echo "Tests failed. Collecting logs..."
    docker compose logs > "logs_${MERGE_POINT}.txt"
fi

# 8. Teardown
echo "Tearing down..."
docker compose down -v

exit $RESULT
```

---

## Templates

### MERGE_POINTS.md File Structure (REQUIRED SECTIONS)

When creating `docs/workstreams/[feature]/MERGE_POINTS.md`, include ALL these sections:

```markdown
# [Feature Name]: Merge Points & Testing Strategy

> **Workstream:** [WORKSTREAM.md](./WORKSTREAM.md)  
> **Status:** [STATUS.md](./STATUS.md)  
> **Created:** [Date]

---

## Overview

[Brief description of the feature and its merge points]

### Key Distinction (if applicable)

[Table showing how this workstream differs from typical implementations]

---

## Code Dependencies vs Runtime Dependencies

[Include the dependency types ASCII diagram from above]

### Task Lifecycle with Dependencies

[Include the lifecycle ASCII diagram from above]

### When Each Dependency Type Matters

[Include the phases table from above]

---

## Development Mode vs Integration Mode

### Development Mode (In Worktree)

[Table showing fallback behaviors when services are down]

### Integration Mode (At Merge Point)

[Table showing what's required at each merge point]

### Runtime Dependencies by Merge Point

[Table: MP vs Service A vs Service B vs DB vs Cache vs External APIs]

### Runtime Dependencies by Task

[Table: Task vs Service vs Needs at Runtime vs During Dev Use]

---

## Merge Point Summary

[ASCII diagram showing the flow from batches through merge points]

---

## MP[N]: [Name]

### Status: ⏳ NOT REACHED / ✅ REACHED (Date)

### Why It's a Merge Point

[Explanation of why these tasks must converge - numbered list]

### Purpose

[Brief description of what this merge point validates]

### What Was Validated

| Aspect | Status | Evidence |
|--------|--------|----------|
| [Aspect 1] | ✅ / ❌ | [Evidence] |

### What Was NOT Validated (Deferred to MP[X])

| Aspect | Status | Notes |
|--------|--------|-------|
| [Aspect 1] | ❌ | [Notes] |

### Validation Command

\`\`\`bash
# MP[N] validation
[command]
# Expected: [output]
\`\`\`

### Converging Tasks

| Task | Description | Status |
|------|-------------|--------|
| [Task ID] | [Description] | ✅ Complete / ⏳ Pending |

### Enables

- [Next batch/tasks]
- [Features unlocked]

### Merge Actions

\`\`\`bash
# 1. Push from worktrees
cd /path/to/worktree-a
git add -A && git commit -m "Complete [tasks]"
git push origin feature/[branch-a]

cd /path/to/worktree-b
git add -A && git commit -m "Complete [tasks]"
git push origin feature/[branch-b]

# 2. Create PRs
gh pr create --base dev --head feature/[branch-a] --title "[Service]: [Batch]" --body "..."
gh pr create --base dev --head feature/[branch-b] --title "[Service]: [Batch]" --body "..."

# 3. Merge to dev (from main repo)
cd /path/to/main-repo
git checkout dev && git pull origin dev
git merge origin/feature/[branch-a] --no-ff -m "Merge [Service A]: [tasks]"
git merge origin/feature/[branch-b] --no-ff -m "Merge [Service B]: [tasks]"
git push origin dev

# 4. Update worktrees
cd /path/to/worktree-a && git fetch origin dev && git rebase origin/dev
cd /path/to/worktree-b && git fetch origin dev && git rebase origin/dev

# 5. Tag merge point
cd /path/to/main-repo
git tag -a mp[N]-reached -m "MP[N]: [Description] - $(date +%Y-%m-%d)"
git push origin mp[N]-reached
\`\`\`

### Container Deployment

\`\`\`bash
# Deploy services for MP[N] verification
cd /path/to/main-repo

# Start required services
docker compose up -d [services]
sleep 15

# Verify services are healthy
curl -sf http://localhost:[port]/health && echo "✅ [Service] healthy"
\`\`\`

### Container Test Scenarios

\`\`\`bash
# ═══════════════════════════════════════════════════════════════
# MP[N] CONTAINER TESTS
# ═══════════════════════════════════════════════════════════════

# Setup: Get required tokens
[Token acquisition commands]

# Test 1: [Description]
echo "Test 1: [Description]..."
curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X [METHOD] "http://localhost:[port]/api/v1/[endpoint]" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '[payload]'
# Expected: [response]

# Test 2: [Description]
echo "Test 2: [Description]..."
[curl command]
# Expected: [response]

# Test 3: [Description]
echo "Test 3: [Description]..."
[curl command]
# Expected: [response]

echo "✅ MP[N] VALIDATION COMPLETE"
\`\`\`

### Cleanup

\`\`\`bash
# Stop services after testing
docker compose down

# Optional: Remove volumes for clean restart
docker compose down -v

# Remove test data only (preserve services)
docker compose exec -T db psql -U [user] -d [db] \
  -c "DELETE FROM [table] WHERE [condition];"
\`\`\`

### Success Criteria

- [ ] [Task A] complete
- [ ] [Task B] complete
- [ ] Unit tests pass in both worktrees
- [ ] Integration tests pass
- [ ] Container deployment works
- [ ] [Specific criterion for this MP]

### Post-Merge Status Update

After reaching MP[N], run:

\`\`\`bash
# 1. Verify batch completion
/verify-batch-completion [batch-id] [feature-name]

# 2. Update STATUS.md
# Mark MP[N] as "✅ REACHED (date)"

# 3. Update this file (MERGE_POINTS.md)
# Change status from "⏳ NOT REACHED" to "✅ REACHED (date)"

# 4. Update BATCH_EXECUTION_PLAN.md Quick Reference
# Mark batch as "✅ Complete"

# 5. Commit status updates
cd /path/to/main-repo
git add docs/workstreams/[feature]/
git commit -m "Mark MP[N] as reached"
git push origin dev
\`\`\`

---

[Repeat the MP[N] section for each merge point]

---

## Testing Strategy by Phase

### Phase 0: Contract Verification

\`\`\`bash
# Endpoints exist and return correct formats
[E2E demo command]
# Success = exit code 0 (mocks OK)
\`\`\`

### Phase 1: Implementation Verification

\`\`\`bash
# Real APIs called, real data returned
[E2E demo command with verbose]

# Verify no mock strings in output
grep -c "Mock" /tmp/demo_output.log
# Success = 0 matches
\`\`\`

### Phase 2: Production Verification

\`\`\`bash
# Security test suite
pytest tests/security/ -v
\`\`\`

---

## Troubleshooting

### MP1 Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| [Issue] | [Cause] | [Fix] |

### MP2 Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| [Issue] | [Cause] | [Fix] |

### MP3 Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| [Issue] | [Cause] | [Fix] |

---

## Container Deployment Schedule

| Merge Point | When to Deploy | Services | Duration |
|-------------|----------------|----------|----------|
| **MP1** | After [batch] complete | [services] | ~X min |
| **MP2** | After [batch] complete | [services] | ~X min |

### Container Environment Setup

\`\`\`bash
# Environment variables for all merge point testing
export [VAR1]=http://localhost:[port]
export [VAR2]=http://localhost:[port]
# ...

# For production testing (final MP)
export ENVIRONMENT=production
\`\`\`

---

## Quick Reference Commands

### Merge Point Validation

\`\`\`bash
# MP1: [Description]
cd /path/to/main-repo
[validation command]
# Expected: [result]

# MP2: [Description]
docker compose up -d [services]
sleep 15
[validation command]
# Expected: [result]
\`\`\`

### Status Verification

\`\`\`bash
# After any merge point reached
/verify-batch-completion [batch-id] [feature-name]

# Manual verification
cat docs/workstreams/[feature]/STATUS.md | grep -E "MP[1-4]"
\`\`\`

### Git Commands

\`\`\`bash
# 1. Push from worktree
cd /path/to/[worktree-name]
git add -A && git commit -m "Complete [task description]"
git push origin feature/[worktree-branch]

# 2. Create PR
gh pr create --base dev --head feature/[worktree-branch] \
  --title "[Service]: [Batch] ([Tasks])" \
  --body "[Description]"

# 3. Merge to dev (after PR review)
cd /path/to/main-repo
git checkout dev && git pull origin dev
git merge origin/feature/[worktree-branch] --no-ff -m "Merge [Service]: [Batch]"
git push origin dev

# 4. Update worktree
cd /path/to/[worktree-name] && git rebase origin/dev

# 5. Tag merge point
cd /path/to/main-repo
git tag -a mp[N]-reached -m "MP[N]: [Description] - $(date +%Y-%m-%d)"
git push origin mp[N]-reached
\`\`\`

---

## Merge Point Status

| Merge Point | Description | Status | Date Reached | Validation |
|-------------|-------------|--------|--------------|------------|
| **MP1** | [Description] | ⏳ NOT REACHED | - | [Command] |
| **MP2** | [Description] | ⏳ NOT REACHED | - | [Command] |
| **MP3** | [Description] | ⏳ NOT REACHED | - | [Command] |
| **MP4** | [Description] | ⏳ NOT REACHED | - | [Command] |

### Progress Summary

\`\`\`
Total Merge Points: [N]
Reached: 0 (0%)
Remaining: [N] (100%)

MP1 ░░░░░░░░░░░░░░░░░░░░   0% ⏳
MP2 ░░░░░░░░░░░░░░░░░░░░   0% ⏳
MP3 ░░░░░░░░░░░░░░░░░░░░   0% ⏳
MP4 ░░░░░░░░░░░░░░░░░░░░   0% ⏳
\`\`\`

---

## History

| Date | Event | Details |
|------|-------|---------|
| [Date] | Workstream created | Initial planning |
| [Date] | MP1 reached | [Details] |
```

---

## Output Verification Checklist (MANDATORY)

**Before declaring MERGE_POINTS.md complete, verify ALL sections exist.**

### Required Sections Checklist

| # | Section | Required? | Purpose |
|---|---------|-----------|---------|
| 1 | **Overview** | ✅ YES | Brief description and key distinctions |
| 2 | **Code Dependencies vs Runtime Dependencies** | ✅ YES | ASCII diagram explaining difference |
| 3 | **Task Lifecycle with Dependencies** | ✅ YES | ASCII diagram showing states |
| 4 | **When Each Dependency Type Matters** | ✅ YES | Phase table |
| 5 | **Development Mode vs Integration Mode** | ✅ YES | Fallback behavior tables |
| 6 | **Runtime Dependencies by Merge Point** | ✅ YES | Service availability table |
| 7 | **Runtime Dependencies by Task** | ✅ YES | Task-level dependencies |
| 8 | **Merge Point Summary** | ✅ YES | ASCII overview diagram |
| 9 | **Per-MP: Status** | ✅ YES | Current status |
| 10 | **Per-MP: Why It's a Merge Point** | ✅ YES | Justification |
| 11 | **Per-MP: Purpose** | ✅ YES | What it validates |
| 12 | **Per-MP: Validation Command** | ✅ YES | How to verify |
| 13 | **Per-MP: Converging Tasks** | ✅ YES | Task table |
| 14 | **Per-MP: Enables** | ✅ YES | What's unlocked |
| 15 | **Per-MP: Merge Actions** | ✅ YES | Git workflow commands |
| 16 | **Per-MP: Container Deployment** | ✅ YES | Docker commands |
| 17 | **Per-MP: Container Test Scenarios** | ✅ YES | curl examples with expected outputs |
| 18 | **Per-MP: Cleanup** | ✅ YES | Cleanup commands |
| 19 | **Per-MP: Success Criteria** | ✅ YES | Checklist |
| 20 | **Per-MP: Post-Merge Status Update** | ✅ YES | Status update commands |
| 21 | **Testing Strategy by Phase** | ✅ YES | P0, P1, P2 sections |
| 22 | **Troubleshooting** | ✅ YES | Issue/Cause/Fix tables |
| 23 | **Container Deployment Schedule** | ✅ YES | When to deploy |
| 24 | **Container Environment Setup** | ✅ YES | Environment variables |
| 25 | **Quick Reference Commands** | ✅ YES | Copy-paste ready |
| 26 | **Merge Point Status** | ✅ YES | Status table |
| 27 | **Progress Summary** | ✅ YES | ASCII progress bars |
| 28 | **History** | ✅ YES | Event log |

### Verification Command

```bash
FEATURE="[feature-name]"
FILE="docs/workstreams/${FEATURE}/MERGE_POINTS.md"

echo "=== MERGE_POINTS.md Section Verification ==="
grep -q "## Code Dependencies vs Runtime Dependencies" $FILE && echo "✅ Code vs Runtime Dependencies" || echo "❌ MISSING"
grep -q "### Task Lifecycle with Dependencies" $FILE && echo "✅ Task Lifecycle" || echo "❌ MISSING"
grep -q "### When Each Dependency Type Matters" $FILE && echo "✅ Dependency Phases" || echo "❌ MISSING"
grep -q "## Development Mode vs Integration Mode" $FILE && echo "✅ Dev vs Integration Mode" || echo "❌ MISSING"
grep -q "### Runtime Dependencies by Merge Point" $FILE && echo "✅ Runtime Deps by MP" || echo "❌ MISSING"
grep -q "### Runtime Dependencies by Task" $FILE && echo "✅ Runtime Deps by Task" || echo "❌ MISSING"
grep -q "## Merge Point Summary" $FILE && echo "✅ MP Summary" || echo "❌ MISSING"
grep -q "### Merge Actions" $FILE && echo "✅ Merge Actions" || echo "❌ MISSING"
grep -q "### Container Deployment" $FILE && echo "✅ Container Deployment" || echo "❌ MISSING"
grep -q "### Container Test Scenarios" $FILE && echo "✅ Container Test Scenarios" || echo "❌ MISSING"
grep -q "### Cleanup" $FILE && echo "✅ Cleanup" || echo "❌ MISSING"
grep -q "### Success Criteria" $FILE && echo "✅ Success Criteria" || echo "❌ MISSING"
grep -q "### Post-Merge Status Update" $FILE && echo "✅ Post-Merge Status" || echo "❌ MISSING"
grep -q "## Testing Strategy by Phase" $FILE && echo "✅ Testing Strategy" || echo "❌ MISSING"
grep -q "## Troubleshooting" $FILE && echo "✅ Troubleshooting" || echo "❌ MISSING"
grep -q "## Container Deployment Schedule" $FILE && echo "✅ Deployment Schedule" || echo "❌ MISSING"
grep -q "## Quick Reference Commands" $FILE && echo "✅ Quick Reference" || echo "❌ MISSING"
grep -q "## Merge Point Status" $FILE && echo "✅ MP Status Table" || echo "❌ MISSING"
grep -q "### Progress Summary" $FILE && echo "✅ Progress Summary" || echo "❌ MISSING"
grep -q "## History" $FILE && echo "✅ History" || echo "❌ MISSING"
echo "=== Verification Complete ==="
```

---

## Pre-Merge Checklist Template

```markdown
## MP[N] Pre-Merge Checklist

### Task Completion
- [ ] [Task A]: Complete with tests passing
- [ ] [Task B]: Complete with tests passing
- [ ] Completion reports generated

### Code Quality
- [ ] `ruff check .` passes
- [ ] `mypy` passes (if used)
- [ ] No TODO/FIXME blocking merge

### Contract Verification (BLOCKING)
- [ ] All endpoints match design doc spec exactly
- [ ] Test endpoints match implementation endpoints
- [ ] Request/response schemas match spec
- [ ] No 404/405 errors from endpoint mismatches

### File Location Verification (BLOCKING)
- [ ] E2E tests at root level (`tests/e2e/`)
- [ ] Demos at root level (`demos/`)
- [ ] Demo tests at root level (`tests/demos/`)

### Technical Requirements (BLOCKING)
- [ ] Async fixtures use `@pytest_asyncio.fixture`
- [ ] HTTP clients use `httpx.AsyncClient`
- [ ] No `AttributeError: 'async_generator'` errors

### Integration Readiness
- [ ] Shared interfaces aligned
- [ ] Environment variables documented
- [ ] Migration scripts ready (if applicable)

### Testing
- [ ] Unit tests: X% coverage
- [ ] Integration tests written for MP[N]
- [ ] Test data/fixtures prepared
- [ ] E2E tests pass with services running

### Documentation
- [ ] API changes documented
- [ ] Configuration changes documented
- [ ] README updated (if needed)
```

---

## Quick Reference

### Merge Point Commands

```bash
# Push worktree
git push origin feature/[branch]

# Create PR
gh pr create --base dev --head feature/[branch] --title "..."

# Merge to dev
git checkout dev && git pull
git merge origin/feature/[branch] --no-ff
git push origin dev

# Update worktree
cd /path/to/worktree && git rebase origin/dev

# Run integration tests
pytest tests/integration/ -m merge_point_N -v

# Container test
./scripts/test_merge_point.sh mpN

# Sync status
/sync-worktree-status [feature]
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Merge conflict | Resolve in main repo, then rebase worktrees |
| Integration test fails | Check service logs, verify configuration |
| Container health fails | Check depends_on, increase wait time |
| Worktree out of sync | `git fetch origin dev && git rebase origin/dev` |

---

## References

- [WORKFLOW_GUIDE.md](../WORKFLOW_GUIDE.md) - Overall workflow guide
- [PARALLEL_EXECUTION_GUIDE.md](../PARALLEL_EXECUTION_GUIDE.md) - Parallel execution patterns
- [TASK_BREAKDOWN.md](../TASK_BREAKDOWN.md) - Task breakdown methodology
- [BATCH_EXECUTION_PLAN.md Template](./BATCH_EXECUTION_PLAN.md) - Example from virtual-mcp-server-mvp
