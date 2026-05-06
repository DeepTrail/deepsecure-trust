# Developer Workflow Guide

> **Last Updated:** May 2026
>
> This document describes the end-to-end workflow for implementing features using Cursor commands.

---

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEFINE PHASE (Plan Mode / Agent Mode)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  0a. /spec                →  Structured requirements & spec creation        │
│                              Output: docs/spec/[feature-name]-spec.md      │
│  0b. /create-design-doc   →  Transform spec into formal design doc          │
│                              Output: docs/design/[feature-name].md         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PLANNING PHASE (Agent Mode)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. /breakdown-design     →  Analyze design doc, create workstreams/tasks  │
│                              (internally runs /explore-codebase first)     │
│  2. /create-workstream    →  Create folder structure (WORKSTREAM.md, etc.) │
│  3. /create-batch-execution-plan → Create batched execution plan           │
│  3.5 /setup-worktrees     →  Create parallel worktrees from batch plan     │
│  4. /create-task-spec     →  Define contracts/interfaces ⚠️ PLAN MODE      │
│  5. /create-task-ticket   →  Create detailed executable tickets            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXECUTION PHASE (Agent Mode)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  6. /execute-task         →  Implement the task (reads ticket, codes)      │
│     /debug                →  Use when execution hits errors (triage)       │
│  7. /complete-task        →  Auto-runs after execute; generates report     │
│                                                                             │
│  [Repeat 6-7 for each task in the batch]                                   │
│  [Move to next batch when current batch complete]                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REVIEW & FINALIZATION PHASE (Agent Mode)             │
├─────────────────────────────────────────────────────────────────────────────┤
│  8. /run-checks           →  Run linting, tests, type checks               │
│  9. /review               →  Five-axis code review (+ subagent reviews)    │
│ 9.5 /security-audit       →  OWASP/STRIDE security audit (auth changes)   │
│ 10. /commit-push-pr       →  Commit changes and create PR                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SHIP PHASE (Agent Mode)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ 11. /ship                 →  Deploy, smoke test, monitor, rollback plan    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Subagent Definitions (for /review and parallel execution)

Specialist subagent roles are defined in `.cursor/agents/`:

| Agent | File | Role | Use With |
|-------|------|------|----------|
| Code Reviewer | `.cursor/agents/code-reviewer.md` | Senior staff engineer five-axis review | `/review`, PR review |
| Test Engineer | `.cursor/agents/test-engineer.md` | QA specialist, coverage analysis, Prove-It pattern | `/review`, test gaps |
| Security Auditor | `.cursor/agents/security-auditor.md` | OWASP assessment, threat modeling, token verification | `/review`, security changes |

To invoke a subagent review:
```
Use Task tool with subagent_type="generalPurpose" and include
the agent definition content from .cursor/agents/[agent-name].md
```

---

## Phase 0: Define (/spec)

Use the `/spec` command to create structured requirements before any design or implementation.

### Step 0: Create Specification

**Mode:** Agent Mode (or Plan Mode for collaborative iteration)

```
/spec [feature-name]
```

**What it does:**
- Surfaces assumptions explicitly (technology, architecture, scope)
- Asks targeted clarification questions grouped by category
- Creates a structured spec covering: Objective, API Contracts, Data Models, Architecture Decisions, Testing Strategy, Boundaries, and Demo Scenarios
- Reframes vague requirements into testable success criteria
- Saves the spec to `docs/spec/[feature-name]-spec.md`

**Output:** `docs/spec/[feature-name]-spec.md`

**When to use /spec vs Plan Mode:**
- `/spec` — When you need a formal, structured specification with all sections
- Plan Mode — When you're still exploring ideas and need open-ended conversation
- Both — Start in Plan Mode to explore, then `/spec` to formalize

**Conversion:** If you already have a `.cursor/plans/*.plan.md` or `plans/*.plan.md`, use `/create-design-doc` to convert it into a formal design doc in `docs/design/`.

