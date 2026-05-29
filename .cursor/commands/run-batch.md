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
/run-batch [batch-id] [feature-name] [--continue] [--auto-heal]
```

**Parameters:**
- `[batch-id]`: The batch identifier from the **first column** of the Quick Reference table
  in `BATCH_EXECUTION_PLAN.md`. Format: `P{Phase}-B{Batch}` (e.g., `P0-B1`, `P1-B2`).
- `[feature-name]`: The workstream/feature name (e.g., `agent-lifecycle`)
- `[--continue]`: *(Optional)* Auto-proceed to the next batch after successful completion. Chains all remaining batches without manual checkpoints. Stops on any failure.
- `[--auto-heal]`: *(Optional)* Enable self-healing retry loops. When a task or validation step fails, automatically investigate the error, fix it, and retest — up to a retry budget per failure class. Also enables skip-and-continue for non-blocking failures and fresh-context retries for stuck tasks. Composable with `--continue` for full AFK mode.

**How to find the batch ID:**
1. Open `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md`
2. Look at the **Quick Reference** table — the first column (`Batch`) lists all batch IDs
3. Use that exact value as the first argument

**Examples:**

    /run-batch P0-B1 agent-lifecycle
    /run-batch P0-B2 agent-lifecycle
    /run-batch P1-B1 agent-lifecycle
    /run-batch P0-B1 mvp-production-readiness

    # Auto-chain all batches from P0-B1 onwards:
    /run-batch P0-B1 ui-improvements-audit-activity --continue

    # Self-healing within a single batch (stops between batches):
    /run-batch P0-B1 ui-improvements-audit-activity --auto-heal

    # Full AFK mode (self-healing + auto-chaining):
    /run-batch P0-B1 ui-improvements-audit-activity --continue --auto-heal

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
        merge_point: null | { id: "MP1", tag: "mp1-dashboard-complete-feature/agent-lifecycle", validation: "..." },
    }

### Step 2: Pre-Flight Checks

Before executing anything, verify readiness:

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
```

**a. Verify feature branch exists (first batch only):**

```bash
git branch --show-current
# If not on feature branch and this is the first batch:
git checkout dev && git pull origin dev
git checkout -b feature/[feature-name] dev 2>/dev/null || git checkout feature/[feature-name]
```

**b. Execute Branch Setup (first batch only):**

**MANDATORY for the first batch of a workstream.** Read `BATCH_EXECUTION_PLAN.md` and check if there is a **"Branch Setup"** section. If yes, execute every command listed in its sub-steps (typically: verify pre-requisites, create feature branch, verify branch). This ensures dependencies are installed, services are running, and the branch is properly created before any task execution begins.

```
1. Read BATCH_EXECUTION_PLAN.md → find "## Branch Setup" section
2. If it exists:
   - Execute each sub-step's commands in order (npm install, docker compose up, etc.)
   - Skip any git commands already handled by Step 2a (branch creation)
   - Report each pre-requisite check result (pass/fail)
3. If the section does not exist: skip (some workstreams may not need setup)
```

**Why this matters:** Without this step, `/run-batch` would attempt to execute tasks without frontend dependencies installed, backend services running, or tool versions verified — causing avoidable failures in the first wave.

**c. Verify prior batch is complete (all batches after the first):**

```bash
# Check STATUS.md for previous batch completion
grep -c "Complete" docs/workstreams/[feature-name]/STATUS.md
```

If the prior batch is NOT complete, STOP and report:

    ## Pre-Flight FAILED: Prior Batch Incomplete

    Batch [N-1] has not been verified as complete.
    Run `/verify-batch-completion [prior-batch-id] [feature-name]` first,
    or run `/run-batch [prior-batch-id] [feature-name]` to complete it.

**d. Verify PLAN phase was fully completed (all 7 required files):**

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

