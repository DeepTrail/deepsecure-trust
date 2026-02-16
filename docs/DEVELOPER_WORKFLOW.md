# Developer Workflow Guide

> **Last Updated:** February 2026
>
> This document describes the end-to-end workflow for implementing features using Cursor commands.

---

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DESIGN PHASE (Plan Mode - Conversational)              │
├─────────────────────────────────────────────────────────────────────────────┤
│  0. Design Doc Creation   →  Conversational design in Plan Mode            │
│                              (No command - creates .cursor/plans/*.plan.md)│
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PLANNING PHASE (Agent Mode)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. /breakdown-design     →  Analyze design doc, create workstreams/tasks  │
│  2. /create-workstream    →  Create folder structure (WORKSTREAM.md, etc.) │
│  3. /create-batch-execution-plan → Create batched execution plan           │
│  4. /create-task-spec     →  Define contracts/interfaces ⚠️ PLAN MODE      │
│  5. /create-task-ticket   →  Create detailed executable tickets            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXECUTION PHASE (Agent Mode)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  6. /execute-task         →  Implement the task (reads ticket, codes)      │
│  7. /complete-task        →  Auto-runs after execute; generates report     │
│                                                                             │
│  [Repeat 6-7 for each task in the batch]                                   │
│  [Move to next batch when current batch complete]                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FINALIZATION PHASE (Agent Mode)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  8. /run-checks           →  Run linting, tests, type checks               │
│  9. /commit-push-pr       →  Commit changes and create PR                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 0: Design (Plan Mode)

Use **Cursor Plan Mode** for initial design document creation. This is conversational - no command exists.

### Step 0: Create Design Document

**Mode:** Plan Mode (conversational)

**What you do:**
- Describe the feature/system you want to build
- Iterate with Claude to refine the design
- Claude creates the design document

**Output:** `.cursor/plans/[feature]_[hash].plan.md`

**How to enter Plan Mode:**
- Use Cursor's mode switcher or keyboard shortcut
- Or Claude will suggest switching via `SwitchMode` tool

---

## Phase 1: Planning (Agent Mode)

Most planning commands run in **Agent Mode** since they create files. The exception is `/create-task-spec` which runs in **Plan Mode**.

### Step 1: Breakdown Design

**Mode:** Agent Mode

```
/breakdown-design [design-doc-path]
```

**What it does:**
- Analyzes the design document
- Identifies architectural boundaries (services, modules, APIs)
- Creates workstreams (WS-A, WS-B, etc.)
- Breaks down into tasks (WS-A1, WS-A2, etc.)
- Identifies dependencies and critical path
- Groups tasks into parallelizable batches

**Output:** `docs/[feature]-breakdown.md`

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

## Phase 3: Finalization

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

### Step 9: Commit and Create PR

```
/commit-push-pr
```

**What it does:**
- Creates git commit with descriptive message
- Pushes to remote branch
- Creates pull request with summary

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
  
  4. Verify batch complete → Move to Batch N+1
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
| **Plan Mode** | Design & specification creation | Design doc creation (conversational), `/create-task-spec` |
| **Agent Mode** | Everything else (file creation, execution) | `/breakdown-design`, `/create-workstream`, `/create-batch-execution-plan`, `/create-task-ticket`, `/execute-task`, `/complete-task`, `/run-checks`, `/commit-push-pr` |

### Mode Switching Pattern

```
Plan Mode:  Design doc creation (Step 0)
                     │
                     ▼
Agent Mode: /breakdown-design → /create-workstream → /create-batch-execution-plan
                     │
                     ▼
Plan Mode:  /create-task-spec (Step 4) ◄── Switch to Plan Mode
                     │
                     ▼
Agent Mode: /create-task-ticket → /execute-task → ... → /commit-push-pr
```

---

## Artifacts Summary

| Stage | Command | Mode | Artifacts Created |
|-------|---------|------|-------------------|
| Design | (conversational) | Plan | `.cursor/plans/[feature]_[hash].plan.md` |
| Breakdown | `/breakdown-design` | Agent | `[feature]-breakdown.md` |
| Workstream | `/create-workstream` | Agent | `WORKSTREAM.md`, `STATUS.md`, directories |
| Batch Plan | `/create-batch-execution-plan` | Agent | `BATCH_EXECUTION_PLAN.md` |
| Task Specs | `/create-task-spec` | **Plan** | `specs/[WS-ID]-spec.md` |
| Task Tickets | `/create-task-ticket` | Agent | `tasks/[WS-ID]-[name].md` |
| Execution | `/execute-task` | Agent | Code files |
| Completion | `/complete-task` | Agent | `reports/[WS-ID]-completion.md` |

---

## Parallel Execution (Multi-Worktree)

For features spanning multiple services (e.g., Control Plane + Gateway):

### Setup Worktrees

```bash
# Create worktrees from dev branch
git worktree add ../vmcp-control -b feature/vmcp-control dev
git worktree add ../vmcp-gateway -b feature/vmcp-gateway dev

# Copy commands to worktrees
cp -r .cursor/commands ../vmcp-control/.cursor/
cp -r .cursor/commands ../vmcp-gateway/.cursor/
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
[PLAN MODE] Design Doc Creation (conversational)
       │
       ▼
═══════════════════════════════════════════════════
[AGENT MODE]
═══════════════════════════════════════════════════
       │
       ▼
/breakdown-design
       │
       ▼
/create-workstream
       │
       ▼
/create-batch-execution-plan
       │
       ▼
┌──────────────────────────┐
│   For each batch:        │
│   ┌────────────────────┐ │
│   │ /create-task-spec  │ │◄─── ⚠️ Switch to PLAN MODE
│   └─────────┬──────────┘ │
│             ▼            │
│   ┌────────────────────┐ │
│   │ /create-task-ticket│ │◄─── Back to AGENT MODE
│   └─────────┬──────────┘ │     Repeat for each task
│             ▼            │
│   ┌────────────────────┐ │
│   │ /execute-task      │ │◄─── Repeat for each task
│   │ (/complete-task)   │ │     (auto-completes)
│   └────────────────────┘ │
└──────────────────────────┘
       │
       ▼
/run-checks
       │
       ▼
/commit-push-pr
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

- [CLAUDE.md](../CLAUDE.md) - Project-specific guidance
- [.cursorrules](../.cursorrules) - Project rules and patterns
- [Task Ticket Template](./workstreams/TASK_TICKET_TEMPLATE.md)
- [Completion Report Template](./workstreams/COMPLETION_REPORT_TEMPLATE.md)

---

## Changelog

| Date | Change |
|------|--------|
| Feb 2026 | Corrected mode assignments: Plan Mode only for design doc + `/create-task-spec`; Agent Mode for all other commands |
| Feb 2026 | Initial workflow documentation |
