# Complete Task and Generate Report

Generate a completion report for a finished task.

## Instructions

1. **Identify the task:**
   - Get the task ID (e.g., WS-A1) from the user
   - Read the original task ticket from `docs/workstreams/[feature]/tasks/[WS-ID]-*.md`

2. **Gather implementation details:**
   - Review git diff or recent commits for changes made
   - Check which files were modified/created
   - Run tests and capture results
   - Note any deviations from the original plan

3. **Create the completion report (LOCAL + MAIN REPO):**

   The report MUST be created where execution happened (local worktree) for accuracy,
   AND also written to main repo for consolidated visibility.

   ```bash
   # Determine paths
   LOCAL_REPO=$(pwd)  # Current worktree or main repo
   MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
   
   # Local report location (where execution data is visible)
   LOCAL_REPORTS_DIR="$LOCAL_REPO/docs/workstreams/[feature]/reports"
   LOCAL_REPORT_FILE="$LOCAL_REPORTS_DIR/[WS-ID]-completion.md"
   
   # Main repo report location (for consolidated visibility)
   MAIN_REPORTS_DIR="$MAIN_REPO/docs/workstreams/[feature]/reports"
   MAIN_REPORT_FILE="$MAIN_REPORTS_DIR/[WS-ID]-completion.md"
   ```
   
   **Step 3a. Create reports folders if missing:**
   ```bash
   # Create locally (where we are)
   mkdir -p docs/workstreams/[feature]/reports
   
   # Create in main repo (for consolidated view)
   mkdir -p $MAIN_REPO/docs/workstreams/[feature]/reports
   ```
   
   **Step 3b. Generate report file LOCALLY first:**
   
   1. Read the template: `docs/workstreams/COMPLETION_REPORT_TEMPLATE.md`
   2. Fill in the template with actual execution data (see Step 4 for content)
   3. **USE THE WRITE TOOL** to create the file:
   
   ```
   Write:
     path: docs/workstreams/[feature]/reports/[WS-ID]-completion.md
     contents: |
       # Completion Report: [WS-ID] [Task Name]
       
       ## Summary
       | Field | Value |
       |-------|-------|
       | **Final Status** | `completed` |
       | **Task Ticket** | [link] |
       ... (full report content from template)
   ```
   
   - File naming convention: `[WS-ID]-completion.md` (e.g., `WS-A1-completion.md`)
   - **This is where the agent can see git changes, run tests, etc.**
   
   **Step 3c. Write SAME report to MAIN REPO:**
   
   **USE THE WRITE TOOL** with absolute path to main repo:
   
   ```
   Write:
     path: /Users/.../[main-repo]/docs/workstreams/[feature]/reports/[WS-ID]-completion.md
     contents: |
       # Completion Report: [WS-ID] [Task Name]
       ... (same content as local report)
   ```
   
   **Get the absolute path:**
   ```bash
   MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
   # Then use: $MAIN_REPO/docs/workstreams/[feature]/reports/[WS-ID]-completion.md
   ```
   
   This ensures main repo has the accurate report immediately.
   
   **Why both locations?**
   - LOCAL: Agent has visibility into execution (git diff, tests, files)
   - MAIN REPO: Consolidated view, links work, reports accessible to all worktrees

4. **Fill in the report with:**

   **Summary:**
   - Final status (completed/partial/failed)
   - Time taken vs estimated
   
   **Accuracy Assessment:**
   - Completion percentage (0-100%)
   - Check each acceptance criterion: ✅ / ❌ / ⚠️
   - Note any scope deviations
   
   **Implementation Details:**
   - Approach taken
   - Key decisions made
   - Files changed with line counts
   
   **Testing:**
   - Tests added
   - Test results (run `pytest` if needed)
   - Document any failures with root cause
   
   **Blockers:**
   - Any blockers encountered and how resolved
   
   **Lessons Learned (Categorized):**
   - **Protocol:** [e.g., "MCP initialize must complete before tools/list"]
   - **Security:** [e.g., "Never forward agent tokens to backends"]
   - **Integration:** [e.g., "E2E tests need deterministic test data"]
   - **Performance:** [e.g., "Batch database queries in loops"]
   - **Architecture:** [e.g., "Keep gateway stateless for scaling"]
   - **Identify if anything should be added to CLAUDE.md**
   
   **Validation Confirmed:**
   - Demo validated: [Demo 1, 2, or N/A]
   - User journey step validated: [Step 3, or N/A]

5. **Update the task ticket:**
   - Change status to `completed`
   - Add completion date

