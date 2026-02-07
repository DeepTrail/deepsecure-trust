# Task: [WS-ID] [Task Name]

> Copy this template to create a new task ticket.
> Save as: `docs/workstreams/[feature-name]/tasks/[WS-ID]-[task-name].md`

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `draft` / `ready` / `in_progress` / `review` / `completed` / `blocked` |
| **Design Doc** | [link to design doc] |
| **Workstream** | [Workstream name] |
| **Code Dependencies** | [Task IDs whose code/API must be complete, or "None"] |
| **Runtime Dependencies** | [Services that must be deployed for integration, or "None"] |
| **Blocked By** | [External blockers if any] |
| **Assigned** | [Agent/Person] |
| **Created** | [Date] |
| **Estimated Complexity** | `S` (< 1hr) / `M` (1-3hr) / `L` (3+ hr) |
| **Batch** | [Batch number] |
| **Target Worktree** | [vmcp-control / vmcp-gateway / both] |

---

## Dependencies

### Code Dependencies (must complete before starting)

Code dependencies are tasks whose **implementation** must be complete before this task can begin.
You need their API contracts, interfaces, or code to build against.

| Task | What We Need | Status |
|------|--------------|--------|
| [WS-XX] | [API contract / interface / model] | ⬜ / ✅ |

### Runtime Dependencies (must be deployed for integration testing)

Runtime dependencies are **services** that must be running for full integration testing.
Development can proceed without them using mocks or local fallbacks.

| Service | Endpoint | Required For |
|---------|----------|--------------|
| [Service Name] | [URL/endpoint] | [What functionality] |

### Development Mode

When runtime dependencies are unavailable:

- [ ] **Fallback behavior**: [How does this task work without the runtime dependency?]
- [ ] **Local testing**: [Can unit tests pass without the service?]
- [ ] **Integration testing**: [Deferred to merge point / container deployment]

> **Note:** A task can be "code complete" while its runtime dependencies are still unavailable.
> Full integration is validated at merge points when all services are deployed together.

---

## Pre-Conditions

Before starting this task, ensure:

- [ ] All **code dependency** tasks are completed: [list task IDs with ✅]
- [ ] API contracts/interfaces from dependencies are available
- [ ] [Any other prerequisites]

**For integration testing (optional at development time):**
- [ ] Runtime dependency services are deployed: [list services]
- [ ] Environment configured: [list env vars]

---

## Task Description

[Detailed description of what needs to be done. Include:]
- What problem this solves
- The approach to take
- Any constraints or considerations

### Context

[Link to relevant design sections, existing code, or documentation]

### Technical Notes

[Any implementation hints, gotchas, or technical context]

---

## Specification (IMMUTABLE AFTER DESIGN APPROVAL)

> **CRITICAL**: This section defines what implementation MUST match exactly.
> Copy from design doc's API Contracts section. Do not modify without updating design doc first.

### API Contract (if applicable)

| Field | Value |
|-------|-------|
| **Method** | `POST` / `GET` / `PUT` / `DELETE` |
| **Path** | `/api/v1/exact/path/from/design` |
| **Auth** | Bearer token / JWT / None |

**Request:**
```json
{
  "field": "type - description"
}
```

**Response (Success):**
```json
{
  "id": "string",
  "status": "string"
}
```

### Test Endpoint Mapping

| Test Case | Method | Endpoint | Expected Status |
|-----------|--------|----------|-----------------|
| Happy path | POST | `/api/v1/exact/path` | 200 |
| Invalid input | POST | `/api/v1/exact/path` | 400 |

### Technical Requirements

| Requirement | Pattern | Notes |
|-------------|---------|-------|
| Async fixtures | `@pytest_asyncio.fixture` | Required for async generators |
| HTTP client | `httpx.AsyncClient` | Project standard |
| Error handling | `raise HTTPException(status_code=X)` | FastAPI pattern |

### File Location Rules

| Artifact | Correct Location | Why |
|----------|------------------|-----|
| Implementation | `[service]/[module]/` | Service-specific |
| Unit tests | `[service]/tests/[module]/` | Co-located with impl |
| E2E tests (if cross-service) | `tests/e2e/` (ROOT) | Spans services |

---

## Acceptance Criteria

### Functional Criteria
- [ ] [Specific, measurable criterion 1]
- [ ] [Specific, measurable criterion 2]
- [ ] [Specific, measurable criterion 3]

