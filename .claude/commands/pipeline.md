# Pipeline: End-to-End Development Automation

Orchestrate the full development lifecycle from idea to production deployment. This is the top-level command that chains all other commands into a coherent, checkpoint-gated pipeline.

```
DEFINE → PLAN → EXECUTE → REVIEW → SHIP
```

Each phase invokes the appropriate sub-commands, pauses at human checkpoints, and maintains a persistent state file so the pipeline can be resumed after interruptions.

## Workflow Position

```
(This IS the workflow — it orchestrates everything else)

DEFINE ──────── PLAN ──────────── EXECUTE ────────── REVIEW ────── SHIP
/spec           /breakdown-       /execute-task      /review       /ship
/create-         design           /complete-task     /security-
 design-doc     (runs /explore-   /run-checks         audit
                 codebase         /setup-worktrees   /commit-
                 internally)      /sync-worktree-     push-pr
                /create-           status
                 workstream       /verify-batch-
                /create-           completion
                 batch-
                 execution-plan
                /create-task-spec
                /create-task-ticket
```

## When to Use

- Starting a new feature from scratch (idea, plan file, or design doc)
- Resuming a partially completed feature pipeline
- Running a specific phase of the pipeline in isolation
- When you want automated orchestration with human checkpoints

**When NOT to use:**
- Single-task fixes or bug fixes (use `/execute-task` directly)
- Exploratory prototyping with no delivery intent
- Hotfixes that need emergency deployment (bypass pipeline, deploy directly)
- When only one phase is needed (invoke the specific command directly)

---

## Pipeline State

The pipeline maintains state in `docs/workstreams/[feature]/PIPELINE_STATE.md`:

```markdown
## Pipeline State: [feature-name]

| Field | Value |
|-------|-------|
| **Feature** | [feature-name] |
| **Started** | [timestamp] |
| **Current Phase** | [DEFINE/PLAN/EXECUTE/REVIEW/SHIP] |
| **Design Doc** | [path to design doc] |
| **Workstream Dir** | [path to workstream] |

### Phase History

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| DEFINE | ✅ Complete | [ts] | [ts] | Spec + design doc created |
| PLAN | 🔄 In Progress | [ts] | — | Codebase explored, 3 workstreams, 12 tasks |
| EXECUTE | ⏳ Pending | — | — | |
| REVIEW | ⏳ Pending | — | — | |
| SHIP | ⏳ Pending | — | — | |

### Current Batch
| Batch | Tasks | Status |
|-------|-------|--------|
| Batch 1 | WS-A1, WS-B1 | ✅ Complete |
| Batch 2 | WS-A2, WS-B2 | 🔄 In Progress |
```

---

## Instructions

### Invocation Modes

**Mode 1: Full Pipeline** (start to finish with checkpoints)
```
/pipeline @design-doc.md
/pipeline @plan-file.plan.md
/pipeline "feature description in plain text"
```

**Mode 2: Resume** (pick up where you left off)
```
/pipeline --resume [feature-name]
```

**Mode 3: Single Phase** (run one phase only)
```
/pipeline @design-doc.md --phase=define
/pipeline @design-doc.md --phase=explore
/pipeline @design-doc.md --phase=plan
/pipeline @design-doc.md --phase=execute
/pipeline @design-doc.md --phase=execute --batch=2
/pipeline @design-doc.md --phase=review
/pipeline @design-doc.md --phase=ship
```

**Mode 4: Single Task** (within an existing pipeline)
```
/pipeline --task=WS-A1 [feature-name]
```

---

## PHASE 1: DEFINE

**Goal:** Produce a structured spec and formal design document.

**Sub-commands invoked:** `/spec`, `/create-design-doc`

### Step 1.1: Determine Starting Point

| Input | Action |
|-------|--------|
| Plain text idea | Run `/spec` to create structured requirements |
| Plan file (`.plan.md`) | Run `/create-design-doc` to formalize |
| Design doc (already exists) | Skip to PLAN phase |
| No input | Ask user what they want to build |