6. **Update the workstream tracker (WORKSTREAM.md):**
   - Mark task as complete in the task table
   - Update progress percentage
   - Update batch status if batch is complete
   - Update Task Tickets section
   - Add to Completion Reports list
   - Add to History

6.5. **CRITICAL: Always update MAIN REPO using absolute paths:**

```bash
# Always determine main repo path (works from any worktree or main repo)
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
# Example result: /Users/imaxxs/repositories/deepsecure-mvp
```

**IMPORTANT:** Use the StrReplace tool with the **full absolute path** to main repo files:

```
# Example - updating STATUS.md from a worktree:
# NOTE: Replace [feature] with actual feature name (e.g., virtual-mcp-server-mvp)
StrReplace:
  path: $MAIN_REPO/docs/workstreams/[feature]/STATUS.md
  old_string: "Tasks Complete: 2/44"
  new_string: "Tasks Complete: 3/44"
```

**Files to update in MAIN REPO (using absolute paths):**
1. `$MAIN_REPO/docs/workstreams/[feature]/STATUS.md` - Task status, metrics
2. `$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md` - Batch status, task table
3. `$MAIN_REPO/docs/[feature]/EXECUTION_STATUS.md` - Phase tracking
4. `$MAIN_REPO/docs/EXECUTION_STATUS.md` - Global portfolio

7. **Automatically update STATUS.md (MAIN REPO - Consolidated View):**

**CRITICAL:** Always update the MAIN REPO's STATUS.md for consolidated visibility.

```bash
# Determine main repo path
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
# Example: /Users/imaxxs/repositories/deepsecure-mvp

# File to update:
STATUS_FILE="$MAIN_REPO/docs/workstreams/[feature]/STATUS.md"
```

**Use the StrReplace tool to update `$MAIN_REPO/docs/workstreams/[feature]/STATUS.md`:**

   a. **Move task from "Ready" or "In Progress" to "Completed" section:**
      - Add row to "✅ Completed" table with completion date, worktree name, and report link
      - Remove from "🔄 In Progress" or "⏳ Ready" table
   
   b. **Update progress metrics (at top of file):**
      - Increment "Tasks Complete" count
      - Update overall progress percentage: `(completed / total) * 100`
      - Decrement "Tasks In Progress" or "Tasks Ready" count
   
   c. **Update batch progress bar:**
      - Update the ASCII progress bar for the current batch
      - Example: `Batch 1  [██████░░░░] 66%` → `Batch 1  [██████████] 100% ✅`
   
   d. **Update workstream status table:**
      - Increment "Tasks Done" for the workstream
      - Update progress percentage
      - Change status to `✅ Complete` if all tasks in workstream done
   
   e. **Check if batch is complete:**
      - If all tasks in current batch are done, update batch progress to 100%
      - Update "Current Batch" to next batch
      - Mark any newly unblocked tasks as "Ready"
   
   f. **Check merge points:**
      - If completed task is part of a merge point, check if all converging tasks are done
      - If merge point is complete, update its status and add timestamp
   
   g. **Update demo/journey validation:**
      - If task validates a demo, check if all validating tasks are complete
      - Update "All Complete?" column accordingly
   
   h. **Add to Timeline (if present):**
      - Add entry: `[date] | Task [WS-ID] completed in [worktree-name]`
   
   i. **Update "Last Updated" timestamp** at top of file

7.5. **Automatically update WORKSTREAM.md (MAIN REPO):**

```bash
WORKSTREAM_FILE="$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md"
```

**Use the StrReplace tool to update `$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md`:**

   a. **Update task status in "All Tasks" section:**
      - Change task status from `ready` or `in progress` to `✅ `complete``
      - Example: `| A1 | ... | `ready` |` → `| A1 | ... | ✅ `complete` |`
   
   b. **Update newly ready tasks (dependencies satisfied):**
      - Change dependent tasks from `pending` to `ready`
   
   c. **Update Batch Execution Model:**
      - If all tasks in batch are complete, update batch status to `✅ `complete``
      - Update next batch status to `ready`
   
   d. **Update Workstreams table:**
      - If workstream status changes (first task → `in_progress`, all done → `complete`)
   
   e. **Update Progress section:**
      - Update progress bar and percentage
      - Update metrics table (Completed, In Progress, Ready, Pending counts)
   
   f. **Update Task Tickets section:**
      - Move task from current batch to completed section
      - Add newly ready tasks to ready section
   
   g. **Update Completion Reports section:**
      - Add link to new completion report
   
   h. **Update History:**
      - Add entry: `| [date] | [WS-ID] completed - [description] |`

8. **Check for newly unblocked tasks:**
   - Identify tasks that depended on the completed task
   - If all their dependencies are now met, update their status to `ready`
   - Create task tickets for newly ready tasks if not already created

