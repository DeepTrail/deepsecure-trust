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
│  ✅ AUTOMATED (Recommended):                                                │
│     /run-plan [design-doc] [feature-name]                                  │
│        Chains: /breakdown-design → /create-workstream →                    │
│                /create-batch-execution-plan → /setup-worktrees (if needed) │
│        Verifies all 8 required files, checkpoints before execution.        │
│                                                                             │
│  Manual alternative (individual steps):                                    │
│  1. /breakdown-design     →  Explore codebase + create workstreams/tasks   │
│                              (auto-chains /create-workstream +             │
│                               /create-batch-execution-plan internally)     │
│  2. /create-workstream    →  Already run by /breakdown-design (manual only)│
│  3. /create-batch-execution-plan → Already run by /breakdown-design        │
│  3.5 /setup-worktrees     →  Create parallel worktrees (if multi-service)  │
│                                                                             │
│  ⚠️  /create-task-spec and /create-task-ticket are NOT manual PLAN steps.  │
│     They run automatically inside /run-batch at the start of each batch.   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXECUTION PHASE (Agent Mode)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✅ AUTOMATED (Recommended):                                                │
│     /run-batch [batch-id] [feature-name]                                   │
│        Chains: /create-task-spec → /create-task-ticket →                   │
│                /execute-task (per wave, parallel if 4+) →                  │
│                /verify-batch-completion                                     │
│        Includes spec-implementation audit + merge point handling.          │
│                                                                             │
│  Manual alternative (individual steps):                                    │
│  6. /execute-task         →  Implement the task (reads ticket, codes)      │
│     /debug                →  Use when execution hits errors (triage)       │
│  7. /complete-task        →  Auto-runs after execute; generates report     │
│  8. /verify-batch-completion → Verify status consistency before next batch │
│                                                                             │
│  [Repeat per batch: /run-batch P0-B1 → checkpoint → /run-batch P0-B2]     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REVIEW & FINALIZATION PHASE (Agent Mode)             │
├─────────────────────────────────────────────────────────────────────────────┤
│  9. /run-checks           →  Run linting, tests, type checks               │
│ 10. /review               →  Five-axis code review (+ subagent reviews)    │
│ 10.5 /security-audit      →  OWASP/STRIDE security audit (auth changes)   │
│ 11. /commit-push-pr       →  Commit changes and create PR                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SHIP PHASE (Agent Mode)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ 12. /ship                 →  Deploy, smoke test, monitor, rollback plan    │
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

All planning commands run in **Agent Mode** since they create files. Task specs and tickets are **not** created here — they are created automatically by `/run-batch` at the start of each batch during the Execution phase.

### Recommended: /run-plan (Automated)

**Mode:** Agent Mode

```
/run-plan [design-doc-path] [feature-name]
```

**What it does (one command):**
1. Runs `/breakdown-design` (which internally runs `/explore-codebase`, `/create-workstream`, `/create-batch-execution-plan`)
2. Verifies all 8 required workstream files exist
3. Decides on and optionally runs `/setup-worktrees` for multi-service features
4. Checkpoints with user — shows workstream summary, task count, critical path, first batch preview
5. Hands off to `/run-batch P0-B1 [feature-name]`

**Output:** Complete workstream scaffold ready for `/run-batch`

**Example:**
```
/run-plan docs/design/agent-auth-flow.md agent-auth
/run-plan plans/claude_code_integration.plan.md claude-code-integration
```

> This is the PLAN-phase equivalent of `/run-batch`. Use it for every new workstream.

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

### Step 4: Run Batch (Automated — Recommended)

**Mode:** Agent Mode

```
/run-batch [batch-id] [feature-name]
```

**Parameters:**
- `[batch-id]`: The batch identifier from the **Quick Reference** table in `BATCH_EXECUTION_PLAN.md`.
  Format: `P{Phase}-B{Batch}` (e.g., `P0-B1`, `P1-B2`).
- `[feature-name]`: The workstream/feature name.

**What it does (automatically, in one command):**
1. Reads `BATCH_EXECUTION_PLAN.md` — extracts task list, wave analysis, dependency graph
2. Runs `/create-task-spec` for all tasks in the batch
3. Runs `/create-task-ticket` for each task
4. Executes waves in order, parallelizing independent tasks via subagents
5. Gates on wave completion before advancing to the next wave
6. Runs `/verify-batch-completion` after all waves
7. Handles merge point tagging if applicable
8. Checkpoints with the user — reports results and asks to proceed