### Step 1.2: Create Spec (if starting from idea)

Invoke `/spec` workflow:
1. CLARIFY — Ask user the 5 essential questions
2. SPECIFY — Generate structured spec with goals, non-goals, constraints
3. VALIDATE — Cross-check for completeness
4. OUTPUT — Write spec to `docs/specs/[feature-name].md`

### Step 1.3: Create Design Doc (mandatory after spec)

Invoke `/create-design-doc` workflow:
1. Read spec (or plan file)
2. Generate 15-section design document (500–800+ lines)
3. Apply DeepSecure conventions
4. Flag sections needing human input
5. Write to `docs/design/[feature-name].md`

### Step 1.4: Extract Feature Name
```
Derive feature-name from design doc title or ask user.
This becomes the canonical identifier for all subsequent operations.
```

**CHECKPOINT 1**: Present spec/design doc summary to user
```
Show:
- Feature name
- Goals (3-5 bullet points)
- Key technical decisions
- Estimated scope

Ask: "Approve this definition? (yes / modify / cancel)"
```

**Update pipeline state → DEFINE ✅**

---

## PHASE 2: PLAN

**Goal:** Explore the codebase, break the design into executable workstreams, tasks, and batches.

**Sub-commands invoked:** `/breakdown-design` (internally runs `/explore-codebase`), `/create-workstream`, `/create-batch-execution-plan`, `/create-task-ticket`, `/create-task-spec`

### Step 2.1: Breakdown Design (includes codebase exploration)

Invoke `/breakdown-design @design-doc.md`:
1. Run `/explore-codebase` internally — inventory existing implementations, cross-reference against design doc claims
2. Classify tasks by codebase state (Create / Modify / Verify / Skip)
3. Identify external dependencies
4. Map data flow and shared state
5. Group into parallel workstreams
6. Order tasks by dependency within each workstream
7. Calculate critical path

### Step 2.2: Create Workstream Structure

Invoke `/create-workstream [feature-name]`:
1. Create `docs/workstreams/[feature-name]/` directory
2. Create `WORKSTREAM.md` with task table
3. Create `STATUS.md` tracking file
4. Create `tasks/` and `reports/` directories

### Step 2.3: Generate Batch Execution Plan

Invoke `/create-batch-execution-plan [feature-name]`:
1. Organize tasks into dependency-ordered batches
2. Identify merge points between workstreams
3. Map parallelizable vs sequential batches
4. Output `BATCH_EXECUTION_PLAN.md`

### Step 2.4: Generate Task Tickets

For each task identified, invoke `/create-task-ticket`:
1. Create task ticket with full metadata
2. Include acceptance criteria and files to modify
3. Link dependencies
4. Include test requirements

### Step 2.5: Setup Worktrees (if parallel execution planned)

If multiple workstreams can execute in parallel, invoke `/setup-worktrees`:
1. Map workstreams to services
2. Create git worktrees
3. Copy configuration to each worktree
4. Output execution commands

**CHECKPOINT 2**: Present plan to user
```
Show:
- Workstream count and task count
- Dependency graph (ASCII)
- Batch table with parallelization opportunities
- Critical path length
- Estimated total effort

Ask: "Approve this plan? (yes / modify / cancel)"
```

**Update pipeline state → PLAN ✅**

---

## PHASE 3: EXECUTE

**Goal:** Implement all tasks, batch by batch, with quality gates.

**Sub-commands invoked:** `/execute-task`, `/complete-task`, `/run-checks`, `/setup-worktrees`, `/sync-worktree-status`, `/verify-batch-completion`

### Step 3.1: Batch Loop

