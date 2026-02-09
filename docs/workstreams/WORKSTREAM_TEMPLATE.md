# Workstream: [Workstream Name]

> Copy this template to create a new workstream.
> Save as: `docs/workstreams/[feature-name]/WORKSTREAM.md`

---

## Overview

| Field | Value |
|-------|-------|
| **Design Doc** | [link to parent design doc] |
| **Workstream ID** | WS-[A/B/C/...] |
| **Status** | `planning` / `in_progress` / `blocked` / `completed` |
| **Owner** | [Person/Team] |
| **Created** | [Date] |
| **Target Completion** | [Date] |

---

## Description

[Brief description of what this workstream accomplishes and why it exists as a separate workstream]

---

## Parallelization Strategy

> This section records the worktree decision for this feature.

### Worktree Assignment

| Worktree | Branch | Services | Workstreams | This Workstream? |
|----------|--------|----------|-------------|------------------|
| `[feature]-control` | `feature/[feature]-control` | deeptrail-control | A, C, E (partial) | ✅ / ❌ |
| `[feature]-gateway` | `feature/[feature]-gateway` | deeptrail-gateway | B, D, E (partial) | ✅ / ❌ |

### Decision Rationale

**Setup:** [X] worktrees based on service boundaries

**Why this decision:**
- [Workstream A] and [Workstream B] are fully parallel (no shared dependencies until MP[X])
- [Service 1] and [Service 2] have separate codebases
- Enables [X] Claude instances working simultaneously

**Alternatives Considered:**
- [X+1] worktrees (one per major workstream) - Rejected: overhead not worth it
- 1 worktree (sequential) - Rejected: misses parallelization opportunity
- Clones instead of worktrees - Rejected: worktrees sufficient, saves disk space

---

## Workstream Dependencies

### Can Run In Parallel With
- Workstream B: [name] - [why parallel is safe]
- Workstream C: [name] - [why parallel is safe]

### Blocked By
- Workstream X: [name] - [why this dependency exists]

### Blocks
- Workstream Y: [name] - [what this workstream produces that Y needs]

---

## Tasks

| Task ID | Task Name | Status | Dependencies | Complexity | Assignee |
|---------|-----------|--------|--------------|------------|----------|
| WS-A1 | [Task name] | `ready` | None | S | - |
| WS-A2 | [Task name] | `draft` | WS-A1 | M | - |
| WS-A3 | [Task name] | `draft` | WS-A1 | M | - |
| WS-A4 | [Task name] | `draft` | WS-A2, WS-A3 | L | - |

### Task Dependency Graph

```
WS-A1
  │
  ├──► WS-A2 ──┐
  │            │
  └──► WS-A3 ──┴──► WS-A4
```

---

## Task Links

### Task Tickets
- [WS-A1: Task Name](./tasks/WS-A1-task-name.md)
- [WS-A2: Task Name](./tasks/WS-A2-task-name.md)
- [WS-A3: Task Name](./tasks/WS-A3-task-name.md)
- [WS-A4: Task Name](./tasks/WS-A4-task-name.md)

### Completion Reports
- [WS-A1 Completion](./reports/WS-A1-completion.md) - ✅ Completed
- [WS-A2 Completion](./reports/WS-A2-completion.md) - ⏳ In Progress
- WS-A3 - Not started
- WS-A4 - Not started

---

## Progress

### Overall Progress: **[X]%**

```
[████████░░░░░░░░░░░░] 40% complete
```

| Metric | Value |
|--------|-------|
| **Total Tasks** | [X] |
| **Completed** | [Y] |
| **In Progress** | [Z] |
| **Blocked** | [W] |

### Milestone Tracking

| Milestone | Target Date | Status | Notes |
|-----------|-------------|--------|-------|
| All task tickets created | [date] | ✅ / ⏳ / ❌ | |
| Core implementation complete | [date] | ✅ / ⏳ / ❌ | |
| **Contract verification passed** | [date] | ✅ / ⏳ / ❌ | Endpoints match spec |
| **File locations verified** | [date] | ✅ / ⏳ / ❌ | E2E tests at root |
| Unit tests passing | [date] | ✅ / ⏳ / ❌ | |
| E2E tests passing | [date] | ✅ / ⏳ / ❌ | |
| Ready for integration | [date] | ✅ / ⏳ / ❌ | |

### Verification Checkpoints (BLOCKING)

> These must pass before marking workstream complete.

| Check | Command | Status |
|-------|---------|--------|
| Endpoints match spec | `grep -r "@router" \| grep "/api/v1"` | ✅ / ❌ |
| Tests use correct endpoints | `grep -r '"/api/v1' tests/` | ✅ / ❌ |
| Async fixtures correct | `grep "@pytest.fixture" tests/ -r` (should be empty for async) | ✅ / ❌ |
| E2E tests at root | `ls tests/e2e/` | ✅ / ❌ |
| Demos at root | `ls demos/` | ✅ / ❌ |

---

## Files Affected

This workstream will create or modify:

### New Files
- `path/to/new/file1.py`
- `path/to/new/file2.py`

### Modified Files
- `path/to/existing/file.py`

### Test Files
- `tests/path/to/test_file.py`

### File Location Rules

> **CRITICAL**: Cross-service artifacts MUST be at root level, not nested in a single service.

| Artifact Type | Correct Location | Wrong Location |
|---------------|------------------|----------------|
| MVP E2E tests (cross-service) | `tests/e2e/` (ROOT) | `[service]/tests/e2e/` |
| MVP demos (cross-service) | `demos/` (ROOT) | `[service]/demos/` |
| Demo tests | `tests/demos/` (ROOT) | `[service]/tests/demos/` |
| Service-specific unit tests | `[service]/tests/` | Root level |

---

## API Contracts (from Design Doc)

> **CRITICAL**: Copy endpoints from design doc's "API Contracts" section.
> These are CANONICAL - implementation and tests MUST match exactly.

| Service | Method | Endpoint | Task |
|---------|--------|----------|------|
| Control | POST | `/api/v1/exact/path` | WS-A1 |
| Gateway | POST | `/api/v1/other/path` | WS-B1 |

---

## Technical Requirements

| Requirement | Pattern | Applies To |
|-------------|---------|------------|
| Async fixtures | `@pytest_asyncio.fixture` | All async tests |
| HTTP client | `httpx.AsyncClient` | All async HTTP |
| Fixture scope | `scope="function"` for clients | Avoid connection issues |

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [Risk description] | High/Med/Low | High/Med/Low | [How to mitigate] |

---

## Notes

[Any additional context, decisions made, or things to remember]

---

## History

| Date | Event |
|------|-------|
| [date] | Workstream created |
| [date] | [Event/decision/milestone] |
