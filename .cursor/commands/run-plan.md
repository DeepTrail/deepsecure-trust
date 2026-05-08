# Run Plan: Automated PLAN Phase Orchestration

Automate the full PLAN phase for a new workstream: explore the codebase, break down the design into tasks and batches, create all workstream scaffolding, and optionally set up parallel worktrees — then checkpoint with the user before handing off to `/run-batch`.

This is the PLAN-phase equivalent of `/run-batch`. Just as `/run-batch` automates the full EXECUTE phase for one batch, `/run-plan` automates the full PLAN phase for one workstream.

## Workflow Position

```
/spec → /create-design-doc → /run-plan → /run-batch 1 → /run-batch 2 → ...
                                 ↑
                            (YOU ARE HERE)

Internally invokes (in order):
  Step 1: /breakdown-design          → BREAKDOWN.md + CODEBASE_ANALYSIS.md
  Step 2: /create-workstream         → WORKSTREAM.md + STATUS.md + MERGE_POINTS.md + tasks/ + reports/
  Step 3: /create-batch-execution-plan → BATCH_EXECUTION_PLAN.md
  Step 4: /setup-worktrees           (optional — only if multi-service parallelization is needed)
  Checkpoint: user approves plan
  State: writes PIPELINE_STATE.md → /run-batch pre-flight passes

Replaces manually running these 4 individual commands from DEVELOPER_WORKFLOW.md:
  /breakdown-design → /create-workstream → /create-batch-execution-plan → /setup-worktrees
```

## Invocation

```
/run-plan [feature-name] [design-doc-path]
```

**Parameters:**
- `[feature-name]`: Canonical identifier used for folder names, branches, and commands (e.g., `mvp-foundation`, `frontend-architecture`)
- `[design-doc-path]`: Path to the design document (e.g., `docs/design/my-feature.md` or `plans/my-feature.plan.md`)

**Examples:**

    /run-plan virtual-mcp-server-mvp docs/design/virtual-mcp-server-mvp.md
    /run-plan claude-code-integration plans/claude_code_integration.plan.md
    /run-plan agent-auth docs/design/agent-auth-flow.md

---

## Step Summary (mirrors /run-batch structure exactly)

| Step | Action | Output |
|------|--------|--------|
| **Pre-flight** | Verify design doc exists; check PLAN not already complete | Status report |
| **Step 1** | `/breakdown-design [design-doc-path]` — includes embedded codebase exploration | `BREAKDOWN.md` + `CODEBASE_ANALYSIS.md` |
| **Step 2** | `/create-workstream [feature-name]` | `WORKSTREAM.md`, `STATUS.md`, `MERGE_POINTS.md`, `tasks/`, `reports/` |
| **Step 3** | `/create-batch-execution-plan [feature-name]` | `BATCH_EXECUTION_PLAN.md` |
| **Step 4** | `/setup-worktrees [feature-name]` (if batch plan shows parallel tracks) | Git worktrees created |
| **Checkpoint** | Present to user: workstream count, task count, batch count, critical path, estimated effort | "Approve plan? (yes / review / cancel)" |
| **State** | Write `PIPELINE_STATE.md` with PLAN phase ✅ | Enables `/run-batch` pre-flight to pass |

---

## Instructions

### Pre-Flight Checks

