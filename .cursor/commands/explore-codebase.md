# Explore Codebase: Inventory Existing Implementations Before Breakdown

Inventory existing implementations in the codebase BEFORE creating a task breakdown. Design documents describe **intent**, not **current state**. This command ensures you understand what actually exists before scoping work.

## Workflow Position

```
/spec → /create-design-doc → /breakdown-design (embeds codebase exploration) → ...
                                                       ↑
                                                  (CALLED BY /breakdown-design)

NOTE: This command is NOT a standalone pipeline step. It is automatically
invoked as Step 1 of /breakdown-design. You should NOT need to call it
separately unless doing ad-hoc codebase exploration outside the pipeline.
```

## When to Use

- **Automatically called** by `/breakdown-design` as its first step — you do NOT need to run this separately
- For **ad-hoc exploration** outside the standard pipeline (e.g., debugging, curiosity, pre-spec research)
- When design docs reference "missing" components and you want to verify before even writing a spec
- When coverage matrices or gap analyses seem potentially stale
- When starting work on an existing codebase you haven't explored recently

**When NOT to use:**
- Before `/breakdown-design` — it's already embedded there, running separately is redundant
- Single-file bug fixes where the affected code is already known
- Documentation-only changes
- Changes to files you already have open and recently read
- After exploration was already completed and results are in `CODEBASE_ANALYSIS.md`

---

## Why This Matters

**Feb 2026 Lesson:** A breakdown was created for "MVP Production Readiness" based on design documents. The design docs said certain endpoints were "missing." After exploration, ~60% of "missing" components **already existed**. The breakdown was over-scoped by 60%.

**Rule:** The codebase is the **source of truth**. Design documents are proposals. Coverage matrices are snapshots. Always explore before scoping.

---

## Instructions

### Phase 1: IDENTIFY — Read the Design Document

Read the design document to understand what features are expected:

```
Read: docs/design/[feature-name].md
```

Extract a list of all components the design says should exist:
- API endpoints
- Services / business logic modules
- Database models
- Middleware / security modules
- Tests

### Phase 2: EXPLORE — Inventory the Actual Codebase

**Use the Task tool with `subagent_type="explore"`** to parallelize exploration across services.

For `deeptrail-control/`:
```
Use Task tool with subagent_type="explore" and prompt:
"Thoroughly inventory all existing implementations in deeptrail-control/:
- List ALL API endpoints in app/api/v1/endpoints/ (method, path, handler function)
- List ALL services in app/services/ (class name, key methods)
- List ALL models in app/models/ (model name, key fields)
- List ALL schemas in app/schemas/ (schema name, key fields)
- List ALL middleware
- Note any MVP-mode vs production-mode code paths
- Check for existing tests in tests/"
```

For `deeptrail-gateway/`:
```
Use Task tool with subagent_type="explore" and prompt:
"Thoroughly inventory all existing implementations in deeptrail-gateway/:
- List ALL MCP handlers in app/mcp/ (handler name, method type)
- List ALL middleware in app/middleware/ (name, purpose)
- List ALL backend clients in app/backends/ (client name, external service)
- List ALL security modules in app/security/
- Note any MVP-mode vs production-mode code paths
- Check for existing tests in tests/"
```

For `deepsecure/` (SDK):
```
Use Task tool with subagent_type="explore" and prompt:
"Inventory existing SDK implementations in deepsecure/:
- List ALL public client methods in client.py
- List ALL core modules in _core/ (module name, purpose)
- List ALL CLI commands in commands/
- List ALL integrations in integrations/
- Check for existing tests in tests/"
```

**Launch these exploration agents in parallel** — they scan independent directories.

### Phase 3: CROSS-REFERENCE — Compare Design vs. Reality

For each "missing" or "to be implemented" item in the design doc, search the codebase:

```bash
# Check if endpoint exists
grep -r "@router\.\(get\|post\|put\|delete\)" deeptrail-control/app/api/ | grep "[endpoint_name]"

# Check if service exists
grep -r "class.*Service" deeptrail-control/app/services/

# Check if model exists
grep -r "class.*Base\)" deeptrail-control/app/models/

# Check if handler exists
grep -r "def.*handler\|async def.*handle" deeptrail-gateway/app/mcp/
```

**Classify each item by actual codebase state:**

| Codebase State | Task Type | Description |
|----------------|-----------|-------------|
| Component doesn't exist | `Create` | Must build from scratch |
| Component exists, format/behavior wrong | `Modify` | Exists but needs changes |
| Component exists, needs validation only | `Verify` | Just confirm it matches spec |
| Component exists, fully correct | `Skip` | Remove from task list |

### Phase 4: DOCUMENT — Create Analysis File

**Use the Write tool** to save results:

```
Write to: docs/workstreams/[feature-name]/CODEBASE_ANALYSIS.md
```

**Template:**

