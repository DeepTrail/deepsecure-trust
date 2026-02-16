# Create Task Ticket

Create a new task ticket from the template for a specific task.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /create-task-spec → /create-task-ticket
                                                                                                   ↑
                                                                                              (YOU ARE HERE)
```

## Pre-Requisites

Before creating task tickets:

1. ✅ `/create-batch-execution-plan` completed (provides batch/task info)
2. ✅ `/create-task-spec` completed for all tasks involving Python code
   - Required for: API endpoints, data models, services, UI components, demo scripts
   - Skip ONLY for: Documentation/README-only tasks (no Python code)

---

## ⚠️ CRITICAL: Worktree Sync Required

**Tickets MUST be copied to worktrees immediately after creation.**

`/execute-task` runs inside worktrees and reads the LOCAL ticket file. If the ticket doesn't exist in the worktree, task execution will FAIL.

**After creating EVERY ticket, you MUST run Step 4 (Sync to Worktrees).**

---

## Workstream-to-Worktree Mapping

Different workstreams execute in different worktrees. Use this mapping to determine where to copy tickets:

| Workstream | Service | Worktree Name Pattern | Example Path |
|------------|---------|----------------------|--------------|
| WS-A (Control Models) | Control Plane | `vmcp-control`, `*-control` | `/Users/.../vmcp-control` |
| WS-B (Gateway Core) | Gateway | `vmcp-gateway`, `*-gateway` | `/Users/.../vmcp-gateway` |
| WS-C (Control APIs) | Control Plane | `vmcp-control`, `*-control` | `/Users/.../vmcp-control` |
| WS-D (Gateway Backends) | Gateway | `vmcp-gateway`, `*-gateway` | `/Users/.../vmcp-gateway` |
| WS-E (Shared/Audit) | Both | Both worktrees | Both paths |
| WS-F (Integration) | Both | Both worktrees | Both paths |

**Quick Reference:**
- **Control Plane tasks (A, C, E, F)** → Copy to `*-control` worktree
- **Gateway tasks (B, D, E, F)** → Copy to `*-gateway` worktree
- **Shared tasks (E, F)** → Copy to BOTH worktrees

---

## Instructions

### 1. Get Task Information

From the user or breakdown document:
- Task ID (e.g., WS-A1)
- Task name (brief, descriptive)
- Feature/workstream name (for folder path)

### 1b. Check for Existing Specification

**Check if a spec exists for this task:**
```
docs/workstreams/[feature-name]/specs/[WS-ID]-spec.md
```

**If spec exists:**
- Reference it in the ticket's "## Specification" section
- Copy key contracts (endpoint path, schemas, interfaces) into ticket
- Link acceptance criteria to spec verification

**If spec doesn't exist:**
- For tasks with Python code: Run `/create-task-spec` first (required)
- For documentation/README-only tasks: Proceed without spec

### 2. Create Directory Structure

If directories don't exist:
```
docs/workstreams/[feature-name]/
├── tasks/
└── reports/
```

### 3. Create Ticket in Main Repo

**Use the Write tool:**
```
Write:
  path: docs/workstreams/[feature]/tasks/[WS-ID]-[task-name].md
  contents: |
    # Task: [WS-ID] [Task Name]
    ... (full ticket content from template)
```

### 4. 🔄 SYNC TO WORKTREES (MANDATORY)

**This step is NOT optional. Execute immediately after Step 3.**

a. **Detect active worktrees:**
```bash
# List all worktrees
git worktree list

# Example output:
# /Users/imaxxs/repositories/deepsecure-mvp   abc123 [dev]              ← Main repo
# /Users/imaxxs/repositories/vmcp-control     def456 [feature/vmcp-control]  ← Control
# /Users/imaxxs/repositories/vmcp-gateway     ghi789 [feature/vmcp-gateway]  ← Gateway
```

b. **Identify target worktree(s) using mapping above:**
   - Extract workstream letter from Task ID (e.g., WS-A1 → A)
   - Look up worktree in mapping table

c. **Copy ticket to target worktree(s):**

**For single worktree (A, B, C, D tasks):**
```bash
# Ensure directory exists
mkdir -p [WORKTREE_PATH]/docs/workstreams/[feature]/tasks

