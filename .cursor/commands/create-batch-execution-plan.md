# Create Batch Execution Plan

Generate a comprehensive batch execution plan with wave analysis, dependency graphs, and commands for a design.

> **Note:** This command is automatically called by `/breakdown-design` after creating the workstream structure.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /create-task-spec → /create-task-ticket
                                               ↑
                                          (YOU ARE HERE)
```

## Usage

```
/create-batch-execution-plan [feature-name]
```

**Parameters:**
- `[feature-name]`: The design/feature name (e.g., `virtual-mcp-server-mvp`)

**Output:**
- Creates `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md`

---

## 📁 Directory Structure Reference (CANONICAL)

**IMPORTANT:** Use these EXACT paths when generating validation commands. Do NOT use `tests/unit/`.

### Test Paths (⚠️ NO `unit/` subdirectory!)

| Service | Test Type | ✅ CORRECT Path | ❌ WRONG Path |
|---------|-----------|-----------------|---------------|
| Control | Schemas | `tests/schemas/` | `tests/unit/schemas/` |
| Control | Services | `tests/services/` | `tests/unit/services/` |
| Control | Models | `tests/models/` | `tests/unit/models/` |
| Control | API | `tests/api/v1/` | `tests/unit/api/` |
| Gateway | Backends | `tests/backends/` | `tests/unit/backends/` |
| Gateway | Middleware | `tests/middleware/` | `tests/unit/middleware/` |
| Gateway | Security | `tests/security/` | `tests/unit/security/` |
| Gateway | MCP | `tests/mcp/` | `tests/unit/mcp/` |

### Absolute Path Templates

```bash
# Main repo
MAIN_REPO="/Users/imaxxs/repositories/deepsecure-mvp"

# Control Plane
CONTROL="${MAIN_REPO}/deeptrail-control"

# Gateway
GATEWAY="${MAIN_REPO}/deeptrail-gateway"

# Worktrees (when created)
WORKTREE_CONTROL="/Users/imaxxs/repositories/mvp-prod-control"
WORKTREE_GATEWAY="/Users/imaxxs/repositories/mvp-prod-gateway"
```

### Validation Command Templates

Always use absolute paths in generated commands:

```bash
# Control Plane validation
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
pytest tests/schemas/ -v
pytest tests/services/ -v

# Gateway validation
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-gateway
pytest tests/backends/ -v
pytest tests/middleware/ -v

# E2E validation
cd /Users/imaxxs/repositories/deepsecure-mvp
python demos/demo_sarah_journey_e2e.py
pytest tests/e2e/ -v
```

---

## Instructions

### 1. Read the Breakdown Document

Read the breakdown document to extract all task information:

```
docs/[feature-name]-breakdown.md
```

or

```
docs/deepsecure-[feature-name]-breakdown.md
```

Extract:
- All workstreams and their tasks
- Task dependencies (the "Dependencies" column)
- Task sizes (S, M, L)
- Batch assignments
- Worktree assignments (which service: control plane vs gateway)
- Merge points

### 2. Read the Workstream File

Read for additional context:

```
docs/workstreams/[feature-name]/WORKSTREAM.md
```

Extract:
- Current batch status
- Worktree paths and branches
- Any completed tasks (to mark dependencies as ✅)

### 3. Build Dependency Graph

For each batch, analyze internal dependencies:

1. **List all tasks in the batch**
2. **For each task, check if any dependencies are ALSO in this batch**
   - If dependency is in a previous batch → mark as ✅ (satisfied)
   - If dependency is in THIS batch → creates a wave dependency
3. **Group tasks into waves:**
   - Wave 1: All tasks whose dependencies are ALL satisfied (from prior batches)
   - Wave 2: Tasks that depend on Wave 1 tasks
   - Wave 3: Tasks that depend on Wave 2 tasks
   - Continue until all tasks assigned

### 4. Determine Worktree Assignment

Map each task to its worktree based on workstream:

| Workstream | Typical Worktree | Service |
|------------|------------------|---------|
| A (Control Plane) | vmcp-control | deeptrail-control |
| B (Gateway Core) | vmcp-gateway | deeptrail-gateway |
| C (Auth) | Split - check each task | Both services |
| D (Backend) | vmcp-gateway | deeptrail-gateway |
| E (Audit) | Split - check each task | Both services |
| F (Integration) | vmcp-gateway | Tests/examples |

**For C and E workstreams, check the file paths in the task:**
- Files in `deeptrail-control/` → vmcp-control
- Files in `deeptrail-gateway/` → vmcp-gateway

### 5. Generate the Execution Plan

Create `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md` with the following structure:

---

## Output Template

```markdown
# Batch Execution Plan: [Feature Name]

