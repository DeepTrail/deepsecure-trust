# Spec: Create Structured Requirements Before Design

Structured requirements gathering and specification creation. Use when starting a new feature, project, or significant change where no specification exists yet.

## Workflow Position

```
/spec → /create-design-doc → /breakdown-design → ...
  ↑
(YOU ARE HERE — This is the FIRST step in the pipeline)
```

**The pipeline is three mandatory steps:**
1. `/spec` — Capture requirements (what + why)
2. `/create-design-doc` — Transform requirements into a full design doc (how) with diagrams, code interfaces, workstream file tables
3. `/breakdown-design` — Create workstreams and tasks from the design doc (internally runs `/explore-codebase`)

**Note:** `/explore-codebase` is NOT a separate step — it is embedded inside `/breakdown-design` as a mandatory pre-breakdown phase.

**Therefore: the spec must contain enough detail for `/create-design-doc` to produce a gold-standard design doc without guessing.** A skeletal spec produces a skeletal design doc, which produces an over-scoped breakdown.

## When to Use

- Starting a new feature or project
- Requirements are ambiguous or only exist as a vague idea
- The change touches multiple files, modules, or services
- An architectural decision needs to be made
- The task would take more than 2 hours to implement
- Translating a `.cursor/plans/*.plan.md` into a formal spec

**When NOT to use:** Single-file fixes, typo corrections, or changes where requirements are unambiguous and self-contained. For those, proceed directly to `/execute-task` or just implement.

## Quality Bar

The spec produced by this command is the **upstream input** for `/create-design-doc`. A shallow spec produces a shallow design doc. The spec must capture enough detail that `/create-design-doc` can transform it into a gold-standard design doc matching:
- `docs/design/idp-enhanced-sso-features.md` — 14 sections, 797 lines
- `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md` — 7 sections, 987 lines

**The spec should be 200–400+ lines** with concrete requirements, not a 50-line skeleton with placeholders.

---

## The Gated Workflow

Specification has four phases. Do not advance to the next phase until the current one is validated.

```
CLARIFY ──→ SPECIFY ──→ VALIDATE ──→ OUTPUT
   │           │           │           │
   ▼           ▼           ▼           ▼
 Surface     Write       Human      Save to
 assumptions  spec       reviews    docs/spec/
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

Ask targeted questions. Group them by category. These questions are designed to surface the information needed for all 15 sections of the downstream design doc:

```markdown
## Questions Requiring Human Input

### Scope
- [ ] What is the MVP boundary? What can we defer? (→ feeds Non-Goals)
- [ ] Who is the primary user/persona? (→ feeds User Journeys)
- [ ] What exists today that this feature extends or replaces? (→ feeds Current State)

### Technical
- [ ] Which services are affected? (Control Plane / Gateway / SDK / Frontend / All)
- [ ] Are there database schema changes required? (→ feeds Data Models)
- [ ] Are there new API endpoints? (→ feeds API Contracts)
- [ ] Does this touch tokens, secrets, encryption, or access control? (→ feeds Security)

### Integration
- [ ] How does this interact with existing features?
- [ ] Are there external API dependencies?
- [ ] Does this feature work differently across providers (Keycloak vs Google)? (→ feeds Provider Parity)

### Acceptance
- [ ] How will we know this is done? What does success look like?
- [ ] Are there demo scenarios that must work end-to-end? (→ feeds Demo Scenarios)
- [ ] What is the rollout strategy — all at once or phased? (→ feeds Rollout Plan)

### Security
- [ ] What security boundaries does this feature cross?
- [ ] What tokens/credentials are involved and how are they stored?
- [ ] What happens on unauthorized access — fail-open or fail-closed?
```

**STOP and wait for answers before proceeding to Phase 2.**

---

## Phase 2: SPECIFY — Write the Spec Document

Write a structured specification covering **all 15 sections** below. This template is designed so that `/create-design-doc` can directly transform each section into its corresponding design doc section without guessing.

**Critical rule:** If the user's input lacks detail for a section, **ask for it** (Phase 1 questions) or **infer it** from context and codebase exploration rather than leaving `[placeholder]` text. A spec with placeholders is a spec that hasn't been written yet.

### Spec Template

```markdown
# Spec: [Feature/Project Name]

