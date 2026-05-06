# Create Batch Execution Plan

Generate a comprehensive batch execution plan with wave analysis, dependency graphs, validation commands, and copy-paste execution scripts for a design.

> **Note:** This command is automatically called by `/breakdown-design` after creating the workstream structure.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /create-task-spec → /create-task-ticket
                                               ↑
                                          (YOU ARE HERE)

Downstream consumers of BATCH_EXECUTION_PLAN.md:
  /execute-task, /complete-task, /verify-batch-completion, /sync-worktree-status
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

## Directory Structure Reference (CANONICAL)

**IMPORTANT:** Use these EXACT paths when generating validation commands. Do NOT use `tests/unit/`.

### Test Paths (NO `unit/` subdirectory!)

| Service | Test Type | CORRECT Path | WRONG Path |
|---------|-----------|-----------------|---------------|
| Control | Schemas | `tests/schemas/` | `tests/unit/schemas/` |
| Control | Services | `tests/services/` | `tests/unit/services/` |
| Control | Models | `tests/models/` | `tests/unit/models/` |
| Control | API | `tests/api/v1/` | `tests/unit/api/` |
| Gateway | Backends | `tests/backends/` | `tests/unit/backends/` |
| Gateway | Middleware | `tests/middleware/` | `tests/unit/middleware/` |
| Gateway | Security | `tests/security/` | `tests/unit/security/` |
| Gateway | MCP | `tests/mcp/` | `tests/unit/mcp/` |
| Frontend | Unit/Integration | `frontend/src/**/__tests__/` | `tests/` at root |
| Frontend | E2E | `frontend/e2e/` | `tests/e2e/` at root |

### Absolute Path Templates

```bash
MAIN_REPO="/Users/imaxxs/repositories/deepsecure-mvp"
CONTROL="${MAIN_REPO}/deeptrail-control"
GATEWAY="${MAIN_REPO}/deeptrail-gateway"
FRONTEND="${MAIN_REPO}/frontend"

# Worktrees (adjust per feature — use feature-specific names from BREAKDOWN.md)
# Example: WORKTREE_CONTROL="/Users/imaxxs/repositories/idp-sso-control"
```

### Validation Command Templates

```bash
# Control Plane validation
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
pytest tests/schemas/ -v
pytest tests/services/ -v

# Gateway validation
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-gateway
pytest tests/backends/ -v
pytest tests/middleware/ -v

# Frontend validation
cd /Users/imaxxs/repositories/deepsecure-mvp/frontend
npm test
npx playwright test

# E2E validation
cd /Users/imaxxs/repositories/deepsecure-mvp
python demos/demo_sarah_journey_e2e.py
pytest tests/e2e/ -v
```

---

## Instructions

### 1. Read the Breakdown Document

Read the breakdown document at:

```
docs/workstreams/[feature-name]/BREAKDOWN.md
```

Extract:
- All workstreams and their tasks
- Task dependencies (the "Dependencies" column)
- Task sizes (S, M, L)
- Batch assignments (from Batch Execution Model)
- Parallelization decision (single worktree vs multi-worktree)
- Merge points and critical path
- Phase distribution (if multi-phase feature)

### 2. Read the Workstream File

Read for additional context:

```
docs/workstreams/[feature-name]/WORKSTREAM.md
```

Extract:
- Current batch status
- Worktree paths and branches
- Any completed tasks (to mark dependencies as completed)
- Key decisions (e.g., single-branch vs worktrees)

### 3. Build Dependency Graph

For each batch, analyze internal dependencies:

1. **List all tasks in the batch**
2. **For each task, check if any dependencies are ALSO in this batch**
   - If dependency is in a previous batch → mark as completed (satisfied)
   - If dependency is in THIS batch → creates a wave dependency
3. **Group tasks into waves:**
   - Wave 1: All tasks whose dependencies are ALL satisfied (from prior batches)
   - Wave 2: Tasks that depend on Wave 1 tasks
   - Wave 3: Tasks that depend on Wave 2 tasks
   - Continue until all tasks assigned

### 4. Determine Worktree / Branch Assignment

Read the BREAKDOWN.md's "Parallelization Decision" section to determine the execution model:

**Single-Branch Model** (e.g., frontend-architecture):
- All tasks run in one branch on the main repo
- Wave Analysis table uses a single column (e.g., "Main Repo" or "Frontend")
- Visual Dependency Graphs show a single track
- No `/sync-worktree-status` commands needed
- Cleanup section is "Branch Cleanup" not "Worktree Cleanup"

**Multi-Worktree Model** (e.g., idp-enhanced-sso, virtual-mcp-server-mvp):
- Tasks split across worktrees by service (control, gateway)
- Map each task based on file paths in the breakdown:
  - Files in `deeptrail-control/` → control worktree
  - Files in `deeptrail-gateway/` → gateway worktree
  - Files in `frontend/` or root → main repo
- Wave Analysis table has columns per worktree
- Include `/sync-worktree-status` after each batch

### 5. Generate the Execution Plan

Create `docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md` with ALL required sections below.

---

## Output Template

The quality bar is set by these proven gold-standard batch execution plans:
- `docs/workstreams/idp-selector/BATCH_EXECUTION_PLAN.md` — 680 lines, single-branch, Quick Start
- `docs/workstreams/idp-enhanced-sso/BATCH_EXECUTION_PLAN.md` — 942 lines, inline MP sections, Worktree Setup
- `docs/workstreams/virtual-mcp-server-mvp/BATCH_EXECUTION_PLAN.md` — 1048 lines, Status+Complete columns, 4 MPs
- `docs/workstreams/mvp-production-readiness/BATCH_EXECUTION_PLAN.md` — 2567 lines, Phase-organized, Optimal Execution, Troubleshooting

**REQUIRED SECTIONS (all must be present):**

### Section 0: Header with Cross-References

    # Batch Execution Plan: [Feature Name]

    > **Generated from:** [BREAKDOWN.md](./BREAKDOWN.md)
    > **Design Doc:** [link to design doc]
    > **Workstream:** [WORKSTREAM.md](./WORKSTREAM.md)
    > **Status:** [STATUS.md](./STATUS.md)
    > **Last Updated:** [date]

### Section 1: Quick Reference Table

Must include **Complete** and **Status** columns for execution tracking.
Pattern from all 4 gold-standard docs.

    ## Quick Reference

    | Batch | Total Tasks | Complete | Waves | Status | Worktrees |
    |-------|-------------|----------|-------|--------|-----------|
    | 1 | [N] | 0 | [N] | ⏳ Pending | [list] |
    | 2 | [N] | 0 | [N] | ⏳ Pending | [list] |

    **Total Tasks:** [N] | **Completed:** 0 | **Remaining:** [N]

### Section 2: Worktree / Branch Reference

For multi-worktree features, include path, branch, workstreams.
For single-branch features, show the single branch with setup commands.

    ## Worktree Reference

    | Worktree | Path | Branch | Workstreams |
    |----------|------|--------|-------------|
    | [name] | [path] | [branch] | [WS list] |

    ```bash
    # Setup commands (concrete, not placeholders)
    ```

### Section 3: Worktree / Branch Setup

Full lifecycle commands: cleanup old → create fresh → verify.
Pattern from idp-enhanced-sso (3-step).
For single-branch features, show branch creation.

    ## Worktree Setup (run once before Batch 1)

    ### Step 1: Clean up old worktrees
    ```bash
    # concrete commands
    ```

    ### Step 2: Create fresh worktrees
    ```bash
    # concrete commands
    ```

### Section 4: Phase Distribution (for multi-phase features)

ASCII timeline showing batch-to-phase mapping.
Pattern from mvp-production-readiness.

    ## Phase Distribution

    ```
    Phase 1 (Foundation)    Phase 2 (Core)    Phase 3 (Demo)    ...
    ──────────────────     ──────────────     ──────────────
    B1 │ B2 │ B3          B4 │ B5            B6 │ B7
    ⏳   ⏳   ⏳           ⏳   ⏳             ⏳   ⏳
                [MP1]                [MP2]                [MP3]
    ```

    Skip this section for features with a single phase or <5 batches.

### Section 5: Per-Batch Sections (repeat for each batch)

Each batch MUST include ALL of these subsections:

**5a. Batch Header with Focus**

    ## Batch [N]: [Description] ([X] tasks)

    **Focus:** [One-line description of what this batch accomplishes]

