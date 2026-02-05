# Sync Worktree Status

Consolidate task status from all parallel worktrees into the main repo's status files.

## ⚠️ MUST RUN FROM MAIN REPO

**This command must be run from the main repository, NOT from a worktree.**

```bash
# ✅ Correct - run from main repo
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp

# ❌ Wrong - do NOT run from worktree
cd /Users/imaxxs/repositories/vmcp-gateway
/sync-worktree-status virtual-mcp-server-mvp  # Will not work correctly!
```

**Why:** The agent needs to operate in the main repo context to update its files.
When run from a worktree, the agent cannot reliably write to the main repo.

## Usage

```
/sync-worktree-status [feature-name]
```

**Parameters:**
- `[feature-name]`: The workstream/feature name (e.g., `virtual-mcp-server-mvp`, `oauth-token-refresh`)

---

## ⚠️ Pre-Check: Auto-Sync Already Active?

**IMPORTANT:** The `/execute-task` and `/complete-task` commands already auto-update the main repo's status files. 

### Before Running This Command, Check:

1. **Are `/execute-task` and `/complete-task` properly updating the main repo?**
   - If YES → You likely **don't need** `/sync-worktree-status`
   - If NO → This command is a fallback for manual consolidation

2. **When to use this command:**
   - `/execute-task` or `/complete-task` failed to update main repo
   - Status files got out of sync due to git conflicts
   - You want to verify/reconcile status across worktrees
   - Initial sync after creating worktrees from existing branches

3. **When NOT to use this command:**
   - Auto-sync via `/execute-task` and `/complete-task` is working correctly
   - A task is currently in progress (wait for completion first)

### Skip Condition

If the main repo's STATUS.md "Last Updated" timestamp is recent (within the last hour) and matches expected task completions, **skip this command** and report:

```markdown
## Sync Skipped: Auto-Sync Active

The main repo's STATUS.md appears to be up-to-date.

**Last Updated:** [timestamp]
**Tasks Completed:** [X]/[Y]

Auto-sync via `/execute-task` and `/complete-task` is active.
Manual sync is not required.

If you believe status is out of sync, run:
`/sync-worktree-status [feature-name] --force`
```

---

## When to Use

Run this command from the **main repo** when:
- Auto-sync failed or wasn't configured
- Status files in worktrees have diverged from main repo
- You need to reconcile after git merge conflicts
- Initial setup after worktrees already have completed tasks

## Instructions

### 0. Check if Sync is Needed

Before proceeding, verify that manual sync is actually needed:

```bash
# Check main repo STATUS.md last modified time
ls -la docs/workstreams/[feature-name]/STATUS.md

# Check if it was recently updated (within last hour)
# If recently updated and task counts match worktrees, skip sync
```

**Compare main repo vs worktrees:**

| Check | Main Repo | Worktree A | Worktree B | Sync Needed? |
|-------|-----------|------------|------------|--------------|
| Tasks Complete | 2 | 1 (A1) | 1 (B1) | ✅ Yes - diverged |
| Tasks Complete | 2 | 1 (A1) | 1 (B1) | ❌ No - already synced |

**If main repo already reflects consolidated status:**
- Report "Sync not needed - auto-sync is active"
- Exit without making changes

**If diverged or user passes `--force`:**
- Proceed with sync

### 1. Get Feature Name from User

The feature name determines which files to sync:
- `docs/workstreams/[feature-name]/STATUS.md` - Task-level status
- `docs/workstreams/[feature-name]/WORKSTREAM.md` - Workstream overview and task tables
- `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md` - Execution waves and checkboxes
- `docs/[feature-name]/EXECUTION_STATUS.md` - Phase-level status

### 2. Identify All Worktrees

```bash
git worktree list
```

Example output:
```
/path/to/main-repo                abc123 [dev]
/path/to/worktree-a               def456 [feature/ws-a]
/path/to/worktree-b               ghi789 [feature/ws-b]
```

The first entry is always the main repo. All others are worktrees.

### 3. Read Status Files from Each Worktree

For each worktree (excluding main repo), read its status files:

**a. STATUS.md:**
```
[worktree-path]/docs/workstreams/[feature-name]/STATUS.md
```

Extract:
- Completed tasks (from "✅ Completed" section)
- In-progress tasks (from "🔄 In Progress" section)
- Ready tasks (from "⏳ Ready" section)
- Batch progress percentages

**b. WORKSTREAM.md:**
```
[worktree-path]/docs/workstreams/[feature-name]/WORKSTREAM.md
```

Extract:
- Task status updates in workstream tables (WS-A, WS-B, etc.)
- Ticket links for created tasks
- Overall progress percentage

**c. Completion Reports:**
```
[worktree-path]/docs/workstreams/[feature-name]/reports/*.md
```

Extract:
- List of completion report files
- Completion dates from report metadata

### 4. Merge Completed Tasks

Consolidate all completed tasks from all worktrees into a single list:

| Task | Completed In | Completion Date | Report |
|------|--------------|-----------------|--------|
| [task-id] | [worktree-name] | [date] | [link] |
| ... | ... | ... | ... |