### Step 0b: Transform Spec/Plan into Design Doc (Mandatory)

```
/create-design-doc docs/spec/[feature-name]-spec.md
```

Or from a plan file:
```
/create-design-doc plans/[feature]_[hash].plan.md
```

**What it does:**
- Reads the spec (or plan file) and transforms into a 15-section design doc (500–800+ lines)
- Creates Mermaid diagrams, code interfaces, workstream file tables
- Applies DeepSecure path conventions and testing patterns
- Flags sections needing human input
- Saves to `docs/design/[feature-name].md`

**When to use:** After `/spec` has produced a requirements document. This step is **mandatory** — it transforms requirements (what + why) into implementation design (how).

**Pipeline:** `/spec` → `/create-design-doc` → `/breakdown-design`

> **Note on `/explore-codebase`:** This is NOT a separate pipeline step. It is embedded inside `/breakdown-design` as a mandatory pre-breakdown phase. You do not need to run it explicitly.

### Exploration Checklist

Before running `/breakdown-design`, verify:

- [ ] Explored `deeptrail-control/app/api/v1/endpoints/` for existing endpoints
- [ ] Explored `deeptrail-control/app/services/` for existing services
- [ ] Explored `deeptrail-control/app/models/` for existing models
- [ ] Explored `deeptrail-gateway/app/mcp/` for existing handlers
- [ ] Explored `deeptrail-gateway/app/middleware/` for existing middleware
- [ ] Explored `deeptrail-gateway/app/backends/` for existing backend clients
- [ ] Cross-referenced design doc "missing" items with actual codebase
- [ ] Identified components that exist but may need modification vs new creation

### Anti-Pattern: Trust but Verify

| Bad Pattern | Good Pattern |
|-------------|--------------|
| Read design doc → Create tasks for "missing" items | Read design doc → Explore codebase → Identify TRUE gaps → Create tasks |
| Assume coverage matrix is current | Verify coverage matrix against codebase |
| Trust "Not Implemented" labels in docs | Grep codebase for actual implementations |
| Create "Create X endpoint" task | Verify endpoint doesn't exist, then create "Create X" or "Verify X" task |

### Output: Pre-Breakdown Analysis

Save exploration results before breakdown:

```markdown
# Pre-Breakdown Codebase Analysis

## Design Document: [name]

## Claimed "Missing" vs Actual Status

| Design Says Missing | Codebase Status | Task Type |
|---------------------|-----------------|-----------|
| User login endpoint | EXISTS at /api/v1/auth/login | Verify |
| Service connection | EXISTS at /api/v1/users/me/services/connect | Verify |
| Delegation token | EXISTS but needs format adjustment | Modify |
| Real OAuth flow | NOT IMPLEMENTED | Create |

## True Implementation Gaps

1. [Only items that genuinely don't exist]
2. ...

## Verification Tasks (Not New Development)

1. [Items that exist but need format verification]
2. ...
```

---

## Phase 1: Planning (Agent Mode)

Most planning commands run in **Agent Mode** since they create files. The exception is `/create-task-spec` which runs in **Plan Mode**.

### Step 1: Breakdown Design

**Mode:** Agent Mode

```
/breakdown-design [design-doc-path]
```

**⚠️ NOTE:** `/breakdown-design` internally runs `/explore-codebase` as its first step to inventory existing implementations before creating tasks.

**What it does:**
- **FIRST:** Verifies codebase exploration was completed (checks for existing implementations)
- Analyzes the design document
- Cross-references design "missing" items against actual codebase
- Identifies architectural boundaries (services, modules, APIs)
- Creates workstreams (WS-A, WS-B, etc.)
- Breaks down into tasks (WS-A1, WS-A2, etc.)
- **DISTINGUISHES:** "Create" tasks vs "Verify/Modify" tasks
- Identifies dependencies and critical path
- Groups tasks into parallelizable batches

**Output:** `docs/[feature]-breakdown.md`

