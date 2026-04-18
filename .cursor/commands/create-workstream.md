# Create Workstream

Create a new workstream folder structure with overview document.

> **Note:** This command is automatically called by `/breakdown-design` after generating the breakdown document.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /create-task-spec → /create-task-ticket
                         ↑
                    (YOU ARE HERE)
```

## Instructions

1. **Get workstream information from the user:**
   - Feature name (for folder: `docs/workstreams/[feature-name]/`)
   - Workstream ID (e.g., WS-A)
   - Workstream name/description
   - Link to parent design document
   - List of planned tasks (if known)

2. **Create the directory structure:**
   ```
   docs/workstreams/[feature-name]/
   ├── WORKSTREAM.md           ← Workstream overview
   ├── STATUS.md               ← Execution progress tracking
   ├── MERGE_POINTS.md         ← Merge point definitions (REQUIRED)
   ├── tasks/
   │   └── .gitkeep
   └── reports/
       └── .gitkeep
   ```
   
   **Note:** `CODEBASE_ANALYSIS.md` should already exist from pre-breakdown exploration.
   `BATCH_EXECUTION_PLAN.md` is created by `/create-batch-execution-plan`.

2b. **Worktree Lifecycle (if parallel execution):**
   
   > **Full guide:** `docs/WORKTREE_GUIDE.md`
   
   **IMPORTANT:** The WORKSTREAM.md and BATCH_EXECUTION_PLAN.md MUST include a complete
   "Worktree Lifecycle" section with all three steps below. This is mandatory for any
   workstream that uses parallel worktrees.
   
   **Step 1: Clean up old worktrees** (from previous features):
   ```bash
   cd /Users/imaxxs/repositories/deepsecure-mvp
   
   # Check existing worktrees
   git worktree list
   
   # Remove stale worktrees (adjust names to match previous feature)
   git worktree remove ../[old-worktree-name] --force
   
   # Delete stale branches (if already merged to dev)
   git branch -D feature/[old-branch-name]
   
   # Verify clean state
   git worktree list
   # Should show only: /Users/imaxxs/repositories/deepsecure-mvp  [dev]
   ```
   
   **Step 2: Create fresh worktrees:**
   ```bash
   cd /Users/imaxxs/repositories/deepsecure-mvp
   
   # Create worktrees from current dev HEAD
   git worktree add ../[feature]-control -b feature/[feature]-control dev
   git worktree add ../[feature]-gateway -b feature/[feature]-gateway dev
   
   # Copy .cursor commands to each worktree (required for /execute-task to work)
   cp -r .cursor ../[feature]-control/
   cp -r .cursor ../[feature]-gateway/
   
   # Verify
   git worktree list
   ```
   
   **Why copy `.cursor/`?** Git worktrees share git history but NOT working directory
   files like `.cursor/`. Commands like `/execute-task` won't be found without this copy.
   
   **Step 3: Post-merge cleanup** (after all merge points complete):
   ```bash
   cd /Users/imaxxs/repositories/deepsecure-mvp
   
   # Remove worktree directories
   git worktree remove ../[feature]-control
   git worktree remove ../[feature]-gateway
   
   # Delete feature branches (after PRs are merged)
   git branch -d feature/[feature]-control
   git branch -d feature/[feature]-gateway
   
   # Prune stale references
   git worktree prune
   ```

3. **Create WORKSTREAM.md** from template with:
   - All metadata filled in
   - **Batch assignments** (which batches this workstream's tasks belong to)
   - **Merge point dependencies** (which merge points this workstream contributes to or depends on)
   - Parallelization notes (what can run parallel, what's blocked)
   - Initial task table (can be empty or populated)
   - Files affected section
   - Risk assessment if applicable

4. **Create MERGE_POINTS.md** (REQUIRED):
   
   **IMPORTANT:** Use the comprehensive template in `docs/workstreams/MERGE_POINT_GUIDE.md`
   
   **Required sections** (see MERGE_POINT_GUIDE.md for full details):
   
   | Section | Purpose |
   |---------|---------|
   | Code Dependencies vs Runtime Dependencies | ASCII diagram explaining difference |
   | Task Lifecycle with Dependencies | ASCII diagram showing blocked→ready→dev→complete |
   | When Each Dependency Type Matters | Phase table |
   | Development Mode vs Integration Mode | Fallback behaviors when services down |
   | Runtime Dependencies by Merge Point | Service availability table |
   | Runtime Dependencies by Task | Task-level dependencies |
   | Merge Point Summary | ASCII overview diagram |
   | **Per-MP: Why It's a Merge Point** | Justification |
   | **Per-MP: Merge Actions** | Git workflow (push, PR, merge, rebase) |
   | **Per-MP: Container Deployment** | Docker commands |
   | **Per-MP: Container Test Scenarios** | curl examples with expected outputs |
   | **Per-MP: Cleanup** | Cleanup commands |
   | **Per-MP: Success Criteria** | Checklist |
   | **Per-MP: Post-Merge Status Update** | Status update commands |
   | Testing Strategy by Phase | P0, P1, P2 validation commands |
   | Troubleshooting | Issue/Cause/Fix tables |
   | Container Deployment Schedule | When to deploy |
   | Quick Reference Commands | Copy-paste ready |
   | Merge Point Status | Status table with Progress Summary |
   | History | Event log |
   
   **Verification command:**
   ```bash
   FEATURE="[feature-name]"
   FILE="docs/workstreams/${FEATURE}/MERGE_POINTS.md"
   
   echo "=== MERGE_POINTS.md Verification ==="
   grep -q "## Code Dependencies vs Runtime Dependencies" $FILE && echo "✅ Dependencies" || echo "❌ MISSING"
   grep -q "### Merge Actions" $FILE && echo "✅ Merge Actions" || echo "❌ MISSING"
   grep -q "### Container Test Scenarios" $FILE && echo "✅ Container Tests" || echo "❌ MISSING"
   grep -q "### Post-Merge Status Update" $FILE && echo "✅ Status Update" || echo "❌ MISSING"
   grep -q "## Quick Reference Commands" $FILE && echo "✅ Quick Reference" || echo "❌ MISSING"
   grep -q "## Merge Point Status" $FILE && echo "✅ Status Table" || echo "❌ MISSING"
   echo "=== Complete ==="
   ```

5. **Update the workstreams README:**
   - Add entry to "Active Workstreams" table in `docs/workstreams/README.md`

6. **Update status files:**
   
   a. **Update `docs/EXECUTION_STATUS.md`** (global portfolio):
      - Add design to "Active Designs" if not present
      - Set phase to "Phase 2: Planning"
      - Link to `docs/workstreams/[design-name]/STATUS.md` for detailed tracking

## Template Location
`docs/workstreams/WORKSTREAM_TEMPLATE.md`

## Output Format

```markdown
## Workstream Created

