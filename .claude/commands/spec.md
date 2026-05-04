# Spec: Create Structured Requirements Before Design

Structured requirements gathering and specification creation. Use when starting a new feature, project, or significant change where no specification exists yet.

## Workflow Position

```
/spec → /explore-codebase → /breakdown-design → /create-workstream → ...
  ↑
(YOU ARE HERE — This is the FIRST step in the pipeline)
```

## When to Use

- Starting a new feature or project
- Requirements are ambiguous or only exist as a vague idea
- The change touches multiple files, modules, or services
- An architectural decision needs to be made
- The task would take more than 2 hours to implement
- Translating a `.cursor/plans/*.plan.md` into a formal design doc

**When NOT to use:** Single-file fixes, typo corrections, or changes where requirements are unambiguous and self-contained. For those, proceed directly to `/execute-task` or just implement.

---

## The Gated Workflow

Specification has four phases. Do not advance to the next phase until the current one is validated.

```
CLARIFY ──→ SPECIFY ──→ VALIDATE ──→ OUTPUT
   │           │           │           │
   ▼           ▼           ▼           ▼
 Surface     Write       Human      Save to
 assumptions  spec       reviews    docs/design/
```

---

## Phase 1: CLARIFY — Surface Assumptions

Before writing anything, explicitly list every assumption you're making:

```markdown
## Assumptions I'm Making

1. [Technology assumption — e.g., "This is a Python/FastAPI backend"]
2. [Architecture assumption — e.g., "This runs in the Control Plane, not Gateway"]
3. [Scope assumption — e.g., "MVP scope, not enterprise-grade"]
4. [Integration assumption — e.g., "Uses existing auth flow, not new OAuth"]
5. [Data assumption — e.g., "PostgreSQL via existing schema patterns"]

→ Correct me now or I'll proceed with these.
```

**Surface ambiguity immediately.** Don't silently fill in gaps. The spec's entire purpose is to surface misunderstandings *before* code gets written.

### Clarification Questions

Ask targeted questions. Group them by category:

```markdown
## Questions Requiring Human Input

### Scope
- [ ] What is the MVP boundary? What can we defer?
- [ ] Who is the primary user/persona?

### Technical
- [ ] Which services are affected? (Control Plane / Gateway / SDK / All)
- [ ] Are there database schema changes required?
- [ ] Are there new API endpoints?

### Integration
- [ ] How does this interact with existing features?
- [ ] Are there external API dependencies?

### Acceptance
- [ ] How will we know this is done? What does success look like?
- [ ] Are there demo scenarios that must work end-to-end?
```

**STOP and wait for answers before proceeding to Phase 2.**

---

## Phase 2: SPECIFY — Write the Spec Document

Write a structured specification covering these sections:

### Spec Template

```markdown
# Spec: [Feature/Project Name]

## 1. Objective
[What we're building and why. 2-3 sentences max.]

### User Stories / Acceptance Criteria
- As a [persona], I want [action] so that [outcome]
- As a [persona], I want [action] so that [outcome]

### Success Criteria
[Specific, testable conditions — not vague "it works".]
- [ ] [Criterion 1 — measurable]
- [ ] [Criterion 2 — measurable]
- [ ] [Criterion 3 — measurable]

## 2. Technical Design

### Services Affected
| Service | Impact | Changes |
|---------|--------|---------|
| deeptrail-control | [High/Medium/Low] | [Summary] |
| deeptrail-gateway | [High/Medium/Low] | [Summary] |
| deepsecure (SDK) | [High/Medium/Low] | [Summary] |

### API Contracts
[Define endpoints, request/response schemas, error codes]

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/v1/...` | [purpose] | [auth type] |

### Data Models
[New or modified database tables/models]

### Architecture Decisions
[Key decisions with rationale — not just what, but WHY]

| Decision | Options Considered | Chosen | Rationale |
|----------|--------------------|--------|-----------|
| [decision] | A, B, C | B | [why] |

## 3. Project Structure

### Files to Create
| File | Purpose |
|------|---------|
| `[service]/app/[path]` | [what it does] |

### Files to Modify
| File | Changes |
|------|---------|
| `[service]/app/[path]` | [what changes] |

## 4. Testing Strategy

### Test Levels
| Level | What | Location | Framework |
|-------|------|----------|-----------|
| Unit | [what] | `[service]/tests/[module]/` | pytest |
| Integration | [what] | `tests/` (root) | pytest |
| E2E | [what] | `tests/e2e/` (root) | pytest + httpx |

### Coverage Requirements
- New code: >80% coverage
- Critical paths: 100% coverage

## 5. Boundaries

### Always Do
- Run tests before marking task complete
- Follow existing code patterns in `deepsecure/_core/`
- Use type hints throughout
- Validate inputs at API boundaries

### Ask First
- Database schema changes (need migration review)
- New external dependencies (need justification)
- Changes to API contracts (breaking change risk)
- Changes to JWT/crypto operations (security review)

### Never Do
- Commit secrets or private keys
- Skip tests to meet deadline
- Change shared state without documenting
- Remove failing tests without understanding why

## 6. Demo Scenarios
[End-to-end scenarios that validate the feature works]

### Demo 1: [Name]
```
Step 1: [action] → Expected: [result]
Step 2: [action] → Expected: [result]
Step 3: [action] → Expected: [result]
```

## 7. Dependencies & Risks

