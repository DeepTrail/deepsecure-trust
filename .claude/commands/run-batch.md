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

**c. Verify PLAN phase was fully completed (all 7 required files):**

> **WHY THIS CHECK EXISTS:** The mvp-foundation workstream was created manually without running
> the full pipeline. `/run-batch` accepted it as valid because it only checked for 3 files.
> These checks enforce that `/run-plan` was actually completed — including the user-approval
> checkpoint — before execution begins.

```bash
FEATURE="[feature-name]"

# Core execution files (already checked above)
ls docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md
ls docs/workstreams/${FEATURE}/WORKSTREAM.md
ls docs/workstreams/${FEATURE}/STATUS.md

# PLAN phase completion proof
ls docs/workstreams/${FEATURE}/BREAKDOWN.md
ls docs/workstreams/${FEATURE}/CODEBASE_ANALYSIS.md
ls docs/workstreams/${FEATURE}/MERGE_POINTS.md
ls docs/workstreams/${FEATURE}/PIPELINE_STATE.md
```

If ANY of the four proof files are missing, STOP and report:

    ## Pre-Flight FAILED: PLAN Phase Incomplete

    The following files are missing — proving the PLAN phase was not fully completed:

    | File | Status | Proves |
    |------|--------|--------|
    | `BREAKDOWN.md` | ❌ MISSING | `/breakdown-design` was run |
    | `CODEBASE_ANALYSIS.md` | ❌ MISSING | `/explore-codebase` was run |
    | `MERGE_POINTS.md` | ❌ MISSING | `/create-workstream` fully completed |
    | `PIPELINE_STATE.md` | ❌ MISSING | user reviewed and approved the plan |

    **Fix:** Run the full PLAN phase before executing:
    ```
    /run-plan [feature-name] [design-doc-path]
    ```

    Or if you have a design doc and want to run the missing steps individually:
    - Missing BREAKDOWN.md or CODEBASE_ANALYSIS.md → `/breakdown-design [design-doc-path]`
    - Missing MERGE_POINTS.md → `/create-workstream [feature-name]`
    - Missing PIPELINE_STATE.md → run `/run-plan` to completion (checkpoint approval required)

    **Do NOT manually create these files** to pass the check — they must be generated
    by the commands above to contain valid content.

**d. Report pre-flight status:**

    ## Pre-Flight: Batch [N] — [feature-name]

    | Check | Status |
    |-------|--------|
    | Feature branch | ✅ `feature/[name]` |
    | Prior batch complete | ✅ (or N/A for Batch 1) |
    | BATCH_EXECUTION_PLAN.md exists | ✅ |
    | WORKSTREAM.md exists | ✅ |
    | STATUS.md exists | ✅ |
    | BREAKDOWN.md exists | ✅ (proves /breakdown-design was run) |
    | CODEBASE_ANALYSIS.md exists | ✅ (proves /explore-codebase was run) |
    | MERGE_POINTS.md exists | ✅ (proves /create-workstream fully completed) |
    | PIPELINE_STATE.md exists | ✅ (proves user approved plan at /run-plan checkpoint) |

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

### Step 6: Spec-Implementation Audit & Gap Fix

> **WHY THIS STEP EXISTS:** When specs/tickets and implementation are created in parallel (or even sequentially), drift happens. Barrel exports get missed, E2E test plans from specs don't get fully implemented, form validation edge cases listed in specs get skipped. This step catches and fixes those gaps automatically before the batch is marked complete.

**MANDATORY:** This step runs after ALL waves are complete and BEFORE `/verify-batch-completion`. Never skip it.

#### 6a. Audit Each Task

For each task in the batch:

1. **Read the task spec** at `docs/workstreams/[feature-name]/specs/WS-[ID]-spec.md`
2. **Read the task ticket** at `docs/workstreams/[feature-name]/tasks/WS-[ID]-*.md`
3. **Read the implementation files** listed in the spec's "Files" section
4. **Systematically compare** spec/ticket against implementation for gaps:

