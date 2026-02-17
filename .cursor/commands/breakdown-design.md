# Breakdown Design Document into Workstreams and Tasks

Analyze the provided design document and create a complete task breakdown.

## ⚠️ CRITICAL: Explore Codebase BEFORE Breakdown

**Lesson Learned (Feb 2026):** A breakdown was created based on design documents claiming endpoints were "missing." After codebase exploration, ~60% of components already existed. Design documents describe **intent**, not **current state**. The codebase is the source of truth.

### Pre-Breakdown Exploration (MANDATORY)

Before proceeding with breakdown, you MUST:

1. **Explore the codebase** using Task tool with `subagent_type="explore"`:
   - Explore `deeptrail-control/` for existing endpoints, services, models
   - Explore `deeptrail-gateway/` for existing handlers, middleware, backends

2. **Cross-reference design doc "missing" items with actual codebase:**
   - Design says "Create X endpoint" → Grep codebase to verify it doesn't exist
   - Design says "Not Implemented" → Check if basic implementation exists but needs enhancement

3. **Classify each item by codebase state:**
   | Codebase State | Task Type | Example |
   |----------------|-----------|---------|
   | Component doesn't exist | `Create` | "Create OAuth service" |
   | Component exists, format wrong | `Modify` | "Update delegation response format" |
   | Component exists, needs verification | `Verify` | "Verify login endpoint matches E2E" |
   | Component exists, fully correct | `Skip` | Remove from task list |

4. **Save exploration results** to `docs/workstreams/[feature]/CODEBASE_ANALYSIS.md`

If you skip this step, you risk creating over-scoped tasks.

---

## 📁 Actual Directory Structure Reference (CANONICAL)

**IMPORTANT:** Use these EXACT paths when generating commands. Do NOT guess paths.

### Repository Root (`/Users/imaxxs/repositories/deepsecure-mvp/`)

```
deepsecure-mvp/
├── demos/                          # Cross-service demos (NOT examples/)
│   ├── demo_01_*.py
│   ├── demo_sarah_journey_e2e.py
│   └── interactive/
├── tests/                          # Root-level SDK/integration tests
│   ├── _core/
│   ├── commands/
│   ├── demos/                      # Demo validation tests
│   ├── e2e/                        # End-to-end tests
│   └── sdk/
├── deepsecure/                     # Python SDK
├── deeptrail-control/              # Control Plane service
├── deeptrail-gateway/              # Gateway service
├── docs/
│   └── workstreams/
│       └── [feature]/
│           ├── WORKSTREAM.md
│           ├── STATUS.md
│           ├── BATCH_EXECUTION_PLAN.md
│           ├── MERGE_POINTS.md
│           ├── CODEBASE_ANALYSIS.md
│           ├── tasks/
│           └── reports/
└── examples/                       # SDK examples ONLY (not demos)
```

### Control Plane (`deeptrail-control/`)

```
deeptrail-control/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/          # API endpoints (*.py)
│   ├── core/                       # Config, settings
│   ├── crud/                       # Database operations
│   ├── db/                         # Database setup
│   ├── models/                     # SQLAlchemy models
│   ├── schemas/                    # Pydantic schemas
│   ├── services/                   # Business logic (*_service.py)
│   └── tests/                      # App-level tests (rarely used)
│       └── services/
├── tests/                          # ⚠️ ACTUAL test location (NOT tests/unit/)
│   ├── api/
│   │   └── v1/
│   ├── crud/
│   ├── models/
│   ├── schemas/                    # ✅ tests/schemas/ (NOT tests/unit/schemas/)
│   ├── services/                   # ✅ tests/services/ (NOT tests/unit/services/)
│   └── utils/
└── alembic/
    └── versions/
```

### Gateway (`deeptrail-gateway/`)

```
deeptrail-gateway/
├── app/
│   ├── backends/                   # Backend API clients (*_client.py)
│   ├── core/                       # Config, settings
│   ├── mcp/                        # MCP protocol handlers
│   │   └── handlers/
│   ├── middleware/                 # Request/response middleware
│   └── security/                   # Security modules
├── tests/                          # ⚠️ ACTUAL test location (NOT tests/unit/)
│   ├── backends/                   # ✅ tests/backends/ (NOT tests/unit/backends/)
│   ├── mcp/
│   │   └── handlers/
│   ├── middleware/                 # ✅ tests/middleware/ (NOT tests/unit/middleware/)
│   └── security/                   # ✅ tests/security/ (NOT tests/unit/security/)
└── (no alembic - gateway is stateless)
```