### External Dependencies
| Dependency | Risk | Mitigation |
|------------|------|------------|
| [what] | [risk] | [mitigation] |

### Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [risk] | [H/M/L] | [H/M/L] | [plan] |

## 8. Open Questions
[Anything unresolved that needs human input before implementation]

- [ ] [Question 1]
- [ ] [Question 2]
```

### Reframe Vague Requirements

When receiving vague requirements, translate them into concrete conditions:

```markdown
## Requirement Reframing

VAGUE: "Make the agent authentication more secure"

REFRAMED SUCCESS CRITERIA:
- Agent keys use Ed25519 (not RSA) — ✅ already done
- Challenge tokens expire after 60 seconds
- Failed auth attempts are rate-limited (5/minute per agent_id)
- JWT tokens include `iss`, `sub`, `exp`, `iat` claims minimum
→ Are these the right targets?
```

---

## Phase 3: VALIDATE — Human Review

Present the spec for review:

```markdown
## Spec Review Checkpoint

**Feature:** [name]
**Sections completed:** [list]
**Open questions:** [count]

### Summary for Review
- [1-sentence summary of what we're building]
- [Key architectural decision]
- [Scope boundary — what's in, what's out]

### I Need Your Input On
1. [Specific question requiring decision]
2. [Trade-off that needs human judgment]

Approve spec to proceed? (approve / modify / reject)
```

**STOP and wait for approval before proceeding to Phase 4.**

---

## Phase 4: OUTPUT — Save and Integrate

### Save Location

```
docs/design/[feature-name].md          ← Primary spec document
```

If converting from a plan file:
```
Input:  plans/[feature]_[hash].plan.md  ← Cursor plan (informal)
Output: docs/design/[feature-name].md   ← Formal spec (canonical)
```

### Post-Spec Actions

After spec is approved, guide the user to next steps:

```markdown
## Spec Complete ✅

**Saved to:** `docs/design/[feature-name].md`

### Next Steps
1. `/explore-codebase` — Verify what already exists before breakdown
2. `/breakdown-design docs/design/[feature-name].md` — Create workstreams and tasks
3. `/create-workstream [feature-name]` — Create tracking structure

### Pipeline Position
/spec ✅ → /explore-codebase → /breakdown-design → /create-workstream → ...
```

---

## DeepSecure-Specific Patterns

### Common Spec Structures

**SDK Feature:**
```
Objective → API Design → Core Implementation → Public Client → CLI → Tests → Examples
```

**Backend Change:**
```
Objective → Schema/Models → Service Logic → API Endpoints → Tests → Migration
```

**Cross-Service Feature:**
```
Objective → API Contracts (canonical) → Control Plane → Gateway → SDK → E2E Tests
```

### Path Conventions (CANONICAL)

| Design Doc Pattern | Actual Implementation |
|--------------------|----------------------|
| `[service]/models/` | `[service]/app/models/` |
| `[service]/services/` | `[service]/app/services/` |
| `[service]/api/[domain]/` | `[service]/app/api/v1/endpoints/` |

### Token Types Reference

| Token | Source | Used For |
|-------|--------|----------|
| User Token | `POST /api/v1/auth/login` → `.token` | User-facing endpoints |
| Agent JWT | Ed25519 challenge-response | Agent-to-Control APIs |
| Internal Token | `docker-compose.yml` env var | Gateway-to-Control internal |

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "This is simple, I don't need a spec" | Simple tasks don't need *long* specs, but they still need acceptance criteria. A 5-line spec is fine. |
| "I'll write the spec after I code it" | That's documentation, not specification. The spec's value is in forcing clarity *before* code. |
| "The spec will slow us down" | A 15-minute spec prevents hours of rework. Debugging the wrong implementation costs 10x more. |
| "Requirements will change anyway" | That's why the spec is a living document. An outdated spec is still better than no spec. |
| "The user knows what they want" | Even clear requests have implicit assumptions. The spec surfaces those assumptions before they become bugs. |
| "Let me just prototype first" | Prototyping is exploring *how*. Spec is clarifying *what*. Do both, but know which you're doing. |

## Red Flags

- Starting to write code without any written requirements
- Asking "should I just start building?" before clarifying what "done" means
- Implementing features not mentioned in any spec
- Making architectural decisions without documenting trade-offs
- Skipping the spec because "it's obvious what to build"
- No success criteria defined — no way to know when you're done
- Open questions left unresolved before implementation starts

## Verification

Before proceeding to `/explore-codebase` or `/breakdown-design`:

- [ ] Objective is specific and testable (not vague)
- [ ] Success criteria are measurable
- [ ] Services affected are identified
- [ ] API contracts are defined (if applicable)
- [ ] Architecture decisions have documented rationale
- [ ] Boundaries (Always/Ask/Never) are defined
- [ ] Open questions are resolved or explicitly deferred
- [ ] Spec is saved to `docs/design/[feature-name].md`
- [ ] Human has reviewed and approved the spec

---

## Reference

This command feeds into:
- `/explore-codebase` — Phase 0.5: Verify what exists before scoping
- `/breakdown-design` — Phase 1: Create workstreams and tasks from this spec
- `CLAUDE.md` — Architecture patterns and conventions

See also:
- `docs/design/DESIGN_TEMPLATE.md` — If one exists
- `docs/DEVELOPER_WORKFLOW.md` — Full pipeline documentation
- Osmani's `spec-driven-development` — Upstream inspiration
