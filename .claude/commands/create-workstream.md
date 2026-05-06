# Create Workstream

Create a new workstream folder structure with a comprehensive overview document that serves as the central hub for all execution tracking.

> **Note:** This command is automatically called by `/breakdown-design` after generating the breakdown document.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /create-task-spec → /create-task-ticket
                         ↑
                    (YOU ARE HERE)

Downstream consumers of WORKSTREAM.md:
  /execute-task, /complete-task, /verify-batch-completion, /sync-worktree-status
```

## Instructions

1. **Get workstream information from the BREAKDOWN.md:**
   - Feature name (for folder: `docs/workstreams/[feature-name]/`)
   - All workstream IDs, names, services, task counts
   - Batch execution model (from breakdown)
   - Merge points and critical path (from breakdown)
   - Link to parent design document
   - Parallelization decision (from breakdown)

2. **Create the directory structure:**
   ```
   docs/workstreams/[feature-name]/
   ├── WORKSTREAM.md           ← Workstream overview (THIS IS THE MAIN OUTPUT)
   ├── STATUS.md               ← Execution progress tracking
   ├── MERGE_POINTS.md         ← Merge point definitions (REQUIRED)
   ├── specs/                  ← Task specification folder
   │   └── .gitkeep
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

3. **Create WORKSTREAM.md — THE MAIN OUTPUT**

   This is the central hub document for the entire feature. It MUST include ALL sections
   listed below. The quality bar is set by proven gold-standard workstream docs:
   
   - `docs/workstreams/idp-selector/WORKSTREAM.md` — 298 lines, Scope section, Verification Checkpoints, detailed History
   - `docs/workstreams/idp-enhanced-sso/WORKSTREAM.md` — 189 lines, Feature Summary, Worktree Lifecycle, Key Files by WS, Batch Overview
   - `docs/workstreams/virtual-mcp-server-mvp/WORKSTREAM.md` — 285 lines, Batch-organized Task Tickets, Completion Reports, Merge Points summary
   - `docs/workstreams/mvp-production-readiness/WORKSTREAM.md` — 197 lines, Executive Summary, Key Decisions, Critical Path, Phase-organized Specs

   **REQUIRED SECTIONS (all 20 — do not omit any):**

   ### Section 1: Header with Cross-References
   ```markdown
   # Workstream: [Feature Name]

   > **Design Doc**: [docs/design/[feature-name].md](../../design/[feature-name].md)
   > **Breakdown**: [BREAKDOWN.md](./BREAKDOWN.md)
   > **Codebase Analysis**: [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md)
   > **Execution Status**: [STATUS.md](./STATUS.md)
   > **Batch Execution Plan**: [BATCH_EXECUTION_PLAN.md](./BATCH_EXECUTION_PLAN.md)
   ```

   ### Section 2: Executive Summary
   2-4 bullet points explaining what this feature delivers and why it matters.
   Business-facing, not technical. Pattern from mvp-production-readiness.

   ### Section 3: Overview Metadata Table
   ```markdown
   | Field | Value |
   |-------|-------|
   | **Design Doc** | [link] |
   | **Breakdown Doc** | [link] |
   | **Status** | `planning` |
   | **Created** | [date] |
   | **Target Completion** | [estimate or -] |
   | **Total Workstreams** | [N] |
   | **Total Tasks** | [N] |
   | **Total Batches** | [N] |
   | **Merge Points** | [N] |
   ```

   ### Section 4: Feature Summary Table (for multi-WS features)
   One-glance view mapping features to workstreams. Pattern from idp-enhanced-sso.
   ```markdown
   | Feature | Workstream | Tasks | Service |
   |---------|-----------|-------|---------|
   | [Feature 1 name] | WS-A | [N] (A1–AN) | deeptrail-control |
   | [Feature 2 name] | WS-B | [N] (B1–BN) | deeptrail-gateway |
   ```

   ### Section 5: Workstreams Summary Table
   High-level workstream relationships. Pattern from virtual-mcp-server-mvp.
   ```markdown
   | WS ID | Name | Status | Parallel With | Depends On | Tasks |
   |-------|------|--------|---------------|------------|-------|
   | WS-A | [Name] | `planning` | WS-B | None | A1–A8 |
   ```

   ### Section 6: Workstream Dependencies (ASCII diagram + text)
   ASCII diagram showing workstream flow. Pattern from idp-enhanced-sso.
   ```markdown
   WS-A (Control) ──────────┐
   WS-B (Gateway) ──────────┤── MP1 ──→ WS-C (E2E)
   ```
   Plus text sections: "Can Run In Parallel", "Blocked By", "Blocks".

   ### Section 7: Parallelization Strategy
   Worktree assignment table + decision rationale + worktree lifecycle commands.
   Pattern from idp-enhanced-sso (with concrete commands, not placeholders).

   ### Section 8: Scope (In-Scope / Out-of-Scope)
   Explicit scope boundaries to prevent scope creep. Pattern from idp-selector.
   ```markdown
   ### In Scope
   - [Bullet list of what IS included]

   ### Out of Scope
   - [Bullet list of what is explicitly NOT included and why]
   ```

   ### Section 9: Key Decisions
   Architectural decisions with rationale. Pattern from mvp-production-readiness.
   ```markdown
   ### [Decision Name]
   **Decision:** [What was chosen]
   **Rationale:** [Why]
   ```

   ### Section 10: Batch Overview
   Batch table with tasks, focus, and status. Pattern from idp-enhanced-sso.
   ```markdown
   | Batch | Tasks | Focus | Status |
   |-------|-------|-------|--------|
   | 1 | A1, B1 | Foundation | ⏳ Pending |
   ```

   ### Section 11: Merge Points Summary
   Quick-reference merge point table (full details in MERGE_POINTS.md). Pattern from virtual-mcp-server-mvp.
   ```markdown
   | Point | Converging Tasks | Enables | Status |
   |-------|------------------|---------|--------|
   | MP1 | A8 + B3 | C1 | ⏳ Pending |
   ```

   ### Section 12: Critical Path
   ASCII showing the critical path. Pattern from mvp-production-readiness.
   ```markdown
   A1 → A2 → B1 → B6 → C2 → E2 → [MP1] → F1
   ```

   ### Section 13: All Tasks (per-workstream tables)
   Task tables per workstream with ID, Name, Status, Dependencies, Complexity, Batch.
   Pattern from virtual-mcp-server-mvp. Include a Task Dependency Graph (ASCII).

   ### Section 14: Task Tickets (organized by batch)
   Linked task tickets organized under batch headers. Pattern from virtual-mcp-server-mvp.
   ```markdown
   ### Batch 1 ⏳ Pending
   - [WS-A1: Task name](./tasks/WS-A1-task-name.md) - ⏳ `pending`

   ### Batch 2 ⏳ Pending
   - [WS-A2: Task name](./tasks/WS-A2-task-name.md) - ⏳ `pending`
   ```

   ### Section 15: Specifications Table
   Links to specs organized by batch. Pattern from idp-selector and mvp-production-readiness.
   ```markdown
   | Task ID | Spec | Ticket | Status | Report |
   |---------|------|--------|--------|--------|
   | WS-A1 | [specs/WS-A1-spec.md](./specs/WS-A1-spec.md) | [tasks/WS-A1-*.md](./tasks/WS-A1-*.md) | ⏳ | — |
   ```

   ### Section 16: Completion Reports
   Running list updated as tasks complete. Pattern from virtual-mcp-server-mvp.
   ```markdown
   ## Completion Reports
   _Filed after each task completes_
   ```

   ### Section 17: Key Files by Workstream
   Files grouped by workstream with create/modify annotations. Pattern from idp-enhanced-sso.

   ### Section 18: Validation Criteria (per phase/milestone)
   Specific commands to run at each merge point. Pattern from mvp-production-readiness.
   ```markdown
   ### MP1 Complete
   ```bash
   pytest tests/... -v
   ```

   ### MP2 Complete
   - [List of criteria]
   ```

   ### Section 19: Progress
   Progress bar, metrics table, milestone tracking, verification checkpoints.
   Pattern from idp-selector and template.

   ### Section 20: History
   Event log with dates. Pattern from all gold-standard docs.
   ```markdown
   | Date | Event |
   |------|-------|
   | [date] | Workstream created from breakdown |
   ```

   **Cross-references section (at bottom):**
   Links to all related docs (BREAKDOWN.md, STATUS.md, BATCH_EXECUTION_PLAN.md,
   MERGE_POINTS.md, CODEBASE_ANALYSIS.md, design doc, spec).

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