**Task Type Classification:**

| Codebase State | Task Type | Example |
|----------------|-----------|---------|
| Component doesn't exist | `Create` | "Create OAuth service" |
| Component exists, format wrong | `Modify` | "Update delegation response format" |
| Component exists, needs verification | `Verify` | "Verify login endpoint matches E2E expectations" |
| Component exists, fully correct | `Skip` | Remove from task list |

### Step 2: Create Workstream

**Mode:** Agent Mode

```
/create-workstream [feature-name]
```

**What it does:**
- Creates folder structure for tracking
- Sets up WORKSTREAM.md (overview) and STATUS.md (progress)
- Creates `tasks/`, `reports/`, `specs/` directories
- Optionally creates git worktrees for parallel execution

**Output:**
```
docs/workstreams/[feature-name]/
├── WORKSTREAM.md          # Overview, task list, dependencies
├── STATUS.md              # Real-time progress tracking
├── specs/                 # Task specifications
├── tasks/                 # Task tickets
└── reports/               # Completion reports
```

### Step 3: Create Batch Execution Plan

**Mode:** Agent Mode

```
/create-batch-execution-plan [feature-name]
```

**What it does:**
- Groups tasks into sequential batches
- Analyzes waves within each batch (parallel opportunities)
- Creates dependency graphs
- Generates execution commands for each batch

**Output:** `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md`

### Step 3.5: Setup Worktrees (For Parallel Execution)

**Mode:** Agent Mode

```
/setup-worktrees [feature-name]
```

**When to use:** When the feature spans multiple services and you want to parallelize execution across agent sessions (Boris Cherny-style parallel worktree workflow).

**What it does:**
- Reads the batch execution plan to understand service boundaries
- Maps workstreams to worktrees by service (Control → worktree-1, Gateway → worktree-2)
- Creates git worktrees with feature branches
- Copies `.cursor/`, `.claude/`, `CLAUDE.md`, and workstream files to each worktree
- Verifies setup and generates ready-to-run execution commands per worktree
- Documents merge points and cleanup commands

**Output:** Worktrees at `../[feature]-control/`, `../[feature]-gateway/`, etc.

**Skip if:** Feature is single-service only or has fewer than 4 tasks.

### Step 4: Create Task Specifications

**Mode:** ⚠️ Plan Mode (switch from Agent Mode)

```
/create-task-spec [batch-number] [feature-name]
```

**What it does:**
- Creates interface/contract specifications for all tasks in a batch
- Defines data models, API signatures, class interfaces
- Establishes acceptance criteria at the spec level
- **Required for:** All tasks involving Python code
- **Skip for:** Documentation-only tasks (no Python code)

**Why Plan Mode:** Spec creation benefits from collaborative design thinking and iteration before committing to implementation details.

**Output:** `docs/workstreams/[feature-name]/specs/[WS-ID]-spec.md`

### Step 5: Create Task Tickets

**Mode:** Agent Mode (switch back from Plan Mode)

```
/create-task-ticket [task-id] [feature-name]
```

**What it does:**
- Creates detailed executable ticket from spec
- Includes pre-conditions, implementation details, acceptance criteria
- Lists specific files to create/modify
- Links to specification document

**Output:** `docs/workstreams/[feature-name]/tasks/[WS-ID]-[name].md`

---

## Phase 2: Execution (Agent Mode)

All execution commands run in **Agent Mode**.

### Step 6: Execute Task

```
/execute-task [task-id] [feature-name]
```

**What it does:**
- Reads the task ticket
- Validates dependencies are complete
- Updates STATUS.md (task → in progress)
- Implements the code following the spec
- Runs tests
- Updates STATUS.md (task → complete)

**Output:** Actual code files as specified in ticket

### Step 7: Complete Task (Auto-runs)

```
/complete-task [task-id] [feature-name]
```

**What it does:**
- Automatically triggered after `/execute-task`
- Generates completion report
- Updates WORKSTREAM.md and STATUS.md
- Records any deviations from plan