Before doing anything, verify inputs and environment:

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
```

**a. Verify the design doc exists:**

```bash
ls [design-doc-path]
```

If the file does not exist, STOP and report:

    ## Pre-Flight FAILED: Design Doc Not Found

    Could not find: [design-doc-path]

    Did you mean one of these?
      ls docs/design/*.md
      ls plans/*.md

    Run `/spec` + `/create-design-doc` first, or provide the correct path.

**b. Check if PLAN phase was already completed (prevent re-running):**

```bash
ls docs/workstreams/[feature-name]/PIPELINE_STATE.md 2>/dev/null
```

If `PIPELINE_STATE.md` already exists:

    ## Pre-Flight: PLAN Phase Already Complete

    docs/workstreams/[feature-name]/PIPELINE_STATE.md exists — this workstream was
    previously planned and user-approved.

    Options:
    - **Proceed to execution:** `/run-batch 1 [feature-name]`
    - **Re-run plan (overwrites existing):** Continue with /run-plan (type "yes" to confirm)
    - **Cancel:** Type "cancel"

    Awaiting user response...

**c. Verify git status is clean (recommended):**

```bash
git status --short | wc -l
```

If there are staged/unstaged changes, warn (do not block):

    ## Pre-Flight Warning: Dirty Working Tree

    There are uncommitted changes. It is recommended to commit or stash before
    starting a new workstream plan, but this is not required.

**d. Report pre-flight status:**

    ## Pre-Flight: /run-plan — [feature-name]

    | Check | Status |
    |-------|--------|
    | Design doc found | ✅ [design-doc-path] |
    | PLAN phase not already complete | ✅ (or ⚠️ if resuming) |
    | Git working tree | ✅ Clean (or ⚠️ Has changes) |

    Starting PLAN phase...

---

### Step 1: Run /breakdown-design

    /breakdown-design [design-doc-path]

**Output:** `BREAKDOWN.md` + `CODEBASE_ANALYSIS.md`

**What `/breakdown-design` does:**
1. **Runs embedded codebase exploration** — inventories existing implementations, cross-references against design doc claims, classifies tasks as Create / Modify / Verify / Skip
2. **Saves** `docs/workstreams/[feature-name]/CODEBASE_ANALYSIS.md`
3. **Analyzes** the design doc — identifies workstreams, tasks, dependencies, parallelization opportunities
4. **Saves** `docs/workstreams/[feature-name]/BREAKDOWN.md`

> **Note on internal chaining:** `/breakdown-design` may internally chain `/create-workstream` and `/create-batch-execution-plan`. `/run-plan` calls these explicitly in Steps 2 and 3 to verify each output individually. If they were already created by the internal chain, the steps confirm they exist and proceed.

**After Step 1, verify outputs:**

```bash
FEATURE="[feature-name]"
[ -f "docs/workstreams/${FEATURE}/BREAKDOWN.md" ] && echo "✅ BREAKDOWN.md" || echo "❌ MISSING — re-run /breakdown-design"
[ -f "docs/workstreams/${FEATURE}/CODEBASE_ANALYSIS.md" ] && echo "✅ CODEBASE_ANALYSIS.md" || echo "❌ MISSING — re-run /breakdown-design"
```

If either is missing, re-run `/breakdown-design [design-doc-path]` before continuing.

---

### Step 2: Run /create-workstream

    /create-workstream [feature-name]

**Output:** `WORKSTREAM.md`, `STATUS.md`, `MERGE_POINTS.md`, `tasks/`, `reports/`

**After Step 2, verify outputs:**

```bash
FEATURE="[feature-name]"
[ -f "docs/workstreams/${FEATURE}/WORKSTREAM.md" ] && echo "✅ WORKSTREAM.md" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/STATUS.md" ] && echo "✅ STATUS.md" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/MERGE_POINTS.md" ] && echo "✅ MERGE_POINTS.md" || echo "❌ MISSING"
[ -d "docs/workstreams/${FEATURE}/tasks" ] && echo "✅ tasks/" || echo "❌ MISSING"
[ -d "docs/workstreams/${FEATURE}/reports" ] && echo "✅ reports/" || echo "❌ MISSING"
```

If any file or directory is missing, re-run `/create-workstream [feature-name]`.

---

### Step 3: Run /create-batch-execution-plan

    /create-batch-execution-plan [feature-name]

**Output:** `BATCH_EXECUTION_PLAN.md`

**After Step 3, verify output:**

```bash
FEATURE="[feature-name]"
[ -f "docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md" ] && echo "✅ BATCH_EXECUTION_PLAN.md" || echo "❌ MISSING — re-run /create-batch-execution-plan"
```

If missing, re-run `/create-batch-execution-plan [feature-name]`.

---

### Step 4: Run /setup-worktrees (conditional)

Read `docs/workstreams/[feature-name]/BREAKDOWN.md` and `BATCH_EXECUTION_PLAN.md` to determine whether parallel worktrees are needed.

**Decision criteria:**

| Scenario | Action |
|----------|--------|
| Feature touches `deeptrail-control/` AND `deeptrail-gateway/` with independent tasks | Run `/setup-worktrees` |
| Feature touches `deeptrail-control/` AND `deeptrail-gateway/` but tasks are fully sequential | Skip worktrees |
| Feature is single-service only (frontend, SDK, or control-only) | Skip worktrees |
| Feature has fewer than 4 tasks total | Skip worktrees (overhead exceeds benefit) |
| BREAKDOWN.md "Parallelization Decision" explicitly recommends worktrees | Run `/setup-worktrees` |
| BREAKDOWN.md "Parallelization Decision" explicitly recommends single-branch | Skip worktrees |

**If worktrees are NOT needed:**

    ## Worktree Decision: Single-Branch

    This feature runs on a single branch. No worktrees needed.
    Reason: [one of the criteria above]

    Proceeding to checkpoint...

**If worktrees ARE needed:**

    /setup-worktrees [feature-name]

**Output:** Git worktrees created for each service track

**Verify setup:**

```bash
git worktree list
# Expected: main repo + one worktree per service
```

If `/setup-worktrees` fails, fall back to single-branch execution:

    ## Worktree Setup FAILED (falling back to single-branch)

    /setup-worktrees encountered an error: [error]

    Falling back to single-branch execution.
    All tasks will execute in the main repo on the feature branch.

---

### Checkpoint — Report Results

**MANDATORY: Checkpoint with the user after all artifacts are created. Do NOT write `PIPELINE_STATE.md` until the user explicitly approves.**

Extract a structured summary from the generated files:

```bash
FEATURE="[feature-name]"