> **Generated from:** [breakdown-doc-path]
>
> **Design Doc:** [design-doc-path]
>
> **Last Updated:** [date]

---

## Quick Reference

| Batch | Total Tasks | Waves | Fully Parallel? | Worktrees |
|-------|-------------|-------|-----------------|-----------|
| [n] | [count] | [waves] | [✅ Yes / ❌ No] | [list] |
...

---

## Worktree Reference

| Worktree | Path | Branch | Workstreams |
|----------|------|--------|-------------|
| [name] | [path] | [branch] | [workstreams] |
...

---

## Batch [N]: [Description] ([X] tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| [ID] | [desc] | [deps or None] | [worktree] |
...

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | [tasks] | [tasks] |
| **2** | [tasks] | [tasks] |
...

### Visual Dependency Graph

```
CONTROL (worktree-control)      GATEWAY (worktree-gateway)
──────────────────────          ─────────────────────────

Wave 1:    [task] ────┐              [task] ──────┐
                      │                           │
Wave 2:               ▼                           ▼
           [task] ────┤              [task] ──────┤
                      │                           │
                      └─────────┬─────────────────┘
                                │
                        [Batch N Complete]
```

### Execution Strategy

[Description of parallel vs sequential requirements]

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH [N] - [WAVE DESCRIPTION]
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd [main-repo-path]
/create-task-spec [N] [feature-name]  # Creates specs for all tasks in this batch

# --- Create Task Tickets (after specs approved) ---
/create-task-ticket WS-[ID] [feature-name]
...

# ───────────────────────────────────────────────────────────────
# WAVE 1: [tasks]
# ───────────────────────────────────────────────────────────────

# Terminal 1: [worktree-1]
cd [worktree-1-path]
/execute-task WS-[ID] [feature-name]
/complete-task WS-[ID] [feature-name]
...

# Terminal 2: [worktree-2]
cd [worktree-2-path]
/execute-task WS-[ID] [feature-name]
/complete-task WS-[ID] [feature-name]
...

# ⏸️ WAIT: [description of what to wait for]

# ───────────────────────────────────────────────────────────────
# WAVE 2: [tasks]
# ───────────────────────────────────────────────────────────────
...

# --- Sync Status (from main repo) ---
cd [main-repo-path]
/sync-worktree-status [feature-name]
```

### ⚠️ Post-Batch Verification (MANDATORY)

**Before proceeding to the next batch, verify status consistency:**

```bash
# Run from main repo
cd [main-repo-path]

# Verify batch completion
/verify-batch-completion [batch-id] [feature-name]
```

**Verification Checklist:**
- [ ] All batch tasks have completion reports in `reports/`
- [ ] STATUS.md shows all tasks as "✅ Complete"
- [ ] WORKSTREAM.md shows all tasks with correct status and report links
- [ ] BATCH_EXECUTION_PLAN.md Quick Reference shows batch as "✅ Complete"
- [ ] If batch triggers merge point, MERGE_POINTS.md shows it as "✅ Reached"

**DO NOT proceed to next batch until verification passes.**

---

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | [X]% ([description]) |
| **Waves** | [count] |
| **Bottleneck** | [task or None] |
| **Merge Point** | [MP or None] |
| **Unblocks** | [next batch tasks] |

---

[Repeat for each batch...]

---

## Overall Execution Summary

### Batch Parallelism Overview

| Batch | Tasks | Waves | Parallel % | Cross-Worktree? |
|-------|-------|-------|------------|-----------------|
...

### Merge Points Summary

| Point | After Batch | Converging | Actions Required |
|-------|-------------|------------|------------------|
...

### Total Commands Needed

| Command Type | Count |
|--------------|-------|
| `/create-task-spec` | [total batches] (one per batch) |
| `/create-task-ticket` | [total tasks] |
| `/execute-task` | [total tasks] |
| `/complete-task` | [total tasks] (auto after execute) |
| `/sync-worktree-status` | [total batches] |
| Merge Point actions | [count] |
| **Total** | [sum] |

### Critical Path

```
[task] → [task] → ... → [task]
│                            │
└────── [X] days minimum ────┘
```

### Worktree Distribution

| Worktree | Tasks |
|----------|-------|
| **[worktree]** | [task list] ([count] tasks) |
...

---

*Generated by `/create-batch-execution-plan` command*
```