**Output:** `docs/workstreams/[feature-name]/reports/[WS-ID]-completion.md`

---

## Phase 3: Review & Finalization

### Step 8: Run Checks

```
/run-checks
```

**What it does:**
- Runs `make check-all` (or equivalent)
- Linting (`ruff check .`)
- Type checking (`mypy`)
- Tests (`pytest`)
- Security scanning (`bandit`)

### Step 8.5: Debug (If Checks Fail)

```
/debug
```

**When to use:** When `/run-checks` or `/execute-task` encounters failures.

**What it does:**
- Follows the Stop-the-Line Rule (stop, preserve, diagnose, fix, guard, resume)
- Triage checklist: Reproduce → Localize → Reduce → Fix Root Cause → Guard → Verify
- DeepSecure-specific error patterns (token types, async fixtures, MCP protocol)
- Requires a regression test before declaring the bug fixed

### Step 9: Code Review

```
/review
```

**What it does:**
- Five-axis review: Correctness, Readability, Architecture, Security, Performance
- Severity-labeled findings (Critical / Required / Nit / Consider / FYI)
- Contract verification (endpoints match spec, correct token types)
- Dead code check and dependency review
- Can invoke subagent specialists for deep review:
  - `.cursor/agents/code-reviewer.md` — Staff engineer review
  - `.cursor/agents/test-engineer.md` — Test coverage analysis
  - `.cursor/agents/security-auditor.md` — Security-focused audit

### Step 9.5: Security Audit (If Security-Relevant)

```
/security-audit
```

**When to use:** When the changeset touches authentication, authorization, JWT/token handling, cryptographic operations, gateway middleware, or new external dependencies.

**What it does:**
- STRIDE threat modeling (Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege)
- Full OWASP Top 10 assessment against changed code
- Token type verification (User Token vs Agent JWT vs Internal Token per endpoint)
- Secrets scan (source code, logs, error responses, git history)
- Dependency audit (`pip audit`, `safety check`)
- Generates structured audit report with severity-labeled findings

**Output:** Security audit report with STRIDE model, OWASP assessment, and verdict (Secure / Needs Fixes / Design Review Required)

### Step 10: Commit and Create PR

```
/commit-push-pr
```

**What it does:**
- Creates git commit with descriptive message
- Pushes to remote branch
- Creates pull request with summary

---

## Phase 4: Ship (Agent Mode)

### Step 11: Deploy to Production

```
/ship
```

**When to use:** After PR is merged and ready for deployment.

**What it does:**
- Pre-flight checks (branch, tests, lint, security audit status)
- Generates changelog from commits since last deployment
- Creates rollback plan with trigger conditions and step-by-step instructions
- Executes deployment (docker compose or SDK release)
- Runs smoke tests (health checks, auth flow, API responsiveness, DB/Redis connectivity)
- Monitors for 15 minutes post-deploy (error rates, response times)
- Generates ship report with deployment status and verdict

**Output:** Ship report with pre-flight results, changelog, rollback plan, smoke test results, and monitoring status

---

## Batch Execution Pattern

For each batch, follow this mini-loop:

```
For Batch N:
  1. Switch to PLAN MODE
     /create-task-spec N [feature]     # Create specs for all batch tasks
  
  2. Switch to AGENT MODE
     For each task in batch:
       /create-task-ticket [task-id] [feature]
  
  3. For each task in batch (respecting wave order):
       /execute-task [task-id] [feature]
       # /complete-task runs automatically
  
  4. If using worktrees:
       /sync-worktree-status [feature]   # Sync status from worktrees to main repo
  
  5. /verify-batch-completion N [feature]  # Verify all tasks done, status consistent
     # DO NOT proceed to Batch N+1 if verification fails
```

### Example: 4-Batch Feature