# Count batches
grep -c "^## Batch" docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md 2>/dev/null

# Count total tasks
grep -c "^| WS-" docs/workstreams/${FEATURE}/WORKSTREAM.md 2>/dev/null

# Count merge points
grep -c "^## ── MERGE POINT\|^## Merge Point" docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md 2>/dev/null
```

Present the plan completion report in this **exact format**:

    ## Plan Phase Complete: [feature-name]

    | Metric | Value |
    |--------|-------|
    | Workstreams | [N] |
    | Total tasks | [N] |
    | Batches | [N] |
    | Worktrees created | [N] (or "None — single-branch") |
    | Critical path | [task chain, e.g. A1 → A2 → B1 → C1] |
    | Estimated effort | [Ns S + Nm M + Nl L] |

    ### PLAN Phase Artifacts

    | Artifact | Status |
    |----------|--------|
    | BREAKDOWN.md ([N] tasks) | ✅ |
    | CODEBASE_ANALYSIS.md ([N] existing, [N] gaps) | ✅ |
    | WORKSTREAM.md | ✅ |
    | STATUS.md | ✅ |
    | MERGE_POINTS.md ([N] merge points) | ✅ |
    | BATCH_EXECUTION_PLAN.md ([N] batches) | ✅ |
    | Worktrees | ✅ [list] (or "N/A — single-branch") |

    ### Batch Overview

    | Batch | Tasks | Waves | Focus |
    |-------|-------|-------|-------|
    | 1 | [task IDs] | [N] | [focus description] |
    | 2 | [task IDs] | [N] | [focus description] |
    | ... | ... | ... | ... |

    ---
    Approve plan? (yes — write state + enable /run-batch / review — open BATCH_EXECUTION_PLAN.md / cancel)

**Wait for user response before continuing:**

- **yes**: proceed to Write PIPELINE_STATE.md, then offer to run `/run-batch 1 [feature-name]`
- **review**: present the full `BATCH_EXECUTION_PLAN.md` content and wait for approval
- **cancel**: STOP; do NOT write PIPELINE_STATE.md; workstream artifacts remain on disk for review

---

### Write PIPELINE_STATE.md

**Only execute this step after the user approves the plan at the checkpoint.**

Write `docs/workstreams/[feature-name]/PIPELINE_STATE.md`:

```markdown
# Pipeline State: [feature-name]

## PLAN Phase: ✅ Complete

| Artifact | Status | Created |
|----------|--------|---------|
| BREAKDOWN.md | ✅ | [date] |
| CODEBASE_ANALYSIS.md | ✅ | [date] |
| WORKSTREAM.md | ✅ | [date] |
| STATUS.md | ✅ | [date] |
| MERGE_POINTS.md | ✅ | [date] |
| BATCH_EXECUTION_PLAN.md | ✅ | [date] |

## EXECUTE Phase: ⏳ Not Started

Run `/run-batch 1 [feature-name]` to begin execution.