**IMPORTANT:** The template provides the skeleton structure. You MUST fill in ALL 20 sections
listed above. Do not just copy the template — populate every section with real data from
the BREAKDOWN.md. If a section is not applicable (e.g., single-workstream features don't need
"Feature Summary Table"), add a brief note explaining why it's omitted.

## Output Format

```markdown
## Workstream Created

**Location:** `docs/workstreams/[feature-name]/`

### Structure
```
[feature-name]/
├── WORKSTREAM.md      ✅ Created (with all 20 sections)
├── STATUS.md          ✅ Created
├── MERGE_POINTS.md    ✅ Created
├── specs/             ✅ Created
├── tasks/             ✅ Created
└── reports/           ✅ Created
```

### Workstream Details
- **Feature:** [Feature Name]
- **Workstreams:** [N] (WS-A through WS-[X])
- **Tasks:** [N] total
- **Design Doc:** [link]
- **Breakdown:** [link]
- **Status:** planning
- **Batches:** [N]
- **Merge Points:** [N]

### Sections Verified
| # | Section | Status |
|---|---------|--------|
| 1 | Header with Cross-References | ✅ |
| 2 | Executive Summary | ✅ |
| 3 | Overview Metadata Table | ✅ |
| 4 | Feature Summary Table | ✅ (or N/A if single-WS) |
| 5 | Workstreams Summary Table | ✅ |
| 6 | Workstream Dependencies | ✅ |
| 7 | Parallelization Strategy | ✅ |
| 8 | Scope (In/Out) | ✅ |
| 9 | Key Decisions | ✅ |
| 10 | Batch Overview | ✅ |
| 11 | Merge Points Summary | ✅ |
| 12 | Critical Path | ✅ |
| 13 | All Tasks (per-WS tables) | ✅ |
| 14 | Task Tickets (by batch) | ✅ |
| 15 | Specifications Table | ✅ |
| 16 | Completion Reports | ✅ |
| 17 | Key Files by Workstream | ✅ |
| 18 | Validation Criteria | ✅ |
| 19 | Progress | ✅ |
| 20 | History | ✅ |

### Next Steps
1. Create batch execution plan with `/create-batch-execution-plan`
2. Create task specifications: `/create-task-spec [batch] [feature]`
3. Create individual task tickets: `/create-task-ticket [WS-ID] [feature]`
4. Start execution: `/execute-task [WS-ID] [feature]`
```