> **Status:** Draft | Review | Approved
> **Author:** [name]
> **Created:** [date]
> **Priority:** [e.g., Priority 1A — Foundation | Priority 2 — Core Experience]
> **Roadmap Phase:** [e.g., Phase 1: Now — Q2 2026 | Phase 2: Q3 2026]
> **Priority Master:** [`plans/PRIORITY_MASTER.md`](../../plans/PRIORITY_MASTER.md)
> **Product Roadmap:** [`plans/PRODUCT_ROADMAP.md`](../../plans/PRODUCT_ROADMAP.md)
> **Design Doc:** [`docs/design/[feature-name].md`](../design/[feature-name].md) *(populated after `/create-design-doc`)*

---

## Priority & Roadmap Mapping

> **Why this section exists:** `plans/PRIORITY_MASTER.md` and `plans/PRODUCT_ROADMAP.md` define the sequence every workstream must follow. This mapping shows exactly where this spec sits in that sequence, which priorities it covers, and what it unblocks. Fill this in from those two files — do not guess or leave as placeholders.

### Priority Master Mapping ([`plans/PRIORITY_MASTER.md`](../../plans/PRIORITY_MASTER.md))

This spec covers **[Priority Group(s)]** from the Priority Master.

| Priority Group | Coverage | Items in This Spec |
|---------------|----------|--------------------|
| **[Priority Name]** *(e.g., Sequential: C1 → C2)* | ✅ Full | [Specific items from PRIORITY_MASTER.md that this spec implements] |
| **[Priority Name]** *(e.g., Parallel with above)* | ⚠️ Partial | [Items pulled in, reason: "shares files already modified"] |
| **[Priority Name]** | ❌ Not in scope | [Items deferred — "deferred to next workstream"] |

### Product Roadmap Mapping ([`plans/PRODUCT_ROADMAP.md`](../../plans/PRODUCT_ROADMAP.md))

This spec delivers **[Phase Name(s)]** from the product roadmap.