## Plan Approval
User approved plan checkpoint on [date].
Total tasks: [N] | Batches: [N] | Critical path: [chain]
Worktrees: [N created / single-branch]
```

**Then offer to start execution:**

    PIPELINE_STATE.md written. ✅ PLAN phase is complete.

    To start execution:
    ```
    /run-batch 1 [feature-name]
    ```

    Start Batch 1 now? (yes / pause)

If user says "yes": automatically run `/run-batch 1 [feature-name]`.
If user says "pause": stop and report the command to run when ready.

---

## Error Recovery

### /breakdown-design fails

| Failure Type | Action |
|-------------|--------|
| Design doc missing required sections | Report missing sections, ask user to add them |
| Codebase exploration timeout | Re-run exploration with narrower scope |
| `/create-workstream` step fails | Run `/create-workstream [feature-name]` manually (Step 2), then re-verify |
| `/create-batch-execution-plan` fails | Run `/create-batch-execution-plan [feature-name]` manually (Step 3) |

### /setup-worktrees fails

| Failure Type | Action |
|-------------|--------|
| Git worktree conflict (stale worktrees) | Run `git worktree list` and remove stale entries, then retry |
| Branch already exists | Run `git branch -D feature/[old-branch]` and retry |
| Copy fails | Manually copy `.cursor/` and workstream files to worktrees |
| Fall back | Continue without worktrees (single-branch mode) |

### Resuming After Failure

    /run-plan [feature-name] [design-doc-path]

The command checks whether each file already exists and skips creation for files that are present. It will only re-create missing files.

---

## Pre-Flight Checklist Requirements for /run-batch

After `/run-plan` completes (with user approval), `/run-batch` will automatically pass its own pre-flight checks because all required files exist:

| `/run-batch` Pre-Flight Check | Satisfied by `/run-plan` |
|-------------------------------|--------------------------|
| Feature branch exists | Created by `/setup-worktrees` or by `/run-batch` Batch 1 |
| `BATCH_EXECUTION_PLAN.md` exists | ✅ Created in Step 3 |
| `WORKSTREAM.md` exists | ✅ Created in Step 2 |
| `STATUS.md` exists | ✅ Created in Step 2 |
| `BREAKDOWN.md` exists | ✅ Created in Step 1 |
| `CODEBASE_ANALYSIS.md` exists | ✅ Created in Step 1 |
| `MERGE_POINTS.md` exists | ✅ Created in Step 2 |
| `PIPELINE_STATE.md` exists | ✅ Written after checkpoint approval |
| Prior batch complete (N/A for Batch 1) | ✅ N/A |

This is the primary value of running `/run-plan` before `/run-batch`: all pre-flight checks pass automatically.

---

## Verification Checklist

After running `/run-plan`, verify:

```bash
FEATURE="[feature-name]"

echo "=== /run-plan Completion Verification ==="

echo ""
echo "--- Required Files ---"
[ -f "docs/workstreams/${FEATURE}/BREAKDOWN.md" ] && echo "✅ BREAKDOWN.md" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/CODEBASE_ANALYSIS.md" ] && echo "✅ CODEBASE_ANALYSIS.md" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/WORKSTREAM.md" ] && echo "✅ WORKSTREAM.md" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/STATUS.md" ] && echo "✅ STATUS.md" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md" ] && echo "✅ BATCH_EXECUTION_PLAN.md" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/MERGE_POINTS.md" ] && echo "✅ MERGE_POINTS.md" || echo "❌ MISSING"
[ -d "docs/workstreams/${FEATURE}/tasks" ] && echo "✅ tasks/" || echo "❌ MISSING"
[ -d "docs/workstreams/${FEATURE}/reports" ] && echo "✅ reports/" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/PIPELINE_STATE.md" ] && echo "✅ PIPELINE_STATE.md (plan approved)" || echo "⚠️  PIPELINE_STATE.md missing — user has not approved plan yet"

echo ""
echo "--- Worktree Status ---"
git worktree list

