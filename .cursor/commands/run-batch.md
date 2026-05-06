# Run Batch: Automated Batch Orchestration

Automate the full lifecycle of a single batch: parse the batch execution plan, create specs, create tickets, execute tasks respecting wave order (parallelizing independent tasks via subagents), verify completion, and checkpoint with the user.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /run-batch
                                                                            ↑
                                                                       (YOU ARE HERE)

Internally invokes (in order):
  /create-task-spec → /create-task-ticket → /execute-task → /verify-batch-completion

Replaces the manual "Batch Execution Pattern" loop from DEVELOPER_WORKFLOW.md.
```

## Invocation

```
/run-batch [batch-number] [feature-name]
```

**Examples:**

    /run-batch 1 frontend-architecture
    /run-batch 4 frontend-architecture
    /run-batch 8 virtual-mcp-server-mvp

---

## Instructions

### Step 1: Parse Batch Execution Plan

Read the batch execution plan and extract all information for the requested batch:

```
Read: docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md
```

**Extract these sections for Batch N:**

| Section | What to Extract | Used For |
|---------|----------------|----------|
| **Dependencies table** | Task IDs, descriptions, dependencies, complexity, service | Task list for this batch |
| **Wave Analysis table** | Wave number → task assignments | Execution ordering |
| **Visual Dependency Graph** | ASCII graph | Understanding parallel vs sequential |
| **Execution Strategy** | Prose description | Decision-making for parallelization |
| **Merge Point** (if any) | MP number, tag name, validation steps | Post-batch merge point handling |

**Build the internal execution model:**

    BATCH = {
        number: N,
        feature: "[feature-name]",
        tasks: [
            { id: "WS-A1", description: "...", dependencies: ["None"], complexity: "L", service: "frontend" },
            { id: "WS-A3", description: "...", dependencies: ["A1"], complexity: "S", service: "frontend" },
            ...
        ],
        waves: [
            { number: 1, tasks: ["WS-A1"] },
            { number: 2, tasks: ["WS-A3", "WS-A4", "WS-A5"] },
        ],
        merge_point: null | { id: "MP1", tag: "mp1-dashboard-complete", validation: "..." },
    }

### Step 2: Pre-Flight Checks

Before executing anything, verify readiness:

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
```

**a. Verify feature branch exists (Batch 1 only):**

```bash
git branch --show-current
# If not on feature branch and this is Batch 1:
git checkout -b feature/[feature-name] dev 2>/dev/null || git checkout feature/[feature-name]
```

**b. Verify prior batch is complete (Batch 2+):**

```bash
# Check STATUS.md for previous batch completion
grep -c "Complete" docs/workstreams/[feature-name]/STATUS.md
```

If the prior batch is NOT complete, STOP and report:

    ## Pre-Flight FAILED: Prior Batch Incomplete

    Batch [N-1] has not been verified as complete.
    Run `/verify-batch-completion [N-1] [feature-name]` first,
    or run `/run-batch [N-1] [feature-name]` to complete it.

**c. Verify workstream directory exists:**

```bash
ls docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md
ls docs/workstreams/[feature-name]/WORKSTREAM.md
ls docs/workstreams/[feature-name]/STATUS.md
```

**d. Report pre-flight status:**

    ## Pre-Flight: Batch [N] — [feature-name]

    | Check | Status |
    |-------|--------|
    | Feature branch | ✅ `feature/[name]` |
    | Prior batch complete | ✅ (or N/A for Batch 1) |
    | BATCH_EXECUTION_PLAN.md exists | ✅ |
    | WORKSTREAM.md exists | ✅ |
    | STATUS.md exists | ✅ |

    **Tasks in this batch:** [count]
    **Waves:** [count]
    **Estimated effort:** [S/M/L tasks breakdown]

    Proceeding with batch execution...

### Step 3: Create Task Specifications

Invoke `/create-task-spec` for this batch:

    /create-task-spec [batch-number] [feature-name]

This creates spec files for all tasks in the batch at:

    docs/workstreams/[feature-name]/specs/[WS-ID]-spec.md

**Verification:** After spec creation, confirm all spec files exist:

```bash
for TASK_ID in [list of task IDs]; do
  ls docs/workstreams/[feature-name]/specs/${TASK_ID}-spec.md 2>/dev/null && echo "✅ $TASK_ID spec" || echo "❌ $TASK_ID spec MISSING"
done
```