| Roadmap Phase | Coverage | What This Spec Delivers |
|--------------|----------|------------------------|
| **[Phase 1: Now — Q2 2026]** | ✅ Complete | [All items from that phase's feature tables] |
| **[Phase 2: Q3 2026]** | ⚠️ Partial ([N] of [M] items) | [Items pulled forward with reason] |
| **[Phase 3: Q4 2026]** | ❌ Not in scope | [e.g., AgentCore, Admin governance] |

### Persona Capability Unlocked by This Spec

Taken from the roadmap's **"Persona Capability Timeline"** — what becomes non-broken for each persona after this spec lands:

| Persona | Capability Unlocked |
|---------|---------------------|
| **Employee** | [What works for this persona after this spec lands — copy from roadmap] |
| **IT Admin** | [What works for this persona] |
| **Security Team** | [What works for this persona] |
| **Engineer / Developer** | [What works for this persona] |

### What This Spec Unblocks

| Blocked Item | Needs | Covered By |
|--------------|-------|-----------|
| [Next priority / workstream / feature] | [Which tables or tracks in this spec] | [Section reference] |
| [Another downstream item] | [Dependency] | [Section reference] |

---

## Table of Contents

1. [Objective](#1-objective)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Background](#3-background)
4. [Technical Design](#4-technical-design)
5. [Data Models](#5-data-models)
6. [API Contracts](#6-api-contracts)
7. [Security Considerations](#7-security-considerations)
8. [Project Structure](#8-project-structure)
9. [Testing Strategy](#9-testing-strategy)
10. [Demo Scenarios / User Journeys](#10-demo-scenarios--user-journeys)
11. [Rollout Plan](#11-rollout-plan)
12. [Boundaries](#12-boundaries)
13. [Dependencies & Risks](#13-dependencies--risks)
14. [Open Questions](#14-open-questions)
15. [References](#15-references)

---

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

---

## 2. Goals & Non-Goals

### Goals
- [ ] [Goal 1 — measurable outcome, maps to a success criterion]
- [ ] [Goal 2 — measurable outcome]
- [ ] [Goal 3 — measurable outcome]

### Non-Goals
[Explicitly state what this feature does NOT do. This prevents scope creep and tells `/create-design-doc` what to exclude.]
- **[Non-goal 1]** — [Why deferred and when to revisit]
- **[Non-goal 2]** — [Why deferred and when to revisit]

---

## 3. Background

### Current State
[Describe what exists TODAY. This section is the single most important input for `/breakdown-design` — it tells the embedded `/explore-codebase` step what to verify rather than assume is missing.]

| Capability | Current Status | Notes |
|------------|----------------|-------|
| [capability 1] | Implemented / Partial / Missing | [details, file location if known] |
| [capability 2] | Implemented / Partial / Missing | [details] |

[If the feature touches multiple providers/services, use a provider comparison table:]

| Capability | Keycloak | Google | Other |
|------------|----------|--------|-------|
| [capability] | [status] | [status] | [status] |

### Motivation
[Business-facing reasons — not just technical. "Why does this matter to users?"]

1. **[Business reason 1.]** [Concrete scenario: "When X happens, users must Y, but today they have to Z..."]
2. **[Business reason 2.]** [Concrete scenario]
3. **[Business reason 3.]** [Concrete scenario]

---

## 4. Technical Design

### Services Affected
| Service | Impact | Changes |
|---------|--------|---------|
| deeptrail-control | [None/Low/Medium/High] | [Summary] |
| deeptrail-gateway | [None/Low/Medium/High] | [Summary] |
| deepsecure (SDK) | [None/Low/Medium/High] | [Summary] |
| frontend | [None/Low/Medium/High] | [Summary] |

### Architecture Overview
[High-level description of how the feature works across services. Include a Mermaid sequence diagram or flowchart — create one even if it's simple.]

` ` `mermaid
sequenceDiagram
    participant Client
    participant ControlPlane as Control Plane
    participant Gateway
    participant ExternalService as External Service

    Client->>ControlPlane: [action]
    ControlPlane->>ExternalService: [call]
    ExternalService-->>ControlPlane: [response]
    ControlPlane-->>Client: [result]
` ` `

### Key Components
[For each major component, describe what it does and include a code-level interface:]

**1. [Component Name]** (`[service]/app/[path]/[file].py`)

` ` `python
class [ClassName]:
    """[What this component does]"""

    async def [method_name](self, [params]: [types]) -> [return_type]:
        """[What this method does]"""
        ...
` ` `

**2. [Component Name]** (`[service]/app/[path]/[file].py`)

` ` `python
async def [function_name]([params]: [types]) -> [return_type]:
    """[What this function does]"""
    ...
` ` `

### Architecture Decisions
[Key decisions with rationale — not just what, but WHY]

| Decision | Options Considered | Chosen | Rationale |
|----------|--------------------|--------|-----------|
| [decision] | A, B, C | B | [why] |

### Provider Parity
[For features touching IdP providers: how does this work with each provider?]

| Aspect | Keycloak | Google | Notes |
|--------|----------|--------|-------|
| [aspect] | [behavior] | [behavior] | [differences] |

[If no provider-specific behavior: "No provider-specific changes needed."]

---

## 5. Data Models

[For each new or modified model, include a full column table with types — NOT just a placeholder.]

### New: [ModelName]

| Column | Type | Description |
|--------|------|-------------|
| `id` | `String(64)` PK | UUID-based identifier |
| `[field]` | `[SQLAlchemy type]` | [Description, constraints, relationships] |
| `[field]` | `[type]` | [Description] |
| `created_at` | `DateTime(timezone=True)` | When record was created |

[If encryption is involved: "Encrypted with [algorithm] using `settings.SECRET_KEY`"]

### Modified: [ExistingModelName]
[If modifying an existing model, state specific changes or "No schema changes."]

### Configuration Models (if non-DB)
[For config-file-based models, show the YAML/JSON structure:]

` ` `yaml
# [config-file-name].yaml
[key]:
  - [field]: "[value]"
    [field]: "[value]"
` ` `

---

## 6. API Contracts

> **CRITICAL**: This section is the CANONICAL source for all API endpoints.
> Task tickets, tests, and implementations MUST match these exactly.
> `/create-design-doc` will copy this section verbatim.

### Endpoint Summary

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| [METHOD] | `/api/v1/[path]` | [purpose] | [token type] |

### [METHOD] /api/v1/[path]

**Request:**
` ` `
Authorization: Bearer <[token-type]>
Content-Type: application/json
` ` `

` ` `json
{
  "[field]": "[example-value]",
  "[field]": [example-number]
}
` ` `

**Response (200):**
` ` `json
{
  "[field]": "[value]",
  "[field]": [number]
}
` ` `

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 400 | [when this error occurs] |
| 401 | [when this error occurs] |
| 403 | [when this error occurs] |
| 404 | [when this error occurs] |

[Repeat for each endpoint. Include MCP tools if applicable:]

**New MCP Tools (if applicable):**
| Namespace | Tool | Arguments |
|-----------|------|-----------|
| `[service].[tool_name]` | [Description] | `[arg]: [type]` |

---

## 7. Security Considerations

[This is a security product. Every spec MUST address security. Include at least 2 of these subsections, depending on what the feature touches:]

### [Token/Credential Storage]
- How tokens/secrets are stored (encrypted at rest? which algorithm?)
- Whether values are ever exposed in API responses or logs
- Revocation behavior

### [Access Control]
- Which scope/permission/role is required
- Fail-open vs fail-closed behavior
- Rate limiting considerations

### [Session/Auth Security]
- Session lifecycle (creation, refresh, expiry)
- Token rotation behavior
- Grace windows

---

## 8. Project Structure

[Group files by workstream/feature area — NOT a flat list. This grouping directly becomes the "Implementation Workstreams" in the design doc.]

### Workstream A: [Name] ([Service])

| File | Action | Purpose |
|------|--------|---------|
| `[service]/app/[path]/[file].py` | Create | [what it does] |
| `[service]/app/[path]/[file].py` | Modify | [what changes] |
| `[service]/tests/[path]/test_[file].py` | Create | [what it tests] |

### Workstream B: [Name] ([Service])

| File | Action | Purpose |
|------|--------|---------|
| `[service]/app/[path]/[file].py` | Create | [what it does] |

### Complexity Estimates

| Workstream | Complexity | Rationale |
|------------|------------|-----------|
| WS-A: [Name] | [S/M/L] ([N] tasks) | [Brief justification] |
| WS-B: [Name] | [S/M/L] ([N] tasks) | [Brief justification] |

---

## 9. Testing Strategy

### Test Matrix

| Level | What | Location | Framework |
|-------|------|----------|-----------|
| Unit | [what] | `[service]/tests/[module]/` | pytest |
| Integration | [what] | `tests/` (root) | pytest |
| E2E | [what] | `tests/e2e/` (root) | pytest + httpx |

### Key Test Scenarios
[Critical paths that must be tested — concrete, not generic:]
- [ ] [Scenario 1: e.g., "Agent with valid delegation can call tools/list"]
- [ ] [Scenario 2: e.g., "Expired token returns 401, not 500"]
- [ ] [Scenario 3: e.g., "Revoked delegation blocks tool execution immediately"]

### Technical Requirements
| Requirement | Correct Pattern | Common Mistake |
|-------------|-----------------|----------------|
| Async fixtures | `@pytest_asyncio.fixture` | `@pytest.fixture` (breaks async) |
| HTTP client | `httpx.AsyncClient` | `requests` (sync) |
| Mock external APIs | `respx` or `httpx` mock | Calling live APIs in tests |

### Coverage Requirements
- New code: >80% coverage
- Critical paths: 100% coverage

---

## 10. Demo Scenarios / User Journeys

[Walk through concrete user journeys that validate this feature end-to-end. These are the "test cases for the design" — if the design can't support these scenarios, it has gaps.]

### Scenario 1: [Persona] — [Journey Title]

**Persona:** [Name, role — e.g., "Sarah, Security Engineer at Acme Corp"]
**Pre-conditions:** [What must exist before this journey starts]

| Step | Action | Expected Result | Validates |
|------|--------|-----------------|-----------|
| 1 | [What the user does] | [What the system responds] | [Which requirement] |
| 2 | [Next action] | [Response] | [Requirement] |
| 3 | [Next action] | [Response] | [Requirement] |

**Success criteria:** [How to verify this scenario passed — curl command, test assertion, or UI check]

### Scenario 2: [Persona] — [Journey Title]
[Same structure. At least 1 scenario per primary persona.]

### Scenario 3: [Error/Edge Case]
[At least one scenario covering a failure path — expired token, missing permission, provider down, etc.]

---

## 11. Rollout Plan

[How is this feature delivered? Phased or all-at-once? What is usable after each phase?]

### Phase 1: [Name] (Workstream [X])
**Tasks:** WS-[X]1 through WS-[X]N
**Duration:** ~[N] sessions
**Deliverable:** [What is usable after this phase]
**Demo impact:** [How this affects existing demos or user-facing behavior]

### Phase 2: [Name] (Workstream [Y])
[Same structure]

---

## 12. Boundaries

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

---

## 13. Dependencies & Risks

### External Dependencies
| Dependency | Risk | Mitigation |
|------------|------|------------|
| [what] | [risk] | [mitigation] |

### Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [risk] | [H/M/L] | [H/M/L] | [plan] |

---

## 14. Open Questions
[Anything unresolved that needs human input before implementation]

- [ ] [Question 1 — with enough context to answer it]
- [ ] [Question 2]

---

## 15. References
- [Related spec/design doc](../../docs/design/[file].md) — [How it relates]
- [Existing implementation](../../[service]/app/[path]) — [What exists today]
- [External reference](https://...) — [What it documents]
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

### Generate Missing Depth

**Critical rule:** If the user's answers from Phase 1 don't provide enough detail for a section, **generate** the content from context — do not leave placeholders.

| Missing from User Input | What to Generate |
|-------------------------|------------------|
| No current state known | Explore existing codebase (use `Task` tool with `subagent_type="explore"`) to document what exists |
| No architecture diagram | Create Mermaid sequence/flowchart from described flow |
| No code interfaces | Write class interfaces and function signatures from described behavior |
| No data model columns | Infer column types from described fields and existing models in codebase |
| No API request/response | Write JSON examples from described endpoints |
| No security concerns | Analyze the feature for token handling, encryption, access control |
| No user journeys | Create persona-based walkthroughs from the feature's goals |
| No error responses | Infer error cases (400, 401, 403, 404, 502) from auth/validation requirements |

---

## Phase 3: VALIDATE — Human Review

Present the spec for review. Include a completeness summary showing which sections have content and which need input:

```markdown
## Spec Review Checkpoint

**Feature:** [name]
**Sections completed:** [N] of 15
**Open questions:** [count]

### Completeness Summary
- [x] Objective & Success Criteria
- [x] Goals & Non-Goals
- [x] Background (Current State + Motivation)
- [x] Technical Design (Architecture diagram + code interfaces)
- [x] Data Models (full column tables)
- [ ] API Contracts ⚠️ [needs endpoint confirmation]
- [x] Security Considerations
- [x] Project Structure (workstream-grouped file tables)
- [x] Testing Strategy (with technical requirements)
- [x] Demo Scenarios ([N] user journeys)
- [x] Rollout Plan
- [x] Boundaries
- [x] Dependencies & Risks
- [x] Open Questions
- [x] References

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
docs/spec/[feature-name]-spec.md       ← Primary spec document
```

**Naming convention:** Always use the `-spec.md` suffix to distinguish specs from design docs, screen designs, and other documentation.

If converting from a plan file:
```
Input:  plans/[feature]_[hash].plan.md        ← Cursor plan (informal)
Output: docs/spec/[feature-name]-spec.md      ← Formal spec (canonical)
```

**Directory purpose:**
- `docs/spec/` — Formal specifications (output of `/spec` command)
- `docs/design/` — Design docs with full implementation detail (output of `/create-design-doc`)
- `plans/` — Cursor plans (informal, pre-spec)

### Post-Spec Actions

After spec is approved, guide the user to next steps:

```markdown
## Spec Complete ✅

**Saved to:** `docs/spec/[feature-name]-spec.md`
**Priority:** [Priority Group from PRIORITY_MASTER.md]
**Roadmap Phase:** [Phase from PRODUCT_ROADMAP.md]
**Sections completed:** [N] of 15
**Quality:** [line count] lines

### Next Steps
1. `/create-design-doc docs/spec/[feature-name]-spec.md` — Transform spec into full design doc (500–800+ lines). Once created, update the `> **Design Doc:**` link in the spec header to point to it.
2. `/breakdown-design docs/design/[feature-name].md` — Create workstreams and tasks (internally runs `/explore-codebase`)

### Pipeline Position
/spec ✅ → /create-design-doc → /breakdown-design → ...
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
| "Current State isn't needed — this is all new" | Even new features replace or extend something. Without a baseline, `/breakdown-design` over-scopes by 60% (Feb 2026 lesson). |
| "Security is someone else's concern" | This is a security product. Every feature touches auth, tokens, or data access. Write the security section. |
| "I'll add the API details during implementation" | Skeletal API contracts → skeletal design doc → `/breakdown-design` has to guess scope. Specify request/response/error NOW. |

## Red Flags

- Starting to write code without any written requirements
- Asking "should I just start building?" before clarifying what "done" means
- Implementing features not mentioned in any spec
- Making architectural decisions without documenting trade-offs
- Skipping the spec because "it's obvious what to build"
- No success criteria defined — no way to know when you're done
- Open questions left unresolved before implementation starts
- Spec under 100 lines (almost certainly missing depth for downstream commands)
- No Current State / Background section (baseline unknown → over-scoped breakdown)
- API Contracts with only a summary table (no request/response/error → skeletal design doc)
- No Security Considerations (every feature in this product needs one)
- No Demo Scenarios (can't validate the design against real usage)
- Flat file list instead of workstream-grouped file tables
- **No Priority & Roadmap Mapping section** — every spec must anchor itself to `plans/PRIORITY_MASTER.md` and `plans/PRODUCT_ROADMAP.md` so the delivery sequence is always visible
- **Metadata header missing `Priority Master` / `Product Roadmap` links** — the header blockquote must include these links so the spec is navigable from the document itself

## Verification

Before proceeding to `/create-design-doc`:

**Header & Mapping (MANDATORY — check these first):**
- [ ] Metadata blockquote includes `Priority`, `Roadmap Phase`, `Priority Master` link, `Product Roadmap` link, and `Design Doc` placeholder link
- [ ] Priority & Roadmap Mapping section is present (immediately after the header, before Table of Contents)
- [ ] Priority Master table rows filled in from `plans/PRIORITY_MASTER.md` — ✅/⚠️/❌ per group, not placeholders
- [ ] Product Roadmap table rows filled in from `plans/PRODUCT_ROADMAP.md` — ✅/⚠️/❌ per phase
- [ ] Persona Capability Unlocked table copied from roadmap's "Persona Capability Timeline"
- [ ] "What This Spec Unblocks" table lists downstream priorities / workstreams

**Content (existing checks):**
- [ ] Spec is 200+ lines (if less, depth is likely missing)
- [ ] All 15 sections present (check Table of Contents)
- [ ] Objective is specific and testable (not vague)
- [ ] Success criteria are measurable
- [ ] Non-Goals explicitly state what's deferred
- [ ] Current State documents what exists today (capability table)
- [ ] Motivation explains business reasons (not just technical)
- [ ] Services affected are identified
- [ ] Architecture overview includes Mermaid diagram
- [ ] Key components include code-level interfaces
- [ ] Data models have full column tables (not placeholders)
- [ ] API contracts have request + response + error tables
- [ ] Security Considerations has at least 2 subsections
- [ ] Files are grouped by workstream (not a flat list)
- [ ] Testing strategy includes Technical Requirements table
- [ ] At least 1 demo scenario per primary persona + 1 error path
- [ ] Rollout plan specifies phases with deliverables
- [ ] Boundaries (Always/Ask/Never) are defined
- [ ] Open questions are resolved or explicitly deferred
- [ ] Spec is saved to `docs/spec/[feature-name]-spec.md`
- [ ] Human has reviewed and approved the spec

---

## Section Mapping: Spec → Design Doc

This table shows exactly how `/create-design-doc` transforms each spec section:

| Spec Section | Design Doc Section | Transformation |
|---|---|---|
| 1. Objective | Overview | Expand into 1-3 paragraph summary |
| 2. Goals & Non-Goals | Goals + Non-Goals | Direct transfer |
| 3. Background | Background | Direct transfer (Current State + Motivation) |
| 4. Technical Design | Technical Design | Add Mermaid diagrams, expand code detail, add Provider Parity per feature |
| 5. Data Models | Data Models | Verify column tables are complete, add config YAML |
| 6. API Contracts | API Contracts (Canonical) | Direct transfer with CANONICAL marker |
| 7. Security Considerations | Security Considerations | Expand into subsections |
| 8. Project Structure | Implementation Workstreams | Convert file tables into task tables + file tables per workstream |
| 9. Testing Strategy | Testing Strategy | Add Technical Requirements if missing |
| 10. Demo Scenarios | Demo Scenarios / User Journeys | Add ASCII wireframes, expand success criteria |
| 11. Rollout Plan | Rollout Plan | Add demo impact per phase |
| 12. Boundaries | *(absorbed into design doc conventions)* | Referenced in Boundaries or Testing |
| 13. Dependencies & Risks | *(merged into relevant sections)* | Risks → Dependencies & Risks |
| 14. Open Questions | Open Questions | Direct transfer |
| 15. References | References | Add links to plan source |

**Key insight:** The more complete the spec, the less `/create-design-doc` has to generate. Sections marked "Direct transfer" pass through unchanged. Sections marked "Expand" require the design doc command to generate depth — if the spec is skeletal here, the design doc will also be skeletal.

**Spec depth determines `/create-design-doc` effort:**

| Spec Quality | `/create-design-doc` Effort | What It Does |
|---|---|---|
| **Thorough** (500+ lines, code snippets, Mermaid diagrams, file tables) | Low — focus on 4 delta items only | Restructures Technical Design into per-feature subsections; converts file tables into WS-ID task tables with dependencies; adds Mermaid dependency graph; verifies/completes data model column tables |
| **Moderate** (200-500 lines, some code, some gaps) | Medium — fill gaps + 4 delta items | Generates missing diagrams, code interfaces, error responses, then applies the 4 delta items |
| **Skeletal** (under 200 lines, placeholders) | High — full generation | Treats like a plan file — generates depth for all 15 sections |

For a thorough spec, consider whether `/create-design-doc` adds enough value to justify running it, or whether you should skip directly to `/breakdown-design` (which generates task tables and dependency analysis as part of its own workflow).

---

## Reference

This command feeds into:
- `/create-design-doc` — **Next step (mandatory).** Transforms this spec into a 15-section design doc (500–800+ lines)
- `/breakdown-design` — Reads the design doc to create workstreams (internally runs `/explore-codebase`)
- `CLAUDE.md` — Architecture patterns and conventions

See also:
- `docs/design/idp-enhanced-sso-features.md` — Gold-standard design doc (what `/create-design-doc` should produce from a good spec)
- `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md` — Gold-standard design doc (persona journey depth)
- `docs/DEVELOPER_WORKFLOW.md` — Full pipeline documentation
