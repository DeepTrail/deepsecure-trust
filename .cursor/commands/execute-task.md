# Execute Task: Implement a Task from Its Ticket

Automatically implement a task by reading its ticket, verifying dependencies, coding the solution, running tests, and completing inline. This is the core build step of the pipeline.

## Workflow Position

```
... → /create-task-ticket → /execute-task → (/debug if errors) → /run-checks → /review → ...
                                  ↑
                             (YOU ARE HERE)
```

## When to Use

- After task tickets have been created (`/create-task-ticket`)
- When the task's dependencies are all satisfied (check STATUS.md)
- When task specifications and tickets exist in the workstream
- When executing tasks in parallel across worktrees

**When NOT to use:**
- Task dependencies are not met (blocked tasks — check STATUS.md first)
- Task ticket doesn't exist yet — run `/create-task-ticket` first
- Task spec is missing for code tasks — run `/create-task-spec` first
- You're unsure what to build — run `/spec` or read the design doc first

---

## Instructions

When given a task ID and feature name, execute the following steps:

### 1. Read and Analyze Task Ticket

```
Read: docs/workstreams/[feature]/tasks/[WS-ID]-*.md
```

Extract and validate:
- [ ] Task description is clear
- [ ] Acceptance criteria are specific and testable
- [ ] Files to create/modify are explicitly listed
- [ ] Implementation hints are provided
- [ ] Dependencies are satisfied (check STATUS.md)

### 2. Update STATUS.md (Task Started) - Workstream Level

Move task from "⏳ Ready" to "🔄 In Progress":
- Add start timestamp
- Add assignee (if applicable)
- Update STATUS.md "Last Updated" timestamp

### 2.5. Update Main Repo Status (CRITICAL for Parallel Execution)

**ALWAYS update the MAIN REPO's status files for consolidated tracking.**

```bash
# Find main repo path (first entry in worktree list is always main repo)
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
# Example: /Users/imaxxs/repositories/deepsecure-mvp
```

**Use the StrReplace tool to update these files in the MAIN REPO:**

a. **`$MAIN_REPO/docs/workstreams/[feature]/STATUS.md`**:
   
   - In "Current Batch" table: Change task status from `ready` to `🔄 in progress`
   - In "Current Task Overview" metrics: Increment "Tasks In Progress", decrement "Tasks Ready"
   - In "⏳ Ready" section: Move task to "🔄 In Progress" section (or add In Progress section if missing)
   - Update "Active Worktrees" table: Add worktree entry if not present
   - Update "Last Updated" timestamp at top

b. **`$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md`**:
   
   - In "All Tasks" section: Change task status from `ready` to `🔄 in progress`
     - Example: `| A2 | ... | `ready` |` → `| A2 | ... | 🔄 `in progress` |`
   - In "Progress" section: Increment "In Progress" count, decrement "Ready" count
   - In "Workstreams" table: Update workstream status to `in_progress` if first task

**Why:** Worktrees have separate working directories. Without updating the main repo, 
there's no consolidated view of progress across parallel worktrees.

**Example StrReplace for STATUS.md** (substitute actual paths):
```
# Update "Tasks In Progress" from 0 to 1
# NOTE: Replace [feature] with actual feature name (e.g., virtual-mcp-server-mvp)
StrReplace:
  path: $MAIN_REPO/docs/workstreams/[feature]/STATUS.md
  old_string: "| **Tasks In Progress** | 0 |"
  new_string: "| **Tasks In Progress** | 1 |"
```

### 3. Evaluate Implementation Readiness

**Check if implementation can proceed:**

a. **Verify dependencies are complete:**
   - Read STATUS.md to confirm all dependency tasks are in "✅ Completed"
   - If not, STOP and report: "Task blocked by incomplete dependencies: [list]"

b. **Verify files to modify exist (for modify tasks):**
   - Check if files listed as "modify" actually exist
   - If not, STOP and report: "Missing prerequisite files: [list]"

c. **Evaluate implementation hints:**
   - Are the hints sufficient to implement?
   - Is the code structure clear?
   - Are there ambiguities that need resolution?

d. **Check for missing information:**
   - Required imports/dependencies
   - Database schema details (for models)
   - API contracts (for endpoints)
   - Test patterns to follow

### 4. Request Clarification (If Needed)

If implementation cannot proceed due to missing information:

```markdown
## Cannot Proceed: Missing Information

**Task:** [WS-ID] [Task Name]

**Missing Details:**
1. [What's missing and why it's needed]
2. [Another missing item]

**Questions:**
1. [Specific question that needs answering]

**Suggested Resolution:**
- [How to resolve, e.g., "Check existing models for pattern"]
```

STOP and wait for user input.

### 5. Execute Implementation

If all checks pass, proceed with implementation:

a. **Create/modify files** as specified in task ticket:
   ```
   For each file in "Files to Create":
     - Create the file with implementation
     - Follow existing code patterns in the codebase
     - Include proper imports and type hints
   
   For each file in "Files to Modify":
     - Read the existing file
     - Make the specified changes
     - Preserve existing functionality
   ```

b. **Follow acceptance criteria:**
   - Implement each criterion as a requirement
   - Protocol criteria → Follow protocol specs exactly
   - Security criteria → Implement security checks
   - Integration criteria → Ensure compatibility

c. **Add tests:**
   - Create test file as specified
   - Cover each acceptance criterion
   - Include edge cases

d. **Run quality checks:**
   ```bash
   # Format code
   make format
   # or: black . && isort .
   
   # Lint
   ruff check [files]
   
   # Type check
   mypy [files]
   
   # Run tests
   pytest [test_file] -v
   ```

### 5.5 Self-Healing Loop (Auto-Fix Failures)

**If any quality check from Step 5d fails, enter the self-healing loop instead of stopping.**

This step is always active — it does not require a flag. The agent should always attempt to fix its own mistakes before giving up.

#### 5.5a. Failure Classification

Classify each failure before attempting a fix:

| Class | Examples | Fix Strategy | Max Retries |
|-------|----------|-------------|-------------|
| **Auto-fixable** | Lint errors, import sorting, formatting, missing imports, wrong type annotation | Run formatter/fixer tool, apply the obvious fix | 2 |
| **Diagnosable** | Test assertion failures, build errors, type check errors with clear messages, API contract mismatches | Read error output + source file, diagnose root cause, edit code | 3 |
| **Opaque** | Timeouts, non-deterministic failures, deep architectural issues, errors with no actionable message | Cannot fix autonomously | 0 (skip immediately) |
| **Security-sensitive** | Auth test failures, crypto errors, permission check failures | Must NOT auto-fix — escalate to human | 0 (escalate immediately) |

**How to classify:** Read the error output. If the error message contains a file path and line number with a clear description (e.g., "missing import X", "expected Y got Z", "undefined variable"), it is Diagnosable. If the error is a formatting/lint violation, it is Auto-fixable. If the error mentions auth, crypto, JWT, key, permission, or signature, it is Security-sensitive. Everything else is Opaque.

#### 5.5b. The Heal Loop

```
RETRY_COUNT = 0

WHILE any quality check is still failing:

  IF RETRY_COUNT >= MAX_RETRIES for this failure class:
    → BREAK (go to 5.5c — exhausted)

  1. CAPTURE the full error output (test traceback, lint message, type error)
  
  2. DIAGNOSE:
     - For Auto-fixable: identify the fixer tool (ruff --fix, black, isort)
     - For Diagnosable: read the failing file at the error line,
       read the test file if it's a test failure, identify the root cause
  
  3. FIX:
     - For Auto-fixable: run the fixer tool, or apply the single-line fix
     - For Diagnosable: edit the source code to address the root cause
     - Run ReadLints on modified files after each fix
  
  4. RETEST: re-run ONLY the check(s) that failed — not the full suite
     - If lint failed: re-run lint on the fixed file
     - If test failed: re-run the specific failing test
     - If type check failed: re-run type check on the fixed file
  
  5. RETRY_COUNT += 1
  
  6. IF all checks now pass: BREAK (healed successfully)
```

#### 5.5c. Exhausted — Mark as BLOCKED

If the heal loop exhausts its retry budget without all checks passing:

1. **Do NOT proceed to Step 6** (Verify Implementation)
2. **Do NOT complete the task** (skip Steps 6-8)
3. **Mark the task as BLOCKED** in STATUS.md with the failure details:
   ```
   | [WS-ID] | [description] | BLOCKED | [date] | Heal loop exhausted: [error summary] |
   ```