**5b. Dependencies Table**

    ### Dependencies

    | Task | Description | Dependencies | Complexity | Worktree |
    |------|-------------|--------------|------------|----------|
    | [ID] | [desc] | [deps or None] | [S/M/L] | [worktree] |

**5c. Wave Analysis**

For multi-worktree: columns per worktree.
For single-branch: single column or columns by domain.

    ### Wave Analysis

    | Wave | Control Plane | Gateway |
    |------|---------------|---------|
    | **1** | [tasks] | [tasks] |

    OR (single-branch):

    | Wave | Tasks |
    |------|-------|
    | **1** | [tasks] |

**5d. Visual Dependency Graph (ASCII)**

    ### Visual Dependency Graph

    ```
    [ASCII diagram showing task flow, waves, and batch completion]
    ```

**5e. Execution Strategy**

    ### Execution Strategy

    [Text description of parallel vs sequential, which worktrees, bottlenecks]

**5f. Commands**

    ### Commands

    ```bash
    # concrete /create-task-spec, /create-task-ticket, /execute-task, /complete-task
    # organized by wave with WAIT markers between waves
    ```

**5g. Validation (Pre-Merge + Post-Merge)**

This is REQUIRED per batch. Pattern from all gold-standard docs.

    ### Validation

    #### Pre-Merge Validation (Unit Tests)

    ```bash
    # concrete pytest / npm test commands for this batch's tasks
    ```

    #### Post-Merge Validation (Integration Tests)

    Only for batches at merge points. Include curl commands with expected status codes.

    ```bash
    # docker compose build/up, curl tests, cleanup
    ```

**5h. Post-Batch Verification (MANDATORY)**

    ### Post-Batch Verification (MANDATORY)

    ```bash
    cd /Users/imaxxs/repositories/deepsecure-mvp
    /verify-batch-completion [batch-id] [feature-name]
    ```

    **Checklist:**
    - [ ] All batch tasks have completion reports
    - [ ] STATUS.md updated
    - [ ] If merge point, MERGE_POINTS.md updated

**5i. Summary Table**

    ### Summary

    | Metric | Value |
    |--------|-------|
    | **Parallelism** | [X]% ([description]) |
    | **Waves** | [count] |
    | **Bottleneck** | [task or None] |
    | **Merge Point** | [MP or None] |
    | **Unblocks** | [next batch tasks] |

### Section 6: Inline Merge Point Sections

Between the batch that triggers a merge point and the next batch, include a
standalone merge point section. Pattern from idp-enhanced-sso.

    ## ── MERGE POINT [N] ──

    ```
    ┌─────────────────────────────────────────────────────────────┐
    │                      MERGE POINT [N]                         │
    │                                                             │
    │  [branch/worktree 1] ──┐                                    │
    │                        ├──→ dev ──→ Batch [N+1]             │
    │  [branch/worktree 2] ──┘                                    │
    │                                                             │
    │  Prerequisites: Batches 1-[N] complete ([X]/[Y] tasks)      │
    │  Action: [Merge/Tag/Rebuild description]                    │
    └─────────────────────────────────────────────────────────────┘
    ```

    See [MERGE_POINTS.md](./MERGE_POINTS.md) for detailed merge actions.

    ### Quick Merge Commands
    ```bash
    # concrete push, PR, merge, rebuild commands
    ```

### Section 7: Overall Execution Summary

    ## Overall Execution Summary

    ### Batch Parallelism Overview

    | Batch | Tasks | Waves | Parallel % | Cross-Worktree? | Status |
    |-------|-------|-------|------------|-----------------|--------|
    | 1 | [N] | [N] | [N]% | [Yes/No] | ⏳ Pending |

    ### Merge Points Summary

    | Point | After Batch | Converging | Actions Required | Status |
    |-------|-------------|------------|------------------|--------|

    ### Total Commands Needed

    | Command Type | Count |
    |--------------|-------|
    | `/create-task-spec` | [N] |
    | `/create-task-ticket` | [N] |
    | `/execute-task` | [N] |
    | `/complete-task` | [N] |
    | `/sync-worktree-status` | [N] |
    | `/verify-batch-completion` | [N] |
    | Merge Point actions | [N] |
    | **Total** | [sum] |

    ### Critical Path

    ```
    [task] → [task] → ... → [task]
    │                            │
    └────── [X] sessions min ────┘
    ```

    ### Worktree Distribution

    | Worktree | Tasks | Count |
    |----------|-------|-------|
    | [name] | [task list] | [N] |

