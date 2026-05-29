# Run Plan: Automated PLAN Phase Orchestration

Automate the full PLAN phase for a new workstream: explore the codebase, break down the design into tasks and batches, create all workstream scaffolding, and optionally set up parallel worktrees — then checkpoint with the user before handing off to `/run-batch`.

This is the PLAN-phase equivalent of `/run-batch`. Just as `/run-batch` automates the full EXECUTE phase for one batch, `/run-plan` automates the full PLAN phase for one workstream.

## Workflow Position

```
/spec → /create-design-doc → /run-plan → /run-batch P0-B1 → /run-batch P0-B2 → ...
                                 ↑
                            (YOU ARE HERE)

Internally invokes (in order):
  Step 1:   /breakdown-design          → BREAKDOWN.md + CODEBASE_ANALYSIS.md
  Step 2:   /create-workstream         → WORKSTREAM.md + STATUS.md + MERGE_POINTS.md + tasks/ + reports/
  Step 3:   /create-batch-execution-plan → BATCH_EXECUTION_PLAN.md
  Step 3.5: Auto-generate mp_configs   → scripts/mp_configs/[feature]-mp[N].conf (one per merge point)
  Step 4:   /setup-worktrees           (optional — only if multi-service parallelization is needed)
  Checkpoint: user approves plan
  State: writes PIPELINE_STATE.md → /run-batch pre-flight passes

Replaces manually running these 4 individual commands from DEVELOPER_WORKFLOW.md:
  /breakdown-design → /create-workstream → /create-batch-execution-plan → /setup-worktrees
```

## Invocation

```
/run-plan [feature-name] [design-doc-path] [--auto-heal] [--skip-checkpoint]
```

**Parameters:**
- `[feature-name]`: Canonical identifier used for folder names, branches, and commands (e.g., `mvp-foundation`, `frontend-architecture`)
- `[design-doc-path]`: Path to the design document (e.g., `docs/design/my-feature.md` or `plans/my-feature.plan.md`)
- `[--auto-heal]`: *(Optional)* Enable self-healing retry loops. When a sub-command fails or produces incomplete output (missing sections, under quality thresholds), automatically diagnose the issue and retry — up to a retry budget per step. Also enables content quality auto-correction (re-running sub-commands or injecting missing sections from templates).
- `[--skip-checkpoint]`: *(Optional)* Bypass the plan-approval gate. Instead of waiting for user confirmation, auto-write `PIPELINE_STATE.md` and chain into `/run-batch [first-batch-id] [feature-name] --continue [--auto-heal]`. The first batch ID is read dynamically from the Quick Reference table in `BATCH_EXECUTION_PLAN.md`. **Use with caution** — skips the human review of the batch plan. Composable with `--auto-heal` for full AFK mode from design doc to shipped code.

**Examples:**

    /run-plan virtual-mcp-server-mvp docs/design/virtual-mcp-server-mvp.md
    /run-plan claude-code-integration plans/claude_code_integration.plan.md
    /run-plan agent-auth docs/design/agent-auth-flow.md

    # Self-healing (reliably reaches checkpoint without stalling):
    /run-plan agent-auth docs/design/agent-auth-flow.md --auto-heal

    # Full AFK mode (skip checkpoint + chain into /run-batch):
    /run-plan agent-auth docs/design/agent-auth-flow.md --auto-heal --skip-checkpoint

---

## Step Summary (mirrors /run-batch structure exactly)

| Step | Action | `--auto-heal` Behavior | Output |
|------|--------|------------------------|--------|
| **Pre-flight** | Verify design doc exists; check PLAN not already complete | *(no healing needed — input validation)* | Status report |
| **Step 1** | `/breakdown-design [design-doc-path]` — includes embedded codebase exploration | Retry up to 2x if BREAKDOWN.md or CODEBASE_ANALYSIS.md missing | `BREAKDOWN.md` + `CODEBASE_ANALYSIS.md` |
| **Step 2** | `/create-workstream [feature-name]` | Retry up to 2x; inject missing sections from template on 2nd retry | `WORKSTREAM.md`, `STATUS.md`, `MERGE_POINTS.md`, `tasks/`, `reports/` |
| **Step 3** | `/create-batch-execution-plan [feature-name]` | Retry up to 2x; distinguish critical vs supplementary missing sections | `BATCH_EXECUTION_PLAN.md` |
| **Step 3.5** | Auto-generate mp_configs for each merge point | Auto-fix syntax errors (escaping, quotes); regenerate from scratch on 2nd failure | `scripts/mp_configs/[feature]-mp[N].conf` |
| **Step 4** | `/setup-worktrees [feature-name]` (if batch plan shows parallel tracks) | Clean stale worktrees, delete conflicting branches; fall back to single-branch if exhausted | Git worktrees created |
| **Checkpoint** | Present plan + healing summary to user | With `--skip-checkpoint`: auto-approve if safety gate passes, chain into `/run-batch` | "Approve plan? (yes / review / cancel)" |
| **State** | Write `PIPELINE_STATE.md` with PLAN phase ✅ | *(same behavior — write is deterministic)* | Enables `/run-batch` pre-flight to pass |

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
    - **Proceed to execution:** `/run-batch [first-batch-id] [feature-name]` (check Quick Reference table in BATCH_EXECUTION_PLAN.md)
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