# Copy the ticket
cp docs/workstreams/[feature]/tasks/[WS-ID]-*.md \
   [WORKTREE_PATH]/docs/workstreams/[feature]/tasks/
```

**For shared tasks (E, F) - copy to BOTH:**
```bash
# Control worktree
mkdir -p [CONTROL_WORKTREE]/docs/workstreams/[feature]/tasks
cp docs/workstreams/[feature]/tasks/[WS-ID]-*.md \
   [CONTROL_WORKTREE]/docs/workstreams/[feature]/tasks/

# Gateway worktree
mkdir -p [GATEWAY_WORKTREE]/docs/workstreams/[feature]/tasks
cp docs/workstreams/[feature]/tasks/[WS-ID]-*.md \
   [GATEWAY_WORKTREE]/docs/workstreams/[feature]/tasks/
```

d. **Verify copy succeeded:**
```bash
# Verify file exists in worktree
ls [WORKTREE_PATH]/docs/workstreams/[feature]/tasks/[WS-ID]-*.md
```

### 5. Fill in Template Details

Fill in the template with:
- All metadata fields (status: `ready`, dependencies, complexity)
- Pre-conditions based on dependencies
- Detailed task description
- **Explicit file paths** (e.g., `deeptrail-control/models/user_session.py` not just "models")
- Specific acceptance criteria (not generic), categorized by type:
  - Protocol criteria (if applicable)
  - Security criteria (if applicable)
  - Integration criteria (if applicable)
- **Validation mapping** (which demo/milestone and user journey step this validates)
- Post-conditions
- References to design doc and related code

### 6. Update Workstream Tracker

If `WORKSTREAM.md` exists:
- Add the task to the task table
- Link to the new task ticket

### 7. Update STATUS.md

a. **Add task to appropriate section:**
   - If no dependencies or all dependencies complete → Add to "⏳ Ready" section
   - If has unmet dependencies → Add to "⏸️ Pending" section

b. **Update task counts:**
   - Increment total tasks if this is a new task
   - Update Ready/Pending counts

c. **Add to Timeline:**
   - Add entry: `[date] | Task ticket [WS-ID] created`

---

## Tool Actions Summary

**Every ticket creation requires these actions:**

| Step | Tool | Location | Action | Required? |
|------|------|----------|--------|-----------|
| 3 | **`Write`** | Main repo | CREATE task ticket | ✅ Always |
| 4 | **`Shell`** | Worktree(s) | `mkdir -p` + `cp` ticket | ✅ Always |
| 6 | `StrReplace` | Main repo WORKSTREAM.md | Add task link | ✅ If exists |
| 7 | `StrReplace` | Main repo STATUS.md | Add to Ready/Pending | ✅ Always |

---

## 🔄 Worktree Sync Commands (Copy-Paste Ready)

### Detect Worktrees First
```bash
# Get worktree paths
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
CONTROL_WT=$(git worktree list | grep -E 'control' | awk '{print $1}')
GATEWAY_WT=$(git worktree list | grep -E 'gateway' | awk '{print $1}')

echo "Main: $MAIN_REPO"
echo "Control: $CONTROL_WT"
echo "Gateway: $GATEWAY_WT"
```

### Copy Based on Workstream Letter

**WS-A task (Control Plane):**
```bash
FEATURE="virtual-mcp-server-mvp"  # Change as needed
TASK_ID="WS-A1"                   # Change as needed