4. **Return a structured failure summary** for `/run-batch` to consume:
   ```
   TASK_RESULT = {
     id: "[WS-ID]",
     status: "BLOCKED",
     failure_class: "Diagnosable",  
     retries_attempted: 3,
     last_error: "[final error output]",
     files_modified: ["path/to/file.ts"],
     suggestion: "Test expects X but implementation returns Y — may need spec clarification"
   }
   ```

#### 5.5d. Healing Log

After the heal loop (whether successful or exhausted), record what happened in the task ticket's Progress Updates:

```markdown
| [date] | Self-healing: [N] retries on [failure class] |
| [date] | Healed: [what was fixed] |
```

Or if blocked:

```markdown
| [date] | Self-healing: [N] retries exhausted on [failure class] |
| [date] | BLOCKED: [final error summary] |
```

### 6. Verify Implementation

After implementation, verify each acceptance criterion:

```markdown
## Implementation Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| [criterion 1] | ✅ / ❌ | [how verified] |
| [criterion 2] | ✅ / ❌ | [how verified] |
```

### 6.5 Contract Verification (CRITICAL)

**Before marking complete, verify API contracts match the specification:**

a. **Extract implemented endpoints:**
```bash
# For FastAPI routers
grep -r "@router\.\(get\|post\|put\|delete\)" [implementation_file] | grep -o '"/[^"]*"'
```

b. **Compare with spec endpoints from task ticket:**
```markdown
## Contract Verification

| Spec Endpoint | Implemented Endpoint | Match? |
|---------------|---------------------|--------|
| `/api/v1/auth/agent/challenge` | [from grep] | ✅ / ❌ |
```

c. **Verify test endpoints match:**
```bash
# Check test file endpoints
grep -r '"/api/v1' [test_file] | grep -o '"/api/v1[^"]*"'
```

d. **If mismatch found:**
   - STOP - Do not complete task
   - Determine which is correct (spec or implementation)
   - If spec is correct → Fix implementation
   - If implementation is correct → Update design doc FIRST, then update task spec

### 6.6 Technical Requirements Verification

**Verify framework-specific requirements:**

| Check | Command | Expected |
|-------|---------|----------|
| Async fixtures | `grep "@pytest.fixture" [test_file]` | Should be empty (use `@pytest_asyncio.fixture`) |
| HTTP client | `grep "httpx.AsyncClient" [test_file]` | Should have matches |
| File location | `ls tests/e2e/` | E2E tests at root if cross-service |

**Fix common issues before completing:**

```python
# WRONG - breaks async tests
@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c

# CORRECT
import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c
```

### 7. Update Task Ticket

Update the task ticket's Execution Log:
```markdown
### Progress Updates

| Date | Update |
|------|--------|
| [today] | Started task |
| [today] | Implemented [component] |
| [today] | Tests passing |
| [today] | Ready for completion |
```

### 8. COMPLETE THE TASK (MANDATORY — INLINE, NOT SEPARATE)

> **CRITICAL:** The steps below MUST execute as part of THIS `/execute-task` run.
> Do NOT end the conversation, do NOT tell the user to run `/complete-task` separately.
> The task is incomplete until ALL sub-steps below have run.

**If all acceptance criteria are met, execute these steps IN ORDER:**

#### 8a. Determine repo paths

```bash
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
LOCAL_REPO=$(pwd)
```

#### 8b. Create completion report (LOCAL)

1. Read the template at `docs/workstreams/COMPLETION_REPORT_TEMPLATE.md`
2. Fill it in with actual execution data (files changed, test results, acceptance criteria)
3. **Write** the report to: `docs/workstreams/[feature]/reports/[WS-ID]-completion.md`

#### 8c. Copy completion report to MAIN REPO

**Write** the same report to: `$MAIN_REPO/docs/workstreams/[feature]/reports/[WS-ID]-completion.md`