### Contract Verification (REQUIRED)
- [ ] Endpoint path matches spec exactly: `[path from spec]`
- [ ] Request schema matches spec
- [ ] Response schema matches spec
- [ ] Error responses match spec (status codes, body format)
- [ ] Tests use correct endpoints from spec

### Technical Criteria
- [ ] Unit tests added and passing
- [ ] Integration tests added (if applicable)
- [ ] Async fixtures use `@pytest_asyncio.fixture` (not `@pytest.fixture`)
- [ ] No new linting errors introduced
- [ ] Type hints added for all public functions
- [ ] Documentation updated (if applicable)

### File Location Verification
- [ ] Implementation in correct service directory
- [ ] Tests in correct location (root `tests/e2e/` if cross-service)
- [ ] No cross-service code in single-service directory

---

## Files to Modify/Create

### Files to Create
- `path/to/new_file.py` - [purpose]

### Files to Modify
- `path/to/existing_file.py` - [what changes]

### Tests to Add
- `tests/path/to/test_file.py` - [what to test]

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest path/to/tests`
- [ ] Linting passes: `make lint`
- [ ] Type checking passes: `mypy deepsecure/`
- [ ] API contract documented (if this task exposes endpoints)
- [ ] **Contract verified**: Endpoints match design doc exactly
- [ ] **Test contracts verified**: Test file uses correct endpoints
- [ ] Completion report created

### Contract Verification Command

```bash
# Verify implemented endpoints match spec
grep -r "router\.\(get\|post\|put\|delete\)" [implementation_file] | grep -o '"/api/v1[^"]*"'

# Compare with spec endpoints
# Expected: /api/v1/exact/path (from design doc)
```

### Integration Complete (validated at merge point)

- [ ] Integration tests pass with deployed services
- [ ] Container deployment tested (see MERGE_POINTS.md)
- [ ] Cross-service communication verified

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| [WS-XX] | Code dependency satisfied | Can start implementation |
| [WS-YY] | Runtime dependency satisfied | Integration testing enabled |

---

## References

- Design Doc: [link]
- Related Issues: [links]
- Related Code: [links to relevant existing code]
- External Docs: [links to API docs, specs, etc.]

---

## Notes

[Any additional context, open questions, or things to watch out for]

---

## Execution Log

<!-- Updated during task execution -->

### Progress Updates

| Date | Update |
|------|--------|
| [date] | Started task |
| [date] | [Progress note] |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| [date] | [description] | [how resolved] |

---

## Template Guidance

### Understanding Dependency Types

This template distinguishes between two types of dependencies:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEPENDENCY TYPES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CODE DEPENDENCY (blocks task start):                                       │
│  ┌──────────┐      ┌──────────┐                                             │
│  │  Task A  │ ───> │  Task B  │  "B needs A's API/interface to build"       │
│  │  (code)  │      │  (code)  │                                             │
│  └──────────┘      └──────────┘                                             │
│  Example: E3 needs E2's API contract to know how to send audit events       │
│                                                                              │
│  RUNTIME DEPENDENCY (blocks integration testing):                           │
│  ┌──────────┐      ┌──────────┐                                             │
│  │ Service A│ ───> │ Service B│  "B needs A running for full testing"       │
│  │(deployed)│      │(deployed)│                                             │
│  └──────────┘      └──────────┘                                             │
│  Example: E3 needs Control Plane deployed to POST audit events              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Task States

| State | Code Deps | Runtime Deps | Meaning |
|-------|-----------|--------------|---------|
| `blocked` | ❌ Not met | - | Cannot start - waiting for code |
| `ready` | ✅ Met | - | Can start development |
| `in_progress` | ✅ Met | ❌ Not deployed | Developing with mocks/local mode |
| `code_complete` | ✅ Met | ❌ Not deployed | Code done, integration pending |
| `completed` | ✅ Met | ✅ Deployed + tested | Fully validated at merge point |

### Development vs Integration

**During Development (in worktree):**
- Only code dependencies block you
- Use mocks, local fallbacks, or "development mode"
- Unit tests should pass without runtime dependencies

**At Merge Point (container deployment):**
- All services deployed together
- Runtime dependencies now available
- Integration tests validate cross-service behavior

### When to Mark a Task Complete

A task can be marked "complete" when:
1. ✅ Code is written and committed
2. ✅ Unit tests pass
3. ✅ API contract is documented (if applicable)
4. ✅ Completion report is created

Integration testing happens at merge points - don't wait for that to mark code complete.

### Cross-Worktree Awareness

Tasks in different worktrees don't automatically know about each other's status.
After completing a task, run `/sync-worktree-status` to propagate completion status.