**Parallelization rules:**
- 1 task in wave → execute inline
- 2-3 tasks in wave → execute sequentially (subagent overhead exceeds benefit)
- 4+ tasks in wave → spawn parallel `best-of-n-runner` subagents

**Output:** Specs, tickets, code, completion reports — everything the manual steps produce.

**Example:**
```
/run-batch P0-B1 agent-lifecycle
# → Creates specs for WS-A1, WS-A2
# → Creates tickets for each task
# → Executes Wave 1: WS-A1, WS-A2 (sequential — 2 tasks)
# → Runs /verify-batch-completion P0-B1 agent-lifecycle
# → Reports results, asks to proceed
```

### Step 4-alt: Manual Batch Execution (Legacy — Use `/run-batch` Instead)

> **⚠️ Superseded by `/run-batch`.** Steps 4a and 5 below describe the manual workflow that `/run-batch` replaced. Only use this if you need fine-grained control over individual tasks (e.g., re-running a single failed spec or ticket). For normal workstream execution, always use `/run-batch`.

#### Step 4a: Create Task Specifications (manual — normally handled by /run-batch)

**Mode:** ⚠️ Plan Mode (switch from Agent Mode)

```
/create-task-spec [batch-id] [feature-name]
```

**What it does:**
- Creates interface/contract specifications for all tasks in a batch
- Defines data models, API signatures, class interfaces
- Establishes acceptance criteria at the spec level
- **Required for:** All tasks involving code
- **Skip for:** Documentation-only tasks (no code)

**Output:** `docs/workstreams/[feature-name]/specs/[WS-ID]-spec.md`

#### Step 5: Create Task Tickets (manual — normally handled by /run-batch)

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

### Recommended: /run-batch (Automated)

```
/run-batch [batch-id] [feature-name]
```

**What it does (one command per batch):**
1. Parses `BATCH_EXECUTION_PLAN.md` — extracts task list, wave analysis, dependency graph
2. Runs `/create-task-spec` for all tasks in the batch
3. Runs `/create-task-ticket` for each task
4. Executes waves in order, parallelizing independent tasks via subagents
5. Runs spec-implementation audit to catch drift between specs and code
6. Runs `/verify-batch-completion` after all waves
7. Handles merge point tagging if applicable
8. Checkpoints with the user — reports results and asks to proceed

**Output:** Specs, tickets, code, completion reports — everything the manual steps produce.

> This is the EXECUTE-phase equivalent of `/run-plan`. Use it for every batch.

### Step 6-alt: Execute Task (Manual — Use `/run-batch` Instead)

> **Superseded by `/run-batch`.** Only use this for re-running a single failed task
> or when you need fine-grained control over individual tasks.

```
/execute-task [task-id] [feature-name]
```

**What it does:**
- Reads the task ticket
- Validates dependencies are complete
- Updates STATUS.md (task → in progress)
- Implements the code following the spec
- Runs tests
- Runs inline completion (Steps 8a-8i: report, status updates, unblock tracking)

**Output:** Actual code files as specified in ticket

### Step 7-alt: Complete Task (Auto-runs inside /execute-task)

```
/complete-task [task-id] [feature-name]
```

**What it does:**
- Automatically triggered at the end of `/execute-task` (Steps 8a-8i)
- Generates completion report
- Updates WORKSTREAM.md and STATUS.md
- Records any deviations from plan

**Output:** `docs/workstreams/[feature-name]/reports/[WS-ID]-completion.md`

### Step 8: Verify Batch Completion (Runs inside /run-batch)

```
/verify-batch-completion [batch-id] [feature-name]
```

**What it does:**
- Cross-references completion reports against STATUS.md, WORKSTREAM.md, BATCH_EXECUTION_PLAN.md
- Verifies progress percentages match actual completion count
- Checks merge point status if applicable
- **BLOCKING** — do NOT proceed to next batch if verification fails

**Output:** Verification report (PASS/FAIL with detailed findings)

---

## Phase 3: Review & Finalization

### Step 9: Run Checks

```
/run-checks
```

**What it does:**
- Runs `make check-all` (or equivalent)
- Linting (`ruff check .`)
- Type checking (`mypy`)
- Tests (`pytest`)
- Security scanning (`bandit`)

### Step 9.5: Debug (If Checks Fail)

```
/debug
```

**When to use:** When `/run-checks` or `/execute-task` encounters failures.

**What it does:**
- Follows the Stop-the-Line Rule (stop, preserve, diagnose, fix, guard, resume)
- Triage checklist: Reproduce → Localize → Reduce → Fix Root Cause → Guard → Verify
- DeepSecure-specific error patterns (token types, async fixtures, MCP protocol)
- Requires a regression test before declaring the bug fixed