---

## ⚠️ Verification Checklist (MANDATORY)

Before declaring workstream creation complete, verify ALL files exist:

| File | Required | Purpose |
|------|----------|---------|
| `WORKSTREAM.md` | ✅ YES | Workstream overview — all 20 sections |
| `STATUS.md` | ✅ YES | Progress tracking |
| `MERGE_POINTS.md` | ✅ YES | Merge point definitions |
| `specs/` | ✅ YES | Task specification folder |
| `tasks/` | ✅ YES | Task ticket folder |
| `reports/` | ✅ YES | Completion reports folder |

**Verification command:**
```bash
FEATURE="[feature-name]"
echo "=== Workstream File Verification ==="
[ -f "docs/workstreams/${FEATURE}/WORKSTREAM.md" ] && echo "✅ WORKSTREAM.md" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/STATUS.md" ] && echo "✅ STATUS.md" || echo "❌ MISSING"
[ -f "docs/workstreams/${FEATURE}/MERGE_POINTS.md" ] && echo "✅ MERGE_POINTS.md" || echo "❌ MISSING"
[ -d "docs/workstreams/${FEATURE}/specs" ] && echo "✅ specs/" || echo "❌ MISSING"
[ -d "docs/workstreams/${FEATURE}/tasks" ] && echo "✅ tasks/" || echo "❌ MISSING"
[ -d "docs/workstreams/${FEATURE}/reports" ] && echo "✅ reports/" || echo "❌ MISSING"
echo ""
echo "=== WORKSTREAM.md Section Verification ==="
FILE="docs/workstreams/${FEATURE}/WORKSTREAM.md"
grep -q "## Executive Summary" $FILE && echo "✅ Executive Summary" || echo "❌ MISSING"
grep -q "## Feature Summary" $FILE && echo "✅ Feature Summary" || echo "⚠️  Missing (OK if single-WS)"
grep -q "## Workstreams" $FILE && echo "✅ Workstreams Table" || echo "❌ MISSING"
grep -q "## Workstream Dependencies" $FILE && echo "✅ Dependencies" || echo "❌ MISSING"
grep -q "## Parallelization Strategy" $FILE && echo "✅ Parallelization" || echo "❌ MISSING"
grep -q "## Scope" $FILE && echo "✅ Scope" || echo "❌ MISSING"
grep -q "## Key Decisions" $FILE && echo "✅ Key Decisions" || echo "❌ MISSING"
grep -q "## Batch Overview" $FILE && echo "✅ Batch Overview" || echo "❌ MISSING"
grep -q "## Merge Points" $FILE && echo "✅ Merge Points" || echo "❌ MISSING"
grep -q "## Critical Path" $FILE && echo "✅ Critical Path" || echo "❌ MISSING"
grep -q "## All Tasks" $FILE && echo "✅ All Tasks" || echo "❌ MISSING"
grep -q "## Task Tickets" $FILE && echo "✅ Task Tickets" || echo "❌ MISSING"
grep -q "## Specifications" $FILE && echo "✅ Specifications" || echo "❌ MISSING"
grep -q "## Completion Reports" $FILE && echo "✅ Completion Reports" || echo "❌ MISSING"
grep -q "## Key Files" $FILE && echo "✅ Key Files" || echo "❌ MISSING"
grep -q "## Validation Criteria" $FILE && echo "✅ Validation Criteria" || echo "❌ MISSING"
grep -q "## Progress" $FILE && echo "✅ Progress" || echo "❌ MISSING"
grep -q "## History" $FILE && echo "✅ History" || echo "❌ MISSING"
echo "=== Complete ==="
```