**Without `--auto-heal`:** If either is missing, re-run `/breakdown-design [design-doc-path]` before continuing.

**With `--auto-heal`:** Enter the Step 1 heal loop:

```
STEP1_RETRY = 0
MAX_STEP1_RETRIES = 2

WHILE (BREAKDOWN.md missing OR CODEBASE_ANALYSIS.md missing) AND STEP1_RETRY < MAX_STEP1_RETRIES:
  1. Read available error output or partial files
  2. If CODEBASE_ANALYSIS.md is missing but BREAKDOWN.md exists:
     - Re-run ONLY the codebase exploration portion of /breakdown-design
  3. If BREAKDOWN.md is missing:
     - Re-run /breakdown-design [design-doc-path] with full scope
  4. Re-verify both files exist
  5. STEP1_RETRY += 1
  6. Log to healing report: "Step 1 retry [N]: [which file was missing]"

IF still missing after MAX_STEP1_RETRIES:
  Log failure to healing report
  STOP — /breakdown-design is a prerequisite for all downstream steps
```

---

### Step 2: Run /create-workstream

    /create-workstream [feature-name]

**Output:** `WORKSTREAM.md`, `STATUS.md`, `MERGE_POINTS.md`, `tasks/`, `reports/`

**After Step 2, verify outputs — FILE EXISTENCE + CONTENT QUALITY (BLOCKING):**

```bash
FEATURE="[feature-name]"
FAIL=0

echo "=== Step 2: File Existence ==="
[ -f "docs/workstreams/${FEATURE}/WORKSTREAM.md" ] && echo "✅ WORKSTREAM.md" || { echo "❌ MISSING"; FAIL=1; }
[ -f "docs/workstreams/${FEATURE}/STATUS.md" ] && echo "✅ STATUS.md" || { echo "❌ MISSING"; FAIL=1; }
[ -f "docs/workstreams/${FEATURE}/MERGE_POINTS.md" ] && echo "✅ MERGE_POINTS.md" || { echo "❌ MISSING"; FAIL=1; }
[ -d "docs/workstreams/${FEATURE}/tasks" ] && echo "✅ tasks/" || { echo "❌ MISSING"; FAIL=1; }
[ -d "docs/workstreams/${FEATURE}/reports" ] && echo "✅ reports/" || { echo "❌ MISSING"; FAIL=1; }

echo ""
echo "=== Step 2: WORKSTREAM.md Content Quality ==="
FILE="docs/workstreams/${FEATURE}/WORKSTREAM.md"
grep -q "## Executive Summary" $FILE && echo "✅ Executive Summary" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## Scope" $FILE && echo "✅ Scope" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## Key Decisions" $FILE && echo "✅ Key Decisions" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## Batch Overview" $FILE && echo "✅ Batch Overview" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## Critical Path" $FILE && echo "✅ Critical Path" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## All Tasks" $FILE && echo "✅ All Tasks" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## Validation Criteria" $FILE && echo "✅ Validation Criteria" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## History" $FILE && echo "✅ History" || { echo "❌ MISSING"; FAIL=1; }
LINES=$(wc -l < "$FILE")
echo "WORKSTREAM.md: ${LINES} lines"
[ "$LINES" -gt 100 ] && echo "✅ Above 100-line minimum" || { echo "❌ UNDER 100 LINES — gold standard is 600+"; FAIL=1; }

echo ""
echo "=== Step 2: MERGE_POINTS.md Content Quality ==="
MP_FILE="docs/workstreams/${FEATURE}/MERGE_POINTS.md"
grep -q "### Merge Actions" $MP_FILE && echo "✅ Merge Actions" || { echo "❌ MISSING"; FAIL=1; }
grep -q "### Container Test Scenarios" $MP_FILE && echo "✅ Container Tests" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## Quick Reference Commands" $MP_FILE && echo "✅ Quick Reference" || { echo "❌ MISSING"; FAIL=1; }

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "✅ Step 2 PASSED — proceeding to Step 3"
else
  echo "❌ Step 2 FAILED — fix missing sections before proceeding"
  echo "STOP: Re-run /create-workstream or manually add missing sections."
fi
```

**Without `--auto-heal`:** If FAIL > 0, STOP. Fix the missing sections before proceeding to Step 3. Re-run `/create-workstream [feature-name]` or manually add missing sections, then re-run the check.

**With `--auto-heal`:** If FAIL > 0, enter the Step 2 heal loop:

