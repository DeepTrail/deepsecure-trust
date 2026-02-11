# Create Batch Execution Plan

Generate a comprehensive batch execution plan with wave analysis, dependency graphs, and commands for a design.

> **Note:** This command is automatically called by `/breakdown-design` after creating the workstream structure.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /create-task-spec → /create-task-ticket
                                               ↑
                                          (YOU ARE HERE)
```

## Usage

```
/create-batch-execution-plan [feature-name]
```

**Parameters:**
- `[feature-name]`: The design/feature name (e.g., `virtual-mcp-server-mvp`)

**Output:**
- Creates `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md`

---

## Instructions

### 1. Read the Breakdown Document

Read the breakdown document to extract all task information:

```
docs/[feature-name]-breakdown.md
```

or

```
docs/deepsecure-[feature-name]-breakdown.md
```

Extract:
- All workstreams and their tasks
- Task dependencies (the "Dependencies" column)
- Task sizes (S, M, L)
- Batch assignments
- Worktree assignments (which service: control plane vs gateway)
- Merge points

### 2. Read the Workstream File

Read for additional context:

```
docs/workstreams/[feature-name]/WORKSTREAM.md
```

Extract:
- Current batch status
- Worktree paths and branches
- Any completed tasks (to mark dependencies as ✅)

### 3. Build Dependency Graph

For each batch, analyze internal dependencies:

1. **List all tasks in the batch**
2. **For each task, check if any dependencies are ALSO in this batch**
   - If dependency is in a previous batch → mark as ✅ (satisfied)
   - If dependency is in THIS batch → creates a wave dependency
3. **Group tasks into waves:**
   - Wave 1: All tasks whose dependencies are ALL satisfied (from prior batches)
   - Wave 2: Tasks that depend on Wave 1 tasks
   - Wave 3: Tasks that depend on Wave 2 tasks
   - Continue until all tasks assigned

### 4. Determine Worktree Assignment

Map each task to its worktree based on workstream:

| Workstream | Typical Worktree | Service |
|------------|------------------|---------|
| A (Control Plane) | vmcp-control | deeptrail-control |
| B (Gateway Core) | vmcp-gateway | deeptrail-gateway |
| C (Auth) | Split - check each task | Both services |
| D (Backend) | vmcp-gateway | deeptrail-gateway |
| E (Audit) | Split - check each task | Both services |
| F (Integration) | vmcp-gateway | Tests/examples |

**For C and E workstreams, check the file paths in the task:**
- Files in `deeptrail-control/` → vmcp-control
- Files in `deeptrail-gateway/` → vmcp-gateway

### 5. Generate the Execution Plan

Create `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md` with the following structure:

---

## Output Template

```markdown
# Batch Execution Plan: [Feature Name]

> **Generated from:** [breakdown-doc-path]
>
> **Design Doc:** [design-doc-path]
>
> **Last Updated:** [date]

---

## Quick Reference

| Batch | Total Tasks | Waves | Fully Parallel? | Worktrees |
|-------|-------------|-------|-----------------|-----------|
| [n] | [count] | [waves] | [✅ Yes / ❌ No] | [list] |
...

---

## Worktree Reference

| Worktree | Path | Branch | Workstreams |
|----------|------|--------|-------------|
| [name] | [path] | [branch] | [workstreams] |
...

---

## Batch [N]: [Description] ([X] tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| [ID] | [desc] | [deps or None] | [worktree] |
...

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | [tasks] | [tasks] |
| **2** | [tasks] | [tasks] |
...

### Visual Dependency Graph

```
CONTROL (worktree-control)      GATEWAY (worktree-gateway)
──────────────────────          ─────────────────────────

Wave 1:    [task] ────┐              [task] ──────┐
                      │                           │
Wave 2:               ▼                           ▼
           [task] ────┤              [task] ──────┤
                      │                           │
                      └─────────┬─────────────────┘
                                │
                        [Batch N Complete]
```

### Execution Strategy

[Description of parallel vs sequential requirements]

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH [N] - [WAVE DESCRIPTION]
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd [main-repo-path]
/create-task-spec [N] [feature-name]  # Creates specs for all tasks in this batch

# --- Create Task Tickets (after specs approved) ---
/create-task-ticket WS-[ID] [feature-name]
...

# ───────────────────────────────────────────────────────────────
# WAVE 1: [tasks]
# ───────────────────────────────────────────────────────────────

# Terminal 1: [worktree-1]
cd [worktree-1-path]
/execute-task WS-[ID] [feature-name]
/complete-task WS-[ID] [feature-name]
...

# Terminal 2: [worktree-2]
cd [worktree-2-path]
/execute-task WS-[ID] [feature-name]
/complete-task WS-[ID] [feature-name]
...

