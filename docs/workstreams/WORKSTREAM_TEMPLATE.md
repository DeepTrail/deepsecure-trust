# Workstream: [Feature Name]

> Copy this template to create a new workstream.
> Save as: `docs/workstreams/[feature-name]/WORKSTREAM.md`
>
> **Quality bar:** Match the depth of proven gold-standard docs:
> - `docs/workstreams/idp-selector/WORKSTREAM.md`
> - `docs/workstreams/idp-enhanced-sso/WORKSTREAM.md`
> - `docs/workstreams/virtual-mcp-server-mvp/WORKSTREAM.md`
> - `docs/workstreams/mvp-production-readiness/WORKSTREAM.md`

> **Design Doc**: [docs/design/[feature-name].md](../../design/[feature-name].md)
> **Breakdown**: [BREAKDOWN.md](./BREAKDOWN.md)
> **Codebase Analysis**: [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md)
> **Execution Status**: [STATUS.md](./STATUS.md)
> **Batch Execution Plan**: [BATCH_EXECUTION_PLAN.md](./BATCH_EXECUTION_PLAN.md)

---

## Executive Summary

[2-4 bullet points: what this feature delivers and why it matters. Business-facing, not technical.]

- **[Point 1]:** [Business value]
- **[Point 2]:** [User impact]

---

## Overview

| Field | Value |
|-------|-------|
| **Design Doc** | [link to parent design doc] |
| **Breakdown Doc** | [link to BREAKDOWN.md] |
| **Status** | `planning` / `in_progress` / `blocked` / `completed` |
| **Created** | [Date] |
| **Target Completion** | [Date or —] |
| **Total Workstreams** | [N] |
| **Total Tasks** | [N] |
| **Total Batches** | [N] |
| **Merge Points** | [N] |

---

## Feature Summary

> Maps features to workstreams for multi-workstream features. For single-workstream features, note "N/A — single workstream" and skip the table.

| Feature | Workstream | Tasks | Service |
|---------|-----------|-------|---------|
| [Feature 1 name] | WS-A | [N] (A1–AN) | deeptrail-control |
| [Feature 2 name] | WS-B | [N] (B1–BN) | deeptrail-gateway |

---

## Workstreams

| WS ID | Name | Status | Parallel With | Depends On | Tasks |
|-------|------|--------|---------------|------------|-------|
| WS-A | [Name] | `planning` | WS-B | None | A1–AN |
| WS-B | [Name] | `planning` | WS-A | None | B1–BN |

---

## Workstream Dependencies

```
WS-A ([Service 1]) ──────────┐
WS-B ([Service 2]) ──────────┤── MP1 ──→ WS-C (E2E)
```

### Can Run In Parallel With
- Workstream B: [name] — [why parallel is safe]

### Blocked By
- [None or dependency list]

### Blocks
- Workstream C: [name] — [what this workstream produces that C needs]

---

## Parallelization Strategy

> This section records the worktree decision for this feature.

### Worktree Assignment

| Worktree | Branch | Services | Workstreams | Status |
|----------|--------|----------|-------------|--------|
| `[feature]-control` | `feature/[feature]-control` | deeptrail-control | A, C | ⏳ Pending |
| `[feature]-gateway` | `feature/[feature]-gateway` | deeptrail-gateway | B, D | ⏳ Pending |

### Decision Rationale

**Setup:** [X] worktrees based on service boundaries

**Why this decision:**
- [Workstream A] and [Workstream B] are fully parallel (no shared dependencies until MP[X])
- [Service 1] and [Service 2] have separate codebases
- Enables [X] Claude instances working simultaneously

**Alternatives Considered:**
- [X+1] worktrees (one per major workstream) — Rejected: overhead not worth it
- 1 worktree (sequential) — Rejected: misses parallelization opportunity
- Clones instead of worktrees — Rejected: worktrees sufficient, saves disk space

### Worktree Lifecycle

| Phase | Action | Commands |
|-------|--------|----------|
| **Setup** | Create worktrees | `git worktree add ../[name] -b feature/[name] dev` |
| **Execution** | Work in worktrees | `/execute-task`, `/complete-task` |
| **Merge** | Merge to dev | `git merge feature/[name] --no-ff` |
| **Cleanup** | Remove worktrees | `git worktree remove ../[name]` |

---

## Scope

### In Scope
- [Bullet list of what IS included]

### Out of Scope
- [Bullet list of what is explicitly NOT included and why]

---

## Key Decisions

### [Decision 1 Name]
**Decision:** [What was chosen]
**Rationale:** [Why this choice over alternatives]

### [Decision 2 Name]
**Decision:** [What was chosen]
**Rationale:** [Why]

---

## Batch Overview

| Batch | Tasks | Focus | Status |
|-------|-------|-------|--------|
| 1 | A1, B1 | Foundation | ⏳ Pending |
| 2 | A2, B2 | Core Logic | ⏳ Pending |
| 3 | C1 | Integration | ⏳ Pending |

---

## Merge Points

> Quick-reference table. Full details in [MERGE_POINTS.md](./MERGE_POINTS.md).

| Point | After Batch | Converging Tasks | Enables | Status |
|-------|-------------|------------------|---------|--------|
| MP1 | Batch 2 | A8 + B3 | C1 (E2E) | ⏳ Pending |

---

## Critical Path

```
A1 → A2 → B1 → B6 → C2 → E2 → [MP1] → F1
```

[Brief explanation of what determines the critical path and what could extend it.]

---

## All Tasks

### WS-A: [Workstream Name]

| Task ID | Task Name | Status | Dependencies | Complexity | Batch |
|---------|-----------|--------|--------------|------------|-------|
| WS-A1 | [Task name] | `ready` | None | S | 1 |
| WS-A2 | [Task name] | `draft` | WS-A1 | M | 2 |