```bash
# ══════════════════════════════════════════════════════════════
# BATCH 1 - Foundation
# ══════════════════════════════════════════════════════════════

# [PLAN MODE] - Create specs
/create-task-spec 1 my-feature

# [AGENT MODE] - Create tickets and execute
/create-task-ticket A1 my-feature
/create-task-ticket A2 my-feature
/execute-task A1 my-feature
/execute-task A2 my-feature

# [AGENT MODE] - Verify batch 1
/sync-worktree-status my-feature            # If using worktrees
/verify-batch-completion 1 my-feature        # Must pass before proceeding

# ══════════════════════════════════════════════════════════════
# BATCH 2 - Core Components
# ══════════════════════════════════════════════════════════════

# [PLAN MODE] - Create specs
/create-task-spec 2 my-feature

# [AGENT MODE] - Create tickets and execute
/create-task-ticket B1 my-feature
/create-task-ticket B2 my-feature
/execute-task B1 my-feature
/execute-task B2 my-feature

# [AGENT MODE] - Verify batch 2
/sync-worktree-status my-feature            # If using worktrees
/verify-batch-completion 2 my-feature        # Must pass before proceeding

# ... continue for remaining batches ...

# ══════════════════════════════════════════════════════════════
# FINALIZATION [AGENT MODE]
# ══════════════════════════════════════════════════════════════
/run-checks
/commit-push-pr
```

---

## Mode Selection Guide

| Mode | When to Use | Commands/Actions |
|------|-------------|------------------|
| **Plan Mode** | Collaborative spec iteration, task spec design | `/spec` (optional), `/create-task-spec` |
| **Agent Mode** | Everything else — design, planning, execution, review, shipping | `/spec`, `/create-design-doc`, `/breakdown-design`, `/create-workstream`, `/create-batch-execution-plan`, `/setup-worktrees`, `/create-task-ticket`, `/execute-task`, `/debug`, `/complete-task`, `/sync-worktree-status`, `/verify-batch-completion`, `/run-checks`, `/review`, `/security-audit`, `/commit-push-pr`, `/ship` |

### Mode Switching Pattern

```
Agent Mode: /spec (Step 0a) ◄── Structured requirements first
                     │
                     ▼
Agent Mode: /create-design-doc (Step 0b) ◄── Transform spec into design doc
                     │
                     ▼
Agent Mode: /breakdown-design → /create-workstream → /create-batch-execution-plan
                     │          (internally runs /explore-codebase)
                     │
                     ▼
Agent Mode: /setup-worktrees (Step 3.5) ◄── Optional: parallel execution setup
                     │
                     ▼
Plan Mode:  /create-task-spec (Step 4) ◄── Switch to Plan Mode for specs
                     │
                     ▼
Agent Mode: /create-task-ticket → /execute-task (/debug if errors) → ...
                     │
                     ▼
Agent Mode: /run-checks → /review → /security-audit → /commit-push-pr → /ship
```

---

## Artifacts Summary

| Stage | Command | Mode | Artifacts Created |
|-------|---------|------|-------------------|
| **Define** | `/spec` | Agent/Plan | `docs/spec/[feature-name]-spec.md` |
| **Define** | `/create-design-doc` | Agent | Transform spec → `docs/design/[feature-name].md` |
| Breakdown | `/breakdown-design` | Agent | `[feature]-breakdown.md` (runs `/explore-codebase` internally → `CODEBASE_ANALYSIS.md`) |
| Workstream | `/create-workstream` | Agent | `WORKSTREAM.md`, `STATUS.md`, directories |
| Batch Plan | `/create-batch-execution-plan` | Agent | `BATCH_EXECUTION_PLAN.md` |
| **Parallel** | `/setup-worktrees` | Agent | Git worktrees + copied config per service |
| Task Specs | `/create-task-spec` | **Plan** | `specs/[WS-ID]-spec.md` |
| Task Tickets | `/create-task-ticket` | Agent | `tasks/[WS-ID]-[name].md` |
| Execution | `/execute-task` | Agent | Code files |
| **Debug** | `/debug` | Agent | Fix + regression test |
| Completion | `/complete-task` | Agent | `reports/[WS-ID]-completion.md` |
| **Review** | `/review` | Agent | Review report with findings |
| **Security** | `/security-audit` | Agent | STRIDE + OWASP audit report |
| **Ship** | `/ship` | Agent | Ship report (smoke tests, rollback plan) |