(Create the `reports/` directory first with `mkdir -p` if it doesn't exist.)

#### 8d. Update task ticket status

**StrReplace** the task ticket's status field from `ready` / `in progress` to `completed` ✅.

Also copy the updated ticket to `$MAIN_REPO` if in a worktree.

#### 8e. Update MAIN REPO STATUS.md

Use **StrReplace** on `$MAIN_REPO/docs/workstreams/[feature]/STATUS.md`:

- Update "Last Updated" timestamp
- Update overall progress metrics (increment completed count, update percentage)
- Update phase progress row (e.g., P2: 0% → 13%)
- Add a P2 batch section if this is the first P2 task completed
- Add the task row to the completed batch table with report link
- Add changelog entry at the top of the Change Log table

#### 8f. Update MAIN REPO WORKSTREAM.md

Use **StrReplace** on `$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md`:

- Change the task's status from `⏳ Ready` to `✅ Complete` in the batch table
- Add report link column
- Check if batch is fully complete; if so, update batch status

#### 8g. Update MAIN REPO EXECUTION_STATUS.md

Use **StrReplace** on `$MAIN_REPO/docs/EXECUTION_STATUS.md`:

- Update progress for this design in the "Active Designs" table

#### 8h. Sync local STATUS.md from main repo (if in worktree)

```bash
cp $MAIN_REPO/docs/workstreams/[feature]/STATUS.md docs/workstreams/[feature]/STATUS.md
```

#### 8i. Identify newly unblocked tasks

Check if any tasks list `[WS-ID]` as a dependency. If all their dependencies
are now satisfied, note them as newly ready.

---

**If issues remain that prevent completion:**

```markdown
## Implementation Incomplete

**Completed:**
- [what was done]

**Remaining:**
- [what still needs work]

**Blockers:**
- [any blockers encountered]

**Why completion steps 8a-8i cannot run:**
- [specific reason — e.g., "2/5 acceptance criteria not met because..."]

**Resume Command:**
`/execute-task [WS-ID] [feature-name]`
```

> **Note:** Even if blocked, you must explicitly state which of steps 8a-8i cannot run and why.

---

## Output Format

### Success Path

```markdown
## Task Execution: [WS-ID] [Task Name]

### Status: ✅ Implementation Complete

### Files Created/Modified
- `path/to/file.py` - [what was done]
- `tests/path/to/test.py` - [tests added]

### Acceptance Criteria
| Criterion | Status |
|-----------|--------|
| [criterion 1] | ✅ Met |
| [criterion 2] | ✅ Met |

### Quality Checks
- Format: ✅ Pass
- Lint: ✅ Pass  
- Type Check: ✅ Pass
- Tests: ✅ 5 passed

### Completion (inline)
- Report: `docs/workstreams/[feature]/reports/[WS-ID]-completion.md` ✅
- Task ticket: updated to `completed` ✅
- Main repo STATUS.md: updated ✅
- Main repo WORKSTREAM.md: updated ✅
- Main repo EXECUTION_STATUS.md: updated ✅
- Newly unblocked: [WS-XX, WS-YY] or "None"
```

### Blocked Path

```markdown
## Task Execution: [WS-ID] [Task Name]

### Status: 🚫 Blocked

### Reason
[Why implementation cannot proceed]

### Required Actions
1. [What needs to happen first]
2. [Another required action]

### Resume Command
Once resolved, run:
`/execute-task [WS-ID] [feature-name]`
```

---

## Example Usage

**User:** `/execute-task WS-A1 virtual-mcp-server-mvp`

**Agent Actions:**
1. Read `docs/workstreams/virtual-mcp-server-mvp/tasks/WS-A1-user-session-model.md`
2. Update STATUS.md (A1 → In Progress)
3. Verify no dependencies (A1 has none)
4. Check implementation hints are sufficient
5. Create `deeptrail-control/models/user_session.py`
6. Create `deeptrail-control/tests/models/test_user_session.py`
7. Run tests and quality checks
8. Verify all acceptance criteria
9. **Inline completion (Steps 8a-8i):**
   - Create completion report (local + main repo)
   - Update task ticket → `completed`
   - Update main repo STATUS.md, WORKSTREAM.md, EXECUTION_STATUS.md
   - Sync local STATUS.md
   - Report newly unblocked tasks

---

## Batch Execution

To execute all tasks in a batch:

```bash
# First, create worktrees and copy commands (from main repo)
git worktree add ../vmcp-control -b feature/vmcp-control dev
git worktree add ../vmcp-gateway -b feature/vmcp-gateway dev
cp -r .cursor ../vmcp-control/
cp -r .cursor ../vmcp-gateway/

# P0-B1 (parallel - run in separate terminals/worktrees)
# Terminal 1 (vmcp-control):
/execute-task WS-A1 virtual-mcp-server-mvp
/execute-task WS-E1 virtual-mcp-server-mvp

# Terminal 2 (vmcp-gateway):
/execute-task WS-B1 virtual-mcp-server-mvp
```

For automated batch execution, use:
```
/run-batch P0-B1 [feature-name]
```

Or via the full pipeline (all phases):
```
/pipeline @design-doc.md --phase=execute --batch=P0-B1
```

---

## Files to Update (Summary)

When `/execute-task` runs, these files in the **MAIN REPO** must be updated:

```bash
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
```

| When | File | Updates |
|------|------|---------|
| Task starts (Step 2) | `$MAIN_REPO/docs/workstreams/[feature]/STATUS.md` | Task → In Progress, metrics |
| Task starts (Step 2) | `$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md` | All Tasks table, Progress section |
| Task completes (Step 8b) | `docs/workstreams/[feature]/reports/[WS-ID]-completion.md` | Create completion report locally |
| Task completes (Step 8c) | `$MAIN_REPO/docs/.../reports/[WS-ID]-completion.md` | Copy report to main repo |
| Task completes (Step 8d) | `docs/workstreams/[feature]/tasks/[WS-ID]-*.md` | Task ticket → `completed` |
| Task completes (Step 8e) | `$MAIN_REPO/docs/workstreams/[feature]/STATUS.md` | Metrics, phase progress, changelog |
| Task completes (Step 8f) | `$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md` | Batch table → ✅ Complete |
| Task completes (Step 8g) | `$MAIN_REPO/docs/EXECUTION_STATUS.md` | Global design progress % |

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "I'll check dependencies later" | Unchecked dependencies cause cascading failures. A task built on incomplete foundations will need rework. |
| "The acceptance criteria are obvious, I don't need to read the ticket" | Tickets contain edge cases, specific contracts, and test requirements you'll miss. Read the full ticket. |
| "I'll write tests after the implementation" | Tests written after implementation test what you built, not what you should have built. Write tests alongside code. |
| "This task is simple, I'll skip the verification step" | Simple tasks cause the most insidious bugs because they're under-scrutinized. Verify every task. |
| "Contract verification is overkill for this endpoint" | One mismatched endpoint path causes cascading E2E failures across services. Verify contracts always. |
| "I'll update STATUS.md after I finish several tasks" | Stale status files break `/verify-batch-completion` and mislead other agents working in parallel. Update immediately. |
| "The completion steps (8a-8i) can wait until later" | They MUST run inline. Separating execution from completion creates orphaned tasks with no reports or status updates. |

## Red Flags

- Starting execution without reading the full task ticket
- Building code that doesn't match the spec's API contracts (wrong endpoint paths, wrong schemas)
- Skipping tests or writing tests that only check the happy path
- Not updating `$MAIN_REPO` status files (breaks parallel execution visibility)
- Proceeding past failing tests to "finish faster"
- Using `@pytest.fixture` for async fixtures instead of `@pytest_asyncio.fixture`
- Placing E2E tests inside a service directory instead of root `tests/e2e/`
- Not running inline completion (Steps 8a-8i) before ending the task
- Using the wrong token type in test validation (User Token vs Agent JWT vs Internal Token)

## Verification

After task execution and inline completion:

- [ ] All acceptance criteria from ticket are met and verified
- [ ] Contract verification passes (implementation endpoints match spec)
- [ ] Tests pass (`pytest [test_file] -v`)
- [ ] Lint passes (`ruff check [files]`)
- [ ] Completion report created (local + main repo)
- [ ] Task ticket status updated to `completed`
- [ ] Main repo STATUS.md updated with progress
- [ ] Main repo WORKSTREAM.md updated
- [ ] Newly unblocked tasks identified

---

## Reference

This command integrates with:
- `/create-task-ticket` → Produces the tickets this reads
- `/create-task-spec` → Produces the specs this references
- `/debug` → Use when implementation hits errors
- `/complete-task` → Now runs inline (Steps 8a-8i)
- `/run-checks` → Run after execution for full quality validation
- `/sync-worktree-status` → Consolidates status from worktrees

See also:
- `CLAUDE.md` → Token Types for API Validation
- `CLAUDE.md` → Async Test Fixtures
- `CLAUDE.md` → Backend Service File Path Conventions
- `docs/DEVELOPER_WORKFLOW.md` → Phase 2: Execution
