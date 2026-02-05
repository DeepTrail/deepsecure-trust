# Orchestrate Feature: Design to Completion

**Agentic workflow that automates the entire design-to-completion process.**

This command orchestrates all phases automatically, only pausing for human approval at key checkpoints.

## Instructions

When given a design document, execute the following phases automatically:

---

## PHASE 1: INITIALIZATION

### Step 1.1: Validate Design Document
```
1. Read the provided design document
2. Verify it has required sections:
   - Overview/Goals
   - Technical Design
   - (Implementation Workstreams can be empty - we'll generate)
3. If missing critical sections, STOP and ask user to complete
```

### Step 1.2: Extract Feature Name
```
1. Derive feature name from design doc title or ask user
2. This becomes: [feature-name] for all subsequent operations
```

**CHECKPOINT 1**: Confirm feature name with user before proceeding

---

## PHASE 2: PLANNING (Automated)

### Step 2.1: Dependency Analysis
Execute `/breakdown-design` logic:
```
1. Identify external dependencies (APIs, services, databases)
2. Identify database/schema changes
3. Map shared state between components
4. Identify API contracts
```

### Step 2.2: Workstream Generation
```
1. Group tasks into parallel workstreams
2. Identify sequential dependencies within workstreams
3. Calculate critical path
4. Estimate complexity per task (S/M/L)
```

### Step 2.3: Create Workstream Structure
Execute `/create-workstream` logic:
```
1. Create docs/workstreams/[feature-name]/
2. Create WORKSTREAM.md with task table
3. Create tasks/ and reports/ directories
```

### Step 2.4: Generate Task Tickets
For each task identified, execute `/create-task-ticket` logic:
```
1. Create task ticket in tasks/ folder
2. Include all metadata, acceptance criteria, files to modify
3. Link dependencies between tasks
```

**CHECKPOINT 2**: Present workstream breakdown to user for approval
```
Show:
- Number of workstreams
- Number of tasks per workstream
- Dependency graph
- Critical path
- Estimated total effort

Ask: "Approve this breakdown? (yes/modify/cancel)"
```

---

## PHASE 3: EXECUTION (Parallel Agentic)

### Step 3.1: Identify Parallel Batches
```
Batch 1: All tasks with no dependencies (can run in parallel)
Batch 2: Tasks that depend only on Batch 1
Batch 3: Tasks that depend on Batch 2
... and so on
```

Output batch table:
```markdown
| Batch | Tasks (Parallel) | Depends On | Blocking For |
|-------|------------------|------------|--------------|
| 1 | A1, B1 | None | Batch 2 |
| 2 | A2, B2, B4 | Batch 1 | Batch 3, MP1 |
```

### Step 3.1.5: Identify Merge Points
```
Merge points occur when:
- Parallel workstreams must synchronize
- A task depends on tasks from multiple workstreams
- Git branches need to be merged before continuing

Output merge point table:
| Point | Converging Tasks | Enables | Git Action |
|-------|------------------|---------|------------|
| MP1 | A3 + B2 | C1 | Merge ws-a, ws-b |
```

### Step 3.2: Execute Batch (Automated with /execute-task)

For each task in current batch, run `/execute-task`:

```
For tasks in current_batch (parallel or sequential):
    /execute-task [WS-ID] [feature-name]
    
    This command automatically:
    1. Reads task ticket
    2. Updates STATUS.md (task → In Progress)
    3. Verifies dependencies are complete
    4. Evaluates implementation readiness
    5. Implements the task (create/modify files)
    6. Runs quality checks
    7. Verifies acceptance criteria
    8. Triggers /complete-task if successful
```

**Batch Execution Commands:**
```bash
# Batch 1 example (parallel)
/execute-task WS-A1 [feature-name]
/execute-task WS-B1 [feature-name]
/execute-task WS-E1 [feature-name]

# Or run all batch tasks:
/orchestrate-feature @design-doc.md --batch=1
```

**Parallel Execution Strategy:**
```
If workstreams can run in parallel:
    - Create git worktrees (from dev branch):
      git worktree add ../[feature]-ws-a -b feature/[feature]-ws-a dev
      git worktree add ../[feature]-ws-b -b feature/[feature]-ws-b dev
    
    - Copy .cursor/commands to each worktree (required for commands to work):
      cp -r .cursor ../[feature]-ws-a/
      cp -r .cursor ../[feature]-ws-b/
    
    - Run /execute-task in each worktree for respective tasks
    - Or execute sequentially in single instance
```

**If /execute-task is blocked:**
```
- Reports missing information or unmet dependencies
- Waits for user resolution
- Resume with: /execute-task [WS-ID] [feature-name]
```

### Step 3.3: Quality Gate
After each task:
```
1. Run /run-checks (lint, typecheck, tests)
2. If failures:
   - Document in completion report
   - Attempt auto-fix
   - If can't fix, flag for human review
3. If all pass: proceed to next task
```

**CHECKPOINT 3**: After each batch completes
```
Show:
- Completed tasks in batch
- Test results summary
- Any failures requiring attention

Ask: "Proceed to next batch? (yes/review-failures/pause)"
```