**e. Report pre-flight status:**

    ## Pre-Flight: Batch [N] — [feature-name]

    | Check | Status |
    |-------|--------|
    | Feature branch | ✅ `feature/[name]` |
    | Branch Setup executed | ✅ (or N/A if no Branch Setup section / not first batch) |
    | Prior batch complete | ✅ (or N/A for first batch) |
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

    /create-task-spec [batch-id] [feature-name]

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

**Step 1: Read the Execution Strategy** from `BATCH_EXECUTION_PLAN.md` for this batch. Look for:
- The **"Execution Strategy"** prose section — it may override the default count-based heuristic
- The **"Recommended execution order within session"** — it specifies the optimal task sequence
- Warnings about **shared files** (e.g., "E1 and E2 modify the same file — do E1 first")
- Explicit instructions like "execute sequentially" or "fully parallel"

**Step 2: Apply the strategy.** The Execution Strategy from the batch plan takes precedence over the default count-based heuristic. Use this decision tree:

```
1. IF Execution Strategy says "execute sequentially" or recommends a specific order:
   → Use Step 5b (sequential), in the recommended order

2. IF Execution Strategy says "fully parallel" with no caveats:
   → Use count-based heuristic (Step 5b for 1-3, Step 5c for 4+)

3. IF Execution Strategy warns about shared files or merge conflicts:
   → Split tasks into conflict-free groups:
     - Tasks that touch DIFFERENT files → can be parallel
     - Tasks that touch the SAME file → must be sequential within that group
   → Execute groups in parallel, but tasks within a group sequentially

4. IF no Execution Strategy section exists:
   → Fall back to the default count-based heuristic below
```

**Default heuristic** (used only when no Execution Strategy exists or it says "fully parallel"):

| Wave Task Count | Strategy | Rationale |
|----------------|----------|-----------|
| 1 task | Execute inline | No parallelization needed |
| 2-3 tasks | Execute sequentially inline | Subagent overhead exceeds benefit for small batches |
| 4+ tasks | Spawn parallel subagents | Significant time savings from parallelization |

**Example — P0-B1 of `ui-improvements-audit-activity`:**

The Execution Strategy says: *"All 5 tasks are independent... Backend tasks (E1, E2) modify the same file (audit.py) — recommend doing E1 first, then E2."* And the recommended order is: A1 → A2 → D2 → E1 → E2.

Decision: Even though 5 tasks ≥ 4 (parallel threshold), the Execution Strategy recommends a specific sequential order AND warns about merge conflicts on `audit.py`. **Follow the recommended order** — execute all 5 tasks sequentially in the order: A1, A2, D2, E1, E2.

Alternatively, with the conflict-group approach: A1, A2, D2 can run in parallel (different files); E1 then E2 must be sequential (same file). But since the batch plan explicitly recommends a full sequence, prefer that.

#### 5b. Sequential Execution (1-3 tasks in wave, or Execution Strategy requires it)

Execute each task one by one, inline in the current agent:

    /execute-task [WS-ID] [feature-name]

The `/execute-task` command handles: reading the ticket, updating STATUS.md, implementing code, running tests, generating the completion report, and updating all status files (Steps 1-8i in execute-task.md).

**Task order:** If the Execution Strategy specifies a "Recommended execution order within session", follow that order exactly. Otherwise, execute tasks in the order they appear in the Dependencies table.

Repeat for each task in the wave. After each task completes, verify it succeeded before starting the next.

#### 5c. Parallel Execution (4+ tasks in wave, AND Execution Strategy allows full parallelism)

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

   **Without `--auto-heal`:**
   - Report the failure to the user
   - Attempt to fix inline if the error is clear
   - If the fix requires user input, STOP and report

   **With `--auto-heal`:**
   - The task's `/execute-task` Step 5.5 has already attempted self-healing
   - If the task returned BLOCKED, check the skip-and-continue logic (see Step 5d-heal below)
   - If the task returned a structured failure summary, log it for the healing report

3. If all tasks succeeded, proceed to the next wave

#### 5d-heal. Skip-and-Continue for BLOCKED Tasks (`--auto-heal` only)

**This step runs ONLY when `--auto-heal` is set and a task returned BLOCKED after exhausting retries.**