```
for batch in BATCH_EXECUTION_PLAN:
    
    # Identify runnable tasks
    tasks = get_tasks_in_batch(batch)
    parallel_tasks = [t for t in tasks if no_unmet_dependencies(t)]
    
    # Execute tasks (parallel or sequential)
    if using_worktrees:
        for task in parallel_tasks:
            spawn_subagent(task, worktree=get_worktree(task))
    else:
        for task in parallel_tasks:
            execute_sequentially(task)
    
    # Quality gate per task
    for task in completed_tasks:
        run_checks(task)  # /run-checks
        complete_task(task)  # /complete-task
    
    # Sync and verify (MANDATORY before next batch)
    if using_worktrees:
        sync_worktree_status(feature)  # /sync-worktree-status
    verify_batch_completion(batch, feature)  # /verify-batch-completion
    # DO NOT proceed if verification fails
    
    # CHECKPOINT: After each batch
    present_batch_results()
    ask("Proceed to next batch?")
    
    # Merge point handling (if applicable)
    if batch_triggers_merge_point:
        merge_branches()
        verify_merge()
        cleanup_worktrees()
```

### Step 3.2: Executing a Single Task

For each task, run `/execute-task [WS-ID] [feature-name]`:

1. Read task ticket from `docs/workstreams/[feature]/tasks/`
2. Update `STATUS.md` — task → In Progress
3. Verify dependencies are complete
4. Implement the task (create/modify files)
5. Run `ReadLints` on modified files
6. Run `/run-checks` (lint, type check, tests)
7. Verify acceptance criteria from task ticket
8. Run `/complete-task` — generate completion report

### Step 3.3: Worktree Coordination

When using worktrees for parallel execution:

```bash
# Each worktree gets its own branch
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')

# Subagent in worktree A
cd ../[feature]-ws-a
/execute-task WS-A1 [feature-name]

# Subagent in worktree B (simultaneously)
cd ../[feature]-ws-b
/execute-task WS-B1 [feature-name]

# After batch: sync status to main repo
cp STATUS.md $MAIN_REPO/docs/workstreams/[feature]/STATUS.md
```

### Step 3.4: Merge Points

When parallel tracks converge:

```bash
# 1. Verify all contributing tasks complete
/verify-batch-completion [batch-id] [feature-name]

# 2. Merge branches
git checkout dev
git merge feature/[feature]-ws-a feature/[feature]-ws-b

# 3. Resolve conflicts if any
# 4. Cleanup completed worktrees
git worktree remove ../[feature]-ws-a

# 5. Create new worktrees for next phase if needed
```

**CHECKPOINT 3**: After each batch
```
Show:
- Completed tasks and their status
- Test results summary (pass/fail/skip)
- Any failures requiring attention

Ask: "Proceed to next batch? (yes / review-failures / pause)"
```

### Step 3.5: Error Recovery

| Failure Type | Action | Resumption |
|-------------|--------|------------|
| Test failure | Attempt auto-fix → if can't fix, flag for review | `/pipeline --resume [feature] --task=[failed-task]` |
| Lint failure | Auto-fix with `ruff --fix`, `black`, `isort` | Automatic |
| Dependency not met | Mark blocked, skip to next task | Unblocks when dependency resolves |
| Task too complex | Split into sub-tasks, re-plan | Update task tickets, re-run batch |
| Git conflict | Present to user | Manual resolution, then resume |

**Update pipeline state → EXECUTE ✅** (when all batches complete)

---

## PHASE 4: REVIEW

**Goal:** Multi-axis code review and security audit before merge.

**Sub-commands invoked:** `/review`, `/security-audit`, `/commit-push-pr`

### Step 4.1: Code Review

Invoke `/review` on the complete changeset:
1. Correctness — Does it do what the spec says?
2. Readability — Can another engineer understand it?
3. Architecture — Does it follow DeepSecure patterns?
4. Security — Quick security check (detailed in 5.2)
5. Performance — No N+1 queries, no memory leaks?

### Step 4.2: Security Audit (if security-relevant changes)

Invoke `/security-audit` if the changeset touches:
- Authentication or authorization code
- API endpoints accepting user input
- JWT, token, or cryptographic operations
- Gateway middleware or request routing
- New external dependencies