**De-duplicate:** If the same task appears in multiple worktrees, use the earliest completion date.

### 5. Update Main Repo STATUS.md

Update `docs/workstreams/[feature-name]/STATUS.md` in the main repo:

a. **Move all completed tasks to "✅ Completed" section**
   - Add worktree name to indicate where task was completed

b. **Update metrics:**
   - Tasks Complete: [consolidated count]
   - Overall Progress: `(completed / total) * 100`
   
c. **Update batch progress:**
   - Calculate progress for each batch based on consolidated completions
   - If all tasks in a batch are complete, mark batch as 100%

d. **Update "Current Batch":**
   - Identify the first batch with incomplete tasks

e. **Check newly unblocked tasks:**
   - For each completed task, check what tasks it unblocks
   - Move newly unblocked tasks from "⏸️ Pending" to "⏳ Ready"

f. **Update workstream status table:**
   - Recalculate "Tasks Done" for each workstream

### 6. Update Main Repo WORKSTREAM.md

Update `docs/workstreams/[feature-name]/WORKSTREAM.md` in the main repo:

a. **Update workstream task tables (WS-A, WS-B, WS-C, etc.):**
   - Change task status from `pending` to `ready` or `complete`
   - Add ticket links for tasks with created tickets: `[TaskID](./tasks/TaskID-name.md)`
   - Update dependency checkmarks (e.g., `A1 ✅`)

b. **Update Batch sections in "Task Tickets":**
   - Update task status indicators (`ready`, `complete`)
   - Add ticket links for newly created tickets

c. **Update Progress section:**
   - Recalculate overall progress percentage
   - Update progress bar visualization
   - Update "Completed" count

d. **Update History section (if present):**
   - Add sync event with timestamp

### 7. Update Main Repo BATCH_EXECUTION_PLAN.md

Update `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md` in the main repo:

a. **Update Batch Overview table:**
   - Update status column for each batch (Pending → In Progress → Complete)
   - Update Tasks Complete column (e.g., "2/9")

b. **Update Wave checkboxes in each batch section:**
   - Mark completed tasks: `- [x] **TaskID**: Description`
   - Keep pending tasks unchecked: `- [ ] **TaskID**: Description`

c. **Update Wave status indicators:**
   - `🟡 In Progress` for waves with some tasks complete
   - `✅ Complete` for waves with all tasks complete
   - `⏳ Pending` for waves not yet started

d. **Update Execution Commands section:**
   - Add checkmarks to commands for completed tasks

e. **Update Summary section:**
   - Update "Current Status" progress percentage
   - Update batch completion indicators

### 8. Update Main Repo EXECUTION_STATUS.md

Update `docs/[feature-name]/EXECUTION_STATUS.md` with comprehensive updates:

a. **Update Current Status Overview (top section):**
   - Update Workflow Phase Status ASCII art progress bars to reflect actual progress
   - Update metrics table:
     - "Current Batch" - update to current active batch
     - "Overall Progress" - recalculate percentage (e.g., "31.8% (14/44 tasks complete)")

b. **Update Phase 3: Execution section:**
   - Batch Overview table:
     - Update Status column (⏸️ Blocked → 🔄 In Progress → ✅ Complete)
     - Update task completion indicator (e.g., "22%")
   - Merge Points table:
     - Update MP status when converging tasks complete (⏸️ Pending → ✅ Complete)
     - Add merge completion date

c. **Update Phase 4: Learning section:**
   - Update task completion count (e.g., "14/44 tasks complete")

d. **Update Demo Validation Status:**
   - For each demo, check if ALL validating tasks are complete
   - Update Status column (⏸️ Pending → 🔄 Partial → ✅ Complete)
   - Update "All Complete?" column (❌ → ✅)

e. **Update Sarah's Journey Validation Status:**
   - For each step, check if ALL implementing tasks are complete
   - Update Status column (⏸️ Pending → 🔄 Partial → ✅ Complete)
   - Update "All Complete?" column (❌ → ✅)

f. **Update Command Execution Log:**
   - Add sync event entry:
     ```
     | [date] | /sync-worktree-status | ✅ | Synced [N] worktrees, [X] tasks consolidated |
     ```

g. **Update Timeline:**
   - Add sync event entry with date and summary:
     ```
     | [date] | `/sync-worktree-status` - progress [X]% ([Y]/[Z]), Batch [N] at [M]% |
     ```

h. **Update Milestones:**
   - Check if any milestones are now complete based on batch completion
   - Update Status column (⏸️ Blocked → ✅ Complete)
   - Add Completed date

### 9. Update Global EXECUTION_STATUS.md

Update `docs/EXECUTION_STATUS.md` with:
- Updated progress percentage for this design

### 10. Copy Completion Reports to Main Repo

```bash
# For each worktree
cp [worktree]/docs/workstreams/[feature-name]/reports/*.md \
   [main-repo]/docs/workstreams/[feature-name]/reports/
```

**Note:** Use `cp -n` to avoid overwriting if reports already exist.

---