### Step 10: Code Review

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

### Step 10.5: Security Audit (If Security-Relevant)

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

### Step 11: Commit and Create PR

```
/commit-push-pr
```

**What it does:**
- Creates git commit with descriptive message
- Pushes to remote branch
- Creates pull request with summary

---

## Phase 4: Ship (Agent Mode)

### Step 12: Deploy to Production

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

### Automated (Recommended)

Use `/run-batch` to automate the entire batch lifecycle:

```
For each batch (from Quick Reference table in BATCH_EXECUTION_PLAN.md):
  /run-batch [batch-id] [feature]
  # Internally: specs → tickets → execute waves (parallel where possible) → verify → checkpoint
  # DO NOT proceed to next batch until checkpoint passes
```

### Example (Automated)

```bash
# ══════════════════════════════════════════════════════════════
# AUTOMATED BATCH EXECUTION
# Batch IDs from BATCH_EXECUTION_PLAN.md Quick Reference table
# Format: P{Phase}-B{Batch} (e.g., P0-B1, P1-B2)
# ══════════════════════════════════════════════════════════════

# Phase 0 — Foundation
/run-batch P0-B1 my-feature    # Foundation — specs, tickets, execute, verify, checkpoint
/run-batch P0-B2 my-feature    # Core — specs, tickets, execute, verify, checkpoint
/run-batch P0-B3 my-feature    # Tests — specs, tickets, execute, verify, checkpoint

# Phase 1 — Integration
/run-batch P1-B1 my-feature    # Components — specs, tickets, execute, verify, checkpoint
/run-batch P1-B2 my-feature    # Wiring — specs, tickets, execute, verify, checkpoint

# ══════════════════════════════════════════════════════════════
# FINALIZATION [AGENT MODE]
# ══════════════════════════════════════════════════════════════
/run-checks
/commit-push-pr
```

### Manual (Alternative)

If you prefer manual control, replace `/run-batch [batch-id]` with the individual steps:

```
For each batch (from Quick Reference table):
  1. Switch to PLAN MODE
     /create-task-spec [batch-id] [feature]     # Create specs for all batch tasks
  
  2. Switch to AGENT MODE
     For each task in batch:
       /create-task-ticket [task-id] [feature]
  
  3. For each task in batch (respecting wave order):
       /execute-task [task-id] [feature]
       # /complete-task runs automatically
  
  4. If using worktrees:
       /sync-worktree-status [feature]   # Sync status from worktrees to main repo
  
  5. /verify-batch-completion [batch-id] [feature]  # Verify all tasks done, status consistent
     # DO NOT proceed to next batch if verification fails
```

---

## Mode Selection Guide

| Mode | When to Use | Commands/Actions |
|------|-------------|------------------|
| **Plan Mode** | Collaborative spec iteration only (rare, manual) | `/spec` (optional), `/create-task-spec` (manual alternative only — normally handled inside `/run-batch`) |
| **Agent Mode** | Everything else — design, planning, execution, review, shipping | `/spec`, `/create-design-doc`, `/run-plan` (automates PLAN phase), `/breakdown-design`, `/create-workstream`, `/create-batch-execution-plan`, `/setup-worktrees`, `/run-batch` (automates EXECUTE phase), `/create-task-spec` (internal), `/create-task-ticket` (internal), `/execute-task`, `/debug`, `/complete-task`, `/sync-worktree-status`, `/verify-batch-completion`, `/run-checks`, `/review`, `/security-audit`, `/commit-push-pr`, `/ship` |

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
Agent Mode: /run-plan [doc] [feature] ◄── Automated PLAN phase (recommended)
                     │               (internally: breakdown → workstream →
                     │                batch plan → worktrees if needed)
                     │
                     │  OR (manual alternative):
                     │
Agent Mode: /breakdown-design → /create-workstream → /create-batch-execution-plan
                     │
Agent Mode: /setup-worktrees (Step 3.5) ◄── Optional: parallel execution setup
                     │
                     ▼
Agent Mode: /run-batch [batch-id] [feature] ◄── Automated EXECUTE phase (recommended)
                     │             (internally: task-spec → ticket → execute →
                     │              verify-batch-completion → checkpoint)
                     │
                     │  OR (manual alternative):
                     │
Plan Mode:  /create-task-spec (Step 4a) ◄── Manual alternative only
                     │
                     ▼
Agent Mode: /create-task-ticket (Step 5) ◄── Manual alternative only
                     │
                     ▼