### Step 4.3: Create PR

Invoke `/commit-push-pr`:
1. Stage changes with clear commit messages
2. Push to feature branch
3. Create PR with structured description
4. Link to design doc and workstream

**CHECKPOINT 4**: Present review summary
```
Show:
- Review findings (Critical / High / Medium / Low)
- Security audit verdict (if applicable)
- PR URL

Ask: "Merge and proceed to ship? (yes / address-findings / cancel)"
```

**Update pipeline state → REVIEW ✅**

---

## PHASE 5: SHIP

**Goal:** Deploy to production/staging with smoke tests and rollback plan.

**Sub-commands invoked:** `/ship`

### Step 5.1: Pre-flight

Run `/ship` Phase 1:
- Verify branch merged, tests pass, security audit passed

### Step 5.2: Changelog & Rollback Plan

Run `/ship` Phase 2-3:
- Generate changelog from commits
- Write rollback plan with trigger conditions

### Step 5.3: Deploy

Run `/ship` Phase 4:
- Execute deployment (docker compose or SDK release)

### Step 5.4: Smoke Test & Monitor

Run `/ship` Phase 5-6:
- Health checks, auth flow, API responsiveness
- 15-minute monitoring window

### Step 5.5: Learning Loop

After successful deployment:
1. Aggregate all completion reports from `reports/`
2. Calculate metrics (tasks planned vs completed, test pass rate)
3. Extract learnings and potential CLAUDE.md updates
4. Run `/update-claude-md` with proposed additions

**CHECKPOINT 5**: Present ship report and learnings
```
Show:
- Ship report (smoke test results, monitoring status)
- Proposed CLAUDE.md updates
- Feature completion metrics

Ask: "Approve CLAUDE.md updates? (yes / modify / skip)"
```

**Update pipeline state → SHIP ✅**

---

## Output Format

After each phase, output:

```markdown
## Pipeline: [feature-name] — Phase [N] Complete: [Phase Name]

### Status
| Phase | Status |
|-------|--------|
| DEFINE | ✅ |
| PLAN | ✅ |
| EXECUTE | 🔄 Batch 2/4 |
| REVIEW | ⏳ |
| SHIP | ⏳ |

### This Phase
- [x] [What was done]
- [x] [What was done]

### Created / Modified Files
- `docs/design/[feature].md`
- `docs/workstreams/[feature]/WORKSTREAM.md`
- ...

### Metrics
- Tasks: [X completed / Y total]
- Tests: [pass / fail / skip]
- Duration: [estimated vs actual]

### Next
→ Phase [N+1]: [Name] — [brief description of what's next]

---
Proceed? (yes / pause / modify)
```

---

## Subagent Coordination

For parallel batch execution, use the Task tool:

```
# Spawn parallel subagents for independent tasks
Task(
    subagent_type="best-of-n-runner",
    description="Execute WS-A1: [task description]",
    prompt="Read task ticket at docs/workstreams/[feature]/tasks/WS-A1.md.
            Execute the task following /execute-task workflow.
            Run /run-checks after implementation.
            Generate completion report.
            Return: task status, test results, files modified.",
    run_in_background=True
)

# Simultaneously:
Task(
    subagent_type="best-of-n-runner",
    description="Execute WS-B1: [task description]",
    prompt="Read task ticket at docs/workstreams/[feature]/tasks/WS-B1.md.
            ...",
    run_in_background=True
)

# Wait for all, then aggregate
```

For code review, use specialized agents:
```
Task(
    subagent_type="generalPurpose",
    description="Security audit for [feature]",
    prompt="You are a security auditor. [include .cursor/agents/security-auditor.md].
            Audit the following changes: [diff].
            Return structured findings per /security-audit output format."
)
```

---

## Error Handling

### Phase Failure
```
1. Record failure in PIPELINE_STATE.md with error details
2. Mark phase as ❌ Failed
3. Present failure to user with options:
   - Retry phase
   - Skip phase (with justification)
   - Abort pipeline
4. Resume: /pipeline --resume [feature-name]
```