mkdir -p $CONTROL_WT/docs/workstreams/$FEATURE/tasks
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $CONTROL_WT/docs/workstreams/$FEATURE/tasks/
```

**WS-B task (Gateway):**
```bash
mkdir -p $GATEWAY_WT/docs/workstreams/$FEATURE/tasks
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $GATEWAY_WT/docs/workstreams/$FEATURE/tasks/
```

**WS-C task (Control Plane):**
```bash
mkdir -p $CONTROL_WT/docs/workstreams/$FEATURE/tasks
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $CONTROL_WT/docs/workstreams/$FEATURE/tasks/
```

**WS-D task (Gateway):**
```bash
mkdir -p $GATEWAY_WT/docs/workstreams/$FEATURE/tasks
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $GATEWAY_WT/docs/workstreams/$FEATURE/tasks/
```

**WS-E or WS-F task (Both):**
```bash
mkdir -p $CONTROL_WT/docs/workstreams/$FEATURE/tasks
mkdir -p $GATEWAY_WT/docs/workstreams/$FEATURE/tasks
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $CONTROL_WT/docs/workstreams/$FEATURE/tasks/
cp docs/workstreams/$FEATURE/tasks/$TASK_ID-*.md $GATEWAY_WT/docs/workstreams/$FEATURE/tasks/
```

### Bulk Sync All Tickets (Use After Creating Multiple Tickets)
```bash
FEATURE="virtual-mcp-server-mvp"

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

## Output Format

After creating the task ticket, output:

```markdown
## Task Ticket Created: [WS-ID]

### Ticket Location
| Location | Path | Status |
|----------|------|--------|
| Main Repo | `docs/workstreams/[feature]/tasks/[WS-ID]-[name].md` | ✅ Created |
| vmcp-control | `[path]/docs/workstreams/[feature]/tasks/[WS-ID]-[name].md` | ✅ Synced |
| vmcp-gateway | `[path]/docs/workstreams/[feature]/tasks/[WS-ID]-[name].md` | ⬜ N/A (not target) |

### Quick Reference
| Field | Value |
|-------|-------|
| Task ID | [WS-ID] |
| Status | `ready` |
| Dependencies | [list or None] |
| Complexity | [S/M/L] |
| Batch | [Batch number] |
| Target Worktree | [vmcp-control / vmcp-gateway / both] |

### Validation Mapping
- **Validates Demo:** [Demo 1, Demo 2, or N/A]
- **Validates User Journey Step:** [Step 3, or N/A]

### Acceptance Criteria Summary
**Protocol:**
- [ ] [criterion if applicable]

**Security:**
- [ ] [criterion if applicable]

**Integration:**
- [ ] [criterion if applicable]

### Files to Touch
- `deeptrail-control/models/user_session.py` (create)
- `deeptrail-gateway/gateway/mcp/protocol.py` (modify)

### Execution Command
```bash
# Run in [vmcp-control/vmcp-gateway] worktree:
cd [worktree-path]
# Then: /execute-task [WS-ID] [feature-name]
```

---

✅ Ticket created and synced. Ready for execution.
```

## Example Usage

User: "Create a task ticket for WS-A1: Define token data models for the MCP gateway feature"

Then create:
- `docs/workstreams/mcp-gateway/tasks/WS-A1-define-token-data-models.md`

With specific details about:
- What data models to create
- Where they go (`deepsecure/_core/models/`)
- What fields they need
- How to test them

---

## ✅ Completion Checklist

Before marking ticket creation complete, verify ALL of these:

| # | Check | Command to Verify |
|---|-------|-------------------|
| 1 | Ticket exists in main repo | `ls docs/workstreams/[feature]/tasks/[WS-ID]-*.md` |
| 2 | Ticket copied to target worktree(s) | `ls [worktree]/docs/workstreams/[feature]/tasks/[WS-ID]-*.md` |
| 3 | WORKSTREAM.md updated with task link | Check task table in WORKSTREAM.md |
| 4 | STATUS.md updated with task in Ready/Pending | Check appropriate section |

**If any check fails, the ticket creation is INCOMPLETE.**

---

## Troubleshooting

### "Ticket not found" during `/execute-task`

**Cause:** Ticket was not synced to the worktree.

**Fix:**
```bash
# From main repo
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
# Verify you're in main repo
git worktree list

# If worktrees don't exist, create them:
git worktree add ../vmcp-control -b feature/vmcp-control dev
git worktree add ../vmcp-gateway -b feature/vmcp-gateway dev
```