---

## Parallel Execution (Multi-Worktree)

For features spanning multiple services (e.g., Control Plane + Gateway):

### Automated Setup (Recommended)

```
/setup-worktrees [feature-name]
```

This command automates the entire worktree setup process:
- Reads the batch execution plan to determine service boundaries
- Creates worktrees with appropriate branches
- Copies `.cursor/`, `.claude/`, `CLAUDE.md`, workstream files, tickets, and specs
- Verifies setup and generates ready-to-run execution commands
- See `.cursor/commands/setup-worktrees.md` for full details

### Manual Setup (Alternative)

```bash
# Create worktrees from dev branch
git worktree add ../vmcp-control -b feature/vmcp-control dev
git worktree add ../vmcp-gateway -b feature/vmcp-gateway dev

# Copy ALL configuration to worktrees (not just commands)
cp -r .cursor ../vmcp-control/
cp -r .cursor ../vmcp-gateway/
cp -r .claude ../vmcp-control/ 2>/dev/null
cp -r .claude ../vmcp-gateway/ 2>/dev/null
cp CLAUDE.md ../vmcp-control/
cp CLAUDE.md ../vmcp-gateway/
```

### Worktree-to-Workstream Mapping

| Workstream | Service | Worktree |
|------------|---------|----------|
| WS-A, WS-C | Control Plane | `vmcp-control` |
| WS-B, WS-D | Gateway | `vmcp-gateway` |
| WS-E, WS-F | Both | Copy to both |

### Sync Status

```
/sync-worktree-status [feature-name]
```

Consolidates status from all worktrees back to main repo.

---

## Quick Reference: Command Flow

```
═══════════════════════════════════════════════════
 DEFINE
═══════════════════════════════════════════════════
       │
/spec ◄──────────────── Structured requirements → docs/spec/[feature-name]-spec.md
       │
       ▼
/create-design-doc ◄─── Transform spec into design doc → docs/design/[feature-name].md
       │
       ▼
═══════════════════════════════════════════════════
 PLAN
═══════════════════════════════════════════════════
       │
/breakdown-design ◄──── Internally runs /explore-codebase, then creates workstreams
       │
/create-workstream
       │
/create-batch-execution-plan
       │
       ▼
┌──────────────────────────┐
│   For each batch:        │
│   ┌────────────────────┐ │
│   │ /create-task-spec  │ │◄── ⚠️ Switch to PLAN MODE
│   └─────────┬──────────┘ │
│             ▼            │
│   ┌────────────────────┐ │
│   │ /create-task-ticket│ │◄── Back to AGENT MODE
│   └─────────┬──────────┘ │
│             ▼            │
│ ═════════════════════════│═══
│  BUILD                   │
│ ═════════════════════════│═══
│   ┌────────────────────┐ │
│   │ /execute-task      │ │◄── Repeat for each task
│   │  └─ /debug (error) │ │    (/debug if things break)
│   │ (/complete-task)   │ │    (auto-completes)
│   └─────────┬──────────┘ │
│             ▼            │
│   ┌────────────────────┐ │
│   │/sync-worktree-status│ │◄── If using worktrees
│   └─────────┬──────────┘ │
│             ▼            │
│   ┌────────────────────┐ │
│   │/verify-batch-       │ │◄── Must pass before next batch
│   │ completion          │ │
│   └────────────────────┘ │
└──────────────────────────┘
       │
       ▼
═══════════════════════════════════════════════════
 REVIEW
═══════════════════════════════════════════════════
       │
/run-checks ◄─────────── Lint, typecheck, tests
       │
/review ◄─────────────── Five-axis review (+ subagent specialists)
       │
/security-audit ◄──────── OWASP/STRIDE audit (if auth/security changes)
       │
/commit-push-pr ◄──────── Commit, push, create PR
       │
       ▼
═══════════════════════════════════════════════════
 SHIP
═══════════════════════════════════════════════════
       │
/ship ◄───────────────── Deploy, smoke test, monitor, rollback
```