```
STEP2_RETRY = 0
MAX_STEP2_RETRIES = 2

WHILE FAIL > 0 AND STEP2_RETRY < MAX_STEP2_RETRIES:
  1. Classify the failure:
     a. Missing files (WORKSTREAM.md, STATUS.md, MERGE_POINTS.md, tasks/, reports/)
        → Re-run /create-workstream [feature-name]
     b. Missing content sections in WORKSTREAM.md (e.g., "Executive Summary", "Critical Path")
        → Re-run /create-workstream with explicit section requirements
        → If still missing after retry: inject missing section from template with
           placeholder content: "## [Section Name]\n\n> TODO: Auto-generated placeholder.
           Review and update.\n"
     c. Missing content sections in MERGE_POINTS.md (e.g., "Merge Actions", "Container Tests")
        → Re-run /create-workstream
        → If still missing after retry: inject from MERGE_POINT_GUIDE.md template
     d. WORKSTREAM.md under 100-line minimum
        → Re-run /create-workstream with instruction to expand all sections
  2. Re-run the full FAIL check from Step 2
  3. STEP2_RETRY += 1
  4. Log to healing report: "Step 2 retry [N]: [failure type] — [action taken]"

IF still failing after MAX_STEP2_RETRIES:
  Log failure to healing report with specific missing sections
  STOP — workstream scaffolding is required for batch planning
```

---

### Step 3: Run /create-batch-execution-plan

    /create-batch-execution-plan [feature-name]

**Output:** `BATCH_EXECUTION_PLAN.md`

**After Step 3, verify output — FILE EXISTENCE + CONTENT QUALITY (BLOCKING):**

```bash
FEATURE="[feature-name]"
FILE="docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md"
FAIL=0

echo "=== Step 3: File Existence ==="
[ -f "$FILE" ] && echo "✅ BATCH_EXECUTION_PLAN.md" || { echo "❌ MISSING"; FAIL=1; }

echo ""
echo "=== Step 3: BATCH_EXECUTION_PLAN.md Content Quality ==="
grep -q "## Quick Reference" $FILE && echo "✅ Quick Reference" || { echo "❌ MISSING"; FAIL=1; }
grep -q "### Wave Analysis" $FILE && echo "✅ Wave Analysis" || { echo "❌ MISSING"; FAIL=1; }
grep -q "### Visual Dependency Graph" $FILE && echo "✅ Visual Graphs" || { echo "❌ MISSING"; FAIL=1; }
grep -q "### Execution Strategy" $FILE && echo "✅ Execution Strategy" || { echo "❌ MISSING"; FAIL=1; }
grep -q "### Commands" $FILE && echo "✅ Commands" || { echo "❌ MISSING"; FAIL=1; }
grep -q "### Validation" $FILE && echo "✅ Validation" || { echo "❌ MISSING"; FAIL=1; }
grep -q "### Summary" $FILE && echo "✅ Summary tables" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## Overall Execution Summary" $FILE && echo "✅ Overall Summary" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## Optimal Execution Strategy" $FILE && echo "✅ Optimal Strategy" || { echo "❌ MISSING"; FAIL=1; }
grep -q "## Quick Start Commands" $FILE && echo "✅ Quick Start" || { echo "❌ MISSING"; FAIL=1; }
LINES=$(wc -l < "$FILE")
echo "BATCH_EXECUTION_PLAN.md: ${LINES} lines"
[ "$LINES" -gt 200 ] && echo "✅ Above 200-line minimum" || { echo "❌ UNDER 200 LINES — gold standard is 680-2567"; FAIL=1; }

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "✅ Step 3 PASSED — proceeding to Step 4"
else
  echo "❌ Step 3 FAILED — fix missing sections before proceeding"
  echo "STOP: Re-run /create-batch-execution-plan or manually add missing sections."
fi
```

**Without `--auto-heal`:** If FAIL > 0, STOP. Fix the missing sections before proceeding to Step 3.5. Re-run `/create-batch-execution-plan [feature-name]` or manually add missing sections, then re-run the check.

**With `--auto-heal`:** If FAIL > 0, enter the Step 3 heal loop:

```
STEP3_RETRY = 0
MAX_STEP3_RETRIES = 2

WHILE FAIL > 0 AND STEP3_RETRY < MAX_STEP3_RETRIES:
  1. Classify the failure:
     a. File missing entirely
        → Re-run /create-batch-execution-plan [feature-name]
     b. Missing content sections (Wave Analysis, Visual Graphs, Execution Strategy, etc.)
        → Re-run /create-batch-execution-plan with explicit section checklist
        → If still missing after retry: flag as non-critical if the section is
           supplementary (e.g., "Visual Dependency Graph" — execution works without it)
           or critical (e.g., "Quick Reference" — /run-batch needs it to find batch IDs)
     c. Under 200-line minimum
        → Re-run with instruction to expand Wave Analysis and Execution Strategy sections
  2. Re-run the full FAIL check from Step 3
  3. STEP3_RETRY += 1
  4. Log to healing report: "Step 3 retry [N]: [failure type] — [action taken]"

IF still failing after MAX_STEP3_RETRIES:
  Log failure to healing report
  IF only supplementary sections are missing (Visual Graphs, Optimal Strategy):
    Log as WARNING, proceed to Step 3.5 — /run-batch can function without them
  ELSE (critical sections missing like Quick Reference, Wave Analysis):
    STOP — /run-batch cannot parse the batch plan without these sections
```