| Audit Dimension | What to Check | Common Gaps |
|----------------|---------------|-------------|
| **Acceptance criteria** | Every AC checkbox in spec has a corresponding implementation | Missing exports, incomplete configurations |
| **File list** | Every file in spec's "Files to Create/Modify" exists | Missing barrel exports, missing test files |
| **Test coverage** | Test plan in spec vs actual test file contents | E2E feature tests listed but not implemented, edge cases listed but not tested |
| **API contracts** | Endpoint shapes, request/response types match | Schema mismatches, missing error handlers |
| **UI components** | Component interfaces, props, behaviors match spec | Missing props, missing a11y attributes |
| **Configuration** | Config changes listed in spec are applied | Missing headers, missing env vars |

#### 6b. Classify Gaps

For each gap found, classify severity:

| Severity | Definition | Action |
|----------|-----------|--------|
| **Critical** | Acceptance criterion not met, feature broken | Must fix before proceeding |
| **Medium** | Spec lists something that exists partially or is structurally incomplete | Fix — likely a few lines of code or a few test cases |
| **Minor** | Cosmetic or documentation-only gap | Fix inline if quick (<5 min), otherwise note and proceed |
| **Negligible** | Implementation is actually better than spec (e.g., stronger security headers) | No fix needed — note as intentional improvement |

#### 6c. Report Gaps

Present audit findings:

    ## Spec-Implementation Audit: Batch [N]

    ### [WS-ID]: [Task Name]
    | # | Gap | Severity | Spec Reference | Implementation State |
    |---|-----|----------|---------------|---------------------|
    | 1 | Missing barrel export for X | Minor | AC #11 | Not exported from index.ts |
    | 2 | E2E feature tests not implemented | Medium | Test Plan rows 4-8 | Only smoke tests present |

    **Total gaps:** [count]
    **Critical:** [count] | **Medium:** [count] | **Minor:** [count] | **Negligible:** [count]

#### 6d. Fix All Gaps

**Automatically fix all Critical, Medium, and Minor gaps.** Do not ask the user — just fix them.

For each gap:

1. Make the code change (add export, add test, fix config, etc.)
2. Run `ReadLints` on modified files
3. If the gap involves tests, run the relevant test suite to verify
4. Track what was fixed

#### 6e. Verify Fixes

After all gaps are fixed:

```bash
# Run full test suite for the service
cd [service-directory]
npm test -- --run  # or pytest, depending on service

# Verify no new lint errors
# ReadLints on all files modified during gap fixes
```

**If any fix introduces new failures:** Fix the cascading issue. Do not proceed with broken tests.

#### 6f. Report Summary

    ## Audit Complete: Batch [N]

    | Task | Gaps Found | Gaps Fixed | Status |
    |------|-----------|-----------|--------|
    | [WS-ID] | 3 (0C, 2M, 1m) | 3 | ✅ All gaps closed |
    | [WS-ID] | 0 | 0 | ✅ Clean |
    | [WS-ID] | 1 (0C, 0M, 0m, 1N) | 0 (negligible) | ✅ No action needed |

    **Tests after fixes:** [X] passing, [Y] failing
    **Lint:** ✅ Clean

Proceed to Step 7 (Verify Batch Completion).

### Step 7: Verify Batch Completion

After audit is complete and all gaps are fixed:

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

### Step 8: Checkpoint — Report Results

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
| "The audit step is redundant — tests already pass" | Tests verify behavior, not spec compliance. Batch 6 found 3 CRITICAL security gaps and 10 MEDIUM gaps despite 414 passing tests. |
| "I will skip the audit for simple batches" | Every batch in Batch 4-6 had spec-implementation gaps. The audit takes ~2 minutes and catches real issues. Never skip it. |

## Red Flags

- Starting Wave 2 before Wave 1 completes
- Spawning subagents for 2-3 tasks (overhead exceeds benefit)
- Not checking for already-completed tasks when resuming
- Skipping `/verify-batch-completion` after the last wave
- **Skipping the Step 6 spec-implementation audit**
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
8. **Audit** — read all 4 specs/tickets, compare against implementations, fix any gaps
9. **Verify** — `/verify-batch-completion 1 frontend-architecture`
10. **Checkpoint** — report results, ask user to proceed

Total time: ~1 session instead of manually running 13 commands.