**If any required section is missing, add it BEFORE declaring complete.**

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "The BREAKDOWN.md already has this info" | WORKSTREAM.md is the *execution* hub — it must be self-contained for day-to-day use without flipping between files |
| "This feature is small, I don't need all 20 sections" | Small features need the same sections — just shorter. Add N/A notes, don't omit sections. |
| "I'll add the Specs/Tickets/Reports sections later" | Create the sections now with placeholder text. Empty sections are better than missing sections. |
| "Scope section is obvious" | Explicit scope prevents scope creep. Every gold-standard doc has it. |
| "Key Decisions are in the design doc" | Decisions need to be surfaced in the execution doc. Developers shouldn't have to read the design doc to understand why choices were made. |

## Red Flags

- WORKSTREAM.md under 100 lines (likely missing sections)
- No Batch Overview table (batch tracking will be ad-hoc)
- No Scope section (scope creep risk)
- No Merge Points summary (developers won't know convergence points without opening MERGE_POINTS.md)
- No Specifications table (spec→ticket→report traceability lost)
- No Completion Reports section (audit trail gaps)
- Task tables not organized by workstream (cross-workstream dependencies obscured)
- No Critical Path (execution priority unclear)

## Reference

This command integrates with:
- `/breakdown-design` → Produces the BREAKDOWN.md that provides all data for WORKSTREAM.md
- `/create-batch-execution-plan` → Automatically called after this command
- `/create-task-spec` → Creates specs linked from the Specifications table
- `/create-task-ticket` → Creates tickets linked from the Task Tickets section
- `/execute-task` → Uses WORKSTREAM.md as the execution reference
- `/complete-task` → Updates Progress and Completion Reports sections
- `/verify-batch-completion` → Verifies batch status against WORKSTREAM.md
- `/sync-worktree-status` → Syncs worktree progress back to WORKSTREAM.md

See also:
- `CLAUDE.md` → "Status Verification Requirements (MANDATORY)"
- `docs/DEVELOPER_WORKFLOW.md` → Phase 1: Planning
- `docs/workstreams/MERGE_POINT_GUIDE.md` → MERGE_POINTS.md template