---

### Step 3.5: Auto-Generate Merge Point Configs

**MANDATORY when merge points exist.** After `BATCH_EXECUTION_PLAN.md` and `MERGE_POINTS.md` are both created, automatically generate `scripts/mp_configs/[feature-name]-mp[N].conf` for each merge point. This replaces the manual task of creating mp_configs per workstream.

#### 3.5a. Detect Merge Points

Read `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md` and count merge points:

```bash
MP_COUNT=$(grep -c "MERGE POINT\|^## Merge Point" docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md 2>/dev/null || echo "0")
```

**If MP_COUNT is 0:** Skip this step entirely.

    ## mp_config Generation: Skipped

    No merge points found in BATCH_EXECUTION_PLAN.md.
    No mp_config files needed.

**If MP_COUNT > 0:** Continue to 3.5b.

#### 3.5b. Extract Merge Point Data

For each merge point (MP1, MP2, ...), read the corresponding section in `MERGE_POINTS.md` to extract:

| Field | Source | Example |
|-------|--------|---------|
| `MP_ID` | Section header in MERGE_POINTS.md | `"MP1"` |
| `WORKSTREAM` | `[feature-name]` parameter | `"ui-improvements-audit-activity"` |
| `WORKSTREAM_DIR` | Standard path | `"docs/workstreams/[feature-name]"` |
| Worktree fields | Step 4 decision (single-branch vs worktree) | Empty for single-branch |
| `COMMIT_MSG` | Merge Actions section → `git commit -m "..."` | `"P0-B1: Foundation complete"` |
| `UNIT_TESTS` | Testing Strategy section OR Success Criteria commands | Array of test commands |
| `BUILD_CMD` | Container Deployment section | `"docker compose build deeptrail-control"` |
| `HEALTH_URL` | Container Test Scenarios section | `"http://localhost:8000/health"` |
| `SMOKE_ENDPOINTS` | Container Test Scenarios curl commands | Array of `"METHOD\|PATH\|JQ_CHECK\|LABEL"` |
| `SMOKE_TESTS` | Success Criteria file-existence checks | Array of `test -f` commands |
| `COMMIT_PATTERN` | Derived from feature name + batch name | `"foundation\|[feature-name]"` |
| `SUCCESS_CRITERIA` | Success Criteria section → verifiable commands | Array of commands |

#### 3.5c. Determine Worktree vs Single-Branch Mode

| Condition | Config Values |
|-----------|---------------|
| Step 4 will run `/setup-worktrees` | Set `WORKTREE_PATH`, `WORKTREE_BRANCH`, `TARGET_BRANCH`, `SYNC_PREFIX`, `MERGE_MSG` from worktree setup |
| Step 4 will skip worktrees (single-branch) | Set all worktree fields to empty: `WORKTREE_PATH=""`, `WORKTREE_BRANCH=""`, `TARGET_BRANCH=""`, `SYNC_PREFIX=""`, `MERGE_MSG=""` |

#### 3.5d. Generate Config File

For each merge point, create `scripts/mp_configs/[feature-name]-mp[N].conf` using this template:

```bash
#!/usr/bin/env bash
# Merge Point Configuration: [feature-name] MP[N] ([MP Title])
# Auto-generated by /run-plan on [date]
# Used by: scripts/execute_merge_point.sh

MP_ID="MP[N]"
WORKSTREAM="[feature-name]"
WORKSTREAM_DIR="docs/workstreams/[feature-name]"

# Git worktree / branch configuration
# Empty values = single-branch mode (no worktree sync)
WORKTREE_PATH="[path or empty]"
WORKTREE_BRANCH="[branch or empty]"
TARGET_BRANCH="[branch or empty]"
COMMIT_MSG="[from Merge Actions section]"
MERGE_MSG="[from Merge Actions section or empty for single-branch]"

# Directory prefix to sync from main repo to worktree (empty for single-branch)
SYNC_PREFIX="[prefix or empty]"

# Test commands (run from repo root, before merge)
UNIT_TESTS=(
    [extracted from Testing Strategy / Success Criteria]
)
INTEGRATION_TESTS=()
REGRESSION_TESTS=()
VERIFY_INTEGRATION="python scripts/verify_integration.py --warn-only"

# Container deployment
MIGRATION_CMD="[from Container Deployment or empty]"
BUILD_CMD="[from Container Deployment or empty]"
RESTART_CMD="[from Container Deployment or empty]"
HEALTH_URL="[from Container Test Scenarios or empty]"
HEALTH_TIMEOUT=60

# Additional deploy steps
DEPLOY_STEPS=(
    [extracted from Container Deployment or empty]
)

# Container smoke test configuration
# Set API_BASE only if the merge point involves backend services
API_BASE="[http://localhost:8000 or empty for frontend-only]"
LOGIN_EMAIL="test@example.com"
LOGIN_PASSWORD="testpass"

# Config-driven API endpoint smoke tests
# Format per entry: "METHOD|PATH|JQ_CHECK|LABEL"
# Extract from Container Test Scenarios curl commands
SMOKE_ENDPOINTS=(
    [extracted from Container Test Scenarios]
)

# Non-API smoke tests (file existence, build checks)
SMOKE_TESTS=(
    [extracted from Success Criteria file checks]
)

# Commit message pattern for merge verification
COMMIT_PATTERN="[derived from feature-name and batch title]"

# Alembic migration revision (empty if no migration)
EXPECTED_ALEMBIC_REV=""

# DB-specific check command (empty if not needed)
DB_CHECK_CMD=""

# Custom success criteria commands
SUCCESS_CRITERIA=(
    [extracted from Success Criteria verifiable commands]
)
```