**CHECKPOINT 3.5**: At merge points (when parallel tracks converge)
```
Show:
- Tasks converging at this merge point
- Branches to merge (if using worktrees)
- Next tasks enabled by this merge

Actions:
1. Verify all contributing tasks complete
2. Merge git branches if using worktrees:
   git checkout dev
   git merge feature/ws-a feature/ws-b
3. Resolve any conflicts
4. Create new worktree for next phase if needed:
   git worktree add ../feature-ws-c -b feature/ws-c dev
   cp -r .cursor ../feature-ws-c/
5. Cleanup completed worktrees:
   git worktree remove ../feature-ws-a

Ask: "Merge point complete. Proceed to dependent tasks? (yes/review/pause)"
```

---

## PHASE 4: LEARNING LOOP (Automated)

### Step 4.1: Aggregate Completion Reports
```
1. Read all completion reports from reports/ folder
2. Calculate overall metrics:
   - Total accuracy %
   - Tasks completed vs planned
   - Test pass rate
   - Time estimated vs actual (if tracked)
```

### Step 4.2: Extract Learnings
```
1. Identify patterns in failures
2. Identify successful approaches
3. Check each report for "CLAUDE.md recommendations"
4. Compile list of potential CLAUDE.md updates
```

### Step 4.3: Update CLAUDE.md
```
For each learning identified:
    1. Check if similar rule already exists
    2. If new, add to appropriate section
    3. If existing, potentially strengthen
```

**CHECKPOINT 4**: Present learnings for approval
```
Show:
- Proposed CLAUDE.md additions
- Summary of feature completion
- Metrics

Ask: "Approve CLAUDE.md updates? (yes/modify/skip)"
```

### Step 4.4: Final Cleanup
```
1. Update WORKSTREAM.md with final status
2. Archive or mark workstream as complete
3. Prepare PR summary if requested
```

---

## EXECUTION MODES

### Mode 1: Fully Automated (with checkpoints)
```
User: /orchestrate-feature @design-doc.md --mode=auto

Flow:
Design → [CHECKPOINT 1] → Planning → [CHECKPOINT 2] → 
Execution → [CHECKPOINT 3 per batch] → Learning → [CHECKPOINT 4] → Done
```

### Mode 2: Phase-by-Phase (manual triggers)
```
User: /orchestrate-feature @design-doc.md --phase=planning
# Completes Phase 2, stops

User: /orchestrate-feature @design-doc.md --phase=execution  
# Completes Phase 3, stops

User: /orchestrate-feature @design-doc.md --phase=learning
# Completes Phase 4
```

### Mode 3: Single Task Focus
```
User: /orchestrate-feature @design-doc.md --task=WS-A1
# Only executes specific task
```

---

## OUTPUT FORMAT

After each phase, output structured summary:

```markdown
## Phase [N] Complete: [Phase Name]

### Completed
- [x] Step 1: ...
- [x] Step 2: ...

### Created Files
- `docs/workstreams/[feature]/WORKSTREAM.md`
- `docs/workstreams/[feature]/tasks/WS-A1-*.md`
- ...

### Metrics
- Tasks identified: X
- Parallel workstreams: Y
- Critical path length: Z tasks

### Next Steps
[What happens next or what user should do]

---
Proceed to Phase [N+1]? (yes/no)
```

---

## SUBAGENT COORDINATION (For Parallel Execution)

When executing parallel tasks, coordinate subagents:

```python
# Pseudocode for parallel execution
parallel_tasks = get_tasks_without_dependencies(current_batch)

for task in parallel_tasks:
    spawn_subagent(
        task=task,
        context={
            'task_ticket': f'docs/workstreams/{feature}/tasks/{task.id}.md',
            'worktree': f'../{feature}-{task.workstream}',
            'on_complete': 'generate_completion_report',
            'on_failure': 'flag_for_review'
        }
    )

wait_for_all_subagents()
aggregate_results()
```

---

## ERROR HANDLING

### Task Failure
```
1. Document failure in completion report
2. Mark task as "blocked" 
3. Identify dependent tasks and mark as "blocked_by: [failed_task]"
4. Present failure to user with options:
   - Retry with different approach
   - Skip and continue
   - Pause entire workflow
```

### Test Failure
```
1. Capture test output
2. Attempt auto-fix (if clear error)
3. If can't fix:
   - Add to completion report failures section
   - Continue with warning, or
   - Stop for human intervention (configurable)
```

### Git Conflicts (in worktree mode)
```
1. Detect conflict during merge
2. Present conflict to user
3. Options:
   - Manual resolution
   - Accept theirs/ours
   - Abort and retry differently
```

---

## REFERENCE

This command integrates:
- `/breakdown-design` - Phase 2 analysis
- `/create-workstream` - Phase 2 structure
- `/create-task-ticket` - Phase 2 task specs
- `/execute-task` - **Phase 3 automated implementation**
- `/run-checks` - Phase 3 quality gates
- `/complete-task` - Phase 4 reporting
- `/update-claude-md` - Phase 4 learning loop

See also:
- `docs/WORKFLOW_GUIDE.md` - Detailed phase documentation (batch model, merge points, acceptance mapping)
- `docs/PARALLEL_EXECUTION_GUIDE.md` - Worktree setup for parallel execution
- `docs/TASK_BREAKDOWN.md` - Breakdown methodology

## Real-World Example
- Design: `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md`
- Breakdown: `docs/deepsecure-virtual-mcp-server-mvp-breakdown.md`
