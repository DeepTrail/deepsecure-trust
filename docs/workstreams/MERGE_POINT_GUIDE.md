# Merge Point Guide: Actions & Testing Strategy

> **Purpose:** Generic guide for handling merge points during parallel workstream execution.
>
> **Applies to:** Any design document broken into workstreams and tasks.
>
> **Last Updated:** January 2026

---

## Table of Contents

1. [What Are Merge Points?](#what-are-merge-points)
2. [Identifying Merge Points](#identifying-merge-points)
3. [Merge Point Workflow](#merge-point-workflow)
4. [Testing Strategy](#testing-strategy)
5. [Container Deployment](#container-deployment)
6. [Templates](#templates)

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

### Merge Point Documentation Template

Create `docs/workstreams/[feature]/MERGE_POINTS.md`:

```markdown
# [Feature Name]: Merge Points & Testing Strategy

## Overview

[Brief description of the feature and its merge points]

---

## Merge Points Summary

| Point | After Batch | Converging | Enables | Integration Type |
|-------|-------------|------------|---------|------------------|
| **MP1** | Batch N | A + B | C | [Type] |
| **MP2** | Batch M | C + D | E | [Type] |

---

## MP1: [Name]

### What's Converging

| Worktree | Task | Description |
|----------|------|-------------|
| [worktree-a] | [Task ID] | [Description] |
| [worktree-b] | [Task ID] | [Description] |

### Why It's a Merge Point

[Explanation of why these tasks must converge]

### Pre-Merge Checklist

- [ ] [Task A] complete
- [ ] [Task B] complete
- [ ] [Shared requirement]

### Testing Requirements

| Test Type | Description | Command |
|-----------|-------------|---------|
| Unit | [Description] | `pytest ...` |
| Integration | [Description] | `pytest ...` |
| Container | [Description] | `docker compose ...` |

### Success Criteria

- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] Integration tests pass
- [ ] Container deployment works

---

## [Repeat for each merge point]

---

## Merge Point Status

| Point | Status | Merged At | Notes |
|-------|--------|-----------|-------|
| MP1 | ⏸️ Pending | - | - |
| MP2 | ⏸️ Pending | - | - |
```

### Pre-Merge Checklist Template

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
