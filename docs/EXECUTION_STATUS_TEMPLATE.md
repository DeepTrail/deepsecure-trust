# [Feature Name]: Execution Status

> **Workflow Guide:** [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md)
>
> **Design Doc:** [link to design doc]
>
> **Breakdown Doc:** [link to breakdown doc]
>
> **Task Status:** [STATUS.md](./workstreams/[feature-name]/STATUS.md)
>
> **Last Updated:** [Date]

---

## Current Status Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WORKFLOW PHASE STATUS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   PHASE 1          PHASE 2          PHASE 3           PHASE 4               │
│   ────────         ────────         ────────          ────────              │
│   DESIGN           PLANNING         EXECUTION         LEARNING              │
│                                                                              │
│   [░░░░░░░░░░]     [░░░░░░░░░░]     [░░░░░░░░░░]     [░░░░░░░░░░]           │
│   ⏸️ NOT STARTED   ⏸️ NOT STARTED   ⏸️ NOT STARTED   ⏸️ NOT STARTED         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Metric | Value |
|--------|-------|
| **Current Phase** | Phase 1: Design |
| **Current Batch** | N/A |
| **Overall Progress** | 0% (0/X tasks complete) |
| **Task Status File** | [workstreams/[feature-name]/STATUS.md](./workstreams/[feature-name]/STATUS.md) |

---

## Phase 1: Design ⏸️ NOT STARTED

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 1.1 | Design document created | ⏸️ Pending | |
| 1.2 | Goals and non-goals defined | ⏸️ Pending | |
| 1.3 | Technical architecture documented | ⏸️ Pending | |
| 1.4 | User journey defined | ⏸️ Pending | |
| 1.5 | Acceptance criteria defined | ⏸️ Pending | |

**Phase 1 Output:** [Design Document](link)

---

## Phase 2: Planning ⏸️ NOT STARTED

| Step | Command | Status | Output |
|------|---------|--------|--------|
| 2a | `/breakdown-design` | ⏸️ Pending | - |
| 2b | `/create-workstream` | ⏸️ Pending | - |
| 2c | Create Task STATUS.md | ⏸️ Pending | - |
| 2d | `/create-task-ticket` (Batch 1) | ⏸️ Pending | - |

### Planning Artifacts

| Artifact | Status | Location |
|----------|--------|----------|
| Workstream breakdown | ⏸️ Pending | - |
| Batch execution model | ⏸️ Pending | - |
| Merge points | ⏸️ Pending | - |
| Critical path analysis | ⏸️ Pending | - |
| Acceptance mapping | ⏸️ Pending | - |

---

## Phase 3: Execution ⏸️ NOT STARTED

### Batch Overview

| Batch | Tasks | Status | Dependencies |
|-------|-------|--------|--------------|
| Batch 1 | [tasks] | ⏸️ Pending | None |
| Batch 2 | [tasks] | ⏸️ Blocked | Batch 1 |
| ... | ... | ... | ... |

### Merge Points

| Point | Converging Tasks | Status | Target Batch |
|-------|------------------|--------|--------------|
| **MP1** | [tasks] | ⏸️ Pending | Before Batch X |
| ... | ... | ... | ... |

### Quality Gates

| Gate | Status | Last Run | Result |
|------|--------|----------|--------|
| `make format` | ⏸️ Pending | - | - |
| `make lint` | ⏸️ Pending | - | - |
| `mypy` | ⏸️ Pending | - | - |
| `pytest` | ⏸️ Pending | - | - |
| `make check-all` | ⏸️ Pending | - | - |

**Detailed Task Status:** See [workstreams/[feature-name]/STATUS.md](./workstreams/[feature-name]/STATUS.md)

---

## Phase 4: Learning ⏸️ NOT STARTED

| Step | Command | Status | Notes |
|------|---------|--------|-------|
| 4a | `/complete-task` (all) | ⏸️ Pending | 0/X tasks complete |
| 4b | `/update-claude-md` | ⏸️ Pending | 0 learnings captured |

### Learnings Captured

| Category | Learning | Source Task | Added to CLAUDE.md |
|----------|----------|-------------|-------------------|
| _None yet_ | - | - | - |

---

## Demo Validation Status

| Demo | Description | Status | Validating Tasks | All Complete? |
|------|-------------|--------|------------------|---------------|
| Demo 1 | [description] | ⏸️ Pending | [tasks] | ❌ |
| ... | ... | ... | ... | ... |

---

## User Journey Validation Status

| Step | Description | Status | Implementing Tasks | All Complete? |
|------|-------------|--------|-------------------|---------------|
| 1 | [step description] | ⏸️ Pending | [tasks] | ❌ |
| ... | ... | ... | ... | ... |

---

## Command Execution Log

| Date | Command | Result | Notes |
|------|---------|--------|-------|
| [date] | [command] | ⏸️ | - |

---

## Milestones

| Milestone | Target | Status | Completed |
|-----------|--------|--------|-----------|
| [milestone] | Day X | ⏸️ Pending | - |

---

## Blockers & Risks

| ID | Description | Blocking | Severity | Status | Resolution |
|----|-------------|----------|----------|--------|------------|
| _None_ | - | - | - | - | - |

---

## Timeline

| Date | Event |
|------|-------|
| [date] | Project started |

---

## Quick Commands

```bash
# Execute tasks
/execute-task [WS-ID] [feature-name]

# Check task status
cat docs/workstreams/[feature-name]/STATUS.md

# Run quality checks
/run-checks
```

---

## Automatic Update Triggers

This EXECUTION_STATUS.md is updated when:

| Command | Updates |
|---------|---------|
| `/breakdown-design` | Phase 2 step 2a, command log |
| `/create-workstream` | Phase 2 step 2b, 2c |
| `/create-task-ticket` | Phase 2 step 2d |
| `/execute-task` | Phase 3 batch status, command log |
| `/complete-task` | Batch progress, learnings, demo/journey validation |
| `/run-checks` | Quality gates |
| Phase transition | Move to next phase section |

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete |
| ⏳ | In Progress / Ready |
| ⏸️ | Not Started / Blocked |
| 🚫 | Blocked (external issue) |
| ❌ | Not Done |

---

*This is the execution status for [Feature Name]. For detailed task-level tracking, see [STATUS.md](./workstreams/[feature-name]/STATUS.md).*
