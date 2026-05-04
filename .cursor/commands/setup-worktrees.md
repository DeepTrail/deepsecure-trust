# Setup Worktrees: Automated Parallel Execution Environment

Automatically create git worktrees from a batch execution plan, map workstreams to worktrees by service boundary, copy configuration, and output ready-to-run execution commands.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /setup-worktrees → /execute-task (parallel)
                                                                            ↑
                                                                       (YOU ARE HERE)
```

## When to Use

- After `/create-batch-execution-plan` has generated the batch plan
- When the feature spans multiple services (Control Plane + Gateway + SDK)
- When you want to parallelize execution across multiple agent sessions
- When setting up for Boris Cherny-style parallel worktree execution

**When NOT to use:**
- Feature is single-service only (no parallelization benefit)
- Feature has fewer than 4 tasks total (overhead exceeds benefit)
- All tasks are sequential (no parallel batches exist)

---

## Instructions

### Step 1: Read the Batch Execution Plan

```
Read: docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md
Read: docs/workstreams/[feature-name]/BREAKDOWN.md
```

Extract:
- Workstream-to-service mapping (which workstreams touch which services)
- Parallelizable task groups (tasks that can run simultaneously)
- Merge points (where parallel tracks must converge)

### Step 2: Analyze Service Boundaries

Classify each workstream by primary service:

| Service | Directory | Typical Workstreams |
|---------|-----------|---------------------|
| Control Plane | `deeptrail-control/` | Models, schemas, services, API endpoints, migrations |
| Gateway | `deeptrail-gateway/` | MCP handlers, middleware, backends, security modules |
| SDK | `deepsecure/` | Core modules, public client, CLI commands |
| Cross-Service | Root level | E2E tests, demos, integration tests |
| Docs-Only | Root level | Documentation, README, design docs |

**Decision matrix for worktree count:**

| Scenario | Worktrees | Rationale |
|----------|-----------|-----------|
| Control + Gateway changes | 2 | Separate service directories, no conflicts |
| Control + Gateway + SDK | 3 | Three independent directories |
| Single service + tests | 1 | No parallelization benefit |
| Control + Gateway + cross-service E2E | 2 + main | E2E runs from main after merge point |

### Step 3: Determine Worktree Configuration

Generate a worktree plan:

```markdown
## Worktree Plan for: [feature-name]

### Base Branch: [dev/main]

### Worktrees to Create

| # | Worktree Name | Branch | Service | Workstreams | Tasks |
|---|---------------|--------|---------|-------------|-------|
| 1 | [feature]-control | feature/[feature]-control | deeptrail-control | WS-A, WS-C | A1-A5, C1-C3 |
| 2 | [feature]-gateway | feature/[feature]-gateway | deeptrail-gateway | WS-B, WS-D | B1-B4, D1-D2 |

### Merge Points

| Point | After Tasks | Git Action | Enables |
|-------|-------------|------------|---------|
| MP1 | A3 + B2 | Merge both into dev | Cross-service tasks |
```

**CHECKPOINT**: Present worktree plan to user for approval before creating.

### Step 4: Clean Up Old Worktrees (if any)

```bash
# Check for existing worktrees
git worktree list

# Remove stale worktrees from previous features
# ONLY if user confirms
git worktree remove ../[old-worktree] --force
git branch -D feature/[old-branch]
```

**Ask user before removing any existing worktrees.**

### Step 5: Create Worktrees

Execute these commands:

```bash
# Ensure we're on the base branch
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev  # or main, depending on project

# Create worktrees for each service
git worktree add ../[feature]-control -b feature/[feature]-control dev
git worktree add ../[feature]-gateway -b feature/[feature]-gateway dev
# Add more as needed based on Step 3
```

### Step 6: Copy Configuration to Each Worktree

**CRITICAL: Without this step, commands won't work in worktrees.**

```bash
# Copy .cursor directory (commands, agents, hooks)
cp -r .cursor ../[feature]-control/
cp -r .cursor ../[feature]-gateway/

