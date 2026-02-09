# [Feature/Component Name] Design Document

> **Status**: Draft | In Review | Approved | Implemented  
> **Author**: [Name]  
> **Created**: [Date]  
> **Last Updated**: [Date]

## Overview

[1-2 paragraph summary of what this design accomplishes]

## Goals

- [ ] Goal 1
- [ ] Goal 2
- [ ] Goal 3

## Non-Goals

- What this design explicitly does NOT address

## Background

[Context and motivation for this design]

## Technical Design

### Architecture

[Describe the architecture, include diagrams if helpful]

### Data Models

[Define new data structures, database schemas]

### API Contracts (CANONICAL SOURCE)

> **CRITICAL**: This section is the CANONICAL source for all API endpoints.
> Task tickets, tests, and implementations MUST match these exactly.
> Any deviation requires updating this design doc first.

#### Service: [Control Plane / Gateway]

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| POST | `/api/v1/exact/path` | [Purpose] | [Schema or link] | [Schema or link] |
| GET | `/api/v1/other/path` | [Purpose] | [Params] | [Schema or link] |

**Request/Response Schemas:**

```json
// POST /api/v1/exact/path - Request
{
  "field": "string"
}

// POST /api/v1/exact/path - Response (200)
{
  "id": "uuid",
  "created_at": "ISO8601"
}
```

### Security Considerations

[Authentication, authorization, encryption, key management]

---

## Implementation Workstreams

### Workstream A: [Name] (can run in parallel with B, C)

| Task ID | Description | Dependencies | Complexity | Acceptance Criteria |
|---------|-------------|--------------|------------|---------------------|
| WS-A1 | [Task description] | None | S/M/L | [How to verify] |
| WS-A2 | [Task description] | WS-A1 | S/M/L | [How to verify] |
| WS-A3 | [Task description] | WS-A1 | S/M/L | [How to verify] |

**Files to modify/create:**
- `path/to/file1.py`
- `path/to/file2.py`

### Workstream B: [Name] (can run in parallel with A, C)

| Task ID | Description | Dependencies | Complexity | Acceptance Criteria |
|---------|-------------|--------------|------------|---------------------|
| WS-B1 | [Task description] | None | S/M/L | [How to verify] |
| WS-B2 | [Task description] | WS-B1 | S/M/L | [How to verify] |

**Files to modify/create:**
- `path/to/file3.py`

### Workstream C: [Name] (blocked by Workstream A)

| Task ID | Description | Dependencies | Complexity | Acceptance Criteria |
|---------|-------------|--------------|------------|---------------------|
| WS-C1 | [Task description] | WS-A3, WS-B2 | S/M/L | [How to verify] |
| WS-C2 | [Task description] | WS-C1 | S/M/L | [How to verify] |

**Files to modify/create:**
- `path/to/file4.py`
- `tests/test_integration.py`

---

## Dependency Graph

```
Workstream A          Workstream B          Workstream C
-----------          ------------          ------------
   A1                     B1
   │                      │
   ├──► A2                │
   │                      │
   └──► A3 ───────────────┴──────────────► C1
                                            │
                                            ▼
                                           C2
```

## Critical Path

The critical path is: `A1 → A3 → C1 → C2`

Workstream B can run entirely in parallel with A.

---

## Parallelization Strategy

> This section documents the decision for how to parallelize work across worktrees/instances.

### Service Boundaries

| Service | Directory | Workstreams | Independent Until |
|---------|-----------|-------------|-------------------|
| [Service 1] | `[service-1]/` | WS-A, WS-C (partial) | MP1 |
| [Service 2] | `[service-2]/` | WS-B, WS-D | MP1 |

### Worktree Recommendation

| Worktree | Branch Pattern | Services | Workstreams | Rationale |
|----------|----------------|----------|-------------|-----------|
| `[feature]-control` | `feature/[feature]-control` | deeptrail-control | A, C (partial) | Control plane changes |
| `[feature]-gateway` | `feature/[feature]-gateway` | deeptrail-gateway | B, D | Gateway changes |