```markdown
# Codebase Analysis for: [Feature Name]

## Analysis Date: [date]
## Design Doc: docs/design/[feature-name].md

## Services Explored
- [x] deeptrail-control/
- [x] deeptrail-gateway/
- [x] deepsecure/ (SDK)

## Existing Implementations

### deeptrail-control

| Component | Type | Location | Status |
|-----------|------|----------|--------|
| User login | Endpoint | app/api/v1/endpoints/auth.py | EXISTS - MVP mode |
| UserService | Service | app/services/user_service.py | EXISTS |

### deeptrail-gateway

| Component | Type | Location | Status |
|-----------|------|----------|--------|
| tools/call handler | MCP Handler | app/mcp/handlers.py | EXISTS |
| credential injection | Middleware | app/middleware/credential_injection.py | EXISTS - mock tokens |

### deepsecure (SDK)

| Component | Type | Location | Status |
|-----------|------|----------|--------|
| Client.authenticate | Method | client.py | EXISTS |

## Design Doc vs Actual Status

| Design Doc Says | Actual Status | Task Type | Notes |
|-----------------|---------------|-----------|-------|
| "Create login endpoint" | EXISTS at /api/v1/auth/login | Verify | Check response format |
| "Create delegation service" | EXISTS with macaroons | Modify | Update response format |
| "Create OAuth flow" | NOT IMPLEMENTED | Create | Full implementation needed |

## Summary

| Category | Count |
|----------|-------|
| Components that EXIST | [X] |
| True implementation gaps (Create) | [Y] |
| Verification-only tasks (Verify) | [Z] |
| Modification tasks (Modify) | [W] |

**Scope adjustment:** Actual scope is ~[N]% smaller than design doc suggests.
```

### Phase 5: REPORT — Summarize for User

Present the findings before proceeding to `/breakdown-design`:

```markdown
## Exploration Complete

| Category | Count |
|----------|-------|
| Components that EXIST | [X] |
| True implementation gaps | [Y] |
| Verification-only tasks | [Z] |
| Modification tasks | [W] |

**Recommendation:** The actual scope is ~[N]% smaller than design doc suggests.

### Next Step
/breakdown-design docs/design/[feature-name].md
(Will use CODEBASE_ANALYSIS.md to correctly classify tasks)
```

---

## Output Format

```markdown
## Codebase Exploration Complete ✅

**Feature:** [feature-name]
**Design Doc:** docs/design/[feature-name].md
**Analysis Saved:** docs/workstreams/[feature-name]/CODEBASE_ANALYSIS.md

### Scope Impact

| Category | Count | Impact |
|----------|-------|--------|
| Already exists (Skip) | [N] | -[N] tasks from original scope |
| Needs verification (Verify) | [N] | [N] minimal tasks |
| Needs modification (Modify) | [N] | [N] reduced-complexity tasks |
| Truly missing (Create) | [N] | [N] full-complexity tasks |

**Original estimated scope:** [N] tasks
**Adjusted scope:** [N] tasks ([X]% reduction)

### Next Steps
1. Review `CODEBASE_ANALYSIS.md` for accuracy
2. Run `/breakdown-design docs/design/[feature-name].md`
3. Breakdown will use the analysis to correctly classify tasks
```

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "The design doc is recent, I don't need to explore" | Even recent design docs describe intent, not current state. Code changes faster than docs. |
| "This is a small feature, exploration is overkill" | Small features that touch existing code benefit most — you need to know what's already there to avoid duplication. |
| "I already know the codebase" | Knowledge decays. Other agents/developers may have changed things since your last session. Verify. |
| "Exploration takes too long" | Exploration with parallel subagents takes 2-3 minutes. Over-scoped breakdowns take hours to undo. |
| "I'll just explore as I go" | Ad-hoc exploration misses the cross-reference step. You'll create tasks for things that already exist. |
| "The coverage matrix says it's not implemented" | Coverage matrices are snapshots in time. The Feb 2026 lesson proved 60% of "missing" items actually existed. |

## Red Flags

- Running `/breakdown-design` without a `CODEBASE_ANALYSIS.md` file
- Design doc "missing" items not verified against actual codebase
- Creating tasks typed as `Create` when the component already exists
- Over-scoped breakdowns (too many tasks for the actual delta)
- Skipping exploration for "small" changes
- Trusting "Not Implemented" labels in design docs without grep verification

## Verification

Before proceeding to `/breakdown-design`:

- [ ] All relevant services explored (Control, Gateway, SDK as applicable)
- [ ] Every "missing" item from design doc cross-referenced against codebase
- [ ] Each item classified as Create / Modify / Verify / Skip
- [ ] `CODEBASE_ANALYSIS.md` created at `docs/workstreams/[feature-name]/`
- [ ] Scope adjustment percentage calculated
- [ ] Findings summarized for user

---

## Reference

This command integrates with:
- `/breakdown-design` → Calls this as its embedded Step 1 (you don't need to call it separately)
- `/spec` or `/create-design-doc` → Produces the design doc this reads
- Task tool (`subagent_type="explore"`) → Used for parallel service inventory

See also:
- `CLAUDE.md` → "Codebase Exploration Before Breakdown (CRITICAL)" section
- `CLAUDE.md` → "Meta Verification: Validate Assumptions"
- `docs/DEVELOPER_WORKFLOW.md` → Phase 1: Planning