### Subagent Review Pattern (Optional)

For complex changes, invoke specialist subagents during `/review`:

```
/review triggers:
    ├── .cursor/agents/code-reviewer.md    → Correctness + Architecture
    ├── .cursor/agents/test-engineer.md    → Test quality + Coverage
    └── .cursor/agents/security-auditor.md → OWASP + Token verification
```

---

## Troubleshooting

### Task Blocked by Dependencies

```
Error: Task blocked by incomplete dependencies: [WS-A1, WS-A2]
```

**Fix:** Execute the dependency tasks first, or check STATUS.md to verify completion status.

### Ticket Not Found in Worktree

```
Error: Ticket not found: docs/workstreams/[feature]/tasks/[WS-ID]-*.md
```

**Fix:** Sync ticket to worktree:
```bash
cp docs/workstreams/[feature]/tasks/[WS-ID]-*.md \
   [WORKTREE_PATH]/docs/workstreams/[feature]/tasks/
```

### Async Event Loop Conflict

If using `questionary` with `asyncio`, use `.ask_async()` instead of `.ask()` in async contexts.

---

## Related Documents

- [CLAUDE.md](../CLAUDE.md) - Project-specific guidance and self-verification
- [.cursorrules](../.cursorrules) - Project rules and patterns
- [Task Ticket Template](./workstreams/TASK_TICKET_TEMPLATE.md)
- [Completion Report Template](./workstreams/COMPLETION_REPORT_TEMPLATE.md)

### Commands (`.cursor/commands/`)

| Phase | Command | Description |
|-------|---------|-------------|
| Define | `/spec` | Structured requirements before design |
| Define | `/create-design-doc` | Transform spec/plan into formal design doc |
| Plan | `/breakdown-design` | Create workstreams and tasks (runs `/explore-codebase` internally) |
| Plan | `/create-workstream` | Create folder structure |
| Plan | `/create-batch-execution-plan` | Create batched execution plan |
| Plan | `/setup-worktrees` | Create parallel worktrees from batch plan |
| Plan | `/create-task-spec` | Define contracts/interfaces (Plan Mode) |
| Plan | `/create-task-ticket` | Create executable tickets |
| Build | `/execute-task` | Implement a task |
| Build | `/debug` | Systematic root-cause debugging |
| Build | `/complete-task` | Generate completion report |
| Verify | `/verify-batch-completion` | Verify batch status consistency |
| Verify | `/sync-worktree-status` | Sync worktree status to main repo |
| Review | `/run-checks` | Lint, typecheck, tests |
| Review | `/review` | Five-axis code review |
| Review | `/security-audit` | OWASP/STRIDE security audit |
| Review | `/commit-push-pr` | Commit, push, create PR |
| Ship | `/ship` | Deploy, smoke test, monitor, rollback |
| Learn | `/update-claude-md` | Capture learnings |
| Meta | `/pipeline` | Orchestrate full DEFINE→PLAN→EXECUTE→REVIEW→SHIP |

### Subagent Definitions (`.cursor/agents/`)

| Agent | File | Perspective |
|-------|------|-------------|
| Code Reviewer | `code-reviewer.md` | Senior staff engineer, five-axis review |
| Test Engineer | `test-engineer.md` | QA specialist, coverage + Prove-It pattern |
| Security Auditor | `security-auditor.md` | Security engineer, OWASP + threat modeling |

### Hooks (`.cursor/hooks.json` + `.cursor/hooks/`)

