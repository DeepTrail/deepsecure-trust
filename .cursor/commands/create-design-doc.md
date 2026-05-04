# Create Design Doc: Convert Plan to Formal Specification

Convert a Cursor plan file (`.cursor/plans/*.plan.md` or `plans/*.plan.md`) into a formal design document in `docs/design/`.

## Workflow Position

```
Plan Mode (informal) → /create-design-doc → /spec (enrich) → /explore-codebase → /breakdown-design → ...
                            ↑
                       (YOU ARE HERE)
```

## When to Use

- You have a `.cursor/plans/*.plan.md` or `plans/*.plan.md` file from a Plan Mode conversation
- You want to formalize an informal plan into a structured design doc
- You need to convert between formats (plan → design doc → breakdown)
- The plan has been approved and needs to become the canonical spec

**When NOT to use:**
- Starting from scratch with no existing plan — use `/spec` instead
- Plan is still in exploratory phase — stay in Plan Mode
- Design doc already exists in `docs/design/` — edit it directly

---

## Instructions

### Step 1: Read the Plan File

```
Read the plan file at the path provided by the user.
Common locations:
  - plans/[feature]_[hash].plan.md
  - .cursor/plans/[feature]_[hash].plan.md
```

Extract from the plan:
- **Title/Name** — from the plan's `name:` frontmatter or first heading
- **Overview** — the `overview:` frontmatter or first paragraph
- **Todos/Phases** — from the `todos:` frontmatter (structured tasks)
- **Technical decisions** — architecture choices, stack decisions, trade-offs
- **Implementation details** — directory structure, patterns, conventions

### Step 2: Determine Feature Name

Derive a kebab-case feature name for the output file:
- From plan title: "Frontend Architecture Plan" → `frontend-architecture`
- From plan overview: "Add a frontend to the existing..." → `frontend-architecture`
- Or ask the user: "What should I name this design doc?"

### Step 3: Create the Design Document

**Output path:** `docs/design/[feature-name].md`

Transform the plan content into the formal design doc structure:

```markdown
# Design: [Feature Name]

> **Status:** Draft | Review | Approved | Implemented
> **Author:** [from plan context or ask]
> **Created:** [today's date]
> **Plan Source:** `plans/[original-plan-file].plan.md`

## 1. Overview

### Problem Statement
[Extract from plan: what problem does this solve?]

### Goals
[Extract from plan: what are we trying to achieve?]
- Goal 1
- Goal 2

### Non-Goals (Out of Scope)
[Extract from plan: what are we explicitly NOT doing?]
- Non-goal 1

### Success Criteria
[Convert plan's goals into testable criteria]
- [ ] Criterion 1 — [measurable condition]
- [ ] Criterion 2 — [measurable condition]

## 2. Technical Design

### Architecture Overview
[Extract from plan: high-level architecture description]
[Include ASCII diagrams if the plan has them]

### Key Decisions
[Extract from plan: decisions with rationale]

| Decision | Options Considered | Chosen | Rationale |
|----------|--------------------|--------|-----------|
| [decision 1] | A, B, C | [chosen] | [why] |

### Services Affected

| Service | Impact | Changes |
|---------|--------|---------|
| deeptrail-control | [level] | [summary] |
| deeptrail-gateway | [level] | [summary] |
| deepsecure (SDK) | [level] | [summary] |
| frontend | [level] | [summary] |

### API Contracts
[Extract from plan: any API definitions, endpoints, schemas]

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| [method] | `/api/v1/...` | [purpose] | [auth] |

### Data Models
[Extract from plan: database models, schemas, data structures]

### Directory Structure
[Extract from plan: proposed file layout]

```
[service]/
├── [dir]/
│   └── [file]
```

## 3. Implementation Plan

### Phases
[Convert plan's todos into implementation phases]

| Phase | Description | Key Deliverables | Status |
|-------|-------------|------------------|--------|
| 1 | [from plan todo] | [deliverables] | pending |
| 2 | [from plan todo] | [deliverables] | pending |

### Phase Details

#### Phase 1: [Name]
[Expand the plan's phase 1 todo into detailed scope]

**Deliverables:**
- [ ] [deliverable 1]
- [ ] [deliverable 2]

**Dependencies:**
- [dependency 1]

#### Phase 2: [Name]
[Expand the plan's phase 2 todo into detailed scope]

### Parallelization Opportunities
[Identify which phases/tasks can run in parallel]

| Parallel Track | Phases | Service |
|---------------|--------|---------|
| Track A | Phase 1a | [service] |
| Track B | Phase 1b | [service] |

## 4. Testing Strategy

### Test Levels

| Level | What | Location | Framework |
|-------|------|----------|-----------|
| Unit | [what] | `[service]/tests/` | pytest |
| Integration | [what] | `tests/` (root) | pytest |
| E2E | [what] | `tests/e2e/` (root) | pytest + httpx |

### Key Test Scenarios
[Extract from plan: critical paths that must be tested]

## 5. Dependencies & Risks

### External Dependencies

| Dependency | Risk | Mitigation |
|------------|------|------------|
| [dep] | [risk] | [plan] |

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [risk] | H/M/L | H/M/L | [plan] |

## 6. Open Questions

[Extract from plan: unresolved items]

- [ ] [question 1]
- [ ] [question 2]

## 7. References

- **Plan source:** `plans/[file].plan.md`
- **Related designs:** [links to related docs]
- **Related code:** [links to relevant code]
```

