# Verify Batch Completion

Verify that all status files are consistent with completion reports for a batch.

**This is a BLOCKING verification.** Do not proceed to the next batch if verification fails.

## Usage

```
/verify-batch-completion [batch-id] [feature-name]
```

**Parameters:**
- `[batch-id]`: The batch identifier (e.g., `P1-B2`, `P0-B3`)
- `[feature-name]`: The workstream/feature name (e.g., `mvp-production-readiness`)

**Example:**
```
/verify-batch-completion P1-B2 mvp-production-readiness
```

---

## ⚠️ MUST RUN FROM MAIN REPO

**This command must be run from the main repository, NOT from a worktree.**

```bash
# ✅ Correct - run from main repo
cd /Users/imaxxs/repositories/deepsecure-mvp
/verify-batch-completion P1-B2 mvp-production-readiness

# ❌ Wrong - do NOT run from worktree
cd /Users/imaxxs/repositories/mvp-prod-control
/verify-batch-completion P1-B2 mvp-production-readiness  # Will not work correctly!
```

---

## Instructions

### 1. Identify Batch Tasks

Read the `BATCH_EXECUTION_PLAN.md` to identify all tasks in the specified batch:

```bash
# Path to batch execution plan
BATCH_PLAN="docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md"
```

Extract the task list for the batch. Example for P1-B2:
```
| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| E2 | Create vault token retrieval endpoint | E1 | mvp-prod-control | ? |
| E3 | Create vault token refresh endpoint | E1 | mvp-prod-control | ? |
| F2 | Create OAuth configuration | F1 | mvp-prod-control | ? |
| F3 | Create OAuth endpoints | F1 | mvp-prod-control | ? |
| G2 | Implement Notion REST API calls | G1 | mvp-prod-gateway | ? |
| G3 | Implement Slack REST API calls | G1 | mvp-prod-gateway | ? |
| G4 | Implement HubSpot REST API calls | G1 | mvp-prod-gateway | ? |
```

Create a checklist of task IDs in the batch:
```
BATCH_TASKS = [E2, E3, F2, F3, G2, G3, G4]  # Example for P1-B2
```

### 2. Check Completion Reports (Source of Truth)

List all completion reports in the reports directory:

```bash
ls -la docs/workstreams/[feature-name]/reports/WS-*.md 2>/dev/null || echo "No reports found"
```

For each task in the batch, check if a completion report exists:

```bash
# For each task ID in BATCH_TASKS
for TASK_ID in E2 E3 F2 F3 G2 G3 G4; do
  REPORT_FILE="docs/workstreams/[feature-name]/reports/WS-${TASK_ID}-completion.md"
  if [ -f "$REPORT_FILE" ]; then
    echo "✅ $TASK_ID: Report exists"
  else
    echo "❌ $TASK_ID: Report MISSING"
  fi
done
```

Build a list of:
- `COMPLETED_TASKS`: Tasks with completion reports
- `MISSING_TASKS`: Tasks without completion reports

### 3. Cross-Reference STATUS.md

Read `docs/workstreams/[feature-name]/STATUS.md` and check:

| Check | How to Verify | Expected |
|-------|---------------|----------|
| Overall Progress | Search for progress percentage | Should reflect completed tasks |
| Completed Tasks Section | List tasks marked "✅ Complete" | Should match COMPLETED_TASKS |
| Ready/Pending Section | List tasks not complete | Should match MISSING_TASKS |
| Batch Status | Find batch in progress table | Should show X/Y complete |

**Extract completed tasks from STATUS.md:**
```bash
grep -E "^\| WS-[A-Z][0-9]" docs/workstreams/[feature-name]/STATUS.md | \
  grep "✅ Complete" | \
  grep -oE "WS-[A-Z][0-9]+"
```

**Compare:**
```
COMPLETED_IN_REPORTS = [tasks with completion reports]
COMPLETED_IN_STATUS = [tasks marked complete in STATUS.md]

MISSING_IN_STATUS = COMPLETED_IN_REPORTS - COMPLETED_IN_STATUS
WRONG_IN_STATUS = COMPLETED_IN_STATUS - COMPLETED_IN_REPORTS
```

### 4. Cross-Reference WORKSTREAM.md

Read `docs/workstreams/[feature-name]/WORKSTREAM.md` and check:

| Check | How to Verify | Expected |
|-------|---------------|----------|
| Task Table | Find batch section | Completed tasks should show "✅ Complete" |
| Report Links | Check "Report" column | Should have links for completed tasks |
| Batch Header | Check batch title | Should show "✅ COMPLETE" if all done |

**Extract task statuses:**
```bash
grep -E "^\| WS-[A-Z][0-9]" docs/workstreams/[feature-name]/WORKSTREAM.md | \
  grep "✅ Complete"
```

### 5. Cross-Reference BATCH_EXECUTION_PLAN.md

Read `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md` and check:

| Check | How to Verify | Expected |
|-------|---------------|----------|
| Quick Reference | Find batch row | Should show "✅ Complete" if all done |
| Dependencies Table | Find batch section | Tasks should show "✅" status |
| Parallelization Summary | Find batch row | Should show "✅ Complete" |
| Merge Points Summary | If batch triggers MP | Should show "✅ Reached" |

**Extract task statuses:**
```bash
# Check Quick Reference table
grep -E "^\| P[0-9]-B[0-9]" docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md

# Check task dependencies table
grep -E "^\| [A-Z][0-9] \|" docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md
```

### 6. Cross-Reference MERGE_POINTS.md (If Applicable)

If this batch triggers a merge point, check `docs/workstreams/[feature-name]/MERGE_POINTS.md`:

| Batch | Triggers Merge Point |
|-------|---------------------|
| P0-B4 | MP1 |
| P1-B2 | MP2 |
| P1-B3 | MP3 |
| P2-B2 | MP4 |

**If batch triggers a merge point:**
```bash
# Check merge point status
grep -A5 "## MP[N]:" docs/workstreams/[feature-name]/MERGE_POINTS.md | grep "Status"
```

### 7. Generate Verification Report

Create a structured report showing:

```markdown
## Batch Verification Report: [batch-id]

**Feature:** [feature-name]
**Verified:** [timestamp]
**Overall Result:** ✅ PASS / ❌ FAIL
**Final Batch:** YES / NO

### Completion Reports (Source of Truth)

| Task | Report Exists | Report Path |
|------|---------------|-------------|
| WS-E2 | ✅ | reports/WS-E2-completion.md |
| WS-E3 | ✅ | reports/WS-E3-completion.md |
| ... | ... | ... |

**Completed:** [X]/[Y] tasks

### Cross-Reference Results

| File | Status | Issues Found |
|------|--------|--------------|
| STATUS.md | ✅ / ❌ | [list issues or "None"] |
| WORKSTREAM.md | ✅ / ❌ | [list issues or "None"] |
| BATCH_EXECUTION_PLAN.md | ✅ / ❌ | [list issues or "None"] |
| MERGE_POINTS.md | ✅ / ❌ / N/A | [list issues or "None"] |
| API_REFERENCE.md | ✅ / ❌ / N/A | [list issues or "None"] |

### Detailed Issues

#### STATUS.md Issues
- [ ] Task WS-E2 has completion report but marked "⏳ Ready"
- [ ] Overall progress shows "31%" but should be "83%"
- ...

#### WORKSTREAM.md Issues
- [ ] Task WS-G3 marked "⏳ Ready" but report exists
- ...

#### BATCH_EXECUTION_PLAN.md Issues
- [ ] Quick Reference shows P1-B2 as "⏳ Pending"
- [ ] Task E2 status shows "⏳" not "✅"
- ...

### Merge Point Status

| Merge Point | Expected | Actual | Status |
|-------------|----------|--------|--------|
| MP2 | ✅ Reached | ⏳ Pending | ❌ MISMATCH |

### Required Actions

If FAIL, list exact files and changes needed:

1. **STATUS.md:**
   - Update overall progress to [X]%
   - Move tasks [list] to "✅ Completed" section
   - Update batch progress

2. **WORKSTREAM.md:**
   - Mark tasks [list] as "✅ Complete"
   - Add report links for [list]

3. **BATCH_EXECUTION_PLAN.md:**
   - Update Quick Reference: P1-B2 → "✅ Complete"
   - Update task statuses in Dependencies table

4. **MERGE_POINTS.md:**
   - Update MP2 status to "✅ Reached"

### Fix Command

To fix all issues automatically:
```bash
/sync-worktree-status [feature-name]
```

Or manually update each file using the issues list above.
```

