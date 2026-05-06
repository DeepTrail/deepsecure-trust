# Breakdown Design: Analyze Design Doc into Workstreams, Tasks, and Batches

Analyze a design document, cross-reference against actual codebase state, and create a complete task breakdown with workstreams, dependency graphs, merge points, and batch execution model.

## Workflow Position

```
/spec → /create-design-doc → /breakdown-design → /create-workstream → /create-batch-execution-plan → ...
                                    ↑
                               (YOU ARE HERE)

This command internally runs codebase exploration as its FIRST step.
/explore-codebase is NOT a separate pipeline stage — it is embedded here.
```

## When to Use

- After a design doc exists at `docs/design/[feature-name].md` (output of `/create-design-doc`)
- When a formal spec exists at `docs/spec/[feature-name]-spec.md` (can also be used as input)
- When the feature requires multi-task implementation across services
- When parallel execution planning is needed

**When NOT to use:**
- No design doc exists — run `/spec` then `/create-design-doc` first
- Single-task changes that don't need workstream structure
- Quick bug fixes or documentation updates

---

## ⚠️ CRITICAL: Embedded Codebase Exploration (Step 1 of This Command)

**Lesson Learned (Feb 2026):** A breakdown was created based on design documents claiming endpoints were "missing." After codebase exploration, ~60% of components already existed. Design documents describe **intent**, not **current state**. The codebase is the source of truth.

**Note:** Codebase exploration is NOT a separate command you run before this. It is the FIRST thing this command does internally. See `/explore-codebase` for the detailed exploration methodology.

### Pre-Breakdown Exploration (MANDATORY — runs as Step 1 of this command)

Before proceeding with the breakdown output, you MUST:

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
│           ├── BREAKDOWN.md
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

The breakdown document MUST include all sections below. This is a **19-section template** — all sections are required. If the feature is small (single-service, <10 tasks), some sections can be abbreviated but not omitted.

**Quality bar:** The output must match the depth of proven breakdowns:
- `docs/workstreams/idp-enhanced-sso/BREAKDOWN.md` — 19 tasks, Type column, Feature→Task matrix
- `docs/workstreams/virtual-mcp-server-mvp/deepsecure-virtual-mcp-server-mvp-breakdown.md` — 44 tasks, File Checklist tree, dual-track critical path
- `docs/workstreams/mvp-production-readiness/mvp-production-readiness-breakdown.md` — 32 tasks, Phase grouping (P0/P1/P2)