---

## Wave Calculation Algorithm

```python
def calculate_waves(batch_tasks, completed_tasks):
    """
    Calculate which wave each task belongs to.
    
    Args:
        batch_tasks: Dict[task_id, List[dependency_ids]]
        completed_tasks: Set[task_id] - tasks completed in prior batches
    
    Returns:
        Dict[wave_num, List[task_id]]
    """
    waves = {}
    assigned = set()
    wave_num = 1
    
    while len(assigned) < len(batch_tasks):
        current_wave = []
        
        for task_id, deps in batch_tasks.items():
            if task_id in assigned:
                continue
            
            # Check if all dependencies are satisfied
            deps_satisfied = all(
                dep in completed_tasks or dep in assigned
                for dep in deps
            )
            
            # For wave 1, only count prior-batch deps
            if wave_num == 1:
                deps_satisfied = all(
                    dep in completed_tasks
                    for dep in deps
                )
            
            if deps_satisfied:
                current_wave.append(task_id)
        
        if not current_wave:
            raise ValueError(f"Circular dependency detected in batch")
        
        waves[wave_num] = current_wave
        assigned.update(current_wave)
        completed_tasks.update(current_wave)
        wave_num += 1
    
    return waves
```

---

## Parallelism Calculation

```
Parallelism % = (Max parallel tasks in any wave / Total tasks) * 100

Example:
- Batch has 9 tasks
- Wave 1: 3 tasks (parallel)
- Wave 2: 2 tasks (parallel)  
- Wave 3: 2 tasks (parallel)
- Wave 4: 2 tasks (parallel)

Parallelism = 3/9 = 33% (or weighted average: (3+2+2+2)/(4*3) = 9/12 = 75%)
```

Use the **maximum concurrent tasks** interpretation:
- If Wave 1 has 3 parallel tasks and that's the max → 33%
- Or use **cross-worktree parallelism**: control and gateway always parallel → 100% cross-worktree

---

## Example Output

See `docs/workstreams/virtual-mcp-server-mvp/BATCH_EXECUTION_PLAN.md` for a complete example.

---

## Post-Creation Steps

After creating the execution plan:

1. **Link from WORKSTREAM.md:**
   ```markdown
   ## Execution
   
   > **Batch Execution Plan:** [BATCH_EXECUTION_PLAN.md](./BATCH_EXECUTION_PLAN.md)
   ```

2. **Link from STATUS.md:**
   Add reference in the header section

3. **Commit the file:**
   ```bash
   git add docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md
   git commit -m "Add batch execution plan for [feature-name]"
   ```

---

## ⚠️ Output Verification Checklist (MANDATORY)

**Before declaring the batch execution plan complete, verify ALL sections exist.**

### Required Sections Checklist

| # | Section | Required? | Purpose |
|---|---------|-----------|---------|
| 1 | **Quick Reference** | ✅ YES | Status tracking table with Complete column |
| 2 | **Worktree Reference** | ✅ YES | Path, Branch, Workstreams mapping |
| 3 | **Per-Batch: Dependencies** | ✅ YES | Table with Worktree column |
| 4 | **Per-Batch: Wave Analysis** | ✅ YES | Table format (Control \| Gateway columns) |
| 5 | **Per-Batch: Visual Dependency Graph** | ✅ YES | ASCII showing CONTROL/GATEWAY |
| 6 | **Per-Batch: Execution Strategy** | ✅ YES | Text description |
| 7 | **Per-Batch: Commands** | ✅ YES | `/create-task-spec`, `/create-task-ticket`, `/execute-task`, `/complete-task` |
| 8 | **Per-Batch: Summary** | ✅ YES | Table with Metric/Value format |
| 9 | **Overall Execution Summary** | ✅ YES | Batch overview, merge points, total commands |
| 10 | **Critical Path** | ✅ YES | ASCII diagram |
| 11 | **Quick Start Commands** | ✅ YES | Copy-paste ready |