**Extraction rules for populating the template:**

| Template Field | How to Extract from MERGE_POINTS.md |
|----------------|-------------------------------------|
| `UNIT_TESTS` | Look in "Testing Strategy" or the test commands in "Merge Actions" `## Verification` step |
| `BUILD_CMD` | First `docker compose build` or `npm run build` command in "Container Deployment" |
| `RESTART_CMD` | First `docker compose up -d` command in "Container Deployment" |
| `HEALTH_URL` | URL from health check curl in "Container Test Scenarios" |
| `SMOKE_ENDPOINTS` | Convert each `curl` in "Container Test Scenarios" to `"METHOD\|PATH\|JQ_CHECK\|LABEL"` format. Extract path relative to API_BASE, jq expression from the `\| jq` part, and derive a label from the comment above the curl |
| `SMOKE_TESTS` | Convert each `test -f` or `test -d` check from "Success Criteria" into an array entry |
| `COMMIT_PATTERN` | Use: `"[batch-title-keyword]\\\|[feature-name]"` (e.g., `"foundation\\\|ui-improvements"`) |
| `SUCCESS_CRITERIA` | Convert each verifiable checkbox from "Success Criteria" into a command (e.g., `"grep -q 'X' path/to/file"`) |

#### 3.5e. Verify Generated Configs

```bash
FEATURE="[feature-name]"
echo "=== Step 3.5: mp_config Generation ==="
for conf in scripts/mp_configs/${FEATURE}-mp*.conf; do
  if [ -f "$conf" ]; then
    bash -n "$conf" && echo "✅ $(basename $conf) — syntax valid" || echo "❌ $(basename $conf) — syntax error"
  fi
done
ls scripts/mp_configs/${FEATURE}-mp*.conf 2>/dev/null | wc -l | xargs -I{} echo "Generated: {} mp_config file(s)"
```

**Without `--auto-heal`:** If syntax check fails, fix the config file before proceeding. Common issues: unescaped quotes in array entries, missing closing parentheses.

**With `--auto-heal`:** If syntax check fails, enter the mp_config heal loop:

```
For each failing config file:
  1. Run `bash -n "$conf" 2>&1` to capture the specific syntax error
  2. Read the config file
  3. Fix the syntax error (common fixes: escape quotes in array entries,
     add missing closing parentheses, fix unmatched quotes)
  4. Re-run `bash -n "$conf"` to verify
  5. If still failing after 2 attempts: regenerate the config from scratch
     using the template and MERGE_POINTS.md data
  6. Log to healing report: "Step 3.5: [config-file] syntax fix — [error] → [fix]"
```

#### 3.5f. Report

    ## mp_config Generation: Complete

    | Merge Point | Config File | Status |
    |-------------|-------------|--------|
    | MP1 | scripts/mp_configs/[feature]-mp1.conf | ✅ Created |
    | MP2 | scripts/mp_configs/[feature]-mp2.conf | ✅ Created |

    These configs enable `execute_merge_point.sh` (belt-and-suspenders verification)
    during `/run-batch` Step 7e.

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

**Without `--auto-heal`:** If `/setup-worktrees` fails, fall back to single-branch execution:

    ## Worktree Setup FAILED (falling back to single-branch)

    /setup-worktrees encountered an error: [error]

    Falling back to single-branch execution.
    All tasks will execute in the main repo on the feature branch.

**With `--auto-heal`:** If `/setup-worktrees` fails, enter the Step 4 heal loop:

```
STEP4_RETRY = 0
MAX_STEP4_RETRIES = 2

WHILE setup fails AND STEP4_RETRY < MAX_STEP4_RETRIES:
  1. Classify the failure:
     a. Stale worktrees from previous runs
        → Run `git worktree list`, identify stale entries
        → Remove with `git worktree remove --force [path]`
        → Retry /setup-worktrees
     b. Branch already exists
        → Delete conflicting branch: `git branch -D feature/[old-branch]`
        → Retry /setup-worktrees
     c. Copy/permission failure
        → Verify target directory is writable
        → Manually copy .cursor/ and workstream files
        → Retry /setup-worktrees
  2. STEP4_RETRY += 1
  3. Log to healing report: "Step 4 retry [N]: [failure type] — [action taken]"

IF still failing after MAX_STEP4_RETRIES:
  Log failure to healing report
  Fall back to single-branch execution (worktrees are optional)
  Log: "Step 4: Worktree setup failed after [N] retries — falling back to single-branch"
```

Worktree failures are **never fatal** — single-branch execution always works. The heal loop tries to fix the issue, but gracefully degrades if it can't.

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
    | mp_configs ([N] files) | ✅ [list] (or "N/A — no merge points") |
    | Worktrees | ✅ [list] (or "N/A — single-branch") |

    ### Batch Overview

    | Batch | Tasks | Waves | Focus |
    |-------|-------|-------|-------|
    | 1 | [task IDs] | [N] | [focus description] |
    | 2 | [task IDs] | [N] | [focus description] |
    | ... | ... | ... | ... |

    ---
    Approve plan? (yes — write state + enable /run-batch / review — open BATCH_EXECUTION_PLAN.md / cancel)

#### Healing Summary (if `--auto-heal` was used)

*Include this section in the checkpoint report ONLY if `--auto-heal` was set and any healing occurred.*

    ### Healing Summary

    | Step | Issue | Retries | Outcome |
    |------|-------|---------|---------|
    | Step 1 | CODEBASE_ANALYSIS.md missing | 1 | Healed (re-ran exploration) |
    | Step 2 | MERGE_POINTS.md missing "Container Tests" | 2 | Healed (injected from template) |
    | Step 3 | Under 200-line minimum | 1 | Healed (expanded Wave Analysis) |
    | Step 3.5 | mp1.conf syntax error (unescaped quote) | 1 | Healed (fixed escaping) |
    | Step 4 | Stale worktree /tmp/wt-old | 1 | Healed (removed stale, retried) |

    **Healing Totals:**
    - Steps healed: [N] of 5
    - Total retries: [N]
    - Steps that required fallback: [N] (e.g., worktree → single-branch)

#### Checkpoint Decision

**Without `--skip-checkpoint`:**

Wait for user response before continuing:

- **yes**: proceed to Write PIPELINE_STATE.md, then offer to run `/run-batch [FIRST_BATCH] [feature-name]`
- **review**: present the full `BATCH_EXECUTION_PLAN.md` content and wait for approval
- **cancel**: STOP; do NOT write PIPELINE_STATE.md; workstream artifacts remain on disk for review

**With `--skip-checkpoint`:**

1. **Still print the full checkpoint report** (for auditability — the user can review it later)
2. **Append:** `Auto-approving plan... (--skip-checkpoint flag)`
3. **Auto-write** `PIPELINE_STATE.md` (proceed to the "Write PIPELINE_STATE.md" step below)
4. **Resolve first batch ID** from the Quick Reference table in `BATCH_EXECUTION_PLAN.md`
5. **Auto-chain into execution** if `--auto-heal` is also set:
   ```
   /run-batch [FIRST_BATCH] [feature-name] --continue --auto-heal
   ```
   If `--auto-heal` is NOT set:
   ```
   /run-batch [FIRST_BATCH] [feature-name] --continue
   ```
6. **Safety gate — do NOT auto-approve if ANY of these are true:**
   - Any step exhausted its retry budget and STOPPED (healing failed)
   - BATCH_EXECUTION_PLAN.md is missing critical sections (Quick Reference, Wave Analysis)
   - Total tasks count is 0 (breakdown produced no tasks)
   - BREAKDOWN.md classified ALL tasks as "Create" with 0 "Modify"/"Verify" (suggests
     codebase exploration was not effective — 60% of tasks are usually Modify/Verify)

   If the safety gate fails:
   ```
   ## Auto-Approve BLOCKED: [reason]

   --skip-checkpoint was set but the plan failed quality checks:
   - [specific reason]

   Please review the plan manually and respond: (yes / review / cancel)
   ```
   Fall back to the normal checkpoint behavior (wait for user).

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

Run `/run-batch [FIRST_BATCH] [feature-name]` to begin execution (FIRST_BATCH = first row of the Quick Reference table in BATCH_EXECUTION_PLAN.md).