### ⚠️ Common Path Mistakes to AVOID

| ❌ WRONG Path | ✅ CORRECT Path | Service |
|---------------|-----------------|---------|
| `tests/unit/schemas/` | `tests/schemas/` | Control |
| `tests/unit/services/` | `tests/services/` | Control |
| `tests/unit/models/` | `tests/models/` | Control |
| `tests/unit/backends/` | `tests/backends/` | Gateway |
| `tests/unit/middleware/` | `tests/middleware/` | Gateway |
| `tests/unit/security/` | `tests/security/` | Gateway |
| `tests/integration/` | `tests/` (root-level) | Both |
| `examples/` (for demos) | `demos/` | Root |
| `deeptrail-control/services/` | `deeptrail-control/app/services/` | Control |
| `deeptrail-gateway/backends/` | `deeptrail-gateway/app/backends/` | Gateway |

### Absolute Path Templates

When generating validation commands, use these absolute path templates:

```bash
# Main repo
cd /Users/imaxxs/repositories/deepsecure-mvp

# Control Plane
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control

# Gateway
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-gateway

# Worktrees (when created)
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway
```

### Test Command Templates

```bash
# Control Plane tests
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
pytest tests/schemas/ -v           # Schema tests
pytest tests/services/ -v          # Service tests
pytest tests/models/ -v            # Model tests
pytest tests/api/v1/ -v            # API tests

# Gateway tests
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-gateway
pytest tests/backends/ -v          # Backend client tests
pytest tests/middleware/ -v        # Middleware tests
pytest tests/security/ -v          # Security tests
pytest tests/mcp/ -v               # MCP handler tests

# Root-level tests
cd /Users/imaxxs/repositories/deepsecure-mvp
pytest tests/e2e/ -v               # E2E tests
pytest tests/demos/ -v             # Demo validation tests
python demos/demo_sarah_journey_e2e.py  # E2E demo
```

---

## Instructions

1. **Read the design document** provided by the user (or use the file path given)

2. **Verify codebase exploration was completed** (check for CODEBASE_ANALYSIS.md or run exploration now)

3. **Identify architectural boundaries:**
   - Services/modules involved
   - External dependencies (APIs, databases, third-party services)
   - Shared state or resources between components

4. **Create workstreams** following these rules:
   - Group related tasks that share dependencies
   - Identify which workstreams can run in PARALLEL
   - Identify which workstreams are SEQUENTIAL (blocked by others)
   - Name workstreams clearly (e.g., "WS-A: Token Service", "WS-B: Gateway Integration")

5. **Break down each workstream into tasks:**
   - Each task should be completable in 1-3 hours
   - Use task IDs: WS-A1, WS-A2, WS-B1, etc.
   - Specify dependencies between tasks
   - Include acceptance criteria for each task
   - List files to create/modify
   - **Use correct task type** based on codebase state (Create/Modify/Verify)

6. **Create the dependency graph** using ASCII visualization

7. **Identify the critical path** (longest sequential chain)

8. **Output format:**

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
│   ├── core/                  ← Config, settings
│   ├── models/                ← SQLAlchemy/Pydantic models
│   ├── schemas/               ← Pydantic schemas (Control only)
│   ├── services/              ← Business logic (*_service.py)
│   ├── middleware/            ← Request/response handling (Gateway only)
│   ├── security/              ← Security-specific (Gateway only)
│   ├── backends/              ← Backend API clients (Gateway only)
│   └── mcp/                   ← MCP handlers (Gateway only)
├── tests/                     ← ⚠️ NO unit/ subdirectory!
│   ├── api/                   ← API tests (Control)
│   ├── schemas/               ← Schema tests (Control)
│   ├── services/              ← Service tests (Control)
│   ├── models/                ← Model tests (Control)
│   ├── backends/              ← Backend tests (Gateway)
│   ├── middleware/            ← Middleware tests (Gateway)
│   ├── security/              ← Security tests (Gateway)
│   └── mcp/                   ← MCP tests (Gateway)
└── alembic/                   ← Migrations (Control only)
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