**Location:** `docs/workstreams/[feature-name]/`

### Structure
```
[feature-name]/
├── WORKSTREAM.md      ✅ Created
├── STATUS.md          ✅ Created
├── MERGE_POINTS.md    ✅ Created
├── tasks/             ✅ Created
└── reports/           ✅ Created
```

### Workstream Details
- **ID:** WS-[X]
- **Name:** [Workstream Name]
- **Design Doc:** [link]
- **Status:** planning
- **Batches:** [1, 2, 3] (which batches this workstream spans)
- **Contributes to Merge Point:** [MP1, or N/A]
- **Depends on Merge Point:** [MP2, or N/A]

### Next Steps
1. Review and refine the task breakdown in WORKSTREAM.md
2. Create batch execution plan with `/create-batch-execution-plan`
3. Create individual task tickets with `/create-task-ticket`
4. Begin execution of ready tasks

### Worktree Lifecycle

| Phase | Action | Commands |
|-------|--------|----------|
| **Setup** | Create worktrees | `git worktree add ../[name] -b feature/[name] dev` |
| **Execution** | Work in worktrees | `/execute-task`, `/complete-task` |
| **Merge** | Merge to dev | `git merge feature/[name] --no-ff` |
| **Cleanup** | Remove worktrees | `git worktree remove ../[name]` |

> **Note:** Cleanup commands are documented in `BATCH_EXECUTION_PLAN.md` under "Worktree Cleanup" section.

---

Workstream is ready for task ticket creation.
```

---

## ⚠️ Verification Checklist (MANDATORY)

Before declaring workstream creation complete, verify ALL files exist:

| File | Required | Purpose |
|------|----------|---------|
| `WORKSTREAM.md` | ✅ YES | Workstream overview and tasks |
| `STATUS.md` | ✅ YES | Progress tracking |
| `MERGE_POINTS.md` | ✅ YES | Merge point definitions |
| `tasks/` | ✅ YES | Task ticket folder |
| `reports/` | ✅ YES | Completion reports folder |

**Verification command:**
```bash
FEATURE="[feature-name]"
ls -la docs/workstreams/${FEATURE}/
```

**Expected output:**
```
WORKSTREAM.md
STATUS.md
MERGE_POINTS.md
tasks/
reports/
```

**If any file is missing, create it BEFORE declaring complete.**

## Example Usage

User: "Create a workstream for the MCP gateway token service feature"

Then create:
```
docs/workstreams/mcp-gateway-token-service/
├── WORKSTREAM.md      ← Workstream overview
├── STATUS.md          ← Progress tracking
├── MERGE_POINTS.md    ← Merge point definitions
├── tasks/
│   └── .gitkeep
└── reports/
    └── .gitkeep
```