### Step 4: Create Task Tickets

Create a ticket for each task in the batch:

    /create-task-ticket [WS-ID] [feature-name]

Repeat for every task in the batch. Create tickets in wave order (Wave 1 first, then Wave 2) so that dependencies are clear when creating downstream tickets.

**Verification:** After ticket creation, confirm all ticket files exist:

```bash
for TASK_ID in [list of task IDs]; do
  ls docs/workstreams/[feature-name]/tasks/${TASK_ID}-*.md 2>/dev/null && echo "✅ $TASK_ID ticket" || echo "❌ $TASK_ID ticket MISSING"
done
```

### Step 5: Execute Waves

This is the core orchestration step. Execute each wave in order, parallelizing independent tasks within a wave.

**FOR EACH WAVE (in order, 1, 2, ...):**

#### 5a. Determine Parallelization Strategy

| Wave Task Count | Strategy | Rationale |
|----------------|----------|-----------|
| 1 task | Execute inline | No parallelization needed |
| 2-3 tasks | Execute sequentially inline | Subagent overhead exceeds benefit for small batches |
| 4+ tasks | Spawn parallel subagents | Significant time savings from parallelization |

#### 5b. Sequential Execution (1-3 tasks in wave)

Execute each task one by one, inline in the current agent:

    /execute-task [WS-ID] [feature-name]

The `/execute-task` command handles: reading the ticket, updating STATUS.md, implementing code, running tests, generating the completion report, and updating all status files (Steps 1-8i in execute-task.md).

Repeat for each task in the wave. After each task completes, verify it succeeded before starting the next.

#### 5c. Parallel Execution (4+ tasks in wave)

Spawn background subagents for parallel execution. Use `best-of-n-runner` subagent type — each gets its own isolated git worktree.

**Subagent prompt template:**

For each task in the wave, spawn a subagent with this prompt:

    You are executing task [WS-ID] for the [feature-name] workstream.

    CONTEXT:
    - Main repo: /Users/imaxxs/repositories/deepsecure-mvp
    - Feature: [feature-name]
    - Task ID: [WS-ID]
    - Task ticket: docs/workstreams/[feature-name]/tasks/[WS-ID]-[task-name].md

    INSTRUCTIONS:
    1. Read the task ticket at the path above
    2. Read the task spec at docs/workstreams/[feature-name]/specs/[WS-ID]-spec.md
    3. Follow the /execute-task workflow:
       a. Update STATUS.md — mark task as in progress
       b. Verify dependencies are complete
       c. Implement the code as specified in the ticket
       d. Run lints on all modified files
       e. Run tests as specified in the ticket's Validation section
       f. Verify all acceptance criteria
       g. Create completion report at docs/workstreams/[feature-name]/reports/[WS-ID]-completion.md
       h. Update task ticket status to completed
       i. Update STATUS.md and WORKSTREAM.md
    4. Return a structured summary:
       - Task ID and name
       - Files created/modified (list)
       - Tests: pass/fail count
       - Acceptance criteria: met/unmet count
       - Any blockers or issues encountered

**Spawning pattern:**

```
# Launch all wave tasks in parallel as background subagents
Task(
    subagent_type="best-of-n-runner",
    description="Execute [WS-ID]: [task-name]",
    prompt="[subagent prompt from template above]",
    run_in_background=True
)

# Repeat for each task in the wave
# All subagents run concurrently
```

**Wait for all subagents to complete** before proceeding to the next wave. The system will notify when each background subagent finishes.

#### 5d. Wave Completion Gate

**CRITICAL: Do NOT start the next wave until ALL tasks in the current wave have completed successfully.**

After all tasks in a wave complete:

1. Verify each task's completion report exists:
   ```bash
   for TASK_ID in [wave tasks]; do
     ls docs/workstreams/[feature-name]/reports/${TASK_ID}-completion.md 2>/dev/null && echo "✅ $TASK_ID" || echo "❌ $TASK_ID"
   done
   ```

2. If any task FAILED:
   - Report the failure to the user
   - Attempt to fix inline if the error is clear
   - If the fix requires user input, STOP and report

3. If all tasks succeeded, proceed to the next wave

#### 5e. Sync Worktree Status (after parallel waves only)