9. **Save the breakdown output** to a reference file:
   - Ask the user: "Would you like to save this breakdown to a file for reference?"
   - If yes, save to: `docs/[feature-name]-breakdown.md`
   - Use naming convention: `[design-doc-name]-breakdown.md`
   - Example: `deepsecure-virtual-mcp-server-mvp.md` → `deepsecure-virtual-mcp-server-mvp-breakdown.md`

10. **Update status files:**
   
   a. **Update `docs/EXECUTION_STATUS.md`** (global portfolio):
      - Add design to "Active Designs" if not already present
      - Set phase to "Phase 2: Planning"
      - Link to `docs/workstreams/[design-name]/STATUS.md` for detailed tracking

11. **Automatically run follow-up commands:**
   
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

12. **Ask about task specifications:**

   For each batch, determine if specifications are needed:
   
   | Task Type | Needs Spec? | Action |
   |-----------|-------------|--------|
   | API endpoint | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | Data model | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | Service/handler | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | UI component | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | Demo script | ✅ Yes | Run `/create-task-spec [batch] [feature]` in Plan mode |
   | Documentation/README only | ❌ No | Skip to `/create-task-ticket` |
   | **Verification task** | ❌ No | Skip spec, minimal ticket needed |
   
   **Rule:** If the task involves writing Python code, it needs a spec. Verification tasks typically don't need specs.
   
   To create specs:
   ```
   /plan  # Switch to Plan mode
   /create-task-spec [batch-number] [feature-name]
   ```

13. **Ask the user** if they want to:
   - Create task specifications: `/create-task-spec [batch] [feature-name]` (if API/model tasks)
   - Generate individual task tickets: `/create-task-ticket [WS-ID] [feature-name]`
   - Proceed with any modifications to the breakdown
   - Start execution with `/execute-task`

---

## ⚠️ Post-Breakdown Verification Checklist (MANDATORY)

**DO NOT declare breakdown complete until ALL of the following files exist.**

### Required Files Checklist

Run this verification BEFORE telling the user the breakdown is complete:

```bash
# Verify all required files exist
FEATURE="[feature-name]"

echo "=== Breakdown Completion Verification ==="
echo ""

# 1. Breakdown document
[ -f "docs/${FEATURE}-breakdown.md" ] && echo "✅ docs/${FEATURE}-breakdown.md" || echo "❌ MISSING: docs/${FEATURE}-breakdown.md"

# 2. Workstream folder structure
[ -d "docs/workstreams/${FEATURE}" ] && echo "✅ docs/workstreams/${FEATURE}/" || echo "❌ MISSING: docs/workstreams/${FEATURE}/"
[ -f "docs/workstreams/${FEATURE}/WORKSTREAM.md" ] && echo "✅ WORKSTREAM.md" || echo "❌ MISSING: WORKSTREAM.md"
[ -f "docs/workstreams/${FEATURE}/STATUS.md" ] && echo "✅ STATUS.md" || echo "❌ MISSING: STATUS.md"
[ -f "docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md" ] && echo "✅ BATCH_EXECUTION_PLAN.md" || echo "❌ MISSING: BATCH_EXECUTION_PLAN.md"
[ -f "docs/workstreams/${FEATURE}/MERGE_POINTS.md" ] && echo "✅ MERGE_POINTS.md" || echo "❌ MISSING: MERGE_POINTS.md"
[ -f "docs/workstreams/${FEATURE}/CODEBASE_ANALYSIS.md" ] && echo "✅ CODEBASE_ANALYSIS.md" || echo "❌ MISSING: CODEBASE_ANALYSIS.md"

# 3. Subdirectories
[ -d "docs/workstreams/${FEATURE}/tasks" ] && echo "✅ tasks/" || echo "❌ MISSING: tasks/"
[ -d "docs/workstreams/${FEATURE}/reports" ] && echo "✅ reports/" || echo "❌ MISSING: reports/"

echo ""
echo "=== Verification Complete ==="
```

### Required Files Table

| # | File | Purpose | Created By |
|---|------|---------|------------|
| 1 | `docs/[feature]-breakdown.md` | Task breakdown document | Step 9 |
| 2 | `docs/workstreams/[feature]/WORKSTREAM.md` | Workstream overview | `/create-workstream` |
| 3 | `docs/workstreams/[feature]/STATUS.md` | Progress tracking | `/create-workstream` |
| 4 | `docs/workstreams/[feature]/BATCH_EXECUTION_PLAN.md` | Execution waves | `/create-batch-execution-plan` |
| 5 | `docs/workstreams/[feature]/MERGE_POINTS.md` | Merge point definitions | `/create-workstream` |
| 6 | `docs/workstreams/[feature]/CODEBASE_ANALYSIS.md` | Existing code inventory | Pre-breakdown exploration |
| 7 | `docs/workstreams/[feature]/tasks/` | Task ticket folder | `/create-workstream` |
| 8 | `docs/workstreams/[feature]/reports/` | Completion reports folder | `/create-workstream` |