```markdown
# Workstream Breakdown: [Design Name]

> **Design Doc**: [docs/design/[feature-name].md](../../design/[feature-name].md)
> **Codebase Analysis**: [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md)
> **Created**: [date]

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Workstreams** | [X] |
| **Total Tasks** | [Y] |
| **Total Batches** | [Z] |
| **Critical Path** | [A1 → A2 → ... → FN] (longest chain) |
| **Merge Points** | [N] |
| **Estimated Total Effort** | [Ns] S + [Nm] M + [Nl] L = [Y] tasks |

### Task Complexity Distribution

| Complexity | Count | Tasks |
|-----------|-------|-------|
| S (< 1hr) | [N] | [A1, C1, D1, ...] |
| M (1-3hr) | [N] | [A2, B2, C3, ...] |
| L (3+ hr) | [N] | [B1, D2, ...] |

### Phase Distribution (if multi-phase)

[Include this table when the feature spans multiple priority phases (P0/P1/P2) or delivery phases. Omit for single-phase features.]

| Phase | Priority | Tasks | Focus |
|-------|----------|-------|-------|
| **P0** | Immediate | [N] | [What P0 enables] |
| **P1** | Short-term | [N] | [What P1 enables] |
| **P2** | Medium-term | [N] | [What P2 enables] |

---

## Pre-requisites (if any)

[Include this section when there are manual or non-code tasks required BEFORE Batch 1 (e.g., creating API keys, provisioning infrastructure, external account setup). Omit if no pre-requisites exist.]

| ID | Description | Type | Complexity |
|----|-------------|------|------------|
| PRE-1 | [Manual task description with specific instructions] | Manual | N/A |
| PRE-2 | [Another manual task] | Manual | N/A |

---

## Parallelization Decision

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

**Worktree Lifecycle:** (see `docs/WORKTREE_GUIDE.md` for full guide)

    # Step 1: Clean up old worktrees (from previous features)
    cd /Users/imaxxs/repositories/deepsecure-mvp
    git worktree list
    git worktree remove ../[old-worktree] --force   # if any exist
    git branch -D feature/[old-branch]               # if already merged

    # Step 2: Create fresh worktrees
    git worktree add ../[feature]-control -b feature/[feature]-control dev
    git worktree add ../[feature]-gateway -b feature/[feature]-gateway dev

    # Step 3: Copy .cursor commands (required for /execute-task)
    cp -r .cursor ../[feature]-control/
    cp -r .cursor ../[feature]-gateway/

---

## Phase 0: [Phase Name] (if multi-phase)

[Group workstreams by priority phase when the feature spans P0/P1/P2. For single-phase features, skip the phase headers and list workstreams directly.]

### Workstream A: [Name] ([Service])

**PARALLEL with B, C** | **Service:** `deeptrail-control`
**Batches:** [1, 2, 3] | **Design Steps Covered:** [Steps X-Y from design doc]
**Contributes to Merge Point:** [MP1 or N/A] | **Depends on Merge Point:** [MP2 or N/A]

| Task ID | Type | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|------|-------------|--------------|------------|-------|---------------------|
| WS-A1 | Create | [description] | None | S | `[service]/app/[path]/[file].py` (create) | [specific, testable criteria] |
| WS-A2 | Modify | [description] | WS-A1 | M | `[service]/app/[path]/[file].py` (modify) | [specific, testable criteria] |
| WS-A3 | Verify | [description] | WS-A2 | S | `[service]/app/[path]/[file].py` (verify) | [specific, testable criteria] |

**Critical Path:** A1 → A2 → A3

### Workstream B: [Name] ([Service])

**PARALLEL with A** | **Service:** `deeptrail-gateway`
**Batches:** [1, 2] | **Design Steps Covered:** [Steps X-Y]
**Contributes to Merge Point:** [MP1] | **Depends on Merge Point:** [N/A]

| Task ID | Type | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|------|-------------|--------------|------------|-------|---------------------|
| WS-B1 | Create | ... | None | M | ... | ... |

**Critical Path:** B1 → B2 → B3

---

## Phase 1: [Phase Name] (if multi-phase)

### Workstream C: [Name] (DEPENDS ON A, B)

**BLOCKED BY A, B** | **Services:** Both `deeptrail-control` and `deeptrail-gateway`
**Batches:** [3, 4] | **Design Steps Covered:** [Steps X-Y]
**Contributes to Merge Point:** [MP2] | **Depends on Merge Point:** [MP1]

| Task ID | Type | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|------|-------------|--------------|------------|-------|---------------------|

**Critical Path:** C1 → C2 → C3

[Continue for all workstreams...]

---

## Batch Execution Model

| Batch | Tasks (Parallel) | Depends On | Blocking For | Worktree | Effort |
|-------|------------------|------------|--------------|----------|--------|
| 1 | A1, B1 | None (or PRE-1) | Batch 2 | Control: A1; Gateway: B1 | 1S + 1M |
| 2 | A2, A3, B2 | Batch 1 | Batch 3 | Control: A2, A3; Gateway: B2 | 2M + 1S |
| 3 | C1, C2 | Batch 2, MP1 | Batch 4 | Control: C1; Gateway: C2 | 2M |

---

## Merge Points

| Point | Converging From | Enables | When | Git Action |
|-------|-----------------|---------|------|------------|
| MP1 | A3 + B2 | C1 (auth) | After Batch 2 | Merge feature branches to dev |
| MP2 | C3 + D2 | E1 (integration) | After Batch 4 | Merge all into dev |

---

## Critical Path Analysis

    ┌─────────────────────────────────────────────────────────────────┐
    │                    DUAL-TRACK CRITICAL PATH                     │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  PRIMARY (Control → Auth → Integration):                        │
    │  A1 → A2 → A3 → C1 → C2 → C3 → E1 → F1                       │
    │  │                                      │                       │
    │  └──────── [N] days minimum ────────────┘                       │
    │                                                                 │
    │  SECONDARY (Gateway → Backends):                                │
    │  B1 → B2 → B3 → D1 → D2 → D3                                  │
    │  │                          │                                   │
    │  └──── [N] days ([N] float) ┘                                   │
    │                                                                 │
    │  CONVERGENCE POINTS:                                            │
    │  • MP1 (Day X): Control meets Gateway                           │
    │  • MP2 (Day X): All middleware complete                         │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘

---

## Dependency Graph

[ASCII diagram showing all workstreams, tasks, and merge points with visual flow. See virtual-mcp-server-mvp breakdown for the gold-standard format.]

       WS-A (Control)                      WS-B (Gateway)
       ══════════════                      ══════════════
            A1 ────────┐                        B1 ────────┐
             │         │                         │         │
             ▼         │                         ▼         │
            A2         │                        B2         │
             │         │                         │         │
             ▼         │                         ▼         │
            A3 ────────┼─────────────────────── B3         │
                       │                                   │
                       ▼                                   ▼
                      MP1 ═════════════════════════════════╗
                                                          ║
       WS-C (Auth)                                        ║
       ═══════════                                        ║
            C1 ◄──────────────────────────────────────────╝
             │
             ▼
            C2 → C3

---

## Acceptance Mapping

### Feature → Task Matrix

[Map each design doc feature to its implementing and validating tasks. This provides traceability.]

| Feature | Description | Implementing Tasks | Validating Tasks |
|---------|-------------|-------------------|------------------|
| F1: [Feature Name] | [from design doc] | A1, A2, A3 | A4 |
| F2: [Feature Name] | [from design doc] | B1, B2, B3 | B4 |

### Demo/Milestone → Task Matrix

| Demo | Description | Validating Tasks |
|------|-------------|------------------|
| Demo 1 | [from design doc] | A1, B3, D1 |
| Demo 2 | [from design doc] | C2, C4 |

### User Journey → Task Matrix (if applicable)

| Step | Action | Implementing Tasks |
|------|--------|-------------------|
| 1 | [from design doc] | A1 |
| 2 | [from design doc] | A3, B3 |

---

## API Contract Summary

> **CRITICAL**: Extract ALL endpoints from design doc. These are CANONICAL.

| Service | Method | Endpoint | Implementing Task | Test Task | Status |
|---------|--------|----------|-------------------|-----------|--------|
| Control | POST | `/api/v1/exact/path` | A1 | F1 | **NEW** |
| Control | GET | `/api/v1/other/path` | C1 | F1 | Modify |
| Gateway | POST | `/api/v1/gateway/path` | B1 | F1 | **NEW** |

---

## File Organization Plan

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

### File Checklist (Annotated Tree View)

[Show all new and modified files in a tree view, annotated with the task ID that creates/modifies each file. This provides a visual overview complementing the table above.]

    deeptrail-control/
    ├── app/
    │   ├── models/
    │   │   └── [new_model].py              ← A1
    │   ├── services/
    │   │   └── [new]_service.py            ← A2
    │   └── api/v1/endpoints/
    │       └── [domain].py                 ← A3 (modify)
    ├── tests/
    │   └── services/
    │       └── test_[new]_service.py       ← A4
    └── alembic/versions/
        └── xxx_[migration].py              ← A1

    deeptrail-gateway/
    ├── app/
    │   ├── backends/
    │   │   └── [new]_client.py             ← B1
    │   └── middleware/
    │       └── [existing].py               ← B2 (modify)
    └── tests/
        └── backends/
            └── test_[new]_client.py        ← B3

    tests/
    └── e2e/
        └── test_[feature].py               ← F1

---

## Testing Strategy

| Batch | What | How |
|-------|------|-----|
| Batch 1 | Unit: [components tested] | `cd [service] && pytest tests/[module]/ -v` |
| Batch 2 | Unit: [components tested] | `cd [service] && pytest tests/[module]/ -v` |
| Batch N | E2E: [full flow description] | `cd [root] && pytest tests/e2e/ -v` or `python demos/[demo].py` |

### Technical Requirements Checklist

| Requirement | Pattern | Applies To |
|-------------|---------|------------|
| Async fixtures | `@pytest_asyncio.fixture` | All E2E tests |
| HTTP client | `httpx.AsyncClient` | All async tests |
| Fixture scope | `scope="function"` for HTTP clients | Avoid connection issues |

---

## File Naming Conventions

| Pattern | Convention | Example | Notes |
|---------|------------|---------|-------|
| Services | `*_service.py` suffix | `[domain]_service.py` | Consistent naming |
| Combined endpoints | Group related operations | `[domain]_auth.py` (related ops in one file) | Reduces file count |
| Validation modules | Use descriptive names | `[x]_validation.py` not `[x]_auth.py` | Clearer purpose |
| Constraint modules | Use active verb form | `[x]_checker.py` not `[x]s.py` | Describes action |
| Backend clients | `*_client.py` suffix | `[provider]_client.py` | Consistent naming |

## Architecture Conventions (DeepSecure Project)

| Convention | Pattern | Rationale |
|------------|---------|-----------|
| FastAPI `app/` prefix | `[service]/app/[module]/` | Framework standard, consistent imports |
| Versioned API | `app/api/v1/endpoints/` | API evolution, breaking change isolation |
| Security separation | Separate `app/security/` directory | First-class security concerns |
| Endpoint consolidation | Related endpoints in single file | Group by domain (e.g., auth, audit) |
| Service suffix | `*_service.py` for all services | Explicit, searchable, consistent |

---

## Next Steps

After saving this breakdown, the following commands are available:

1. **Create workstream structure:** `/create-workstream [feature-name]`
2. **Create batch execution plan:** `/create-batch-execution-plan [feature-name]`
3. **Create task specifications:** `/plan` then `/create-task-spec [batch] [feature-name]`
4. **Generate task tickets:** `/create-task-ticket WS-[ID] [feature-name]`
5. **Start execution:** `/execute-task WS-[ID] [feature-name]`
```