### Section 8: Optimal Execution Strategy

How to allocate developers/Claude instances. Pattern from mvp-production-readiness.

    ## Optimal Execution Strategy

    | Phase | Max Parallel Instances | Worktrees Needed |
    |-------|------------------------|------------------|
    | Phase 1 | [N] | [N] |

    **Recommended:**
    - [Phase/Batch range]: [description of developer allocation]

### Section 9: Quick Start Commands

Copy-paste-ready condensed script for the entire lifecycle.
Pattern from all 4 gold-standard docs.

    ## Quick Start Commands

    ```bash
    # ═══════════════════════════════════════════════════════════════
    # QUICK START: [Feature Name]
    # ═══════════════════════════════════════════════════════════════

    # Setup
    cd /Users/imaxxs/repositories/deepsecure-mvp
    [branch/worktree creation commands]

    # Batch 1
    /create-task-spec 1 [feature]
    /create-task-ticket WS-[ID] [feature]
    ...
    /execute-task WS-[ID] [feature] && /complete-task WS-[ID] [feature]
    /verify-batch-completion 1 [feature]

    # Batch 2
    ...

    # Merge
    [merge commands]

    # Cleanup
    [cleanup commands]
    ```

### Section 10: Worktree Cleanup / Branch Cleanup

For multi-worktree: full cleanup with pre-verification, remove, delete branches, troubleshooting.
For single-branch: branch deletion after merge.

    ## Worktree Cleanup (End of Workstream)

    > **When to run:** After ALL phases are complete and merged to `dev` branch.
    > **Prerequisites:** All merge points must be reached.

    ### Pre-Cleanup Verification

    ```bash
    cd /Users/imaxxs/repositories/deepsecure-mvp
    git checkout dev && git pull origin dev
    git branch --merged dev | grep "[feature-prefix]"
    ```

    ### Remove Worktrees

    ```bash
    git worktree remove ../[worktree-1]
    git worktree remove ../[worktree-2]
    git worktree list
    ```

    ### Delete Feature Branches

    ```bash
    git branch -d feature/[branch-1]
    git branch -d feature/[branch-2]
    ```

    ### Troubleshooting

    | Issue | Solution |
    |-------|----------|
    | "worktree is dirty" | Commit or stash changes before removal |
    | "branch still checked out" | Run from main repo, not from worktree |
    | "worktree not found" | Already removed, or wrong path |
    | "cannot delete branch" | Branch not fully merged; use `-D` (careful!) |

    ### Cleanup Summary Checklist

    | Step | Command | Verified |
    |------|---------|----------|
    | 1. All phases complete | Check STATUS.md | ☐ |
    | 2. All merge points reached | Check MERGE_POINTS.md | ☐ |
    | 3. Branches merged to dev | `git branch --merged dev` | ☐ |
    | 4. E2E passes | `[test command]` | ☐ |
    | 5. Worktrees/branches removed | `git worktree list` | ☐ |

---

## Wave Calculation Algorithm

```python
def calculate_waves(batch_tasks, completed_tasks):
    waves = {}
    assigned = set()
    wave_num = 1

    while len(assigned) < len(batch_tasks):
        current_wave = []

        for task_id, deps in batch_tasks.items():
            if task_id in assigned:
                continue

            if wave_num == 1:
                deps_satisfied = all(dep in completed_tasks for dep in deps)
            else:
                deps_satisfied = all(
                    dep in completed_tasks or dep in assigned
                    for dep in deps
                )

            if deps_satisfied:
                current_wave.append(task_id)

        if not current_wave:
            raise ValueError("Circular dependency detected in batch")

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
- Batch has 9 tasks across 4 waves
- Wave 1: 3 tasks → max parallel = 3
- Parallelism = 3/9 = 33%
```

Use the **maximum concurrent tasks** interpretation for the Parallelism column.

---

## Example Outputs

| Pattern | See |
|---------|-----|
| Single-branch, small feature | `docs/workstreams/idp-selector/BATCH_EXECUTION_PLAN.md` |
| Multi-worktree, medium feature | `docs/workstreams/idp-enhanced-sso/BATCH_EXECUTION_PLAN.md` |
| Multi-worktree, large feature | `docs/workstreams/virtual-mcp-server-mvp/BATCH_EXECUTION_PLAN.md` |
| Multi-phase, large feature | `docs/workstreams/mvp-production-readiness/BATCH_EXECUTION_PLAN.md` |