# ⏸️ WAIT: [description of what to wait for]

# ───────────────────────────────────────────────────────────────
# WAVE 2: [tasks]
# ───────────────────────────────────────────────────────────────
...

# --- Sync Status (from main repo) ---
cd [main-repo-path]
/sync-worktree-status [feature-name]
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | [X]% ([description]) |
| **Waves** | [count] |
| **Bottleneck** | [task or None] |
| **Merge Point** | [MP or None] |
| **Unblocks** | [next batch tasks] |

---

[Repeat for each batch...]

---

## Overall Execution Summary

### Batch Parallelism Overview

| Batch | Tasks | Waves | Parallel % | Cross-Worktree? |
|-------|-------|-------|------------|-----------------|
...

### Merge Points Summary

| Point | After Batch | Converging | Actions Required |
|-------|-------------|------------|------------------|
...

### Total Commands Needed

| Command Type | Count |
|--------------|-------|
| `/create-task-spec` | [total batches] (one per batch) |
| `/create-task-ticket` | [total tasks] |
| `/execute-task` | [total tasks] |
| `/complete-task` | [total tasks] (auto after execute) |
| `/sync-worktree-status` | [total batches] |
| Merge Point actions | [count] |
| **Total** | [sum] |

### Critical Path

```
[task] → [task] → ... → [task]
│                            │
└────── [X] days minimum ────┘
```

### Worktree Distribution

| Worktree | Tasks |
|----------|-------|
| **[worktree]** | [task list] ([count] tasks) |
...

---

*Generated by `/create-batch-execution-plan` command*
```

---

## Wave Calculation Algorithm

```python
def calculate_waves(batch_tasks, completed_tasks):
    """
    Calculate which wave each task belongs to.
    
    Args:
        batch_tasks: Dict[task_id, List[dependency_ids]]
        completed_tasks: Set[task_id] - tasks completed in prior batches
    
    Returns:
        Dict[wave_num, List[task_id]]
    """
    waves = {}
    assigned = set()
    wave_num = 1
    
    while len(assigned) < len(batch_tasks):
        current_wave = []
        
        for task_id, deps in batch_tasks.items():
            if task_id in assigned:
                continue
            
            # Check if all dependencies are satisfied
            deps_satisfied = all(
                dep in completed_tasks or dep in assigned
                for dep in deps
            )
            
            # For wave 1, only count prior-batch deps
            if wave_num == 1:
                deps_satisfied = all(
                    dep in completed_tasks
                    for dep in deps
                )
            
            if deps_satisfied:
                current_wave.append(task_id)
        
        if not current_wave:
            raise ValueError(f"Circular dependency detected in batch")
        
        waves[wave_num] = current_wave
        assigned.update(current_wave)
        completed_tasks.update(current_wave)
        wave_num += 1
    
    return waves
```

---

## Parallelism Calculation

```
Parallelism % = (Max parallel tasks in any wave / Total tasks) * 100

Example:
- Batch has 9 tasks
- Wave 1: 3 tasks (parallel)
- Wave 2: 2 tasks (parallel)  
- Wave 3: 2 tasks (parallel)
- Wave 4: 2 tasks (parallel)

Parallelism = 3/9 = 33% (or weighted average: (3+2+2+2)/(4*3) = 9/12 = 75%)
```

Use the **maximum concurrent tasks** interpretation:
- If Wave 1 has 3 parallel tasks and that's the max → 33%
- Or use **cross-worktree parallelism**: control and gateway always parallel → 100% cross-worktree

---

## Example Output

See `docs/workstreams/virtual-mcp-server-mvp/BATCH_EXECUTION_PLAN.md` for a complete example.

---

## Post-Creation Steps

After creating the execution plan:

1. **Link from WORKSTREAM.md:**
   ```markdown
   ## Execution
   
   > **Batch Execution Plan:** [BATCH_EXECUTION_PLAN.md](./BATCH_EXECUTION_PLAN.md)
   ```

2. **Link from STATUS.md:**
   Add reference in the header section

3. **Commit the file:**
   ```bash
   git add docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md
   git commit -m "Add batch execution plan for [feature-name]"
   ```

---

## Related Commands

| Command | Purpose |
|---------|---------|
| `/breakdown-design` | Creates the breakdown document (input) |
| `/create-workstream` | Creates WORKSTREAM.md |
| `/create-task-spec` | Creates specs for a batch (run before tickets) |
| `/create-task-ticket` | Creates individual task tickets |
| `/execute-task` | Executes a task |
| `/complete-task` | Marks task complete (auto after execute) |
| `/sync-worktree-status` | Syncs status across worktrees |