echo ""
echo "--- Ready for Execution ---"
echo "Run: /run-batch 1 ${FEATURE}"
echo "=== Done ==="
```

---

## Relationship to /pipeline

`/pipeline` is the top-level command that orchestrates ALL five phases (DEFINE → PLAN → EXECUTE → REVIEW → SHIP). `/run-plan` is a focused automation for just the PLAN phase, giving users who already have a design doc a fast path to execution without running the full 5-phase pipeline.

```
Full automation:     /pipeline docs/design/feature.md
PLAN only:           /run-plan feature-name docs/design/feature.md
EXECUTE only:        /run-batch 1 feature-name
PLAN + EXECUTE:      /run-plan feature-name docs/design/feature.md
                     → (after checkpoint + approval) /run-batch 1 feature-name
                     → /run-batch 2 feature-name ...
```

---

## Common Rationalizations

| Rationalization | Why It Is Wrong |
|----------------|----------------|
| "I'll run the 4 commands manually" | Manual execution skips the per-step verification, the checkpoint, and does not write `PIPELINE_STATE.md`. `/run-batch` pre-flight will fail without it. |
| "I don't need /explore-codebase, I know the codebase" | `/breakdown-design` runs exploration internally. The Feb 2026 lesson proved 60% of 'missing' items already existed. Never skip it. |
| "I'll skip /setup-worktrees for multi-service features" | Without worktrees, parallel service tracks must share a branch, creating merge conflicts and blocking parallel execution. |
| "I don't need to wait for user approval at checkpoint" | `PIPELINE_STATE.md` is only written after approval. Without it, `/run-batch` pre-flight fails with "PLAN Phase Incomplete". |
| "The plan phase is done when /breakdown-design finishes" | Plan phase is done only when all artifacts are verified, the user has reviewed and approved the batch plan, AND `PIPELINE_STATE.md` is written. |

## Red Flags

- Running `/run-batch 1` before `/run-plan` finishes (`PIPELINE_STATE.md` won't exist — pre-flight will fail)
- Skipping the worktree decision for multi-service features (they will have conflicts)
- Writing `PIPELINE_STATE.md` without the user approving the plan (defeats the checkpoint)
- Missing `CODEBASE_ANALYSIS.md` after Step 1 completes (exploration was skipped)
- BREAKDOWN.md classifying ALL tasks as "Create" (exploration was not done properly)

---

## Related Commands

| Command | Relationship |
|---------|-------------|
| `/spec` | Creates the spec that feeds `/create-design-doc` (upstream) |
| `/create-design-doc` | Produces the design doc this command reads (upstream) |
| `/breakdown-design` | Invoked internally — Step 1 of this command |
| `/create-workstream` | Invoked internally — Step 2 of this command |
| `/create-batch-execution-plan` | Invoked internally — Step 3 of this command |
| `/setup-worktrees` | Invoked internally (conditional) — Step 4 of this command |
| `/run-batch` | The natural next command after `/run-plan` completes |
| `/pipeline` | Parent command that invokes `/run-plan` in its PLAN phase |

---

## Example: Planning the claude-code-integration Feature

```
/run-plan claude-code-integration plans/claude_code_integration.plan.md
```

The agent will:

1. **Pre-flight** — verify `plans/claude_code_integration.plan.md` exists; check for existing `PIPELINE_STATE.md`
2. **Step 1** — `/breakdown-design plans/claude_code_integration.plan.md`:
   - Explores `deepsecure/`, `deeptrail-control/`, `deeptrail-gateway/` for existing components
   - Saves `CODEBASE_ANALYSIS.md` — classifies existing vs. new
   - Analyzes design doc, classifies tasks
   - Saves `BREAKDOWN.md`
3. **Step 2** — `/create-workstream claude-code-integration` → saves `WORKSTREAM.md`, `STATUS.md`, `MERGE_POINTS.md`, `tasks/`, `reports/`
4. **Step 3** — `/create-batch-execution-plan claude-code-integration` → saves `BATCH_EXECUTION_PLAN.md`
5. **Step 4** — reads BREAKDOWN.md parallelization section; runs `/setup-worktrees claude-code-integration` if multi-service
6. **Checkpoint** — presents: 3 workstreams, 12 tasks, 4 batches, 2 merge points, critical path — "Approve plan?"
7. **State** — after approval: writes `PIPELINE_STATE.md` with PLAN phase ✅
8. **Handoff** — "Start Batch 1 now? → `/run-batch 1 claude-code-integration`"

Total: 1 command instead of running 4 commands manually.