### Tradeoff Analysis

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Git Worktrees** | Disk efficient, shared .git, consistent config | Git locks can conflict on heavy ops | ✅ Recommended |
| Multiple Clones | Complete isolation, no lock conflicts | Disk heavy, config/env sync overhead | ❌ Overkill for most |
| Single Worktree | Simple, no sync issues | Misses parallelization opportunity | ❌ Sequential only |

### Why This Setup

- **[X] worktrees** based on service boundaries (not workstream count)
- Workstreams A and B are fully parallel until Merge Point 1
- Each worktree maps to a distinct service directory
- Enables [X] Claude instances working simultaneously on independent code

### Merge Points

| Point | Converging From | Enables | When |
|-------|-----------------|---------|------|
| MP1 | Worktree 1 + Worktree 2 | Integration workstreams | After Batch [N] |

---

## Testing Strategy

### Unit Tests
- [ ] Test for component X
- [ ] Test for component Y

**Location:** `[service]/tests/[module]/test_*.py`

### Integration Tests
- [ ] Test for workflow Z

**Location:** `[service]/tests/integration/test_*.py`

### End-to-End Tests (MVP Level)

> **CRITICAL**: E2E tests that span multiple services MUST be at root level, not nested in a single service.

| Test File | Location | What It Validates | Services Required |
|-----------|----------|-------------------|-------------------|
| `test_[persona]_journey.py` | `tests/e2e/` (ROOT) | Full user journey | Control + Gateway |

**Location Rules:**
- Cross-service E2E tests → `tests/e2e/` (root)
- Service-specific E2E tests → `[service]/tests/e2e/`

### Test Endpoint Verification

> Tests MUST use the exact endpoints from "API Contracts" section above.

| Test | Endpoint Used | Matches Contract? |
|------|---------------|-------------------|
| `test_user_login` | `/api/v1/auth/login` | ✅ Verify |
| `test_agent_auth` | `/api/v1/auth/agent/challenge` | ✅ Verify |

### Technical Requirements for Tests

| Requirement | Correct Pattern | Common Mistake |
|-------------|-----------------|----------------|
| Async fixtures | `@pytest_asyncio.fixture` | `@pytest.fixture` (breaks async) |
| HTTP client | `httpx.AsyncClient` | `requests` (sync) |
| Fixture scope | `scope="function"` for clients | `scope="session"` (connection issues) |

---

## File Organization

### Cross-Service vs Service-Specific

| Type | Scope | Location | Example |
|------|-------|----------|---------|
| MVP demos | Cross-service | `demos/` (root) | `demos/demo_01_[value].py` |
| MVP E2E tests | Cross-service | `tests/e2e/` (root) | `tests/e2e/test_[persona]_journey.py` |
| Demo tests | Cross-service | `tests/demos/` (root) | `tests/demos/test_demo_01.py` |
| Service unit tests | Single service | `[service]/tests/` | `deeptrail-gateway/tests/mcp/` |
| Service-specific demos | Single service | `[service]/demos/` | (rare) |

### File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Journey test | `test_[persona]_journey.py` | `test_sarah_journey.py` |
| Value prop demo | `demo_[NN]_[value].py` | `demo_01_unified_connection.py` |
| Model | `[entity].py` | `user_session.py` |
| API router | `[resource]_router.py` | `delegation_router.py` |

---

## Rollout Plan

### Phase 1: [Description]
- Tasks: WS-A1, WS-A2, WS-B1

### Phase 2: [Description]  
- Tasks: WS-A3, WS-B2

### Phase 3: [Description]
- Tasks: WS-C1, WS-C2

---

## Open Questions

- [ ] Question 1?
- [ ] Question 2?

## References

- [Link to related design docs]
- [Link to external documentation]