---

## Post-Creation Steps

After creating the execution plan:

1. **Link from WORKSTREAM.md** (should already have the link if created by `/create-workstream`)
2. **Link from STATUS.md** — add reference in the header
3. **Verify MERGE_POINTS.md exists** — should already be created by `/create-workstream`

---

## Output Verification Checklist (MANDATORY)

**Before declaring the batch execution plan complete, verify ALL sections exist.**

### Required Sections Checklist

| # | Section | Required? | Purpose |
|---|---------|-----------|---------|
| 0 | **Header with Cross-References** | YES | Links to BREAKDOWN, WORKSTREAM, STATUS, design doc |
| 1 | **Quick Reference** (Complete + Status columns) | YES | At-a-glance tracking with Total/Completed/Remaining counter |
| 2 | **Worktree / Branch Reference** | YES | Path, Branch, Workstreams mapping |
| 3 | **Worktree / Branch Setup** | YES | Lifecycle commands (cleanup old, create fresh, verify) |
| 4 | **Phase Distribution** | IF multi-phase | ASCII timeline |
| 5a | **Per-Batch: Header with Focus** | YES | One-line focus description |
| 5b | **Per-Batch: Dependencies** | YES | Table with Complexity and Worktree columns |
| 5c | **Per-Batch: Wave Analysis** | YES | Columns adapt to worktree model |
| 5d | **Per-Batch: Visual Dependency Graph** | YES | ASCII |
| 5e | **Per-Batch: Execution Strategy** | YES | Text description |
| 5f | **Per-Batch: Commands** | YES | `/create-task-spec`, `/create-task-ticket`, `/execute-task`, `/complete-task` |
| 5g | **Per-Batch: Validation** | YES | Pre-Merge (unit tests) + Post-Merge (integration, if MP) |
| 5h | **Per-Batch: Post-Batch Verification** | YES | `/verify-batch-completion` with checklist |
| 5i | **Per-Batch: Summary** | YES | Metric/Value table |
| 6 | **Inline Merge Point sections** | IF merge points exist | ASCII box + quick merge commands between batches |
| 7 | **Overall Execution Summary** | YES | Parallelism (with Status), Merge Points (with Status), Total Commands, Critical Path, Worktree Distribution |
| 8 | **Optimal Execution Strategy** | YES | Developer/instance allocation per phase |
| 9 | **Quick Start Commands** | YES | Condensed copy-paste lifecycle script |
| 10 | **Worktree / Branch Cleanup** | YES | Cleanup with Troubleshooting table |

### Verification Command