**Run this step ONLY when Step 5c was used** (i.e., 4+ tasks spawned parallel subagents via `best-of-n-runner`). Skip for sequential execution (Step 5b).

Each `best-of-n-runner` subagent operates in its own isolated git worktree. When multiple subagents update STATUS.md and WORKSTREAM.md concurrently, the last write wins and earlier updates are lost. This step consolidates all worktree status into the main repo before batch verification.

    /sync-worktree-status [feature-name]

**What this does:**
- Scans all worktrees for completion reports, STATUS.md, and WORKSTREAM.md changes
- Merges completed task entries from all worktrees into the main repo's status files
- De-duplicates and reconciles any conflicting status entries
- Copies completion reports from worktree `reports/` directories to the main repo

**Verification after sync:**

```bash
# Confirm all wave tasks appear as completed in main repo STATUS.md
for TASK_ID in [parallel wave tasks]; do
  grep -q "$TASK_ID.*[Cc]omplete" docs/workstreams/[feature-name]/STATUS.md && echo "✅ $TASK_ID synced" || echo "❌ $TASK_ID NOT in STATUS.md"
done
```

**If sync shows discrepancies:** Report to user before proceeding. Do NOT run `/verify-batch-completion` on stale status files.

### Step 6: Verify Batch Completion

After all waves are complete (and status is synced if parallel subagents were used):

    /verify-batch-completion [batch-number] [feature-name]

**If this batch triggers a merge point** (check the parsed batch plan):

```bash
# Create merge point tag
git tag [tag-name]
# Example: git tag mp1-dashboard-complete
```

Report merge point status:

    ## Merge Point [MP-ID] Reached

    | Field | Value |
    |-------|-------|
    | **Merge Point** | [MP-ID] |
    | **After Batch** | [N] |
    | **Tag** | `[tag-name]` |
    | **Converging Tasks** | [task list] |
    | **Enables** | [what gets unblocked] |

### Step 7: Checkpoint — Report Results

**MANDATORY: Always checkpoint with the user after each batch.**

Present the batch completion report:

    ## Batch [N] Complete: [Batch Title]

    ### Execution Summary

    | Metric | Value |
    |--------|-------|
    | **Batch** | [N] of [total batches] |
    | **Tasks Completed** | [count] |
    | **Waves** | [count] |
    | **Parallelization** | [X% — Y of Z tasks ran in parallel] |
    | **Merge Point** | [MP-ID reached / None] |

    ### Task Results

    | Task | Status | Tests | Files | Notes |
    |------|--------|-------|-------|-------|
    | [WS-ID] | ✅ Complete | 5/5 pass | 3 created | — |
    | [WS-ID] | ✅ Complete | 8/8 pass | 2 modified | — |

    ### Quality Summary
    - Lint: ✅ All files pass
    - Tests: ✅ [X] tests passing
    - Acceptance criteria: ✅ All met

    ### What This Batch Unblocks
    - Batch [N+1]: [description]
    - Tasks: [list of newly unblocked tasks]

    ### Next Batch Preview
    - **Batch [N+1]:** [title] — [task count] tasks, [wave count] waves
    - **Key tasks:** [brief list]

    ---
    Proceed to Batch [N+1]? (yes / pause / review)

**Wait for user confirmation before proceeding.**

---

## Error Recovery

### Task Failure During Wave Execution

| Failure Type | Action |
|-------------|--------|
| **Lint failure** | Auto-fix with formatter, retry |
| **Test failure** | Attempt auto-fix; if cannot, report to user and pause |
| **Dependency not met** | Should not happen (wave gating prevents this); report as bug |
| **File conflict** (parallel) | Merge conflict in worktree — report to user for resolution |
| **Subagent timeout** | Check subagent output, retry if transient; report if persistent |

### Partial Batch Completion

If some tasks in a wave succeeded and others failed:

1. Record successes — do NOT re-run successful tasks
2. Report failures with specific errors
3. Options:
   - **Retry failed tasks:** Re-run only the failed tasks
   - **Skip and continue:** Mark as blocked, continue with non-dependent tasks
   - **Pause:** Wait for user to investigate

### Resuming After Failure

    /run-batch [batch-number] [feature-name]

The command checks STATUS.md for already-completed tasks in this batch and skips them. Only incomplete tasks are executed.

---

## Merge Point Reference

Merge points are defined in `BATCH_EXECUTION_PLAN.md` and `MERGE_POINTS.md`.

