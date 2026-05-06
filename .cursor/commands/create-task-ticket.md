# Create Task Ticket

Create a new task ticket from the template for a specific task.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /create-task-spec → /create-task-ticket
                                                                                                   ↑
                                                                                              (YOU ARE HERE)

Downstream consumers of task tickets:
  /execute-task, /complete-task, /debug, /verify-batch-completion
```

## Quality Bar

The quality bar is set by these proven gold-standard task tickets:

- `docs/workstreams/idp-enhanced-sso/tasks/WS-A1-add-fetch-groups-to-idp-config.md` — Config field: 193 lines, full manual verification scripts, spec Key Contracts
- `docs/workstreams/mvp-production-readiness/tasks/WS-E3-vault-token-refresh-endpoint.md` — API endpoint: 312 lines, inline code in What to Implement, Contract Verification from spec, Progress Updates
- `docs/workstreams/mvp-production-readiness/tasks/WS-H1-gateway-credential-injection-from-vault.md` — Middleware: 248 lines, 8-step What to Implement, cross-file changes
- `docs/workstreams/interactive-demo/tasks/C1-create-apiclient.md` — Component: 252 lines, Code vs Runtime Dependencies, Development Mode, Blockers table
- `docs/workstreams/idp-selector/tasks/WS-A2-implement-google-provider.md` — Provider class: 310 lines, No-Change Zones, 10-step What to Implement, 22 test cases, Reference Implementation

**Read at least 2-3 of these before writing your first ticket.** If your ticket is shorter or less
detailed than the relevant gold-standard example, add more detail.

## Pre-Requisites

Before creating task tickets:

1. ✅ `/create-batch-execution-plan` completed (provides batch/task info)
2. ✅ `/create-task-spec` completed for all tasks involving code
   - Required for: API endpoints, data models, services, UI components, demo scripts, React components
   - Skip ONLY for: Documentation/README-only tasks (no code in any language)

---

## ⚠️ CRITICAL: Worktree / Branch Sync

**Tickets MUST be accessible from the execution context.**

- **Multi-Worktree Model:** Tickets must be copied to worktrees immediately after creation.
  `/execute-task` runs inside worktrees and reads the LOCAL ticket file.
- **Single-Branch Model:** Tickets stay in the main repo. No copy needed.

**Detect which model is in use:**

```bash
# Check for active worktrees
WORKTREE_COUNT=$(git worktree list | wc -l)
if [ "$WORKTREE_COUNT" -gt 1 ]; then
  echo "Multi-Worktree Model — must sync tickets"
else
  echo "Single-Branch Model — tickets stay in main repo"
fi
```

---

## Workstream-to-Worktree Mapping (Multi-Worktree Only)

Different workstreams execute in different worktrees. Use this mapping to determine where to copy tickets:

| Workstream | Service | Worktree Name Pattern | Example Path |
|------------|---------|----------------------|--------------|
| WS-A (Control Models) | Control Plane | `*-control` | `/Users/.../vmcp-control` |
| WS-B (Gateway Core) | Gateway | `*-gateway` | `/Users/.../vmcp-gateway` |
| WS-C (Control APIs) | Control Plane | `*-control` | `/Users/.../vmcp-control` |
| WS-D (Gateway Backends) | Gateway | `*-gateway` | `/Users/.../vmcp-gateway` |
| WS-E (Shared/Audit) | Both | Both worktrees | Both paths |
| WS-F (Integration) | Both | Both worktrees | Both paths |
| WS-G+ (Frontend) | Frontend | `*-frontend` or main repo | Depends on setup |

**Quick Reference:**
- **Control Plane tasks (A, C)** → Copy to `*-control` worktree
- **Gateway tasks (B, D)** → Copy to `*-gateway` worktree
- **Shared tasks (E, F)** → Copy to BOTH worktrees
- **Frontend tasks** → Copy to `*-frontend` worktree or stay in main repo

---

## Instructions

### 1. Get Task Information

From the Batch Execution Plan and Workstream:
- Task ID (e.g., WS-A1)
- Task name (brief, descriptive)
- Feature/workstream name (for folder path)
- Batch number
- Complexity (S/M/L)
- Dependencies

### 1b. Check for Existing Specification

**Check if a spec exists for this task:**

    docs/workstreams/[feature-name]/specs/[WS-ID]-spec.md

**If spec exists:**
- Reference it in the ticket's "## Specification" section
- Copy key contracts (endpoint path, schemas, interfaces) into ticket
- Add "Contract Verification (from spec)" subsection to Acceptance Criteria

**If spec doesn't exist:**
- For tasks with code (any language): Run `/create-task-spec` first (required)
- For documentation/README-only tasks: Proceed without spec

### 2. Create Directory Structure

If directories don't exist:

    docs/workstreams/[feature-name]/
    ├── tasks/
    └── reports/

### 3. Create Ticket in Main Repo

Use the Write tool to create the ticket at:

    docs/workstreams/[feature]/tasks/[WS-ID]-[task-name].md

Use the **Full Ticket Template** below, filling in ALL sections.

### 4. 🔄 SYNC TO WORKTREES (Multi-Worktree Model Only)

**Skip this step entirely for single-branch features.**

For multi-worktree features:

a. **Detect active worktrees:**

```bash
git worktree list
```

b. **Identify target worktree(s) using mapping above**

c. **Copy ticket to target worktree(s):**

```bash
FEATURE="[feature-name]"
TASK_ID="[WS-ID]"

