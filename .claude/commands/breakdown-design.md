# Breakdown Design Document into Workstreams and Tasks

Analyze the provided design document and create a complete task breakdown.

## Instructions

1. **Read the design document** provided by the user (or use the file path given)

2. **Identify architectural boundaries:**
   - Services/modules involved
   - External dependencies (APIs, databases, third-party services)
   - Shared state or resources between components

3. **Create workstreams** following these rules:
   - Group related tasks that share dependencies
   - Identify which workstreams can run in PARALLEL
   - Identify which workstreams are SEQUENTIAL (blocked by others)
   - Name workstreams clearly (e.g., "WS-A: Token Service", "WS-B: Gateway Integration")

4. **Break down each workstream into tasks:**
   - Each task should be completable in 1-3 hours
   - Use task IDs: WS-A1, WS-A2, WS-B1, etc.
   - Specify dependencies between tasks
   - Include acceptance criteria for each task
   - List files to create/modify

5. **Create the dependency graph** using ASCII visualization

6. **Identify the critical path** (longest sequential chain)

7. **Output format:**

```markdown
## Workstream Breakdown for: [Design Name]

### Summary
- Total Workstreams: X
- Total Tasks: Y
- Total Batches: Z
- Critical Path: [list of task IDs]
- Merge Points: [number]
- Estimated Total Effort: [S/M/L tasks breakdown]

### Parallelization Decision

**Recommended Setup:** [X] worktrees based on service boundaries

| Worktree | Service | Workstreams | Branch Pattern |
|----------|---------|-------------|----------------|
| `[feature]-control` | deeptrail-control | A, C (partial), E (partial) | `feature/[feature]-control` |
| `[feature]-gateway` | deeptrail-gateway | B, D, E (partial) | `feature/[feature]-gateway` |

**Rationale:**
- WS-A and WS-B are independent until MP1 (Merge Point 1)
- deeptrail-control and deeptrail-gateway directories have no cross-dependencies
- Enables [X] parallel Claude instances

**Tradeoff:**
| Option | Decision | Why |
|--------|----------|-----|
| Git Worktrees | ✅ Chosen | Disk efficient, shared config |
| Multiple Clones | ❌ | Overkill, sync overhead |
| Single Worktree | ❌ | Misses parallelization |

**Setup Commands:**
```bash
# From main repo
git worktree add ../[feature]-control -b feature/[feature]-control dev
git worktree add ../[feature]-gateway -b feature/[feature]-gateway dev
```

### Workstream A: [Name] (PARALLEL with B, C)

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-A1 | ... | None | S | `path/to/file.py` (create) | ... |
| WS-A2 | ... | WS-A1 | M | `path/to/other.py` (modify) | ... |

### Workstream B: [Name] (PARALLEL with A)
...

### Workstream C: [Name] (BLOCKED BY A, B)
...

### Batch Execution Model

| Batch | Tasks (Parallel) | Depends On | Blocking For |
|-------|------------------|------------|--------------|
| 1 | A1, B1 | None | Batch 2 |
| 2 | A2, A3, B2 | Batch 1 | Batch 3 |
| 3 | C1, C2 | Batch 2 | Batch 4 |

### Merge Points

| Point | Converging Tasks | Enables | Git Action |
|-------|------------------|---------|------------|
| MP1 | A3 + B2 | C1 | Merge ws-a, ws-b |
| MP2 | C3 + D2 | E1 | Merge ws-c, ws-d |

### Critical Path Analysis

```
Primary:   A1 → A2 → A3 → C1 → C3 → E1 → F1
Secondary: B1 → B2 → D1 → D3 → F1 (if dual-track)
```

[Explanation of the critical path and parallelization opportunities]

### Acceptance Mapping

#### Demo/Milestone → Task Matrix
| Demo | Description | Validating Tasks |
|------|-------------|------------------|
| Demo 1 | [from design doc] | A1, B3, D1 |
| Demo 2 | [from design doc] | C2, C4 |

#### User Journey → Task Matrix (if applicable)
| Step | Action | Implementing Tasks |
|------|--------|-------------------|
| 1 | [from design doc] | A1 |
| 2 | [from design doc] | A3, B3 |

### API Contract Summary

> **CRITICAL**: Extract ALL endpoints from design doc. These are CANONICAL.

| Service | Method | Endpoint | Implementing Task | Test Task |
|---------|--------|----------|-------------------|-----------|
| Control | POST | `/api/v1/exact/path` | A1 | F1 |
| Gateway | POST | `/api/v1/other/path` | B1 | F1 |

### File Organization Plan

| Type | Location | Files | Notes |
|------|----------|-------|-------|
| MVP E2E Tests | `tests/e2e/` (ROOT) | `test_[persona]_journey.py` | Cross-service |
| MVP Demos | `demos/` (ROOT) | `demo_[NN]_*.py` | Cross-service |
| Demo Tests | `tests/demos/` (ROOT) | `test_demo_[NN].py` | Cross-service |
| Control Models | `deeptrail-control/app/models/` | `*.py` | FastAPI `app/` prefix |
| Control Services | `deeptrail-control/app/services/` | `*_service.py` | Use `_service` suffix |
| Control API | `deeptrail-control/app/api/v1/endpoints/` | `*.py` | Versioned API (v1/) |
| Gateway MCP | `deeptrail-gateway/app/mcp/` | `*.py` | FastAPI `app/` prefix |
| Gateway Security | `deeptrail-gateway/app/security/` | `*.py` | Separate security concerns |
| Gateway Middleware | `deeptrail-gateway/app/middleware/` | `*.py` | Request handling only |
| Gateway Backends | `deeptrail-gateway/app/backends/` | `*_client.py` | MCP backend clients |

### File Naming Conventions

| Pattern | Convention | Example | Notes |
|---------|------------|---------|-------|
| Services | `*_service.py` suffix | `[domain]_service.py` | Consistent naming |
| Combined endpoints | Group related operations | `[domain]_auth.py` (related ops in one file) | Reduces file count |
| Validation modules | Use descriptive names | `[x]_validation.py` not `[x]_auth.py` | Clearer purpose |
| Constraint modules | Use active verb form | `[x]_checker.py` not `[x]s.py` | Describes action |
| Backend clients | `*_client.py` suffix | `[provider]_client.py` | Consistent naming |

### Architecture Conventions (DeepSecure Project)

| Convention | Pattern | Rationale |
|------------|---------|-----------|
| FastAPI `app/` prefix | `[service]/app/[module]/` | Framework standard, consistent imports |
| Versioned API | `app/api/v1/endpoints/` | API evolution, breaking change isolation |
| Security separation | Separate `app/security/` directory | First-class security concerns |
| Endpoint consolidation | Related endpoints in single file | Group by domain (e.g., auth, audit) |
| Service suffix | `*_service.py` for all services | Explicit, searchable, consistent |

**Directory Structure Template:**
```
[service-name]/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/     ← Flat structure, grouped by domain
│   ├── models/                ← SQLAlchemy/Pydantic models
│   ├── services/              ← Business logic (*_service.py)
│   ├── middleware/            ← Request/response handling
│   ├── security/              ← Security-specific (fail-closed, constraints)
│   └── [domain]/              ← Domain-specific modules (e.g., mcp/)
├── tests/
│   ├── unit/
│   └── integration/
└── migrations/
```

### Technical Requirements Checklist

| Requirement | Pattern | Applies To |
|-------------|---------|------------|
| Async fixtures | `@pytest_asyncio.fixture` | All E2E tests |
| HTTP client | `httpx.AsyncClient` | All async tests |
| Fixture scope | `scope="function"` for HTTP clients | Avoid connection issues |

### Dependency Graph
[ASCII diagram]
```