## Output Format

### If Sync Skipped (Auto-Sync Active)

```markdown
## Sync Skipped: Already Up-to-Date

**Feature:** [feature-name]

### Current Status (Main Repo)
- **Tasks Completed:** [X]/[Y] ([Z]%)
- **Last Updated:** [timestamp]

### Worktrees Checked
| Worktree | Tasks Completed | Matches Main? |
|----------|-----------------|---------------|
| [worktree-a] | [task-list] | ✅ Yes |
| [worktree-b] | [task-list] | ✅ Yes |

**Conclusion:** Auto-sync via `/execute-task` and `/complete-task` is working correctly.
No manual sync required.

To force sync anyway: `/sync-worktree-status [feature-name] --force`
```

### If Sync Performed

```markdown
## Worktree Status Sync Complete

### Feature: [feature-name]

### Worktrees Scanned
| Worktree | Branch | Tasks Completed |
|----------|--------|-----------------|
| [worktree-a] | [branch-a] | [task-list] |
| [worktree-b] | [branch-b] | [task-list] |

### Consolidated Status
- **Total Tasks Completed:** [X]/[Y] ([Z]%)
- **Batch [N] Progress:** [X]% [✅ Complete if 100%]
- **Current Batch:** Batch [N]

### Tasks Newly Ready (Unblocked)
| Task | Batch | Unblocked By |
|------|-------|--------------|
| [task-id] | [batch] | [dependency] |
| ... | ... | ... |

### Files Updated
- `docs/workstreams/[feature-name]/STATUS.md` ✅
- `docs/workstreams/[feature-name]/WORKSTREAM.md` ✅
- `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md` ✅
- `docs/[feature-name]/EXECUTION_STATUS.md` ✅
- `docs/EXECUTION_STATUS.md` ✅
- Copied [N] completion reports ✅

### Next Steps
1. Create task tickets for newly ready tasks
2. Continue parallel execution in worktrees
```

---

## Automation Recommendation

To avoid manual syncing, consider running this after each merge point:

```bash
# At merge point, before creating new worktrees:
1. git checkout dev
2. git merge feature/[worktree-a-branch]
3. git merge feature/[worktree-b-branch]
4. /sync-worktree-status [feature-name]  # Consolidate any remaining status
5. git worktree add ../[new-worktree] -b feature/[new-branch] dev
6. cp -r .cursor ../[new-worktree]/
```

---

## Example Usage

**User:** `/sync-worktree-status my-feature`

**Agent Actions:**
1. List all worktrees with `git worktree list`
2. Read status files from each worktree:
   - `docs/workstreams/my-feature/STATUS.md`
   - `docs/workstreams/my-feature/WORKSTREAM.md`
   - `docs/workstreams/my-feature/reports/*.md`
3. Consolidate completed tasks from all worktrees
4. Update main repo's `docs/workstreams/my-feature/STATUS.md`
5. Update main repo's `docs/workstreams/my-feature/WORKSTREAM.md`
6. Update main repo's `docs/workstreams/my-feature/BATCH_EXECUTION_PLAN.md`
7. Update main repo's `docs/my-feature/EXECUTION_STATUS.md`
8. Update main repo's `docs/EXECUTION_STATUS.md`
9. Copy completion reports from worktrees to main repo
10. Report consolidated status

---

## Reference Files

| File | Purpose | Updated By Sync? |
|------|---------|------------------|
| `docs/workstreams/[feature]/STATUS.md` | Task-level status (batches, tasks, ready/complete) | ✅ Yes |
| `docs/workstreams/[feature]/WORKSTREAM.md` | Workstream overview, task tables, progress | ✅ Yes |
| `docs/workstreams/[feature]/BATCH_EXECUTION_PLAN.md` | Execution waves, checkboxes, commands | ✅ Yes |
| `docs/[feature]/EXECUTION_STATUS.md` | Phase-level status (see detailed sections below) | ✅ Yes |
| `docs/EXECUTION_STATUS.md` | Global portfolio status | ✅ Yes |
| `docs/workstreams/[feature]/reports/` | Completion reports | ✅ Yes (copied) |
| `docs/workstreams/[feature]/tasks/` | Task tickets | ❌ No (read only) |

### EXECUTION_STATUS.md Sections Updated

| Section | Updated? | Details |
|---------|----------|---------|
| Current Status Overview (ASCII art) | ✅ Yes | Progress bars, metrics table |
| Phase 3: Batch Overview | ✅ Yes | Status, completion % |
| Phase 3: Merge Points | ✅ Yes | MP status when tasks complete |
| Phase 4: Learning | ✅ Yes | Task completion count |
| Demo Validation Status | ✅ Yes | Status per demo |
| Sarah's Journey Validation | ✅ Yes | Status per step |
| Command Execution Log | ✅ Yes | Sync event entry |
| Timeline | ✅ Yes | Sync event with progress |
| Milestones | ✅ Yes | Milestone completion |
| Quality Gates | ❌ No | Updated by `/run-checks` only |
| Blockers & Risks | ❌ No | Manual updates only |