# For single worktree (A, B, C, D tasks):
TARGET_WT="[WORKTREE_PATH]"
mkdir -p $TARGET_WT/docs/workstreams/$FEATURE/tasks
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $TARGET_WT/docs/workstreams/$FEATURE/tasks/

# For shared tasks (E, F) - copy to BOTH:
mkdir -p $CONTROL_WT/docs/workstreams/$FEATURE/tasks
mkdir -p $GATEWAY_WT/docs/workstreams/$FEATURE/tasks
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $CONTROL_WT/docs/workstreams/$FEATURE/tasks/
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $GATEWAY_WT/docs/workstreams/$FEATURE/tasks/
```

d. **Verify copy succeeded:**

```bash
ls $TARGET_WT/docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md
```

### 5. Update Workstream Tracker

If `WORKSTREAM.md` exists:
- Add the task to the task table
- Link to the new task ticket

### 6. Update STATUS.md

a. **Add task to appropriate section:**
   - If no dependencies or all dependencies complete → Add to "⏳ Ready" section
   - If has unmet dependencies → Add to "⏸️ Pending" section

b. **Update task counts** and add to Timeline

---

## Full Ticket Template

> **CRITICAL**: Use this COMPLETE template for every ticket. Include ALL sections.
> Omit a section only when clearly N/A, and leave a brief note explaining why.

    # Task: [WS-ID] [Task Name]

    > **Status:** `ready`
    > **Batch:** [Batch number]
    > **Branch:** `[branch-name]` (or Worktree: `[worktree-name]`)

    ---

    ## Metadata

    | Field | Value |
    |-------|-------|
    | **Task ID** | [WS-ID] |
    | **Workstream** | [WS-X: Workstream Name] |
    | **Phase** | [Batch N — Description] |
    | **Dependencies** | [WS-X1 ✅, WS-X2 or None] |
    | **Complexity** | [S (< 1hr) / M (1-3hr) / L (3+ hr)] |
    | **Service** | [deeptrail-control / deeptrail-gateway / frontend / SDK] |
    | **Status** | `ready` |
    | **Validates** | [Demo X, User Journey Step Y] |

    ---

    ## Validation Mapping

    | Mapping | Value |
    |---------|-------|
    | **Validates Demo** | [Demo 1: Name, Demo 2: Name, or N/A (foundation task)] |
    | **Validates User Journey Step** | [Step N: Description, or N/A] |

    ---

    ## Specification

    > See full specification: [specs/WS-ID-spec.md](../specs/WS-ID-spec.md)

    ### Key Contracts

    | Contract | Value |
    |----------|-------|
    | **[Primary contract]** | [Value] |
    | **[Secondary contract]** | [Value] |

    > If no spec exists (documentation-only task):
    > **Note:** This is a documentation task — no specification required.

    ---

    ## API Contracts

    > For tasks WITH API endpoints:

    ### Endpoint: [Name]

    | Field | Value |
    |-------|-------|
    | **Method** | `POST` / `GET` / `PUT` / `DELETE` |
    | **Path** | `/api/v1/exact/path` |
    | **Auth** | Bearer token / Agent JWT / Internal API token |

    **Request Headers:**

    | Header | Required | Description |
    |--------|----------|-------------|
    | `Authorization` | Yes | `Bearer <token>` |
    | `X-User-ID` | Conditional | Required for internal calls |

    **Request Body:**
    ```json
    { "field": "value" }
    ```

    **Response (200):**
    ```json
    { "result": "value" }
    ```

    **Error Responses:**

    | Status | Condition |
    |--------|-----------|
    | 401 | Invalid/missing token |
    | 404 | Resource not found |

    > For tasks WITHOUT API endpoints:

    > **Note:** This task implements an internal module/service, not API endpoints.
    > [Brief explanation of what the task creates.]
    > See [WS-XX] for related API endpoints.

    ---

    ## Dependencies

    ### Code Dependencies (must complete before starting)

    | Dependency | Status | What It Provides |
    |------------|--------|-----------------|
    | [WS-X1] | ✅ / ⏳ | [What this task needs from it] |
    | None | - | No blocking dependencies |

    ### Runtime Dependencies (must be deployed for integration testing)

    | Service | Endpoint | Required For |
    |---------|----------|--------------|
    | Control Plane | http://localhost:8000 | API calls |
    | Gateway | http://localhost:8002 | MCP calls |

    ### Development Mode

    > Describe how this task can be developed without runtime dependencies.

    - [x] **Fallback behavior**: [What happens without backend services]
    - [x] **Local testing**: [How to test without dependencies]
    - [x] **Integration testing**: Requires [which services] for full testing

    ---

    ## Pre-Conditions

    Before starting this task, ensure:

    - [x] [Dependency task] complete
    - [x] [Required file/service] exists
    - [ ] [Any setup needed]

    ---

    ## Task Description

    ### Objective

    [One paragraph: What this task accomplishes and why it matters.]

    ### Background

    [Context from the design doc. What exists today, what needs to change, and why.
    Include relevant quotes from the design doc or spec.]

    ### What to Implement

    > **CRITICAL**: This section must contain NUMBERED STEPS with CODE SNIPPETS
    > showing the expected implementation. Vague descriptions like "Add refresh endpoint"
    > are NOT acceptable. Show the actual function signatures, decorators, and logic flow.

    1. **[First implementation step]:**
       ```python
       # Show the exact code structure expected
       @router.post("/path", response_model=ResponseSchema)
       async def endpoint_name(
           param: str,
           request: RequestSchema,
           dep: Service = Depends(),
       ):
           # Step-by-step logic
           result = await dep.method(param)
           return ResponseSchema(field=result)
       ```

    2. **[Second implementation step]:**
       ```python
       # Another code block showing expected structure
       class NewModel(Base):
           __tablename__ = "table_name"
           id = Column(String(64), primary_key=True)
       ```

    3. **[Third step]** — wire up in [file]:
       ```python
       # Show how to connect components
       ```

    [Continue numbering until all implementation work is described.]

    ---

    ## Files to Create/Modify

    | File | Action | Description |
    |------|--------|-------------|
    | `[service]/app/[path]/[file].py` | **Create** | [What this file contains] |
    | `[service]/app/[path]/[file].py` | **Modify** | [What to add/change] |
    | `[service]/tests/[path]/test_[file].py` | **Create** | [Test description] |

    ### No-Change Zones

    > **CRITICAL**: Do NOT modify these files — they are owned by other tasks.

    | File | Reason |
    |------|--------|
    | `[service]/app/[path]/[file].py` | Owned by [WS-XX] |
    | `[service]/app/[path]/__init__.py` | [WS-YY] handles exports |

    > If no restrictions: "No restrictions — all listed files are scoped to this task."

    ---

    ## Acceptance Criteria

    ### Functional Criteria

    - [ ] [Specific, measurable criterion]
    - [ ] [Another criterion with exact expected behavior]

    ### Security Criteria

    - [ ] [Security-specific requirement]
    - [ ] No secrets logged

    ### Integration Criteria

    - [ ] [How this integrates with other components]
    - [ ] All existing tests pass (regression check)

    ### Contract Verification (from spec)

    > **REQUIRED** when a spec exists. Pull checklist items directly from the spec.

    - [ ] [Exact contract check, e.g., "Endpoint path matches: `/api/v1/vault/tokens/{service_id}/refresh`"]
    - [ ] [Schema check, e.g., "`refreshed` boolean in response"]
    - [ ] [Auth check, e.g., "Internal token auth (not agent JWT)"]
    - [ ] Implementation matches [specs/WS-ID-spec.md](../specs/WS-ID-spec.md) exactly

    ---

    ## Test Cases

    | Test Case | Method/Class | Endpoint/Module | Expected | Notes |
    |-----------|-------------|-----------------|----------|-------|
    | Happy path | POST / Unit | `/api/v1/path` or `test_file.py` | 200 / True | |
    | Invalid input | POST / Unit | `/api/v1/path` | 400 | Missing field |
    | Unauthorized | POST / Unit | `/api/v1/path` | 401 | No token |
    | [Edge case] | Unit | `test_file.py` | [Expected] | [Notes] |

    ---

    ## Post-Conditions

    After this task is complete:

    - [ ] [What gets unblocked, e.g., "WS-H2 unblocked (constructor changes in place)"]
    - [ ] [What becomes available, e.g., "Gateway can fetch real OAuth tokens"]
    - [ ] [Merge point progress, e.g., "MP2 closer to completion"]

    ---

    ## Validation

    ### Unit Tests

    ```bash
    cd [service-directory]
    pytest tests/[module]/test_[file].py -v
    ```

    ### Manual Verification

    ```bash
    # 1. [First verification step]
    [command]
    # Expected: [exact expected output]

    # 2. [Second verification step]
    [command]
    # Expected: [exact expected output]

    # 3. Lint check
    ruff check [file_path]
    # Expected: no errors
    ```

    ---

    ## References

    - **Specification:** [specs/WS-ID-spec.md](../specs/WS-ID-spec.md)
    - **Design Doc:** [link to design doc section]
    - **Upstream:** [WS-X1 (description)] ✅, [WS-X2 (description)]
    - **Downstream:** [WS-Y1 (uses this component)]
    - **Reference Implementation:**
      - `[service]/app/[path]/[similar_file].py` — follow same patterns
      - `[service]/tests/[path]/test_[similar_file].py` — follow same test structure
    - **Related Code:**
      - `[service]/app/[path]/[file].py` — [why it's relevant]
      - `[service]/app/[path]/[file].py` — [why it's relevant]

    ---

    ## Execution

    ```bash
    # For multi-worktree:
    cd [worktree-path]
    /execute-task [WS-ID] [feature-name]

    # For single-branch:
    cd /Users/imaxxs/repositories/deepsecure-mvp
    /execute-task [WS-ID] [feature-name]

    # After completion:
    /complete-task [WS-ID] [feature-name]
    ```

    ---

    ## Notes

    > Optional but recommended. Include implementation tips, edge cases, and considerations.

    - [Hint about implementation approach]
    - [Edge case to watch for]
    - [Future consideration beyond MVP scope]

    ---

    ## Progress Updates

    | Date | Update |
    |------|--------|
    | - | Task ticket created |

    ## Blockers Encountered

    | Date | Blocker | Resolution |
    |------|---------|------------|
    | - | - | - |

---

## ⚠️ Common Rationalizations (REJECT These)

| Rationalization | Why It's Wrong |
|----------------|----------------|
| "The ticket is long enough already" | Gold-standard tickets are 190-310 lines — shorter means missing detail |
| "What to Implement is obvious from the spec" | Specs define WHAT; tickets define HOW with numbered steps and code |
| "No-Change Zones aren't needed" | Without them, agents modify files owned by other tasks |
| "Progress Updates section is boilerplate" | `/execute-task` and `/complete-task` record progress here — it MUST exist |
| "Development Mode doesn't apply" | Almost every task can be developed without full backend — document how |
| "Contract Verification is redundant with spec" | It's a checklist IN the ticket so agents verify during implementation |
| "This is a frontend task, no need for full detail" | Frontend tasks need the same rigor — Props, hooks, routes, BFF contracts |

## 🚩 Red Flags Your Ticket Is Missing Detail

- Ticket is under 100 lines → Almost certainly missing sections
- "What to Implement" has no code snippets → Agent will guess the implementation
- No "Files to Create/Modify" table → Agent won't know which files to touch
- No "No-Change Zones" → Agent may modify files owned by other tasks
- No "Contract Verification (from spec)" → Spec compliance won't be verified
- "Validation" has no manual verification commands → Can't verify without running tests
- No "Progress Updates" table → `/execute-task` has nowhere to record progress
- No "Reference Implementation" in References → Agent has no pattern to follow

---

## ⚠️ Verification Checklist (MANDATORY)

After creating tickets for a batch, verify completeness:

```bash
FEATURE="[feature-name]"