### Per-Batch Command Template (MUST include ALL)

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH [N] - [DESCRIPTION]
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd /path/to/main/repo
/plan
/create-task-spec [batch] [feature-name]

# --- Create Task Tickets (from main repo) ---
/create-task-ticket WS-[ID] [feature-name]
...

# ───────────────────────────────────────────────────────────────
# WAVE 1: [tasks]
# ───────────────────────────────────────────────────────────────

# Terminal 1: [worktree]
cd /path/to/worktree
/execute-task WS-[ID] [feature-name]
/complete-task WS-[ID] [feature-name]

# Terminal 2: [worktree]
cd /path/to/other-worktree
/execute-task WS-[ID] [feature-name]
/complete-task WS-[ID] [feature-name]

# ⏸️ WAIT: [dependency description if needed]

# ───────────────────────────────────────────────────────────────
# WAVE 2: [tasks]
# ───────────────────────────────────────────────────────────────
...

# --- Sync Status (from main repo) ---
cd /path/to/main/repo
/sync-worktree-status [feature-name]
```

### Verification Command

Before completing, grep for required sections:

```bash
FEATURE="[feature-name]"
FILE="docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md"

echo "=== Section Verification ==="
grep -q "## Quick Reference" $FILE && echo "✅ Quick Reference" || echo "❌ MISSING: Quick Reference"
grep -q "## Worktree Reference" $FILE && echo "✅ Worktree Reference" || echo "❌ MISSING: Worktree Reference"
grep -q "### Dependencies" $FILE && echo "✅ Dependencies tables" || echo "❌ MISSING: Dependencies tables"
grep -q "### Wave Analysis" $FILE && echo "✅ Wave Analysis tables" || echo "❌ MISSING: Wave Analysis tables"
grep -q "### Visual Dependency Graph" $FILE && echo "✅ Visual Graphs" || echo "❌ MISSING: Visual Graphs"
grep -q "### Execution Strategy" $FILE && echo "✅ Execution Strategy" || echo "❌ MISSING: Execution Strategy"
grep -q "### Commands" $FILE && echo "✅ Commands sections" || echo "❌ MISSING: Commands sections"
grep -q "/create-task-spec" $FILE && echo "✅ /create-task-spec" || echo "❌ MISSING: /create-task-spec"
grep -q "/create-task-ticket" $FILE && echo "✅ /create-task-ticket" || echo "❌ MISSING: /create-task-ticket"
grep -q "/execute-task" $FILE && echo "✅ /execute-task" || echo "❌ MISSING: /execute-task"
grep -q "/complete-task" $FILE && echo "✅ /complete-task" || echo "❌ MISSING: /complete-task"
grep -q "### Summary" $FILE && echo "✅ Summary tables" || echo "❌ MISSING: Summary tables"
grep -q "## Overall Execution Summary" $FILE && echo "✅ Overall Summary" || echo "❌ MISSING: Overall Summary"
grep -q "### Critical Path" $FILE && echo "✅ Critical Path" || echo "❌ MISSING: Critical Path"
echo "=== Verification Complete ==="
```

### Why This Matters

**Lesson Learned (Feb 2026):** The `mvp-production-readiness` batch plan was created without:
- Quick Reference table
- Worktree Reference table  
- Per-batch Commands with `/create-task-spec`, `/execute-task`, etc.
- Per-batch Summary tables

This made it inconsistent with `virtual-mcp-server-mvp` and harder to execute.

---

## Worktree Cleanup Section (MUST Include)

Every BATCH_EXECUTION_PLAN.md must include a cleanup section at the end.

### Required Cleanup Template

```markdown
## Worktree Cleanup (End of Workstream)

> **When to run:** After ALL phases are complete and merged to `dev` branch.
> **Prerequisites:** All merge points must be ✅ REACHED.

### Pre-Cleanup Verification

Before removing worktrees, verify all work is merged:

\`\`\`bash
# 1. Navigate to main repo
cd /Users/imaxxs/repositories/deepsecure-mvp

# 2. Update dev branch
git checkout dev
git pull origin dev

# 3. Check if worktree branches are fully merged
git branch --merged dev | grep "[worktree-branch-prefix]"

# 4. If branches NOT shown above, merge them first:
git merge feature/[worktree-1] --no-ff -m "Merge [feature]: [service 1]"
git merge feature/[worktree-2] --no-ff -m "Merge [feature]: [service 2]"

# 5. Verify E2E demo passes on merged code
python demos/demo_sarah_journey_e2e.py
\`\`\`

### Remove Worktrees

\`\`\`bash
# Navigate to main repo
cd /Users/imaxxs/repositories/deepsecure-mvp

# List current worktrees
git worktree list

# Remove worktrees (safe removal - fails if uncommitted changes)
git worktree remove ../[worktree-1]
git worktree remove ../[worktree-2]

# Verify removal
git worktree list
\`\`\`

### Delete Feature Branches (Optional)

\`\`\`bash
# Delete local feature branches
git branch -d feature/[worktree-1]
git branch -d feature/[worktree-2]

# If pushed to remote, delete there too
git push origin --delete feature/[worktree-1]
git push origin --delete feature/[worktree-2]
\`\`\`

### Force Removal (Use with Caution)

\`\`\`bash
# ⚠️ WARNING: Discards ALL uncommitted changes!
git worktree remove --force ../[worktree-1]
git worktree remove --force ../[worktree-2]
\`\`\`

### Cleanup Summary Checklist

| Step | Command | Verified |
|------|---------|----------|
| 1. All phases complete | Check `STATUS.md` | ☐ |
| 2. All merge points reached | Check `MERGE_POINTS.md` | ☐ |
| 3. Branches merged to dev | `git branch --merged dev` | ☐ |
| 4. E2E demo passes | `python demos/...` | ☐ |
| 5. Worktrees removed | `git worktree remove ...` | ☐ |
| 6. Feature branches deleted | `git branch -d ...` | ☐ |
| 7. Worktree list clean | `git worktree list` | ☐ |
```

### Verification: Cleanup Section Exists

Add to the verification command:

```bash
grep -q "## Worktree Cleanup" $FILE && echo "✅ Worktree Cleanup" || echo "❌ MISSING: Worktree Cleanup"
grep -q "### Remove Worktrees" $FILE && echo "✅ Remove Worktrees" || echo "❌ MISSING: Remove Worktrees"
grep -q "git worktree remove" $FILE && echo "✅ Cleanup commands" || echo "❌ MISSING: Cleanup commands"
```

---

## Validation Sections (Per-Batch REQUIRED)

Every batch must include Pre-Merge and Post-Merge validation sections.

### Validation Template

```markdown
### Validation

#### Pre-Merge Validation (Unit Tests Only)

Run these BEFORE merging to dev branch:

\`\`\`bash
# Control worktree: Run unit tests
cd /path/to/control-worktree/[service-dir]
pytest tests/[relevant-tests]/ -v

# Gateway worktree: Run unit tests
cd /path/to/gateway-worktree/[service-dir]
pytest tests/[relevant-tests]/ -v
\`\`\`

#### Post-Merge Validation (Integration Tests)

Run these AFTER merging and rebuilding containers:

\`\`\`bash
# ═══════════════════════════════════════════════════════════════
# [BATCH-ID] VALIDATION - [Description] (POST-MERGE)
# ═══════════════════════════════════════════════════════════════
# All commands should return 200 (or expected status codes)
# ═══════════════════════════════════════════════════════════════

# 0. Rebuild containers with new code
cd /path/to/main-repo
docker compose build [services]
docker compose up -d [dependencies] [services]
sleep 15

# 1. Verify services are healthy
curl -sf http://localhost:[port]/health && echo "✅ [Service] healthy"

# 2. Verify new endpoints exist
curl -s http://localhost:[port]/openapi.json | jq '.paths | keys | map(select(contains("[keyword]")))' 

# ─────────────────────────────────────────────────────────────────
# SETUP: Get required tokens
# ─────────────────────────────────────────────────────────────────

# 3. Get user token via login (note: returns "token" field)
USER_TOKEN=$(curl -s -X POST http://localhost:[port]/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"email":"[user]","password":"[password]"}' | jq -r '.token')
echo "User token: \${USER_TOKEN:0:20}..."

# ─────────────────────────────────────────────────────────────────
# TEST [N]: [Description]
# ─────────────────────────────────────────────────────────────────

echo "Test [N]: [Description]..."
curl -s -w "\\nHTTP Status: %{http_code}\\n" \\
  -X [METHOD] "http://localhost:[port]/api/v1/[endpoint]" \\
  -H "Authorization: Bearer $[TOKEN_VAR]" \\
  -H "Content-Type: application/json" \\
  -d '[payload]'
# Expected: [response description]

# ─────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────

docker compose down

echo "✅ [BATCH-ID] Post-Merge Validation Complete"
\`\`\`
```