## Plan Approval
User approved plan checkpoint on [date].
Total tasks: [N] | Batches: [N] | Critical path: [chain]
Worktrees: [N created / single-branch]
```

**Then resolve the first batch ID dynamically and offer to start execution:**

```bash
# Extract first batch ID from Quick Reference table
FIRST_BATCH=$(grep -E '^\| P[0-9]+-B[0-9]+' docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md | head -1 | awk -F'|' '{print $2}' | tr -d ' ')
echo "First batch: $FIRST_BATCH"
```

**Why dynamic resolution:** The first batch ID is typically `P0-B1` but is defined by `/create-batch-execution-plan`. Reading it from the Quick Reference table guarantees correctness regardless of how batches were named.

**Without `--skip-checkpoint`:**

    PIPELINE_STATE.md written. ✅ PLAN phase is complete.

    To start execution:
    ```
    /run-batch [FIRST_BATCH] [feature-name]
    ```

    Start first batch now? (yes / pause)

If user says "yes": automatically run `/run-batch [FIRST_BATCH] [feature-name]`.
If user says "pause": stop and report the command to run when ready.

**With `--skip-checkpoint`:**

    PIPELINE_STATE.md written. ✅ PLAN phase is complete.
    Auto-chaining into execution... (--skip-checkpoint flag)
    First batch ID (from Quick Reference): [FIRST_BATCH]

Automatically invoke:

```
# If --auto-heal was also set:
/run-batch [FIRST_BATCH] [feature-name] --continue --auto-heal

# If --auto-heal was NOT set:
/run-batch [FIRST_BATCH] [feature-name] --continue
```

This is the full AFK handoff — the agent transitions from PLAN to EXECUTE without human intervention.

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
| Feature branch exists | Created by `/setup-worktrees` or by `/run-batch` (first batch) |
| `BATCH_EXECUTION_PLAN.md` exists | ✅ Created in Step 3 |
| `WORKSTREAM.md` exists | ✅ Created in Step 2 |
| `STATUS.md` exists | ✅ Created in Step 2 |
| `BREAKDOWN.md` exists | ✅ Created in Step 1 |
| `CODEBASE_ANALYSIS.md` exists | ✅ Created in Step 1 |
| `MERGE_POINTS.md` exists | ✅ Created in Step 2 |
| `PIPELINE_STATE.md` exists | ✅ Written after checkpoint approval |
| Prior batch complete (N/A for first batch) | ✅ N/A |
| mp_configs exist (for `/run-batch` Step 7e) | ✅ Created in Step 3.5 (if merge points exist) |

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
echo "--- mp_config Files ---"
MP_CONFIGS=$(ls scripts/mp_configs/${FEATURE}-mp*.conf 2>/dev/null | wc -l | tr -d ' ')
echo "Found: ${MP_CONFIGS} mp_config file(s)"
for conf in scripts/mp_configs/${FEATURE}-mp*.conf; do
  [ -f "$conf" ] && bash -n "$conf" 2>/dev/null && echo "✅ $(basename $conf)" || true
done

echo ""
echo "--- Worktree Status ---"
git worktree list

echo ""
echo "--- Ready for Execution ---"
FIRST_BATCH=$(grep -E '^\| P[0-9]+-B[0-9]+' docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md | head -1 | awk -F'|' '{print $2}' | tr -d ' ')
echo "Run: /run-batch ${FIRST_BATCH} ${FEATURE}"
echo "=== Done ==="
```

---

## Relationship to /pipeline

`/pipeline` is the top-level command that orchestrates ALL five phases (DEFINE → PLAN → EXECUTE → REVIEW → SHIP). `/run-plan` is a focused automation for just the PLAN phase, giving users who already have a design doc a fast path to execution without running the full 5-phase pipeline.

```
Full automation:     /pipeline docs/design/feature.md
PLAN only:           /run-plan feature-name docs/design/feature.md
EXECUTE only:        /run-batch P0-B1 feature-name
PLAN + EXECUTE:      /run-plan feature-name docs/design/feature.md
                     → (after checkpoint + approval) /run-batch P0-B1 feature-name
                     → /run-batch P0-B2 feature-name ...
Full AFK:            /run-plan feature-name docs/design/feature.md --auto-heal --skip-checkpoint
                     → (auto-chains into) /run-batch P0-B1 feature-name --continue --auto-heal
                     → /run-batch P0-B2 ... → workstream complete
```

---

## Common Rationalizations