---

## Decision Logic

### PASS Criteria

All of these must be true for PASS:

1. **All batch tasks have completion reports**
2. **STATUS.md shows all completed tasks as "✅ Complete"**
3. **WORKSTREAM.md shows all completed tasks with correct status and report links**
4. **BATCH_EXECUTION_PLAN.md shows batch and tasks as complete**
5. **If batch triggers merge point, MERGE_POINTS.md shows it as reached**

### FAIL Criteria

Any of these results in FAIL:

1. **Missing completion report** for a task claimed as complete
2. **Task has completion report but not marked complete** in status files
3. **Progress percentages don't match** actual completion count
4. **Merge point not updated** when all converging tasks are complete

---

## Blocking Behavior

### If Verification PASSES

```markdown
## ✅ Verification PASSED

Batch [batch-id] is verified complete.

**Summary:**
- Completion Reports: [X]/[X] ✅
- STATUS.md: Consistent ✅
- WORKSTREAM.md: Consistent ✅
- BATCH_EXECUTION_PLAN.md: Consistent ✅
- MERGE_POINTS.md: [MP status if applicable] ✅

**You may proceed to the next batch.**

Next batch: [next-batch-id]
Ready tasks: [list of tasks now ready]
```

### If Verification FAILS

```markdown
## ❌ Verification FAILED

Batch [batch-id] has [N] inconsistencies that MUST be fixed.

**DO NOT PROCEED to the next batch until fixed.**

### Issues Found

[Detailed issues list from Section 7]

### Required Actions

[List of exact changes needed]

### Fix Options

**Option 1: Automatic Sync**
```bash
/sync-worktree-status [feature-name]
```

**Option 2: Manual Fix**
Use StrReplace tool to update each file listed above.

### After Fixing

Re-run verification:
```bash
/verify-batch-completion [batch-id] [feature-name]
```
```

---

## Auto-Closure: Final Batch Detection (Step 8)

**After verification PASSES, check if this was the LAST batch in the workstream.**

### 8a. Detect Final Batch

Read `BATCH_EXECUTION_PLAN.md` and determine:

```
ALL_BATCHES = [list every batch ID from the Quick Reference table]
CURRENT_BATCH = [batch-id being verified]

IS_FINAL_BATCH = (CURRENT_BATCH == last item in ALL_BATCHES)
```

Also verify ALL prior batches are complete:

```bash
# Every batch in the Quick Reference table should show "✅ Complete"
grep -E "^\| (P[0-9]-)?B[0-9]" docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md | \
  grep -v "✅ Complete" | wc -l
# Result must be 0
```

**If this is NOT the final batch:** Stop here. Report PASS and show next batch.

**If this IS the final batch:** Continue to Step 8b — Auto-Close Workstream.

### 8b. Auto-Close Workstream

When the final batch passes verification, automatically perform ALL of the following:

#### 1. Update STATUS.md

Set the workstream to complete:

- Change `**Phase:**` line to `✅ COMPLETE`
- Update `Tasks Complete` to `[N] / [N]` (all tasks)
- Update `Batches Complete` to `[N] / [N]` (all batches)
- Mark the final batch as `✅ Complete` in the Batch Status table
- Mark remaining tasks as `✅ Complete` in the Task Status table
- Add a History entry: `| [today's date] | Workstream COMPLETE — all batches verified |`

#### 2. Update BATCH_EXECUTION_PLAN.md

- Mark the final batch as `✅ Complete` in the Status table
- Ensure all batches show `✅ Complete`

#### 3. Update MERGE_POINTS.md

- Set the progress bar to 100%: `MP[N]: ██████████ 100% ([N]/[N] tasks)`
- Update Merge Point Status table to `✅ Complete`
- Add a History entry: `| [today's date] | All merge points complete — workstream closed |`

#### 4. Update docs/workstreams/README.md

- In the **Active Workstreams** table, change the feature's status to `complete` and progress to `100%`
- In the **Completed Workstreams** table, add a row:
  `| [Feature Name] | [today's date] | [total tasks] | [WORKSTREAM.md link] |`

#### 5. Report Closure

Output the closure summary:

```markdown
## 🏁 Workstream [feature-name] is COMPLETE

**Final batch [batch-id] verified.** All status files have been auto-closed.

| File | Action |
|------|--------|
| STATUS.md | ✅ Updated — Phase: COMPLETE, [N]/[N] tasks |
| BATCH_EXECUTION_PLAN.md | ✅ Updated — all batches complete |
| MERGE_POINTS.md | ✅ Updated — 100% progress |
| workstreams/README.md | ✅ Updated — moved to Completed |

**No further action needed for this workstream.**
```

### 8c. Why Auto-Closure Matters

| Without Auto-Closure | With Auto-Closure |
|----------------------|-------------------|
| User must remember to ask for closure | Closure happens automatically on final batch |
| 5 files need manual updates | All 5 files updated in one step |
| Easy to forget, leaving stale "in progress" status | Workstream is always in a clean state |
| Status drift between files | All files updated atomically |

> **Lesson (May 2026):** The p3-gcp-ux-alignment workstream was fully deployed and verified
> on the live site, but all status files still showed "in progress" because closure was manual.
> Auto-closure eliminates this gap.

---

## Integration with Other Commands

### When to Run This Command

| Trigger | Action |
|---------|--------|
| After `/complete-task` for last task in batch | Run `/verify-batch-completion` |
| Before starting next batch | Run `/verify-batch-completion` for previous batch |
| After `/sync-worktree-status` | Run to confirm sync worked |
| Before merge point validation | Run for all batches leading to MP |

### Add to BATCH_EXECUTION_PLAN.md

Each batch section should include a verification checkpoint:

```markdown
### Post-Batch P1-B2 Verification (MANDATORY)

Before proceeding to P1-B3, run:
```bash
/verify-batch-completion P1-B2 mvp-production-readiness
```

**Do NOT proceed until verification passes.**
```

---

## Example Execution

**User:** `/verify-batch-completion P1-B2 mvp-production-readiness`

**Agent Actions:**

1. Read BATCH_EXECUTION_PLAN.md to get P1-B2 task list
2. List completion reports in `docs/workstreams/mvp-production-readiness/reports/`
3. For each P1-B2 task (E2, E3, F2, F3, G2, G3, G4):
   - Check if `WS-{ID}-completion.md` exists
4. Read STATUS.md and verify:
   - All completed tasks marked "✅ Complete"
   - Progress percentage is accurate
5. Read WORKSTREAM.md and verify:
   - Task table shows correct statuses
   - Report links present
6. Read BATCH_EXECUTION_PLAN.md and verify:
   - Quick Reference shows batch complete
   - Task dependencies show "✅"
7. Check if P1-B2 triggers merge point (MP2)
   - If yes, verify MERGE_POINTS.md shows MP2 as reached
8. Generate verification report
9. Report PASS/FAIL with detailed findings

---

## Checklist for Agent

When running this command, ensure you:

- [ ] Identified all tasks in the batch from BATCH_EXECUTION_PLAN.md
- [ ] Checked for completion reports (source of truth)
- [ ] Cross-referenced STATUS.md
- [ ] Cross-referenced WORKSTREAM.md
- [ ] Cross-referenced BATCH_EXECUTION_PLAN.md
- [ ] Checked MERGE_POINTS.md if applicable
- [ ] Generated detailed verification report
- [ ] Clearly stated PASS or FAIL
- [ ] If FAIL, listed exact files and changes needed
- [ ] If FAIL, did NOT suggest proceeding to next batch
- [ ] Checked if this is the FINAL batch in the workstream
- [ ] If final batch PASSES, ran auto-closure (Step 8b) on all status files

---

## Reference Files

| File | Purpose | What to Check |
|------|---------|---------------|
| `docs/workstreams/[feature]/reports/*.md` | Completion reports (SOURCE OF TRUTH) | Existence of WS-{ID}-completion.md |
| `docs/workstreams/[feature]/STATUS.md` | Task status, progress | Completed section, percentages |
| `docs/workstreams/[feature]/WORKSTREAM.md` | Task tables, batch status | Task statuses, report links |
| `docs/workstreams/[feature]/BATCH_EXECUTION_PLAN.md` | Batch overview, task deps | Quick Reference, Dependencies |
| `docs/workstreams/[feature]/MERGE_POINTS.md` | Merge point status | MP status if batch triggers one |
| `docs/API_REFERENCE.md` | API documentation | New endpoints documented |