8. **Save the breakdown output** to a reference file:
   - Ask the user: "Would you like to save this breakdown to a file for reference?"
   - If yes, save to: `docs/[feature-name]-breakdown.md`
   - Use naming convention: `[design-doc-name]-breakdown.md`
   - Example: `deepsecure-virtual-mcp-server-mvp.md` → `deepsecure-virtual-mcp-server-mvp-breakdown.md`

9. **Update status files:**
   
   a. **Update `docs/EXECUTION_STATUS.md`** (global portfolio):
      - Add design to "Active Designs" if not already present
      - Set phase to "Phase 2: Planning"
      - Link to `docs/workstreams/[design-name]/STATUS.md` for detailed tracking

10. **Automatically run follow-up commands:**
   
   After saving the breakdown, immediately execute these commands in sequence:
   
   a. **Create workstream structure:**
      ```
      /create-workstream [feature-name]
      ```
      This creates `docs/workstreams/[feature-name]/` with WORKSTREAM.md, STATUS.md, tasks/, reports/
   
   b. **Create batch execution plan:**
      ```
      /create-batch-execution-plan [feature-name]
      ```
      This creates `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md` with:
      - Wave analysis for each batch
      - Visual dependency graphs
      - Copy-paste ready commands
      - Parallelism calculations