### Token Types Reference

Different endpoints require different token types. Use this reference:

| Token Type | How to Obtain | Used For |
|------------|---------------|----------|
| **User Token** | `POST /api/v1/auth/login` → `.token` | User-facing endpoints |
| **Agent JWT** | Challenge-response flow (Ed25519) | Agent-to-Control communication |
| **Internal Token** | From docker-compose.yml env var | Gateway-to-Control internal APIs |
| **Admin Token** | Admin login or env var | Administrative endpoints |

### Agent JWT Creation Template

For endpoints requiring Agent JWT:

```bash
# Generate Ed25519 keypair
python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey.generate()
public_key = private_key.verify_key
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env

# Register agent
curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"test-agent-001\",
    \"name\": \"Test Agent\",
    \"public_key\": \"$PUBLIC_KEY_B64\"
  }"

# Create delegation
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent-001", "permissions": ["service:scope:action"]}'

# Request and sign challenge
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent-001"}' | jq -r '.challenge')

SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
signed = private_key.sign('$CHALLENGE'.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

# Get Agent JWT
AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"test-agent-001\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')
```

---

## MERGE_POINTS.md Creation

Alongside BATCH_EXECUTION_PLAN.md, create MERGE_POINTS.md using the template guide.

### When to Create

- **After** BATCH_EXECUTION_PLAN.md is created
- **Before** starting batch execution

### How to Create

1. **Read the template guide:**
   ```
   docs/workstreams/MERGE_POINT_GUIDE.md
   ```

2. **Create the file:**
   ```
   docs/workstreams/[feature-name]/MERGE_POINTS.md
   ```

3. **Required sections** (see MERGE_POINT_GUIDE.md for full template):
   - Code Dependencies vs Runtime Dependencies
   - Development Mode vs Integration Mode
   - Runtime Dependencies by Merge Point
   - Per-MP: Merge Actions, Container Deployment, Container Test Scenarios, Cleanup, Success Criteria, Post-Merge Status Update
   - Testing Strategy by Phase
   - Troubleshooting
   - Container Deployment Schedule
   - Quick Reference Commands
   - Merge Point Status table with Progress Summary
   - History

### Post-Creation Verification

```bash
FEATURE="[feature-name]"
FILE="docs/workstreams/${FEATURE}/MERGE_POINTS.md"

echo "=== MERGE_POINTS.md Verification ==="
grep -q "## Code Dependencies vs Runtime Dependencies" $FILE && echo "✅ Dependencies section" || echo "❌ MISSING"
grep -q "### Merge Actions" $FILE && echo "✅ Merge Actions" || echo "❌ MISSING"
grep -q "### Container Test Scenarios" $FILE && echo "✅ Container Tests" || echo "❌ MISSING"
grep -q "### Post-Merge Status Update" $FILE && echo "✅ Status Update" || echo "❌ MISSING"
grep -q "## Quick Reference Commands" $FILE && echo "✅ Quick Reference" || echo "❌ MISSING"
grep -q "## Merge Point Status" $FILE && echo "✅ Status Table" || echo "❌ MISSING"
echo "=== Verification Complete ==="
```

---

## Related Commands

| Command | Purpose |
|---------|---------|
| `/breakdown-design` | Creates the breakdown document (input) |
| `/create-workstream` | Creates WORKSTREAM.md |
| `/create-task-spec` | Creates specs for a batch (run before tickets) |
| `/create-task-ticket` | Creates individual task tickets |
| `/execute-task` | Executes a task |
| `/complete-task` | Marks task complete (auto after execute) |
| `/sync-worktree-status` | Syncs status across worktrees |
| `/verify-batch-completion` | Verifies batch completion status |

## Related Templates

| Template | Purpose |
|----------|---------|
| `docs/workstreams/MERGE_POINT_GUIDE.md` | Template for MERGE_POINTS.md creation |
| `docs/workstreams/TASK_SPEC_TEMPLATE.md` | Template for task specifications |
| `docs/workstreams/TASK_TICKET_TEMPLATE.md` | Template for task tickets |