9. **Save the breakdown output** to a reference file:
   - Ask the user: "Would you like to save this breakdown to a file for reference?"
   - If yes, save to: `docs/workstreams/[feature-name]/BREAKDOWN.md`
   - This colocates the breakdown with all other workstream files (WORKSTREAM.md, STATUS.md, etc.)

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
[ -f "docs/workstreams/${FEATURE}/BREAKDOWN.md" ] && echo "✅ docs/workstreams/${FEATURE}/BREAKDOWN.md" || echo "❌ MISSING: docs/workstreams/${FEATURE}/BREAKDOWN.md"

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
| 1 | `docs/workstreams/[feature]/BREAKDOWN.md` | Task breakdown document | Step 9 |
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
   
   **Expected results (minimum 6 files):**
   - BREAKDOWN.md
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
   | `CODEBASE_ANALYSIS.md` | Re-run embedded codebase exploration (Step 1 of this command) |

16. **Final confirmation to user:**
   
   Only after ALL files are verified, output:
   
   ```markdown
   ## ✅ Breakdown Complete
   
   **Workstream:** [feature-name]
   
   ### Files Created
   
   | File | Status |
   |------|--------|
   | `docs/workstreams/[feature]/BREAKDOWN.md` | ✅ |
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
- Breakdown: `docs/workstreams/virtual-mcp-server-mvp/BREAKDOWN.md`

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

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "I don't need to explore first, the design doc is accurate" | Design docs describe intent, not current state. The Feb 2026 lesson proved 60% of "missing" items already existed. Explore first. |
| "I'll classify task types later during execution" | Wrong task types (Create vs Verify) lead to wildly inaccurate effort estimates and over-scoped work. Classify now. |
| "This feature is simple enough for one workstream" | Even simple features benefit from service-boundary workstreams when they cross Control/Gateway/SDK. Parallelization pays off. |
| "Merge points add unnecessary overhead" | Without merge points, parallel worktrees diverge until conflicts are unresolvable. Merge points are insurance. |
| "I'll figure out the batches as I go" | Ad-hoc batching misses dependency chains and creates blocked tasks. Plan batches explicitly. |
| "The breakdown is close enough, let me start coding" | Over-scoped breakdowns waste hours on unnecessary tasks. Under-scoped breakdowns miss critical work. Get it right before execution. |
| "I don't need to auto-run /create-workstream and /create-batch-execution-plan" | Manual creation leads to forgotten files and inconsistent structure. Always chain the follow-up commands. |

## Red Flags

- Running `/breakdown-design` without `CODEBASE_ANALYSIS.md` existing
- All tasks classified as `Create` (suggests exploration was skipped)
- No `Verify` or `Modify` tasks in a mature codebase (something's wrong)
- More than 30 tasks (likely over-scoped — split into phases)
- No merge points defined for multi-service features
- Worktree setup referenced but file paths not using canonical conventions
- Tasks with `tests/unit/` paths instead of correct `tests/[module]/` paths
- E2E tests placed inside service directories instead of root `tests/e2e/`
- Missing post-breakdown verification (all 8 required files must exist)

## Verification

Before declaring breakdown complete:

- [ ] `CODEBASE_ANALYSIS.md` was consulted (not just the design doc)
- [ ] Tasks correctly classified (Create / Modify / Verify / Wire / Skip)
- [ ] Workstreams align with service boundaries
- [ ] Dependencies form a valid DAG (no circular dependencies)
- [ ] Batches respect dependency ordering
- [ ] Merge points defined for parallel tracks
- [ ] Critical path identified
- [ ] All 8 required files exist (BREAKDOWN.md, WORKSTREAM.md, STATUS.md, BATCH_EXECUTION_PLAN.md, MERGE_POINTS.md, CODEBASE_ANALYSIS.md, tasks/, reports/)
- [ ] File paths follow canonical conventions (see path tables above)

---

## Reference

This command integrates with:
- `/explore-codebase` → Embedded as Step 1 of this command (produces `CODEBASE_ANALYSIS.md`)
- `/create-workstream` → Automatically called after breakdown
- `/create-batch-execution-plan` → Automatically called after workstream creation
- `/setup-worktrees` → Optional next step for parallel execution
- `/create-task-spec` → Next step for tasks requiring specifications
- `/verify-batch-completion` → Run after each batch during execution
- `/sync-worktree-status` → Run after worktree tasks complete

See also:
- `CLAUDE.md` → "Codebase Exploration Before Breakdown (CRITICAL)"
- `CLAUDE.md` → "Backend Service File Path Conventions"
- `CLAUDE.md` → "Task Ticket Structure Requirements"
- `docs/DEVELOPER_WORKFLOW.md` → Phase 1: Planning