11. **Ask about task specifications:**

   For each batch, determine if specifications are needed:
   
   | Task Type | Needs Spec? | Action |
   |-----------|-------------|--------|
   | API endpoint | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | Data model | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | Service/handler | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | UI component | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | Demo script | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | Documentation/README only | ❌ No | Skip to `/create-task-ticket` |
   
   **Rule:** If the task involves writing Python code, it needs a spec.
   
   To create specs:
   ```
   /plan  # Switch to Plan mode
   /create-task-spec [batch-number] [feature-name]
   ```

12. **Ask the user** if they want to:
   - Create task specifications: `/create-task-spec [batch] [feature-name]` (if API/model tasks)
   - Generate individual task tickets: `/create-task-ticket [WS-ID] [feature-name]`
   - Proceed with any modifications to the breakdown
   - Start execution with `/execute-task`

## Reference Files
- Design template: `docs/design/DESIGN_TEMPLATE.md`
- Task breakdown framework: `docs/TASK_BREAKDOWN.md`
- Workflow guide: `docs/WORKFLOW_GUIDE.md` (batch model, merge points, acceptance mapping)
- Workstream template: `docs/workstreams/WORKSTREAM_TEMPLATE.md`
- Project rules: `.cursorrules`

## Real-World Example
- Design: `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md`
- Breakdown: `docs/deepsecure-virtual-mcp-server-mvp-breakdown.md`

## DeepSecure-Specific Patterns

When breaking down DeepSecure features, consider these common patterns:

**SDK Feature:**
```
WS-A: Core (_core/) → WS-B: Public API → WS-C: CLI → WS-D: Tests → WS-E: Examples
```

**Backend Change:**
```
WS-A: Schema/Migrations → WS-B: Control Plane → WS-C: Gateway → WS-D: SDK → WS-E: E2E Tests
```

**Cross-Service:**
```
WS-A: Contracts → WS-B: Control (parallel) → WS-C: Gateway (parallel) → WS-D: Integration
```

### File Path Mapping (Design Doc → Implementation)

When design docs propose paths, translate to actual project conventions:

| Design Doc Pattern | Actual Implementation Pattern | Notes |
|--------------------|------------------------------|-------|
| `[service]/models/` | `[service]/app/models/` | Add `app/` prefix |
| `[service]/services/` | `[service]/app/services/` | Add `app/` prefix |
| `[service]/api/[domain]/` | `[service]/app/api/v1/endpoints/` | Versioned, flat structure |
| `[service]/gateway/` | `[service]/app/` | Use `app/` not domain name |
| `middleware/[security].py` | `security/[security].py` | Separate security concerns |
| `examples/` (for MVP demos) | `demos/` | `examples/` = SDK only |

**Service directories in this project:**
- `deeptrail-control/` - Control Plane service
- `deeptrail-gateway/` - Gateway service

### Endpoint Consolidation Patterns

When design docs specify separate files, consider consolidating related operations:

| Design Doc Pattern | Consolidated Pattern | Rationale |
|--------------------|---------------------|-----------|
| `api/[domain]/[action1].py` + `api/[domain]/[action2].py` | `api/v1/endpoints/[domain].py` | Group related operations |
| `api/[domain]/[action].py` | `api/v1/endpoints/[domain].py` | Simplified, versioned |
| `services/[name].py` | `services/[name]_service.py` | Consistent `_service` suffix |

**Examples of consolidation:**
- Auth operations (challenge, verify, refresh) → single `[domain]_auth.py`
- CRUD operations on same resource → single `[resource].py`
- Related query endpoints → single `[domain].py`

### Pre-Breakdown Checklist

Before finalizing task breakdown, verify all file paths follow conventions:

- [ ] All service files use `*_service.py` suffix
- [ ] API endpoints use versioned path (`/api/v1/...`)
- [ ] Security modules in separate `security/` directory
- [ ] Middleware only contains request/response handling
- [ ] Related endpoints consolidated into single files
- [ ] File paths include `app/` prefix for FastAPI services
- [ ] E2E tests at `tests/e2e/` (ROOT) for cross-service tests
- [ ] Demos at `demos/` (ROOT), not `examples/` (SDK-only)