| Rationalization | Why It Is Wrong |
|----------------|----------------|
| "I'll run the 4 commands manually" | Manual execution skips the per-step verification, the checkpoint, and does not write `PIPELINE_STATE.md`. `/run-batch` pre-flight will fail without it. |
| "I don't need /explore-codebase, I know the codebase" | `/breakdown-design` runs exploration internally. The Feb 2026 lesson proved 60% of 'missing' items already existed. Never skip it. |
| "I'll skip /setup-worktrees for multi-service features" | Without worktrees, parallel service tracks must share a branch, creating merge conflicts and blocking parallel execution. |
| "I don't need to wait for user approval at checkpoint" | `PIPELINE_STATE.md` is only written after approval. Without it, `/run-batch` pre-flight fails with "PLAN Phase Incomplete". Use `--skip-checkpoint` explicitly if you want to bypass this. |
| "The plan phase is done when /breakdown-design finishes" | Plan phase is done only when all artifacts are verified, the user has reviewed and approved the batch plan, AND `PIPELINE_STATE.md` is written. |
| "I'll use --skip-checkpoint to save time on every run" | `--skip-checkpoint` skips human review of the plan. Use it only when you trust the design doc and want full AFK. For new or complex features, human review of the batch plan catches architectural mistakes. |
| "The sub-command failed, so I'll stop and ask the user" | With `--auto-heal`, retry first. Most sub-command failures are transient (incomplete output, missing sections) and resolve on retry. Only stop after retries are exhausted. |
| "--auto-heal makes the plan phase reliable, so --skip-checkpoint is always safe" | Auto-heal ensures the plan *completes* but doesn't ensure the plan is *correct*. A plan where all tasks are classified as "Create" (no codebase exploration) will pass all quality checks but produce a bad workstream. |

## Red Flags

- Running `/run-batch` before `/run-plan` finishes (`PIPELINE_STATE.md` won't exist — pre-flight will fail)
- Skipping the worktree decision for multi-service features (they will have conflicts)
- Writing `PIPELINE_STATE.md` without the user approving the plan (defeats the checkpoint — unless `--skip-checkpoint` is explicitly set)
- Missing `CODEBASE_ANALYSIS.md` after Step 1 completes (exploration was skipped)
- BREAKDOWN.md classifying ALL tasks as "Create" (exploration was not done properly)
- Manually creating mp_config files instead of letting Step 3.5 auto-generate them
- Missing mp_configs when merge points exist (`/run-batch` Step 7e will have nothing to run)
- Using `--skip-checkpoint` on a feature with security/crypto/auth tasks (these need human plan review)
- Auto-heal retrying a sub-command more than MAX_RETRIES (indicates a deeper issue)
- Not including the Healing Summary in the checkpoint report when `--auto-heal` was used
- Using `--skip-checkpoint` without `--auto-heal` (plan may reach checkpoint in a broken state)

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
5. **Step 3.5** — detects 2 merge points → auto-generates `scripts/mp_configs/claude-code-integration-mp1.conf` and `claude-code-integration-mp2.conf`
6. **Step 4** — reads BREAKDOWN.md parallelization section; runs `/setup-worktrees claude-code-integration` if multi-service
7. **Checkpoint** — presents: 3 workstreams, 12 tasks, 4 batches, 2 merge points, critical path — "Approve plan?"
8. **State** — after approval: writes `PIPELINE_STATE.md` with PLAN phase ✅
9. **Handoff** — "Start first batch now? → `/run-batch P0-B1 claude-code-integration`"

Total: 1 command instead of running 5+ commands manually.

## Example: Self-Healing Plan Phase

```
/run-plan agent-auth docs/design/agent-auth-flow.md --auto-heal
```

The agent will:

1. **Pre-flight** — verify design doc exists
2. **Step 1** — `/breakdown-design` runs, but CODEBASE_ANALYSIS.md is incomplete (exploration timed out)
   - **Self-heal:** Re-run exploration with narrower scope (just `deepsecure/_core/` and `deeptrail-control/app/`)
   - Second attempt produces complete CODEBASE_ANALYSIS.md — healed
3. **Step 2** — `/create-workstream` produces MERGE_POINTS.md missing "Container Test Scenarios"
   - **Self-heal:** Re-run `/create-workstream` with explicit section requirements
   - Second attempt still missing → inject section from `MERGE_POINT_GUIDE.md` template — healed
4. **Step 3** — `/create-batch-execution-plan` succeeds on first attempt
5. **Step 3.5** — mp1.conf has unescaped quote in SMOKE_ENDPOINTS array
   - **Self-heal:** Read bash syntax error, fix escaping, re-verify — healed
6. **Step 4** — Stale worktree from previous run blocks creation
   - **Self-heal:** Remove stale worktree, retry — healed
7. **Checkpoint** — presents plan with Healing Summary (4 heals across 4 steps)
   - Waits for user approval (no `--skip-checkpoint`)

The plan reached the checkpoint reliably — without `--auto-heal`, it would have stopped at Step 1.

## Example: Full AFK Mode (Design Doc to Shipped Code)

```
/run-plan agent-auth docs/design/agent-auth-flow.md --auto-heal --skip-checkpoint
```

The agent will:

1. **Steps 1-4** — same as above, with self-healing as needed
2. **Checkpoint** — prints the full plan report for auditability
   - Safety gate passes: tasks include Modify/Verify (not all Create), critical sections present
   - Auto-approves: writes `PIPELINE_STATE.md`
3. **Auto-chain** into `/run-batch P0-B1 agent-auth --continue --auto-heal`
4. **Execution** — `/run-batch` runs all batches with self-healing and auto-chaining
5. **Completion** — entire workstream completes autonomously

From one command to a fully planned and executed workstream — write the design doc, walk away, check results later.