# Copy .claude directory if it exists
if [ -d ".claude" ]; then
  cp -r .claude ../[feature]-control/
  cp -r .claude ../[feature]-gateway/
fi

# Copy CLAUDE.md (project rules)
cp CLAUDE.md ../[feature]-control/
cp CLAUDE.md ../[feature]-gateway/

# Copy .cursorrules if it exists
if [ -f ".cursorrules" ]; then
  cp .cursorrules ../[feature]-control/
  cp .cursorrules ../[feature]-gateway/
fi
```

### Step 7: Copy Workstream Files to Each Worktree

```bash
# Ensure workstream directories exist in worktrees
mkdir -p ../[feature]-control/docs/workstreams/[feature-name]/tasks
mkdir -p ../[feature]-control/docs/workstreams/[feature-name]/reports
mkdir -p ../[feature]-control/docs/workstreams/[feature-name]/specs
mkdir -p ../[feature]-gateway/docs/workstreams/[feature-name]/tasks
mkdir -p ../[feature]-gateway/docs/workstreams/[feature-name]/reports
mkdir -p ../[feature]-gateway/docs/workstreams/[feature-name]/specs

# Copy workstream docs
cp docs/workstreams/[feature-name]/*.md ../[feature]-control/docs/workstreams/[feature-name]/
cp docs/workstreams/[feature-name]/*.md ../[feature]-gateway/docs/workstreams/[feature-name]/

# Copy task tickets (if already created)
cp docs/workstreams/[feature-name]/tasks/*.md ../[feature]-control/docs/workstreams/[feature-name]/tasks/ 2>/dev/null
cp docs/workstreams/[feature-name]/tasks/*.md ../[feature]-gateway/docs/workstreams/[feature-name]/tasks/ 2>/dev/null

# Copy specs (if already created)
cp docs/workstreams/[feature-name]/specs/*.md ../[feature]-control/docs/workstreams/[feature-name]/specs/ 2>/dev/null
cp docs/workstreams/[feature-name]/specs/*.md ../[feature]-gateway/docs/workstreams/[feature-name]/specs/ 2>/dev/null
```

### Step 8: Verify Setup

Run verification checks:

```bash
echo "=== Worktree Setup Verification ==="

# Check worktrees exist
echo ""
echo "1. Worktrees:"
git worktree list

# Check .cursor commands in each worktree
echo ""
echo "2. Commands available:"
for wt in ../[feature]-control ../[feature]-gateway; do
  echo "  $wt: $(ls $wt/.cursor/commands/ 2>/dev/null | wc -l) commands"
done

# Check workstream files
echo ""
echo "3. Workstream files:"
for wt in ../[feature]-control ../[feature]-gateway; do
  echo "  $wt: $(ls $wt/docs/workstreams/[feature-name]/*.md 2>/dev/null | wc -l) docs"
done

# Check task tickets
echo ""
echo "4. Task tickets:"
for wt in ../[feature]-control ../[feature]-gateway; do
  echo "  $wt: $(ls $wt/docs/workstreams/[feature-name]/tasks/*.md 2>/dev/null | wc -l) tickets"
done

echo ""
echo "=== Verification Complete ==="
```

### Step 9: Generate Execution Commands

Output ready-to-use commands for each worktree:

```markdown
## Ready for Parallel Execution

### Worktree 1: [feature]-control
**Path:** /Users/imaxxs/repositories/[feature]-control
**Branch:** feature/[feature]-control
**Tasks:** [list]

Open a new terminal/agent session:
```bash
cd /Users/imaxxs/repositories/[feature]-control

# Batch 1
/execute-task WS-A1 [feature-name]
/execute-task WS-A2 [feature-name]
```

### Worktree 2: [feature]-gateway
**Path:** /Users/imaxxs/repositories/[feature]-gateway
**Branch:** feature/[feature]-gateway
**Tasks:** [list]

Open a new terminal/agent session:
```bash
cd /Users/imaxxs/repositories/[feature]-gateway

# Batch 1
/execute-task WS-B1 [feature-name]
/execute-task WS-B2 [feature-name]
```

### After Batch Completion (from main repo)
```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/verify-batch-completion [batch-id] [feature-name]
/sync-worktree-status [feature-name]
```

### At Merge Point MP1
```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev
git merge feature/[feature]-control
git merge feature/[feature]-gateway
# Resolve conflicts if any
# Create new worktrees for next phase if needed
```
```

---

## Worktree Lifecycle Management

### Creation → Execution → Merge → Cleanup

```
CREATE                    EXECUTE                 MERGE                 CLEANUP
┌──────┐               ┌──────┐               ┌──────┐              ┌──────┐
│ This │ ────────────▶ │/exec │ ────────────▶ │Merge │ ──────────▶ │Remove│
│ cmd  │               │/task │               │Point │              │ wt   │
└──────┘               └──────┘               └──────┘              └──────┘
/setup-worktrees        Parallel in            git merge             git worktree
                        each worktree          both branches         remove
```

### Ticket Sync Reminder

**CRITICAL:** When new task tickets are created after worktree setup, they MUST be copied to the relevant worktrees:

```bash
# After /create-task-ticket creates a new ticket
cp docs/workstreams/[feature]/tasks/WS-[ID]-*.md \
   ../[feature]-control/docs/workstreams/[feature]/tasks/
cp docs/workstreams/[feature]/tasks/WS-[ID]-*.md \
   ../[feature]-gateway/docs/workstreams/[feature]/tasks/
```

This is already handled in `/create-task-ticket` Step 4, but verify it worked.

---

## Output Format

```markdown
## Worktree Setup Complete ✅

### Feature: [feature-name]
### Base Branch: dev

### Worktrees Created

| # | Name | Path | Branch | Service | Tasks |
|---|------|------|--------|---------|-------|
| 1 | [feature]-control | /Users/.../[feature]-control | feature/[feature]-control | Control Plane | A1-A5 |
| 2 | [feature]-gateway | /Users/.../[feature]-gateway | feature/[feature]-gateway | Gateway | B1-B4 |

### Configuration Copied
- [x] .cursor/commands/ ([N] commands)
- [x] .cursor/agents/ ([N] agents)
- [x] .cursor/hooks.json (if exists)
- [x] .claude/ (if exists)
- [x] CLAUDE.md
- [x] .cursorrules
- [x] Workstream docs
- [x] Task tickets ([N] tickets)
- [x] Task specs ([N] specs)

### Verification
- [x] All worktrees accessible
- [x] Commands available in each worktree
- [x] Workstream files present
- [x] Task tickets synced

### Merge Points

| Point | Trigger | Git Action |
|-------|---------|------------|
| MP1 | After A3 + B2 | Merge both into dev |

### Ready-to-Run Commands
[Generated commands per worktree, as in Step 9]

### Next Steps
1. Open parallel terminal/agent sessions for each worktree
2. Run /execute-task commands in each session
3. After batch completion: /verify-batch-completion from main repo
4. At merge points: merge branches and create new worktrees if needed
5. Cleanup: git worktree remove ../[feature]-control
```

---

## Cleanup After Feature Completion

After all tasks are done and branches merged:

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Remove worktrees
git worktree remove ../[feature]-control
git worktree remove ../[feature]-gateway

# Delete feature branches (if merged)
git branch -d feature/[feature]-control
git branch -d feature/[feature]-gateway

# Verify cleanup
git worktree list  # Should only show main repo
git branch -a      # Feature branches should be gone
```

---

## Reference

This command integrates with:
- `/create-batch-execution-plan` — Provides the batch plan this reads
- `/execute-task` — Runs in each worktree after setup
- `/sync-worktree-status` — Consolidates status from worktrees to main
- `/verify-batch-completion` — Verifies batch status consistency
- `/create-task-ticket` — Must sync new tickets to worktrees (Step 4)
- Boris Cherny's parallel worktree workflow — Upstream inspiration