Quality gates that run deterministically at agent lifecycle events:

| Hook | Script | What It Does |
|------|--------|-------------|
| `afterFileEdit` | `hooks/after-file-edit.sh` | Lint Python files immediately after edit (Micro Verification) |
| `beforeShellExecution` | `hooks/before-shell.sh` | Block force-push to main/dev, dangerous `rm -rf`, `--no-verify` |
| `stop` | `hooks/on-task-stop.sh` | macOS notification + lint summary on task completion |

Hooks are deterministic (unlike rules) and run outside the LLM loop, making them faster and more reliable for safety gates. See [Deep Dive into Cursor Hooks](https://blog.gitbutler.com/cursor-hooks-deep-dive) for details.

---

## Lessons Learned

### Lesson 1: Design Docs ≠ Current State (Feb 2026)

**What happened:** Created a breakdown for "MVP Production Readiness" based on design documents that claimed certain endpoints were "missing." After codebase exploration, discovered ~60% of "missing" components actually existed.

**Root cause:**
1. Design docs describe **intent**, not **current state**
2. Coverage matrices become stale as development continues
3. "Not Implemented" in gap analysis meant "not enterprise-grade" not "doesn't exist"
4. No codebase exploration was done before breakdown

**Solution:** Embedded codebase exploration as a mandatory first step inside `/breakdown-design`.

**Key learning:** The codebase is the **source of truth**. Design documents are proposals. Coverage matrices are snapshots. Always explore before scoping.

### Lesson 2: Task Classification Matters

**What happened:** Tasks were scoped as "Create X endpoint" when the endpoint existed but needed format adjustment.

**Impact:** Over-estimated effort, wrong task descriptions, misleading progress tracking.

**Solution:** Three task types based on codebase state:
- `Create` - Component doesn't exist
- `Modify` - Component exists but needs changes
- `Verify` - Component exists, needs validation against requirements

### Lesson 3: Cross-Reference E2E Tests with Implementations

**What happened:** Read E2E test expectations, didn't grep for actual endpoint implementations.

**Solution:** When E2E test shows `POST /api/v1/auth/login`:
1. ✅ Grep codebase: `grep -r "auth/login" deeptrail-control/`
2. ✅ Check if endpoint exists
3. ✅ Compare response format to test expectations
4. ❌ Don't assume endpoint is missing just because test exists

---

## Changelog

| Date | Change |
|------|--------|
| May 2026 | Added `/security-audit` — OWASP/STRIDE security audit with token verification and secrets scan |
| May 2026 | Added `/ship` — production deployment with smoke tests, rollback plan, and monitoring |
| May 2026 | Renamed `/orchestrate-feature` → `/pipeline` — full state machine: DEFINE→PLAN→EXECUTE→REVIEW→SHIP (EXPLORE embedded in PLAN) |
| May 2026 | Added `/setup-worktrees` — automated parallel worktree creation from batch plan |
| May 2026 | Added `/create-design-doc` — convert plan files to formal design docs |
| May 2026 | Added Cursor hooks system — quality gates for file edits, shell commands, task completion |
| May 2026 | Added `/spec` command — structured requirements before design (Phase 0: Define) |
| May 2026 | Added `/review` command — five-axis code review with anti-rationalization tables |
| May 2026 | Added `/debug` command — systematic root-cause debugging with triage checklist |
| May 2026 | Added subagent definitions: code-reviewer, test-engineer, security-auditor |
| May 2026 | Updated pipeline: Define → Plan → Build → Review → Ship (Explore embedded in Plan) |
| Feb 2026 | Added codebase exploration (embedded in `/breakdown-design`) after learning from MVP Production Readiness over-scoping |
| Feb 2026 | Added Lessons Learned section documenting process improvements |
| Feb 2026 | Corrected mode assignments: Plan Mode only for design doc + `/create-task-spec`; Agent Mode for all other commands |
| Feb 2026 | Initial workflow documentation |
