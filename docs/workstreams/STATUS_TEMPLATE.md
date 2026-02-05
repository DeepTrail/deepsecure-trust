# [Feature Name]: Task Status

> **Execution Status:** [EXECUTION_STATUS.md](../../[feature-name]/EXECUTION_STATUS.md) ← Phase tracking
>
> **Workstream Details:** [WORKSTREAM.md](./WORKSTREAM.md)
>
> **Last Updated:** [Date]

---

## Current Task Overview

| Metric | Value |
|--------|-------|
| **Current Batch** | Batch X (of Y) |
| **Tasks Complete** | 0/X (0%) |
| **Tasks In Progress** | 0 |
| **Tasks Ready** | 0 |
| **Tasks Blocked** | 0 |
| **Active Worktrees** | 0 |

---

## Batch Progress

```
Batch 1  [░░░░░░░░░░] 0%   ← CURRENT
Batch 2  [░░░░░░░░░░] 0%   (blocked by Batch 1)
...
```

---

## Current Batch: Batch X

| Task ID | Task Name | Status | Worktree | Assignee |
|---------|-----------|--------|----------|----------|
| [ID](./tasks/WS-ID-*.md) | Task name | `ready` | - | - |

**Batch X Commands:**
```bash
/execute-task WS-ID [feature-name]
```

---

## Parallel Execution Status

### Active Worktrees

| Worktree | Branch | Working On | Status |
|----------|--------|------------|--------|
| _None active_ | - | - | - |

### Merge Points Status

| Point | Converging Tasks | Status | Merged At |
|-------|------------------|--------|-----------|
| **MP1** | [tasks] | ⏸️ Pending | - |

---

## Workstream Status

| WS | Name | Status | Progress | Tasks Done |
|----|------|--------|----------|------------|
| **A** | [Workstream Name] | ⏸️ Ready | 0% | 0/X |
| **B** | [Workstream Name] | ⏸️ Blocked | 0% | 0/X |

---

## All Tasks by Status

### ✅ Completed (0)

| Task ID | Task Name | Completed | Report |
|---------|-----------|-----------|--------|
| _None yet_ | - | - | - |

### 🔄 In Progress (0)

| Task ID | Task Name | Started | Assignee | Worktree |
|---------|-----------|---------|----------|----------|
| _None yet_ | - | - | - | - |

### ⏳ Ready (0)

| Task ID | Task Name | Batch | Ticket |
|---------|-----------|-------|--------|
| _None yet_ | - | - | - |

### ⏸️ Pending (0)

<details>
<summary>Click to expand pending tasks</summary>

| Task ID | Task Name | Batch | Blocked By |
|---------|-----------|-------|------------|
| _None yet_ | - | - | - |

</details>

### 🚫 Blocked (0)

| Task ID | Task Name | Blocked By | Reason |
|---------|-----------|------------|--------|
| _None_ | - | - | - |

---

## Blockers & Issues

| ID | Description | Blocking | Severity | Status | Resolution |
|----|-------------|----------|----------|--------|------------|
| _None_ | - | - | - | - | - |

---

## Quick Commands Reference

### Create Worktrees (if parallel execution)
```bash
# Create worktrees from dev branch
git worktree add ../[worktree-name] -b feature/[branch-name] dev

# Copy .cursor/commands to each worktree (required for commands to work)
cp -r .cursor ../[worktree-name]/
```

### Execute Tasks
```bash
/execute-task WS-ID [feature-name]
```

### Complete a Task
```bash
/complete-task WS-ID [feature-name]
```

### Run Quality Checks
```bash
/run-checks
```

### At Merge Points
```bash
git merge [branch-1] [branch-2]
```

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete |
| 🔄 | In Progress |
| ⏳ | Ready (can start) |
| ⏸️ | Pending (waiting on dependencies) |
| 🚫 | Blocked (external issue) |

---

## Automatic Update Triggers

This STATUS.md file is automatically updated by:

| Command | Updates |
|---------|---------|
| `/create-task-ticket` | Adds task to Ready/Pending section, updates counts |
| `/execute-task` | Moves task to In Progress, adds start time |
| `/complete-task` | Moves task to Completed, updates progress, unblocks dependent tasks |
| `/run-checks` | Updates blockers if checks fail |

---

*This is the task status file. For phase-level execution tracking, see [EXECUTION_STATUS.md](../../[feature-name]/EXECUTION_STATUS.md).*