### Verification Steps

14. **Verify all files created:**
   
   Before declaring breakdown complete, use the Glob tool to verify:
   
   ```
   Glob: docs/workstreams/[feature]/*.md
   ```
   
   **Expected results (minimum 5 files):**
   - WORKSTREAM.md
   - STATUS.md
   - BATCH_EXECUTION_PLAN.md
   - MERGE_POINTS.md
   - CODEBASE_ANALYSIS.md

15. **If any files are missing, create them NOW:**
   
   | Missing File | Action |
   |--------------|--------|
   | `WORKSTREAM.md` | Run `/create-workstream` again |
   | `STATUS.md` | Create from template |
   | `BATCH_EXECUTION_PLAN.md` | Run `/create-batch-execution-plan` |
   | `MERGE_POINTS.md` | Create from template (see `docs/workstreams/MERGE_POINT_GUIDE.md`) |
   | `CODEBASE_ANALYSIS.md` | Run `/explore-codebase` |

16. **Final confirmation to user:**
   
   Only after ALL files are verified, output:
   
   ```markdown
   ## ✅ Breakdown Complete
   
   **Workstream:** [feature-name]
   
   ### Files Created
   
   | File | Status |
   |------|--------|
   | `docs/[feature]-breakdown.md` | ✅ |
   | `docs/workstreams/[feature]/WORKSTREAM.md` | ✅ |
   | `docs/workstreams/[feature]/STATUS.md` | ✅ |
   | `docs/workstreams/[feature]/BATCH_EXECUTION_PLAN.md` | ✅ |
   | `docs/workstreams/[feature]/MERGE_POINTS.md` | ✅ |
   | `docs/workstreams/[feature]/CODEBASE_ANALYSIS.md` | ✅ |
   | `docs/workstreams/[feature]/tasks/` | ✅ |
   | `docs/workstreams/[feature]/reports/` | ✅ |
   
   ### Next Steps
   
   1. Review the breakdown document
   2. Create task specs: `/create-task-spec [batch] [feature]`
   3. Create task tickets: `/create-task-ticket [WS-ID] [feature]`
   4. Start execution: `/execute-task [WS-ID] [feature]`
   ```

---

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

- [ ] **⚠️ Codebase exploration completed** (CODEBASE_ANALYSIS.md created)
- [ ] **⚠️ Design doc "missing" items verified** against actual codebase
- [ ] **⚠️ Tasks classified correctly** (Create vs Modify vs Verify)
- [ ] All service files use `*_service.py` suffix
- [ ] API endpoints use versioned path (`/api/v1/...`)
- [ ] Security modules in separate `security/` directory
- [ ] Middleware only contains request/response handling
- [ ] Related endpoints consolidated into single files
- [ ] File paths include `app/` prefix for FastAPI services
- [ ] E2E tests at `tests/e2e/` (ROOT) for cross-service tests
- [ ] Demos at `demos/` (ROOT), not `examples/` (SDK-only)

### Task Classification Guide

| Task Type | When to Use | Task Description Pattern | Complexity Adjustment |
|-----------|-------------|-------------------------|----------------------|
| `Create` | Component doesn't exist in codebase | "Create X service/endpoint/model" | Full complexity |
| `Modify` | Component exists but needs changes | "Update X to include Y" | Reduced complexity |
| `Verify` | Component exists, needs validation | "Verify X matches E2E expectations" | Minimal (S) |
| `Wire` | Component exists, needs connection | "Wire X endpoint to router" | Minimal (S) |

**Example reclassification:**

| Original Task (Over-scoped) | After Exploration | Revised Task |
|-----------------------------|-------------------|--------------|
| "Create user login endpoint" | Endpoint EXISTS at /api/v1/auth/login | "Verify login response format matches E2E" |
| "Create UserAuthService" | Service EXISTS | "Verify UserAuthService handles all cases" |
| "Create delegation token model" | Model EXISTS with macaroons | "Verify delegation response includes required fields" |
