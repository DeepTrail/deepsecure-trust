# Execute Task

Automatically implement a task by reading its ticket and executing the implementation.

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

c. **`$MAIN_REPO/docs/[design-name]/EXECUTION_STATUS.md`**:
   
   - Update "Phase 3: Execution" status to "⏳ In Progress" if this is the first task
   - Add entry to "Command Execution Log" table:
     ```
     | [date] | /execute-task [WS-ID] | Started | In [worktree-name] |
     ```

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

### 6. Verify Implementation

After implementation, verify each acceptance criterion:

```markdown
## Implementation Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| [criterion 1] | ✅ / ❌ | [how verified] |
| [criterion 2] | ✅ / ❌ | [how verified] |
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

### 8. Trigger Completion

If all acceptance criteria are met:
```
/complete-task [WS-ID] [feature-name]
```

If issues remain:
```markdown
## Implementation Incomplete

**Completed:**
- [what was done]

**Remaining:**
- [what still needs work]

**Blockers:**
- [any blockers encountered]
```

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

### Next Steps
Running `/complete-task [WS-ID] [feature-name]` to finalize...
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
9. Run `/complete-task WS-A1 virtual-mcp-server-mvp`

---

## Batch Execution

To execute all tasks in a batch:

```bash
# First, create worktrees and copy commands (from main repo)
git worktree add ../vmcp-control -b feature/vmcp-control dev
git worktree add ../vmcp-gateway -b feature/vmcp-gateway dev
cp -r .cursor ../vmcp-control/
cp -r .cursor ../vmcp-gateway/

# Batch 1 (parallel - run in separate terminals/worktrees)
# Terminal 1 (vmcp-control):
/execute-task WS-A1 virtual-mcp-server-mvp
/execute-task WS-E1 virtual-mcp-server-mvp

# Terminal 2 (vmcp-gateway):
/execute-task WS-B1 virtual-mcp-server-mvp
```

For automated batch execution, use:
```
/orchestrate-feature @design-doc.md --phase=execution --batch=1
```

---

## Files to Update (Summary)

When `/execute-task` runs, these files in the **MAIN REPO** must be updated:

```bash
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
```

| When | File | Updates |
|------|------|---------|
| Task starts | `$MAIN_REPO/docs/workstreams/[feature]/STATUS.md` | Task → In Progress, metrics |
| Task starts | `$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md` | All Tasks table, Progress section |
| Task starts | `$MAIN_REPO/docs/[design]/EXECUTION_STATUS.md` | Command log entry |
| Task completes | Trigger `/complete-task` which updates all status files |

---

## Reference Files
- Task tickets: `docs/workstreams/[feature]/tasks/`
- STATUS.md: `docs/workstreams/[feature]/STATUS.md`
- WORKSTREAM.md: `docs/workstreams/[feature]/WORKSTREAM.md`
- EXECUTION_STATUS.md (per-design): `docs/[design-name]/EXECUTION_STATUS.md`
- Workflow guide: `docs/WORKFLOW_GUIDE.md`