When a task is BLOCKED, decide whether to skip it or stop the batch:

1. **Check downstream dependencies** in `BATCH_EXECUTION_PLAN.md`:
   - Read the wave analysis for this batch
   - Identify which tasks in later waves depend on the BLOCKED task
   - A task depends on the BLOCKED task if it references the same files, imports modules created by it, or is explicitly listed as a dependency

2. **If NO downstream tasks depend on the BLOCKED task:**
   - Mark as BLOCKED in STATUS.md with the error summary
   - Log to the healing report: `"[WS-ID]: SKIPPED (no downstream deps)"`
   - Continue to the next task/wave

3. **If downstream tasks DO depend on the BLOCKED task:**
   - Attempt to run the dependent tasks anyway — they may work with partial output
   - If a dependent task also fails (and its failure trace references the BLOCKED task's output):
     - Mark the dependent task as BLOCKED too
     - If this cascades to the point where the majority of remaining tasks are blocked: STOP the batch
   - If the dependent tasks succeed despite the upstream block: continue

4. **Safety guardrails — always STOP (never skip) for:**
   - Security-related task failures (auth, crypto, permissions, JWT)
   - Database migration tasks
   - Tasks in the **final batch** of a workstream (no room for partial success)
   - Tasks where `verify_integration.py` CRITICAL count increased

5. **After skip-and-continue decisions, update STATUS.md:**
   ```
   | [WS-ID] | [description] | BLOCKED | [date] | Skipped: [reason]. No downstream deps. |
   ```

#### 5d-fresh. Fresh-Context Retry for Stuck Tasks (`--auto-heal` only)

**Before marking a task as permanently BLOCKED**, give it one final chance with clean context.

When a task exhausts its MAX_RETRIES in `/execute-task` Step 5.5 and `--auto-heal` is set:

1. **Spawn a fresh `best-of-n-runner` subagent** with ONLY this context:
   - The task ticket (from `docs/workstreams/[feature-name]/tickets/`)
   - The task spec (from `docs/workstreams/[feature-name]/specs/`)
   - The current state of the implementation files it needs to modify
   - The error output from the last failed attempt
   - A one-line instruction: `"Fix the following error in this task's implementation. The previous agent tried [N] times and failed. You have ONE attempt."`

2. **Why fresh context:** The original agent's context is polluted with failed fix attempts, stale assumptions, and potentially contradictory edits. A fresh agent approaches the problem without that baggage — it only sees the spec, the current code, and the error.

3. **Execution:**
   ```
   Task tool with subagent_type="best-of-n-runner":
     prompt: [task ticket + spec + current file contents + error output]
     description: "Fresh retry: [WS-ID] [task name]"
     run_in_background: false  (block — we need the result before continuing)
   ```

4. **Outcome:**
   - If the fresh agent succeeds (returns completion report): accept its changes, mark task complete, continue
   - If the fresh agent fails: mark the task as BLOCKED permanently, proceed to skip-and-continue logic

5. **Do NOT use fresh-context retry for:**
   - Security-sensitive tasks (auth, crypto, permissions)
   - Database migration tasks
   - Tasks in the final batch of a workstream
   - Tasks that already had a fresh-context retry (no recursive retries)

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

Proceed to Step 6.5 (Batch Commands & Validation from BATCH_EXECUTION_PLAN.md).

### Step 6.5: Execute Batch Commands & Validation (from BATCH_EXECUTION_PLAN.md)

**MANDATORY after all waves are complete and audit is done, BEFORE the merge point check.**

After each batch is run, go to `BATCH_EXECUTION_PLAN.md` and:

#### 6.5a. Run the "Commands" section

Find the **"Commands"** section for this batch in `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md`. Execute each command listed there. **Skip any lines that start with `/run-batch` or other `/` orchestration commands** — those are self-references to the command you're already executing. Only run the actual shell commands (e.g., `cd`, `docker build`, `pytest`, `curl`, `gcloud`).

#### 6.5b. Run the "Validation" section

Find the **"Validation"** section for this batch in `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md`. Execute every validation command listed. Report each result (expected vs actual).

**If any validation command fails:**

- **Without `--auto-heal`:** Attempt a single fix. If the fix is non-trivial, STOP and report to the user.
- **With `--auto-heal`:** Enter the validation heal loop (max 2 retries):

```
VALIDATION_RETRY = 0
MAX_VALIDATION_RETRIES = 2

WHILE any validation command is failing AND VALIDATION_RETRY < MAX_VALIDATION_RETRIES:
  1. Read the failing validation command's output
  2. Identify which task's code is causing the failure
  3. Read the relevant source files
  4. Apply the fix
  5. Re-run ONLY the failing validation command(s)
  6. VALIDATION_RETRY += 1

IF still failing after MAX_VALIDATION_RETRIES:
  Log the failure to the healing report
  If the failure is in a non-blocking validation: continue to Step 7
  If the failure is in a blocking validation (tests, type checks): STOP
```

**Example flow:**
```
1. Read BATCH_EXECUTION_PLAN.md → find "### Commands" for this batch
2. Execute each command (tests, builds, curls)
3. Read BATCH_EXECUTION_PLAN.md → find "### Validation" for this batch
4. Execute each validation command
5. If fail + --auto-heal: enter heal loop (diagnose → fix → retest, up to 2x)
6. Report: all pass → proceed to Step 7 | any fail → fix or report
```

### Step 7: Verify Batch Completion

After audit is complete and all gaps are fixed:

    /verify-batch-completion [batch-id] [feature-name]

**If this batch triggers a merge point** (check the parsed batch plan):

**MANDATORY: Before moving to the next batch, always check if there is a merge point at the end of the batch in `BATCH_EXECUTION_PLAN.md`. If yes, go to `MERGE_POINTS.md` and execute the following in order:**

> **IMPORTANT — Execution Order:** Container Deployment (7a) must run BEFORE Container Test Scenarios (7b). You cannot test the new container behavior until the container is rebuilt with the batch's code changes.

#### 7a. Container Deployment (from MERGE_POINTS.md)

Open `docs/workstreams/[feature-name]/MERGE_POINTS.md`, find the merge point section for this batch, and execute every command listed under **"Container Deployment"**. This builds and deploys the containers with the batch's code changes so that subsequent test scenarios run against the updated services.

**With `--auto-heal`:** If a container deployment fails, enter a heal loop (max 2 retries). Read container/build logs to identify the error, fix the source code or configuration, and re-run the deployment. Container deployment failures after 2 retries should escalate to the human — they likely indicate an infrastructure issue.

#### 7b. Container Test Scenarios (from MERGE_POINTS.md)

Execute every command listed under **"Container Test Scenarios"** in the merge point section. Report each result.

**With `--auto-heal`:** If a container test fails, enter a heal loop (max 2 retries). Diagnose the failure (read the curl output, check container logs with `docker compose logs`), fix the source code or configuration, rebuild if needed (`docker compose build && docker compose up -d`), then retest the failing scenario.

#### 7c. Success Criteria (from MERGE_POINTS.md)

Go through each checkbox under **"Success Criteria"** in the merge point section. Verify each one explicitly and report pass/fail for every criterion. If any criterion fails, STOP and report to user.

#### 7d. Merge Actions (from MERGE_POINTS.md)

Execute the **"Merge Actions"** from the merge point section. This typically includes:
1. Verifying all batch tasks are complete
2. Running verification checks (type checks, tests)
3. Committing and tagging
4. Pushing to remote

**IMPORTANT:**
- **Commit locally:** Always commit the batch's code changes to the feature branch without asking.
- **Push to remote:** Always push to the remote feature branch (`origin feature/[name]`) without asking.
- **Pre-existing uncommitted changes (tracked files):** Include in the commit without asking — these are part of the feature work.
- **Untracked files:** ASK the user which untracked files (if any) should be added before committing. List the untracked files and wait for confirmation.

#### 7e. Merge Point Tag

After merge actions are confirmed and executed:

**Tag naming convention:** Tags MUST include the feature branch name as a suffix so that merge point tags are unique across workstreams. The format is `{base-tag}-{feature-branch}`, where `{base-tag}` comes from `BATCH_EXECUTION_PLAN.md` and `{feature-branch}` is the current branch from `git branch --show-current`.

```bash
# Derive the full tag name
BASE_TAG="[tag-name-from-batch-plan]"
FEATURE_BRANCH=$(git branch --show-current)
FULL_TAG="${BASE_TAG}-${FEATURE_BRANCH}"

# Create merge point tag
git tag "$FULL_TAG"
# Example: git tag mp1-foundation-complete-feature/ui-improvements-audit-activity
# Example: git tag mp1-dashboard-complete-feature/agent-lifecycle
```

Report merge point status:

    ## Merge Point [MP-ID] Reached

    | Field | Value |
    |-------|-------|
    | **Merge Point** | [MP-ID] |
    | **After Batch** | [N] |
    | **Tag** | `[full-tag-with-branch]` |
    | **Converging Tasks** | [task list] |
    | **Enables** | [what gets unblocked] |

#### 7f. Belt-and-Suspenders: `execute_merge_point.sh` (if mp_config exists)

After the inline merge point handling (7a–7e), check if a matching mp_config exists for automated verification:

```bash
MP_CONFIG="scripts/mp_configs/[feature-name]-mp[N].conf"
# Example: scripts/mp_configs/ui-improvements-audit-activity-mp1.conf

if [ -f "$MP_CONFIG" ]; then
    echo "Running execute_merge_point.sh with $MP_CONFIG..."
    ./scripts/execute_merge_point.sh "$MP_CONFIG" --skip-cleanup
fi
```

**Why:** `execute_merge_point.sh` is a 7-phase automated engine that runs tests, smoke checks, success criteria, and status updates. Running it after the inline merge point steps provides an independent verification layer.

**With `--auto-heal`:** If `execute_merge_point.sh` fails (non-zero exit), do NOT retry it — it is a secondary verification. Instead, read its output to identify which phase failed, log the failure to the healing report, and continue. The merge point is already validated by Steps 7a–7e; this is belt-and-suspenders.

**Flags to use:**
- `--skip-cleanup`: Always skip cleanup — `/run-batch` manages branch lifecycle
- `--skip-tests`: Add if tests already passed in Step 6.5
- `--skip-container`: Add if no container changes in this batch
- `--dry-run`: Use for first-time validation of a new mp_config

**If the config does not exist:** Skip this step silently — the inline 7a–7e steps are sufficient.

**If `execute_merge_point.sh` reports failures:** Report to user but do NOT block — the inline steps (7a–7e) are the primary gate. Log the discrepancy for investigation.

#### 7g. Live E2E Validation: `validate_integration.sh` (backend batches only)

**Run ONLY if this batch modified backend services** (e.g., `deeptrail-control/` or `deeptrail-gateway/` files). Skip for frontend-only batches.

```bash
# Check if backend files were modified in this batch
BACKEND_CHANGES=$(git diff --name-only HEAD~1 HEAD | grep -cE "^(deeptrail-control|deeptrail-gateway)/" || true)

if [ "$BACKEND_CHANGES" -gt 0 ]; then
    echo "Backend changes detected — running live E2E validation..."
    ./scripts/validate_integration.sh --skip-setup
fi
```

**What this runs:** 16 live E2E scenarios covering auth flow, agent lifecycle, vault operations, gateway proxy, and MCP protocol.

**Flags:**
- `--skip-setup`: Skip Docker Compose setup (services should already be running from 7a/7i)

**If validation fails:** Report failures to user. These are live integration tests — failures may indicate real regressions that per-task tests missed.

**With `--auto-heal`:** Do NOT auto-retry `validate_integration.sh` (max 1 attempt). If it fails, log the failure to the healing report and stop the batch — live E2E regressions are too risky to auto-fix. **Exception:** if the `verify_integration.py` CRITICAL count increased (regression detected), always escalate to human regardless of flags.

#### 7h. Build Verify

Run full lint and type checks on every file modified in this batch:

```bash
cd deeptrail-control && ruff check app/ tests/ && echo "✅ ruff clean"
cd frontend && npx tsc --noEmit && echo "✅ tsc clean"
```

If either fails, fix the errors before proceeding. **With `--auto-heal`:** enter a heal loop (max 2 retries) — run `ruff check --fix` for lint errors, read and fix `tsc` errors, then re-run the check. Report to user only if the fix is non-trivial and retries are exhausted.

#### 7i. Container Rebuild

Rebuild backend containers with the batch's changes and verify they start healthy:

```bash
docker compose build deeptrail-control deeptrail-gateway
docker compose up -d deeptrail-control deeptrail-gateway
sleep 5

# Health checks
curl -sf http://localhost:8000/health && echo "✅ Control healthy" || echo "❌ Control unhealthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy"  || echo "❌ Gateway unhealthy"
```

If either service fails health check, inspect logs with `docker compose logs <service>` and fix before proceeding. **With `--auto-heal`:** enter a heal loop (max 2 retries). Read container logs to identify the startup error, fix the source code or configuration, rebuild, restart, and re-check health. Container failures after 2 retries should escalate to the human — they likely indicate an infrastructure issue.

#### 7j. Browser Smoke Test

Quick frontend smoke test to confirm the dashboard still renders after backend changes:

```bash
cd frontend && npm run build && echo "✅ Frontend builds"
```

If available, use the browser-use MCP to navigate to `http://localhost:3000/dashboard` and verify the page renders without console errors. Report any regression.

### Step 7.5: Cross-Service Integration Verification

**MANDATORY after every batch.** Run the static integration verifier to catch cross-service contract violations that per-task audits cannot see:

```bash
python scripts/verify_integration.py
```

**Checks performed:**
1. **Model-Migration Parity** — every `__tablename__` has an Alembic migration
2. **Frontend-Backend Route Existence** — every frontend API proxy path has a backend route
3. **Auth Mechanism Compatibility** — no APIKeyDep endpoints called from JWT proxy
4. **Request Body Shape** — frontend field names match backend Pydantic models
5. **In-Memory Storage Detection** — no module-level mutable dicts/lists in endpoints

**If exit code is 1 (CRITICAL findings):**
- This is expected on early batches — the known issues are being fixed across the workstream.
- Use `--warn-only` flag to continue: `python scripts/verify_integration.py --warn-only`
- Track findings: compare CRITICAL count against previous batch — it must be strictly decreasing.
- On the **final batch**: exit code MUST be 0 (all findings resolved).

**If findings INCREASED from previous batch:**
- STOP. Report to user. A regression was introduced.

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

    ### Healing Summary (if `--auto-heal` was used)

    *Omit this section entirely if `--auto-heal` was not used or no healing occurred.*

    | Task | Failure | Retries | Fresh Retry | Outcome |
    |------|---------|---------|-------------|---------|
    | [WS-ID] | tsc error in audit.ts | 1 | — | Healed (missing import) |
    | [WS-ID] | pytest assertion error | 3 | ✅ Attempted | BLOCKED (test logic) |
    | [WS-ID] | lint formatting | 1 | — | Healed (auto-format) |

    **Healing Totals:**
    - Auto-healed: [N] tasks
    - Blocked: [N] tasks
    - Skipped (no downstream deps): [N] tasks
    - Fresh-context retries: [N] attempted, [M] succeeded

    **Blocked Task Details** (if any):

    For each BLOCKED task, include:
    - Task ID and description
    - Failure class (Auto-fixable / Diagnosable / Opaque / Security)
    - Retries attempted (including fresh-context)
    - Last error output (truncated to key lines)
    - Impact: which downstream tasks were affected
    - Suggestion: what the human should investigate

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

#### 8a. Auto-Continue Behavior (`--continue` flag)

**If `--continue` was specified:**

1. **Determine the next batch ID** from the Quick Reference table in `BATCH_EXECUTION_PLAN.md`.
   Parse the table to find the row after the current batch. The next batch ID is in the first column.

2. **Safety gate — all of these must be true to auto-proceed:**
   - All tasks in the current batch completed successfully (no failures), OR `--auto-heal` is set and all failures were handled (healed or skipped with no downstream impact)
   - `verify-batch-completion` passed
   - All merge point success criteria passed (if applicable)
   - `verify_integration.py` exit code is 0 (or `--warn-only` on non-final batches)
   - `execute_merge_point.sh` did not report FAIL results (if it ran)
   - No BLOCKED tasks have unresolved downstream dependencies in the next batch

3. **If all checks pass and a next batch exists:**
   - Still present the checkpoint report (for the user to see)
   - Append to the report: `Auto-continuing to Batch [N+1]... (--continue flag)`
   - Pass through `--auto-heal` if it was set: `/run-batch [next-batch-id] [feature-name] --continue --auto-heal`
   - If `--auto-heal` was not set: `/run-batch [next-batch-id] [feature-name] --continue`

4. **If any check fails:**
   - **Without `--auto-heal`:** Present the checkpoint report with failure details.
     Append: `Auto-continue STOPPED: [reason]. Fix the issue and re-run: /run-batch [next-batch-id] [feature-name] --continue`
     STOP and wait for user.
   - **With `--auto-heal`:** Check if the failures are skippable (non-blocking, non-security, non-final-batch).
     If skippable: log to healing report, append `Auto-continuing with [N] BLOCKED tasks...`, and proceed.
     If not skippable: STOP with the healing report attached so the user sees what was attempted.

5. **If this is the final batch (no next batch in the table):**
   - Present the final completion report
   - Run `/verify-batch-completion` for the final batch (which auto-closes the workstream)
   - Append: `Workstream complete. All batches executed successfully.`
   - STOP — nothing more to chain

**If `--continue` was NOT specified:**

Wait for user confirmation before proceeding (existing behavior).

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

    /run-batch [batch-id] [feature-name]

The command checks STATUS.md for already-completed tasks in this batch and skips them. Only incomplete tasks are executed.

---

## Merge Point Reference

Merge points are defined in `BATCH_EXECUTION_PLAN.md` and `MERGE_POINTS.md`.

**Tag Naming Convention:** `{base-tag}-{feature-branch}`

| Pattern | Merge Point Batch | Base Tag | Full Tag Example |
|---------|-------------------|----------|------------------|
| `MP1` | After last `P0-B*` batch | `mp1-*-complete` | `mp1-foundation-complete-feature/ui-improvements-audit-activity` |
| `MP2` | After last `P1-B*` batch | `mp2-*-complete` | `mp2-integration-complete-feature/agent-lifecycle` |
| `MP3` | After last `P2-B*` batch | `mp3-*-complete` | `mp3-e2e-complete-feature/gcp-background-agent` |

The base tag names are feature-specific — read them from `BATCH_EXECUTION_PLAN.md`. The feature branch is always appended at tag creation time using `git branch --show-current`.

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
| "The audit step is redundant — tests already pass" | Tests verify behavior, not spec compliance. Past batches found 3 CRITICAL security gaps and 10 MEDIUM gaps despite 414 passing tests. |
| "I will skip the audit for simple batches" | Past batches consistently had spec-implementation gaps. The audit takes ~2 minutes and catches real issues. Never skip it. |

## Red Flags

- Starting Wave 2 before Wave 1 completes
- Spawning subagents for 2-3 tasks (overhead exceeds benefit)
- Not checking for already-completed tasks when resuming
- Skipping `/verify-batch-completion` after the last wave
- **Skipping the Step 6 spec-implementation audit**
- Not creating the merge point tag when required
- Proceeding past a failed task without user acknowledgment
- Not presenting the checkpoint report to the user
- Skipping Step 7f (`execute_merge_point.sh`) when an mp_config exists
- Using `--continue` after a batch with failures (safety gate should have stopped this)
- Not running `validate_integration.sh` for batches that modify backend services
- Auto-healing security-related failures (auth, crypto, JWT, permissions) — always escalate these
- Auto-healing database migration failures — always escalate these
- Using `--auto-heal` on the final batch of a workstream — should not skip-and-continue
- Retrying a fresh-context subagent recursively (max 1 fresh retry per task)
- Not including the Healing Summary in the Step 8 report when `--auto-heal` was used

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

## Example: Running Batch P0-B1 of agent-lifecycle

```
/run-batch P0-B1 agent-lifecycle
```

The agent will:

1. **Parse** `BATCH_EXECUTION_PLAN.md` — find Batch P0-B1: 2 tasks (WS-A1, WS-A2), 1 wave
2. **Pre-flight** — verify branch `feature/agent-lifecycle-backend`, verify PLAN phase files
3. **Specs** — `/create-task-spec P0-B1 agent-lifecycle` (creates 2 spec files)
4. **Tickets** — create tickets for WS-A1, WS-A2
5. **Wave 1** — execute WS-A1, WS-A2 sequentially (2 tasks = below parallel threshold)
6. **Audit** — read both specs/tickets, compare against implementations, fix any gaps
7. **Verify** — `/verify-batch-completion P0-B1 agent-lifecycle`
8. **Checkpoint** — report results, ask user to proceed

Total time: ~1 session instead of manually running 13 commands.

## Example: Auto-Chaining All Batches

```
/run-batch P0-B1 ui-improvements-audit-activity --continue
```

The agent will:

1. Execute **P0-B1** (Foundation) — 5 tasks, MP1
   - All Steps 1–7 as normal
   - Step 7e: Run `execute_merge_point.sh` with mp_config (belt-and-suspenders)
   - Step 7f: Run `validate_integration.sh` (backend changes detected)
   - Step 8: All checks pass → auto-continue
2. Execute **P0-B2** (Core Implementation) — 7 tasks
   - All Steps 1–8 as normal
   - Step 8: All checks pass → auto-continue
3. Execute **P0-B3** (Tests + Polish) — 4 tasks
   - All Steps 1–8 as normal
   - Final batch → workstream closure
   - STOP — all batches complete

If any batch fails, auto-continue stops at that batch with a detailed failure report.

## Example: Full AFK Mode (Auto-Heal + Auto-Chain)

```
/run-batch P0-B1 ui-improvements-audit-activity --continue --auto-heal
```

The agent will:

1. Execute **P0-B1** (Foundation) — 5 tasks, MP1
   - Task WS-A1: Implementation succeeds, all checks pass
   - Task WS-A2: `tsc` error → **self-heal** (1 retry, fixes missing import) → passes
   - Task WS-E1: Test assertion failure → **self-heal** (2 retries, fixes mapping logic) → passes
   - Task WS-C1: Pytest failure → **self-heal** (3 retries exhausted) → **fresh-context retry** → passes
   - Task WS-D1: All checks pass
   - Step 6.5 validation: passes
   - Step 7: MP1 merge point → container rebuild, smoke tests pass
   - Step 8: Healing Summary shows 3 healed tasks, 0 blocked → auto-continue
2. Execute **P0-B2** (Core Implementation) — 7 tasks
   - Task WS-B3: Test failure → self-heal (3 retries) → fresh-context retry → **BLOCKED**
   - No downstream tasks depend on WS-B3 → **skip-and-continue**
   - Remaining 6 tasks: all pass
   - Step 8: Healing Summary shows 1 blocked, 1 skipped → auto-continue (non-blocking)
3. Execute **P0-B3** (Tests + Polish) — 4 tasks, FINAL BATCH
   - All tasks pass (no skip-and-continue allowed on final batch)
   - Workstream closure
   - Final Healing Summary: 3 healed across all batches, 1 blocked (WS-B3)
   - STOP — all batches complete

If a security-related task fails, or `verify_integration.py` detects a regression, the auto-heal stops immediately and reports to the user.