### Task Failure Within Execution Phase
```
1. Mark task as blocked in STATUS.md
2. Identify dependent tasks → mark as blocked_by
3. Continue with non-blocked tasks in batch
4. Present failures at batch checkpoint
```

### Git Conflicts at Merge Points
```
1. Detect conflict during merge
2. Present conflicting files to user
3. Options: manual resolution / accept-theirs / accept-ours / abort
4. After resolution, re-run checks on merged code
```

### Pipeline Interruption
```
The pipeline can be interrupted at any point.
State is persisted in PIPELINE_STATE.md.
Resume with: /pipeline --resume [feature-name]
The pipeline reads state and picks up at the last incomplete phase.
```

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "I'll skip codebase exploration, I know this codebase" | Exploration in Feb 2026 found 60% of "missing" components already existed. `/breakdown-design` runs it automatically — don't bypass it. |
| "Let me just code it, planning takes too long" | Unplanned features take 3x longer due to rework, missing edge cases, and architecture mismatches. |
| "Security audit is overkill for this feature" | Every feature that touches auth, tokens, or user input needs a security audit. The cost of not auditing is a vulnerability in production. |
| "I'll write tests after shipping" | Tests written after shipping never get written. Pipeline enforces tests at execution time. |
| "Just merge it, the review is a formality" | Reviews catch bugs, security issues, and architectural problems that the author is blind to. |
| "We can skip the rollback plan, this is straightforward" | Straightforward deployments cause the biggest outages. Always have a rollback plan. |
| "I can hold the pipeline state in my head" | State files exist because conversations get interrupted, context windows overflow, and agents forget. Always persist state. |

## Red Flags

- Skipping codebase exploration (embedded in PLAN phase) to save time
- Jumping straight to EXECUTE from a plan file without formal spec or design doc
- Executing all tasks sequentially when the batch plan shows parallel opportunities
- No PIPELINE_STATE.md being maintained
- Merge points handled without verifying all contributing tasks completed
- Deploying without smoke tests
- No checkpoint pauses (running fully automated without human review)
- Pipeline state showing phases "complete" without corresponding artifacts
- Proceeding to SHIP phase without REVIEW phase completing

## Verification

Before declaring the pipeline complete:

- [ ] Each phase has corresponding artifacts (spec, design doc, workstream, reports)
- [ ] PIPELINE_STATE.md shows all 5 phases ✅
- [ ] All completion reports generated in `reports/`
- [ ] STATUS.md consistent with completion reports
- [ ] CLAUDE.md updated with learnings (if any)
- [ ] PR merged
- [ ] Deployment successful (if applicable)
- [ ] Smoke tests passing (if applicable)

---

## Reference

This command orchestrates all other pipeline commands:

| Phase | Commands Invoked |
|-------|-----------------|
| DEFINE | `/spec`, `/create-design-doc` |
| PLAN | `/breakdown-design` (internally runs `/explore-codebase`), `/create-workstream`, `/create-batch-execution-plan`, `/create-task-ticket`, `/create-task-spec` |
| EXECUTE | `/execute-task`, `/complete-task`, `/run-checks`, `/setup-worktrees`, `/sync-worktree-status`, `/verify-batch-completion` |
| REVIEW | `/review`, `/security-audit`, `/commit-push-pr` |
| SHIP | `/ship`, `/update-claude-md` |

See also:
- `docs/DEVELOPER_WORKFLOW.md` — Full workflow documentation
- `docs/PARALLEL_EXECUTION_GUIDE.md` — Worktree setup
- `docs/WORKFLOW_GUIDE.md` — Batch model and merge points
- `.cursor/agents/` — Subagent definitions for parallel/review work

## Real-World Example
- Design: `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md`
- Breakdown: `docs/deepsecure-virtual-mcp-server-mvp-breakdown.md`