9. **Update `$MAIN_REPO/docs/[design-name]/EXECUTION_STATUS.md`** (per-design execution):

```bash
EXEC_STATUS="$MAIN_REPO/docs/[design-name]/EXECUTION_STATUS.md"
```

**Use the StrReplace tool to update this file:**
   
   a. **Update Phase 3 batch status:**
      - If batch is complete, mark batch as ✅
      - Update batch completion percentage
   
   b. **Check phase completion:**
      - If all batches complete, update Phase 3 to ✅ Complete
      - Update Phase 4 status if learnings captured
   
   c. **Update demo/journey validation:**
      - If task validates a demo, check if all demo tasks complete
      - If task validates a user journey step, update status
   
   d. **Add to Command Execution Log:**
      - Entry: `| [date] | /complete-task [WS-ID] | ✅ | Completed in [worktree-name] |`
   
   e. **Update Milestones:**
      - Check if any milestones are now complete
   
   f. **Update Overall Progress in metrics table:**
      - Update "Overall Progress" row

10. **Update `$MAIN_REPO/docs/EXECUTION_STATUS.md`** (global portfolio):

```bash
GLOBAL_STATUS="$MAIN_REPO/docs/EXECUTION_STATUS.md"
```

**Use the StrReplace tool to update:**
    - Update progress percentage for this design in "Active Designs" table
    - If design completes, move to "Completed" section

---

## Tool Actions Summary (CRITICAL)

**You MUST use these tools explicitly:**

```bash
# First, determine main repo path
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
```

| Step | Tool | File | Action |
|------|------|------|--------|
| 3a | `Shell` | `mkdir -p` | Create reports folders |
| 3b | **`Write`** | `docs/workstreams/[feature]/reports/[WS-ID]-completion.md` | **CREATE completion report locally** |
| 3c | **`Write`** | `$MAIN_REPO/docs/.../reports/[WS-ID]-completion.md` | **CREATE completion report in main repo** |
| 5 | `StrReplace` | Task ticket | Update status to `completed` |
| 7 | `StrReplace` | STATUS.md | Update task status, metrics |
| 7.5 | `StrReplace` | WORKSTREAM.md | Update batch status, task table |
| 9 | `StrReplace` | EXECUTION_STATUS.md (per-design) | Update batch, command log |
| 10 | `StrReplace` | EXECUTION_STATUS.md (global) | Update global progress |

---

## Files to Update (Summary)

When `/complete-task` runs, these files must be updated:

```bash
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
# Example: /Users/imaxxs/repositories/deepsecure-mvp
```

| # | File | Tool | Updates |
|---|------|------|---------|
| 1 | `docs/workstreams/[feature]/reports/[WS-ID]-completion.md` | **Write** | **CREATE completion report locally** |
| 2 | `$MAIN_REPO/docs/workstreams/[feature]/reports/[WS-ID]-completion.md` | **Write** | **CREATE completion report in main repo** |
| 3 | `$MAIN_REPO/docs/workstreams/[feature]/STATUS.md` | StrReplace | Task → Complete, metrics, batch progress |
| 4 | `$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md` | StrReplace | All Tasks table, Batch Execution Model, Progress, History |
| 5 | `$MAIN_REPO/docs/[design]/EXECUTION_STATUS.md` | StrReplace | Batch status, command log, demos/journey |
| 6 | `$MAIN_REPO/docs/EXECUTION_STATUS.md` | StrReplace | Global progress % |
| 7 | `docs/workstreams/[feature]/tasks/[WS-ID]-*.md` | StrReplace | Task ticket → status: completed |

**Example absolute paths** (substitute `[feature]` and `[design]` with actual names):
```
$MAIN_REPO/docs/workstreams/[feature]/STATUS.md
$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md
$MAIN_REPO/docs/[design]/EXECUTION_STATUS.md
$MAIN_REPO/docs/EXECUTION_STATUS.md

# Concrete example for virtual-mcp-server-mvp:
# /Users/.../deepsecure-mvp/docs/workstreams/virtual-mcp-server-mvp/STATUS.md
```

**Critical:** The StrReplace tool works with absolute paths, so updates from worktrees to main repo ARE possible.

---

## Template Location
`docs/workstreams/COMPLETION_REPORT_TEMPLATE.md`

## Output Format

After creating the report, output:

```markdown
## Completion Report Generated

**File:** `docs/workstreams/[feature]/reports/[WS-ID]-completion.md`

### Summary
- **Status:** completed ✅
- **Accuracy:** [X]%
- **Time:** Estimated [S/M/L] → Actual [X hours]

### Acceptance Criteria Results
| Criterion | Status |
|-----------|--------|
| [criterion 1] | ✅ |
| [criterion 2] | ✅ |
| [criterion 3] | ⚠️ partial |

### Test Results
- Passed: X
- Failed: Y
- Coverage: Z%

### Files Changed
- `file1.py` (+50/-10)
- `file2.py` (+30/-5)

### Validation Confirmed
- **Demo validated:** [Demo 1, or N/A]
- **User journey step validated:** [Step 3, or N/A]

### Contract Verification
| Check | Spec | Implemented | Match |
|-------|------|-------------|-------|
| Endpoint path | `/api/v1/from/spec` | `/api/v1/from/impl` | ✅ / ❌ |
| Request schema | [matches] | [matches] | ✅ / ❌ |
| Test endpoints | [correct] | [correct] | ✅ / ❌ |

### File Location Verification
| Artifact | Expected | Actual | Correct? |
|----------|----------|--------|----------|
| E2E test | `tests/e2e/` (root) | [actual] | ✅ / ❌ |
| Demo | `demos/` (root) | [actual] | ✅ / ❌ |

### Learnings by Category
| Category | Learning |
|----------|----------|
| Protocol | [if any] |
| Security | [if any] |
| Integration | [if any] |
| Contract | [any spec/impl mismatches] |
| File Org | [any location issues] |

### CLAUDE.md Update Recommended?
- [ ] Yes: "[suggested addition]" (Category: [Protocol/Security/Integration/etc.])
- [x] No generalizable learnings

---

### STATUS.md Updated
- **Overall Progress:** [X]% → [Y]% ([N]/[Total] tasks)
- **Batch Progress:** Batch [N] now [X]% complete
- **Workstream [WS]:** [X]/[Y] tasks complete
- **Newly Ready Tasks:** [list of task IDs now unblocked, or "None"]
- **Merge Point Status:** [MP status if applicable]

---

Task [WS-ID] is now complete. Downstream tasks can proceed.
```

## Automatic Checks

Before generating the report, verify:
1. `make lint` passes (or note failures)
2. `pytest [relevant tests]` passes (or document failures)
3. All acceptance criteria can be evaluated
4. **Contract verification passes** (see below)
5. **File locations are correct** (see below)

### Contract Verification (BLOCKING)

**This check MUST pass before task can be completed:**

```bash
# 1. Extract implemented endpoints
IMPL_ENDPOINTS=$(grep -r "@router\.\(get\|post\|put\|delete\)" [impl_file] | grep -o '"/api/v1[^"]*"' | sort -u)

# 2. Extract test endpoints
TEST_ENDPOINTS=$(grep -r '"/api/v1' [test_file] | grep -o '"/api/v1[^"]*"' | sort -u)

# 3. Compare with spec (from task ticket's Specification section)
```

**If endpoints don't match:**
- Do NOT complete task
- Report: "Contract mismatch - implementation uses `/api/v1/X` but spec says `/api/v1/Y`"
- Fix implementation OR update design doc + spec first

### File Location Verification (BLOCKING)

**Verify cross-service artifacts are at root level:**

| Check | Command | Expected |
|-------|---------|----------|
| E2E tests | `ls tests/e2e/test_*_journey.py` | Cross-service tests here |
| Demos | `ls demos/demo_*.py` | MVP demos here |
| Demo tests | `ls tests/demos/test_demo_*.py` | Demo tests here |

**If files are in wrong location:**
- Move to correct location before completing
- Update any imports that reference old location

### Technical Requirements Verification

```bash
# Check for common async fixture mistake
if grep -q "@pytest.fixture" [test_file] && grep -q "async def" [test_file]; then
  echo "WARNING: Async fixtures should use @pytest_asyncio.fixture"
fi
```

## Example Usage

User: "Complete task WS-A1 for the virtual-mcp-server-mvp feature"

Then:
1. Read `docs/workstreams/virtual-mcp-server-mvp/tasks/WS-A1-*.md`
2. Check git status/diff for recent changes
3. Run relevant tests
4. Generate `docs/workstreams/virtual-mcp-server-mvp/reports/WS-A1-completion.md`
5. Update task ticket status to `completed`
6. Update WORKSTREAM.md task table
7. **Automatically update STATUS.md:**
   - Move A1 from "Ready" to "Completed" section
   - Update progress: 0% → 2% (1/44 tasks)
   - Update WS-A: 0/8 → 1/8 tasks
   - Update Batch 1 progress
   - Check if A2, A3, A5 are now ready (they depend on A1)
   - Add timeline entry
8. Create task tickets for newly ready tasks (A2, A3, A5)