### WS-B: [Workstream Name]

| Task ID | Task Name | Status | Dependencies | Complexity | Batch |
|---------|-----------|--------|--------------|------------|-------|
| WS-B1 | [Task name] | `ready` | None | S | 1 |

### Task Dependency Graph

```
WS-A1 ──→ WS-A2 ──→ WS-A3 ──┐
                               ├──→ [MP1] ──→ WS-C1
WS-B1 ──→ WS-B2 ──→ WS-B3 ──┘
```

---

## Task Tickets

### Batch 1 ⏳ Pending
- [WS-A1: Task Name](./tasks/WS-A1-task-name.md) — ⏳ `pending`
- [WS-B1: Task Name](./tasks/WS-B1-task-name.md) — ⏳ `pending`

### Batch 2 ⏳ Pending
- [WS-A2: Task Name](./tasks/WS-A2-task-name.md) — ⏳ `pending`
- [WS-B2: Task Name](./tasks/WS-B2-task-name.md) — ⏳ `pending`

### Batch 3 ⏳ Pending
- [WS-C1: Task Name](./tasks/WS-C1-task-name.md) — ⏳ `pending`

---

## Specifications

| Task ID | Spec | Ticket | Status | Report |
|---------|------|--------|--------|--------|
| WS-A1 | [specs/WS-A1-spec.md](./specs/WS-A1-spec.md) | [tasks/WS-A1-*.md](./tasks/WS-A1-task-name.md) | ⏳ | — |
| WS-A2 | [specs/WS-A2-spec.md](./specs/WS-A2-spec.md) | [tasks/WS-A2-*.md](./tasks/WS-A2-task-name.md) | ⏳ | — |

---

## Completion Reports

_Filed after each task completes._

| Task ID | Report | Filed |
|---------|--------|-------|
| WS-A1 | [reports/WS-A1-completion.md](./reports/WS-A1-completion.md) | — |

---

## Key Files by Workstream

### WS-A: [Workstream Name]

| File | Action | Description |
|------|--------|-------------|
| `path/to/new/file1.py` | Create | [What it does] |
| `path/to/existing/file.py` | Modify | [What changes] |

### WS-B: [Workstream Name]

| File | Action | Description |
|------|--------|-------------|
| `path/to/new/file2.py` | Create | [What it does] |

### File Location Rules

> **CRITICAL**: Cross-service artifacts MUST be at root level, not nested in a single service.

| Artifact Type | Correct Location | Wrong Location |
|---------------|------------------|----------------|
| MVP E2E tests (cross-service) | `tests/e2e/` (ROOT) | `[service]/tests/e2e/` |
| MVP demos (cross-service) | `demos/` (ROOT) | `[service]/demos/` |
| Demo tests | `tests/demos/` (ROOT) | `[service]/tests/demos/` |
| Service-specific unit tests | `[service]/tests/` | Root level |

---

## Validation Criteria

### MP1 Complete
```bash
# Run service-level tests
pytest [service]/tests/ -v

# Verify endpoints match spec
grep -r "@router" [service]/app/api/ | grep "/api/v1"
```

### All Batches Complete
```bash
# Full E2E validation
pytest tests/e2e/ -v

# Contract verification
curl -s http://localhost:8000/openapi.json | jq '.paths | keys'
```

---

## API Contracts (from Design Doc)

> **CRITICAL**: Copy endpoints from design doc's "API Contracts" section.
> These are CANONICAL — implementation and tests MUST match exactly.

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

## Progress

### Overall Progress: **0%**

```
[░░░░░░░░░░░░░░░░░░░░] 0% complete
```

| Metric | Value |
|--------|-------|
| **Total Tasks** | [N] |
| **Completed** | 0 |
| **In Progress** | 0 |
| **Blocked** | 0 |

### Milestone Tracking

| Milestone | Target Date | Status | Notes |
|-----------|-------------|--------|-------|
| All task tickets created | [date] | ⏳ | |
| Core implementation complete | [date] | ⏳ | |
| **Contract verification passed** | [date] | ⏳ | Endpoints match spec |
| **File locations verified** | [date] | ⏳ | E2E tests at root |
| Unit tests passing | [date] | ⏳ | |
| E2E tests passing | [date] | ⏳ | |
| Ready for integration | [date] | ⏳ | |

### Verification Checkpoints (BLOCKING)

> These must pass before marking workstream complete.

| Check | Command | Status |
|-------|---------|--------|
| Endpoints match spec | `grep -r "@router" \| grep "/api/v1"` | ❌ |
| Tests use correct endpoints | `grep -r '"/api/v1' tests/` | ❌ |
| Async fixtures correct | `grep "@pytest.fixture" tests/ -r` (should be empty for async) | ❌ |
| E2E tests at root | `ls tests/e2e/` | ❌ |
| Demos at root | `ls demos/` | ❌ |

---

## History

| Date | Event |
|------|-------|
| [date] | Workstream created from breakdown |
| [date] | [Event/decision/milestone] |

---

## Cross-References

- **Design Doc:** [docs/design/[feature-name].md](../../design/[feature-name].md)
- **Spec:** [docs/spec/[feature-name]-spec.md](../../spec/[feature-name]-spec.md)
- **Breakdown:** [BREAKDOWN.md](./BREAKDOWN.md)
- **Codebase Analysis:** [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md)
- **Status:** [STATUS.md](./STATUS.md)
- **Batch Execution Plan:** [BATCH_EXECUTION_PLAN.md](./BATCH_EXECUTION_PLAN.md)
- **Merge Points:** [MERGE_POINTS.md](./MERGE_POINTS.md)