### Step 4: Handle Plan Frontmatter

Cursor plan files have YAML frontmatter with structured todos. Convert them:

**Plan frontmatter format:**
```yaml
---
name: feature name
overview: description
todos:
  - id: phase-1
    content: "Phase 1: Description of what to do"
    status: pending
  - id: phase-2
    content: "Phase 2: Next phase description"
    status: pending
---
```

**Conversion rules:**
- `name:` → Document title
- `overview:` → Section 1 (Overview)
- `todos:` → Section 3 (Implementation Plan) phases
- `todos[].status` → Phase status column
- Body content below frontmatter → Distribute across relevant sections

### Step 5: Enrich with DeepSecure Conventions

When converting, apply project-specific conventions:

**Path translations:**
| Plan Says | Design Doc Should Say |
|-----------|----------------------|
| `frontend/` | `frontend/` (new service) |
| `backend/` or `api/` | `deeptrail-control/app/` |
| `gateway/` | `deeptrail-gateway/app/` |
| `sdk/` or `client/` | `deepsecure/` |
| `tests/` | Context-dependent (see File Organization Rules) |

**Testing conventions:**
| Test Type | Correct Location |
|-----------|-----------------|
| Service unit tests | `[service]/tests/[module]/` |
| Cross-service E2E | `tests/e2e/` (root) |
| Integration | `tests/` (root) |
| Demos | `demos/` (root) |

### Step 6: Validate Completeness

Before saving, verify the design doc has all required sections:

```markdown
## Design Doc Completeness Check

- [ ] Section 1: Overview (with Success Criteria)
- [ ] Section 2: Technical Design (with Key Decisions table)
- [ ] Section 3: Implementation Plan (with Phases)
- [ ] Section 4: Testing Strategy
- [ ] Section 5: Dependencies & Risks
- [ ] Section 6: Open Questions
- [ ] Section 7: References (with link back to plan source)
```

Flag any sections that couldn't be filled from the plan:
```markdown
### ⚠️ Sections Needing Human Input
- [ ] API Contracts — Plan did not specify endpoints
- [ ] Data Models — Plan mentions database but no schema
```

### Step 7: Save and Report

Save the design doc:
```
docs/design/[feature-name].md
```

**If a plan was in `~/.cursor/plans/` or `.cursor/plans/`:**
The original plan file remains untouched — the design doc is a new artifact.

---

## Output Format

```markdown
## Design Doc Created ✅

**Source:** `plans/[original-plan].plan.md`
**Output:** `docs/design/[feature-name].md`

### Conversion Summary
- **Phases extracted:** [N]
- **Key decisions captured:** [N]
- **Services affected:** [list]
- **Open questions:** [N]

### Sections Filled
- [x] Overview & Success Criteria
- [x] Technical Design
- [x] Implementation Plan ([N] phases)
- [x] Testing Strategy
- [ ] API Contracts ⚠️ [needs human input]
- [x] Dependencies & Risks
- [x] Open Questions

### Next Steps
1. Review and enrich: `docs/design/[feature-name].md`
2. Optionally run `/spec` to add detailed API contracts and acceptance criteria
3. Run `/explore-codebase` to verify what already exists
4. Run `/breakdown-design docs/design/[feature-name].md` to create workstreams

### Pipeline Position
/create-design-doc ✅ → /spec (optional enrich) → /explore-codebase → /breakdown-design → ...
```

---

## Example: Converting the Frontend Architecture Plan

**Input:** `plans/frontend_architecture_plan_26af34d6.md`

**Frontmatter extraction:**
```
name: frontend architecture plan
overview: Add a frontend to the existing deepsecure-mvp monorepo...
todos:
  - scaffold (pending) → Phase 1a
  - design-system (pending) → Phase 1b
  - auth (pending) → Phase 1c
  - dashboard (pending) → Phase 2
  - demo-ui (pending) → Phase 3
  - realtime-polish (pending) → Phase 4
```

**Output:** `docs/design/frontend-architecture.md`

**Conversion:**
- Plan's `overview:` → Section 1 (Overview)
- Plan's 6 todos → 4 phases with detailed deliverables
- Plan's monorepo decision → Section 2 Key Decisions table
- Plan's directory structure → Section 2 Directory Structure
- Plan's tech stack → Section 2 Architecture Overview

---

## Reference

This command integrates with:
- Plan Mode — Creates the `.plan.md` files this reads
- `/spec` — Can further enrich the generated design doc
- `/explore-codebase` — Next step after design doc is ready
- `/breakdown-design` — Reads the design doc to create workstreams
- `.cursorrules` → Plan file location rules (must be in `plans/` directory)