echo "=== Ticket File Verification ==="
ls docs/workstreams/${FEATURE}/tasks/ 2>/dev/null | wc -l
echo "ticket files in tasks/"

echo ""
echo "=== Per-Ticket Section Verification ==="
for TICKET in docs/workstreams/${FEATURE}/tasks/*.md; do
  echo ""
  echo "--- $(basename $TICKET) ---"
  grep -q "## Metadata" $TICKET && echo "✅ Metadata" || echo "❌ MISSING Metadata"
  grep -q "## Specification\|## API Contracts" $TICKET && echo "✅ Spec/API section" || echo "❌ MISSING"
  grep -q "## Pre-Conditions\|## Dependencies" $TICKET && echo "✅ Pre-Conditions/Dependencies" || echo "❌ MISSING"
  grep -q "## Task Description" $TICKET && echo "✅ Task Description" || echo "❌ MISSING"
  grep -q "### What to Implement" $TICKET && echo "✅ What to Implement" || echo "❌ MISSING What to Implement"
  grep -q "## Files to Create/Modify\|## Files to Modify" $TICKET && echo "✅ Files section" || echo "❌ MISSING"
  grep -q "No-Change Zone" $TICKET && echo "✅ No-Change Zones" || echo "⚠️  No No-Change Zones (OK if no restrictions)"
  grep -q "## Acceptance Criteria" $TICKET && echo "✅ Acceptance Criteria" || echo "❌ MISSING"
  grep -q "Contract Verification" $TICKET && echo "✅ Contract Verification" || echo "⚠️  No Contract Verification (OK if no spec)"
  grep -q "## Test Cases" $TICKET && echo "✅ Test Cases" || echo "❌ MISSING"
  grep -q "## Post-Conditions" $TICKET && echo "✅ Post-Conditions" || echo "❌ MISSING"
  grep -q "## Validation" $TICKET && echo "✅ Validation" || echo "❌ MISSING"
  grep -q "### Manual Verification" $TICKET && echo "✅ Manual Verification" || echo "❌ MISSING Manual Verification"
  grep -q "## References" $TICKET && echo "✅ References" || echo "❌ MISSING"
  grep -q "Reference Implementation\|Related Code" $TICKET && echo "✅ Reference Implementation/Related Code" || echo "⚠️  No Reference Implementation"
  grep -q "## Execution" $TICKET && echo "✅ Execution" || echo "❌ MISSING"
  grep -q "## Progress Updates\|## Execution Log" $TICKET && echo "✅ Progress Updates" || echo "❌ MISSING Progress Updates"
  grep -q "## Blockers Encountered\|Blockers" $TICKET && echo "✅ Blockers section" || echo "⚠️  No Blockers section"
  LINES=$(wc -l < $TICKET)
  echo "📏 $LINES lines"
  [ $LINES -lt 100 ] && echo "🚩 WARNING: Ticket under 100 lines — likely missing detail"
done

echo ""
echo "=== Worktree Sync Check ==="
WORKTREE_COUNT=$(git worktree list | wc -l)
if [ "$WORKTREE_COUNT" -gt 1 ]; then
  echo "Multi-Worktree Model — checking sync..."
  for WT in $(git worktree list | tail -n +2 | awk '{print $1}'); do
    echo "  $WT:"
    ls $WT/docs/workstreams/${FEATURE}/tasks/*.md 2>/dev/null | wc -l
    echo "  tickets synced"
  done
else
  echo "Single-Branch Model — no sync needed"
fi

echo ""
echo "=== WORKSTREAM.md and STATUS.md ==="
grep -c "tasks/" docs/workstreams/${FEATURE}/WORKSTREAM.md 2>/dev/null
echo "task links in WORKSTREAM.md"
grep -c "WS-" docs/workstreams/${FEATURE}/STATUS.md 2>/dev/null
echo "task references in STATUS.md"

echo "=== Complete ==="
```

---

## Tool Actions Summary

**Every ticket creation requires these actions:**

| Step | Tool | Location | Action | Required? |
|------|------|----------|--------|-----------|
| 3 | **`Write`** | Main repo | CREATE task ticket | ✅ Always |
| 4 | **`Shell`** | Worktree(s) | `mkdir -p` + `cp` ticket | ✅ Multi-worktree only |
| 5 | `StrReplace` | Main repo WORKSTREAM.md | Add task link | ✅ If exists |
| 6 | `StrReplace` | Main repo STATUS.md | Add to Ready/Pending | ✅ Always |

---

## 🔄 Worktree Sync Commands (Copy-Paste Ready)

### Detect Worktrees First

```bash
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
CONTROL_WT=$(git worktree list | grep -E 'control' | awk '{print $1}')
GATEWAY_WT=$(git worktree list | grep -E 'gateway' | awk '{print $1}')

echo "Main: $MAIN_REPO"
echo "Control: $CONTROL_WT"
echo "Gateway: $GATEWAY_WT"
```

### Single-Branch (No Worktrees)

```bash
# Nothing to do — tickets are already in main repo
echo "Single-branch model: tickets are in place"
```

### Bulk Sync All Tickets (Multi-Worktree)

```bash
FEATURE="[feature-name]"

# Control Plane tickets (A, C, E, F)
for letter in A C E F; do
  cp docs/workstreams/$FEATURE/tasks/WS-${letter}*.md $CONTROL_WT/docs/workstreams/$FEATURE/tasks/ 2>/dev/null
done

# Gateway tickets (B, D, E, F)
for letter in B D E F; do
  cp docs/workstreams/$FEATURE/tasks/WS-${letter}*.md $GATEWAY_WT/docs/workstreams/$FEATURE/tasks/ 2>/dev/null
done

echo "Synced all tickets to worktrees"
```

---

## Template Location

`docs/workstreams/TASK_TICKET_TEMPLATE.md`

---

## Output Format

After creating the task ticket, output:

    ## Task Ticket Created: [WS-ID]

    ### Ticket Location
    | Location | Path | Status |
    |----------|------|--------|
    | Main Repo | `docs/workstreams/[feature]/tasks/[WS-ID]-[name].md` | ✅ Created |
    | [worktree-name] | `[path]/.../[WS-ID]-[name].md` | ✅ Synced / ⬜ N/A (single-branch) |

    ### Quick Reference
    | Field | Value |
    |-------|-------|
    | Task ID | [WS-ID] |
    | Status | `ready` |
    | Dependencies | [list or None] |
    | Complexity | [S/M/L] |
    | Batch | [Batch number] |
    | Execution Context | [worktree-name / main repo (single-branch)] |

    ### Sections Verified
    | # | Section | Status |
    |---|---------|--------|
    | 1 | Metadata | ✅ |
    | 2 | Validation Mapping | ✅ |
    | 3 | Specification + Key Contracts | ✅ |
    | 4 | API Contracts | ✅ |
    | 5 | Dependencies (Code + Runtime + Dev Mode) | ✅ |
    | 6 | Pre-Conditions | ✅ |
    | 7 | Task Description (Objective + Background + What to Implement with code) | ✅ |
    | 8 | Files to Create/Modify + No-Change Zones | ✅ |
    | 9 | Acceptance Criteria (Functional + Security + Integration + Contract Verification) | ✅ |
    | 10 | Test Cases | ✅ |
    | 11 | Post-Conditions | ✅ |
    | 12 | Validation (Unit Tests + Manual Verification) | ✅ |
    | 13 | References (Spec + Design + Upstream/Downstream + Reference Implementation + Related Code) | ✅ |
    | 14 | Execution | ✅ |
    | 15 | Notes | ✅ (or N/A) |
    | 16 | Progress Updates + Blockers | ✅ |

    ### Next Steps
    - Execute: `/execute-task [WS-ID] [feature-name]`

    ---
    ✅ Ticket created. Ready for execution.

---

## Example Usage

User: "Create a task ticket for WS-A1: Define token data models for the MCP gateway feature"

Then create:
- `docs/workstreams/mcp-gateway/tasks/WS-A1-define-token-data-models.md`

With specific details about:
- What data models to create (numbered steps with code)
- Where they go (`deeptrail-control/app/models/`) — exact paths
- What fields they need (from the spec)
- No-Change Zones (which files NOT to touch)
- Reference implementation (existing model to follow)
- Manual verification commands
- Progress Updates table for execution tracking

---

## ✅ Completion Checklist

Before marking ticket creation complete, verify ALL of these:

| # | Check | How to Verify |
|---|-------|---------------|
| 1 | Ticket exists in main repo | `ls docs/workstreams/[feature]/tasks/[WS-ID]-*.md` |
| 2 | Ticket synced to worktree(s) (if multi-worktree) | `ls [worktree]/.../tasks/[WS-ID]-*.md` |
| 3 | All sections present (run verification command) | See ⚠️ Verification Checklist above |
| 4 | "What to Implement" has code snippets | Visual check |
| 5 | "No-Change Zones" present (or explicit "no restrictions") | Visual check |
| 6 | "Progress Updates" table present | Visual check |
| 7 | WORKSTREAM.md updated with task link | Check task table |
| 8 | STATUS.md updated with task in Ready/Pending | Check appropriate section |

**If any check fails, the ticket creation is INCOMPLETE.**

---

## Troubleshooting

### "Ticket not found" during `/execute-task`

**Cause:** Ticket was not synced to the worktree.

**Fix:**

```bash
WORKTREE=[path-to-worktree]
FEATURE=[feature-name]
TASK_ID=[WS-ID]

mkdir -p $WORKTREE/docs/workstreams/$FEATURE/tasks
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $WORKTREE/docs/workstreams/$FEATURE/tasks/
```

### Worktree not detected

**Cause:** Worktree not yet created or running from wrong directory.

**Fix:**

```bash
git worktree list

# If worktrees don't exist, create them:
git worktree add ../[name]-control -b feature/[name]-control dev
git worktree add ../[name]-gateway -b feature/[name]-gateway dev
```

### Single-branch feature — no worktrees needed

**Not an error.** For features like `frontend-architecture` or `idp-selector` that use a single
branch, tickets stay in the main repo. The "Sync to Worktrees" step is skipped entirely.

---

## Related Commands

| Command | Purpose |
|---------|---------|
| `/create-task-spec` | Creates the immutable spec this ticket references (input) |
| `/create-batch-execution-plan` | Provides batch/task info (input) |
| `/execute-task` | Reads and implements the ticket (consumer) |
| `/complete-task` | Updates the ticket's Progress Updates section (consumer) |
| `/debug` | Uses the ticket for context when debugging (consumer) |