```bash
FEATURE="[feature-name]"
FILE="docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md"

echo "=== BATCH_EXECUTION_PLAN.md Section Verification ==="
grep -q "## Quick Reference" $FILE && echo "✅ Quick Reference" || echo "❌ MISSING"
grep -q "**Total Tasks:**" $FILE && echo "✅ Total/Completed counter" || echo "❌ MISSING"
grep -q "## Worktree Reference\|## Branch Reference" $FILE && echo "✅ Worktree/Branch Reference" || echo "❌ MISSING"
grep -q "## Worktree Setup\|## Branch Setup" $FILE && echo "✅ Setup section" || echo "❌ MISSING"
grep -q "### Dependencies" $FILE && echo "✅ Dependencies tables" || echo "❌ MISSING"
grep -q "### Wave Analysis" $FILE && echo "✅ Wave Analysis" || echo "❌ MISSING"
grep -q "### Visual Dependency Graph" $FILE && echo "✅ Visual Graphs" || echo "❌ MISSING"
grep -q "### Execution Strategy" $FILE && echo "✅ Execution Strategy" || echo "❌ MISSING"
grep -q "### Commands" $FILE && echo "✅ Commands" || echo "❌ MISSING"
grep -q "### Validation" $FILE && echo "✅ Validation" || echo "❌ MISSING"
grep -q "/create-task-spec" $FILE && echo "✅ /create-task-spec" || echo "❌ MISSING"
grep -q "/execute-task" $FILE && echo "✅ /execute-task" || echo "❌ MISSING"
grep -q "/verify-batch-completion" $FILE && echo "✅ /verify-batch-completion" || echo "❌ MISSING"
grep -q "### Summary" $FILE && echo "✅ Summary tables" || echo "❌ MISSING"
grep -q "MERGE POINT\|No merge points" $FILE && echo "✅ Merge Point sections" || echo "⚠️  Check if merge points needed"
grep -q "## Overall Execution Summary" $FILE && echo "✅ Overall Summary" || echo "❌ MISSING"
grep -q "## Optimal Execution Strategy" $FILE && echo "✅ Optimal Strategy" || echo "❌ MISSING"
grep -q "## Quick Start Commands" $FILE && echo "✅ Quick Start" || echo "❌ MISSING"
grep -q "## Worktree Cleanup\|## Branch Cleanup" $FILE && echo "✅ Cleanup" || echo "❌ MISSING"
grep -q "### Troubleshooting" $FILE && echo "✅ Troubleshooting" || echo "❌ MISSING"
grep -q "### Critical Path" $FILE && echo "✅ Critical Path" || echo "❌ MISSING"
echo "=== Verification Complete ==="
```

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "Validation is obvious, I'll skip it" | Every gold-standard doc has per-batch validation. Without it, issues found late. |
| "Quick Start is redundant with the per-batch Commands" | Quick Start is the condensed, copy-paste-ready version. Developers use it, not the detailed sections. |
| "This feature has no merge points" | Still need inline `No merge points in this feature` note. And still need Overall Summary. |
| "Single-branch doesn't need worktree setup" | It needs Branch Setup (creation, naming). Just simpler. |
| "Phase Distribution is overhead for a small feature" | Skip it for <5 batches. Required for 5+ batches. |

## Red Flags

- BATCH_EXECUTION_PLAN.md under 200 lines (likely missing sections)
- No `### Validation` subsections in any batch (will miss broken endpoints)
- No Quick Start Commands (developers will re-derive the execution sequence)
- Quick Reference missing Complete/Status columns (tracking will be ad-hoc)
- No inline Merge Point sections (developers won't know what to do at convergence)
- Escaped backticks (`\`\`\``) in the output (template rendering issue)
- Worktree commands using placeholder paths instead of concrete absolute paths

---

## Token Types Reference

Different endpoints require different token types in validation commands:

| Token Type | How to Obtain | Used For |
|------------|---------------|----------|
| **User Token** | `POST /api/v1/auth/login` → `.token` | User-facing endpoints |
| **Agent JWT** | Challenge-response flow (Ed25519) | Agent-to-Control communication |
| **Internal Token** | From docker-compose.yml env var | Gateway-to-Control internal APIs |
| **Admin Token** | Admin login or env var | Administrative endpoints |

### Agent JWT Creation Template

For validation commands needing Agent JWT:

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

# Challenge-response
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

AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"test-agent-001\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')
```

---

## MERGE_POINTS.md Note

MERGE_POINTS.md should already exist (created by `/create-workstream`). If not, create it using
`docs/workstreams/MERGE_POINT_GUIDE.md` as the template. Verify with:

```bash
FEATURE="[feature-name]"
[ -f "docs/workstreams/${FEATURE}/MERGE_POINTS.md" ] && echo "✅ Exists" || echo "❌ MISSING — create it"
```

---

## Related Commands

| Command | Purpose |
|---------|---------|
| `/breakdown-design` | Creates the breakdown document (input) |
| `/create-workstream` | Creates WORKSTREAM.md + MERGE_POINTS.md + STATUS.md |
| `/create-task-spec` | Creates specs for a batch (run before tickets) |
| `/create-task-ticket` | Creates individual task tickets |
| `/execute-task` | Executes a task |
| `/complete-task` | Marks task complete |
| `/sync-worktree-status` | Syncs status across worktrees |
| `/verify-batch-completion` | Verifies batch completion status |

## Related Templates

| Template | Purpose |
|----------|---------|
| `docs/workstreams/MERGE_POINT_GUIDE.md` | Template for MERGE_POINTS.md |
| `docs/workstreams/TASK_SPEC_TEMPLATE.md` | Template for task specifications |
| `docs/workstreams/TASK_TICKET_TEMPLATE.md` | Template for task tickets |