Agent Mode: /execute-task (/debug if errors) → /verify-batch-completion
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
| **Plan Phase** | `/run-plan` *(recommended)* | Agent | Orchestrates breakdown → workstream → batch plan → worktrees (automated) |
| Breakdown | `/breakdown-design` *(internal to /run-plan)* | Agent | `BREAKDOWN.md`, `CODEBASE_ANALYSIS.md` (runs `/explore-codebase` internally; auto-chains workstream + batch plan) |
| Workstream | `/create-workstream` *(internal to /run-plan)* | Agent | `WORKSTREAM.md`, `STATUS.md`, `MERGE_POINTS.md`, directories |
| Batch Plan | `/create-batch-execution-plan` *(internal to /run-plan)* | Agent | `BATCH_EXECUTION_PLAN.md` |
| Parallel Setup | `/setup-worktrees` *(internal to /run-plan, conditional)* | Agent | Git worktrees + copied config per service |
| **Batch Run** | `/run-batch` | Agent | Orchestrates specs → tickets → execute → verify (automated) |
| Task Specs | `/create-task-spec` *(internal to /run-batch)* | Agent (Plan in manual mode) | `specs/[WS-ID]-spec.md` — created automatically by `/run-batch` |
| Task Tickets | `/create-task-ticket` *(internal to /run-batch)* | Agent | `tasks/[WS-ID]-[name].md` — created automatically by `/run-batch` |
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
┌──────────────────────────────────────────────────────┐
│ /run-plan [design-doc] [feature]  ◄── Recommended   │
│   ├─ /breakdown-design (internal)                    │◄── Explores codebase, creates workstreams
│   │    ├─ /explore-codebase                          │
│   │    ├─ /create-workstream                         │
│   │    └─ /create-batch-execution-plan               │
│   ├─ Verifies all 8 required files                   │
│   └─ /setup-worktrees (internal, if multi-service)   │
└──────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│   For each batch:                        │
│   ┌──────────────────────────────────┐   │
│   │ /run-batch [batch-id] [feature]  │   │◄── Automated: specs → tickets → execute → verify
│   │   ├─ /create-task-spec (internal)│   │    (spec + ticket creation happen inside here)
│   │   ├─ /create-task-ticket (int.)  │   │
│   │   ├─ /execute-task (per wave)    │   │
│   │   │    └─ /debug (if errors)     │   │
│   │   ├─ /sync-worktree-status       │   │◄── If using worktrees
│   │   └─ /verify-batch-completion    │   │◄── Must pass before next batch
│   └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
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
| Plan | `/run-plan` | **Automated PLAN phase** — chains breakdown + workstream + batch plan + worktrees (one command) |
| Plan | `/breakdown-design` | Explore codebase + create workstreams/tasks — *internal to /run-plan, manual alternative* |
| Plan | `/create-workstream` | Create folder structure — *internal to /breakdown-design* |
| Plan | `/create-batch-execution-plan` | Create batched execution plan — *internal to /breakdown-design* |
| Plan | `/setup-worktrees` | Create parallel worktrees — *internal to /run-plan (conditional)* |
| Build | `/run-batch` | **Automated EXECUTE phase** — create specs + tickets → execute → verify (one command per batch) |
| Build | `/create-task-spec` | Define contracts/interfaces — *manual alternative only, internal to /run-batch* |
| Build | `/create-task-ticket` | Create executable tickets — *manual alternative only, internal to /run-batch* |
| Build | `/execute-task` | Implement a task — *internal to /run-batch, manual alternative for single tasks* |
| Build | `/debug` | Systematic root-cause debugging |
| Build | `/complete-task` | Generate completion report — *auto-runs inside /execute-task* |
| Build | `/verify-batch-completion` | Verify batch status consistency — *internal to /run-batch, blocks next batch* |
| Build | `/sync-worktree-status` | Sync worktree status to main repo — *internal to /run-batch when using worktrees* |
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
| May 2026 | Moved `/create-task-spec` and `/create-task-ticket` out of PLAN phase — they run automatically inside `/run-batch` at the start of each batch; manual steps kept as legacy alternative only |
| May 2026 | Added `/run-plan` command — automates the full PLAN phase (breakdown + workstream + batch plan + worktrees) as the PLAN-phase equivalent of `/run-batch` |
| May 2026 | Fixed EXECUTION PHASE to show `/run-batch` as primary command (matching pipeline.md); added `/verify-batch-completion` to overview; marked `/execute-task` and `/complete-task` as manual alternatives |
| Feb 2026 | Initial workflow documentation |