| Pattern | Merge Point Batch | Tag |
|---------|-------------------|-----|
| `MP1` | After Batch 5 | `mp1-*-complete` |
| `MP2` | After Batch 7 | `mp2-*-complete` |
| `MP3` | After Batch 9 | `mp3-*-complete` |

The exact tag names are feature-specific — read them from `BATCH_EXECUTION_PLAN.md`.

---

## Common Rationalizations

| Rationalization | Why It Is Wrong |
|----------------|----------------|
| "I will skip specs for simple tasks" | Specs define contracts. Without them, tickets lack precision and agents guess. |
| "3 tasks is enough to parallelize" | Subagent startup overhead (~30s) exceeds benefit for 2-3 small tasks. Sequential is faster. |
| "Wave gating is unnecessary — all tasks are independent" | The batch plan analyzed dependencies. Trust the wave analysis. |
| "I will skip the checkpoint — the user said to keep going" | Checkpoints catch errors early. One bad task can cascade through all downstream batches. |
| "I will create all tickets at once, then execute all at once" | Tickets for Wave 2 tasks may reference Wave 1 outputs. Create in wave order. |
| "The batch failed, I will re-run everything" | Check which tasks succeeded. Re-running completed tasks wastes time and may cause conflicts. |

## Red Flags

- Starting Wave 2 before Wave 1 completes
- Spawning subagents for 2-3 tasks (overhead exceeds benefit)
- Not checking for already-completed tasks when resuming
- Skipping `/verify-batch-completion` after the last wave
- Not creating the merge point tag when required
- Proceeding past a failed task without user acknowledgment
- Not presenting the checkpoint report to the user

---

## Verification Checklist

After running `/run-batch`, verify:

```bash
FEATURE="[feature-name]"
BATCH="[N]"

echo "=== Batch $BATCH Verification ==="

echo ""
echo "--- Specs ---"
ls docs/workstreams/$FEATURE/specs/ 2>/dev/null | wc -l
echo "spec files"

echo ""
echo "--- Tickets ---"
ls docs/workstreams/$FEATURE/tasks/ 2>/dev/null | wc -l
echo "ticket files"

echo ""
echo "--- Completion Reports ---"
ls docs/workstreams/$FEATURE/reports/ 2>/dev/null | wc -l
echo "completion reports"

echo ""
echo "--- STATUS.md ---"
grep -c "Complete" docs/workstreams/$FEATURE/STATUS.md 2>/dev/null
echo "completed task entries"

echo ""
echo "--- WORKSTREAM.md ---"
grep -c "completed\|Complete" docs/workstreams/$FEATURE/WORKSTREAM.md 2>/dev/null
echo "completed task entries"

echo "=== Done ==="
```

---

## Related Commands

| Command | Relationship |
|---------|-------------|
| `/create-batch-execution-plan` | Produces the `BATCH_EXECUTION_PLAN.md` this command reads (input) |
| `/create-task-spec` | Invoked internally for spec creation (sub-step) |
| `/create-task-ticket` | Invoked internally for ticket creation (sub-step) |
| `/execute-task` | Invoked internally for task implementation (sub-step) |
| `/verify-batch-completion` | Invoked internally for batch verification (sub-step) |
| `/pipeline` | Can invoke `/run-batch` in its EXECUTE phase (parent) |

---

## Example: Running Batch 1 of frontend-architecture

```
/run-batch 1 frontend-architecture
```

The agent will:

1. **Parse** `BATCH_EXECUTION_PLAN.md` — find Batch 1: 4 tasks (A1, A3, A4, A5), 2 waves
2. **Pre-flight** — create branch `feature/frontend-architecture`, verify directories
3. **Specs** — `/create-task-spec 1 frontend-architecture` (creates 4 spec files)
4. **Tickets** — create tickets for WS-A1, WS-A3, WS-A4, WS-A5
5. **Wave 1** — execute WS-A1 inline (single task, no parallelization)
6. **Wave gate** — verify A1 completion report exists
7. **Wave 2** — execute WS-A3, WS-A4, WS-A5 sequentially (3 tasks = below parallel threshold)
8. **Verify** — `/verify-batch-completion 1 frontend-architecture`
9. **Checkpoint** — report results, ask user to proceed

Total time: ~1 session instead of manually running 13 commands.
