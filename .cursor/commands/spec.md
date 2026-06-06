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

## Persona Coverage Protocol (MANDATORY)

DeepSecure specs serve **four personas** (Employee, IT Admin, Security Team, Engineer / Developer). A common failure mode is writing user stories only for IT Admin while the **Persona Capability Unlocked** table lists outcomes for all four — leaving implementers and reviewers to guess what "done" means for everyone else.

**Rule: Every persona row in the Persona Capability table MUST have matching artifacts in §1 and §11.**

| Artifact | Requirement |
|----------|-------------|
| **Persona Capability table** | One row per affected persona; include **User Stories** column linking to §1 subsection anchors |
| **§1 User Stories** | Grouped by persona (`#### User Stories — IT Admin`, etc.); **≥2 stories per persona** listed in the capability table (≥1 if persona has only a single narrow outcome) |
| **§1 Success Criteria** | Grouped by the same persona headings; at least one measurable checkbox per persona |
| **§11 Demo Scenarios** | **≥1 scenario per persona** in the capability table (plus ≥1 error/edge-case scenario) |

**Persona parity checklist (run before VALIDATE phase):**

```
For each persona P in Persona Capability table:
  □ §1 has "User Stories — P" with stories covering every bullet in "Capability Unlocked"
  □ §1 Success Criteria has a "P" subsection with testable checkboxes
  □ §11 has a scenario titled with persona P (or Security Team member / Engineer as appropriate)
```

**Do NOT:**

- List capabilities for Employee / Security / Engineer in the mapping table but only write IT Admin user stories
- Use a flat bullet list of stories without persona headings when multiple personas are affected
- Mark a persona "N/A" without explicit justification in Non-Goals

### Domain Semantics Boxes (when behavior is ambiguous)

When a feature has **marketing language that sounds simple but behavior has branches** (e.g. "admin sets once, N users onboard", "auto-provision", "narrow permissions", "role-based visibility"), add a dedicated subsection in §1 **before Success Criteria**:

```markdown
### [Feature Name] Semantics

> **What "[phrase from requirements]" means in this spec**

1. [Step-by-step system behavior]
2. [What the user does NOT have to do — explicit negatives matter]
3. [Modes / feature flags / edge cases in a table]

**What users may still do (optional, not required):** [table]
```

Examples requiring a semantics box: auto-provision vs manual delegate, invite vs on_login, PATCH narrow vs revoke+recreate, role vs group vs user visibility OR-rules.

Reference implementation: `docs/spec/p5.2-gap-closure-spec.md` §1 Auto-Provision Semantics.

---

## UI Wireframes Protocol (OPTIONAL-BUT-EXPECTED)

Specs that touch the **frontend** must document **what users see** on new or changed screens — not only APIs and backend behavior. A common failure mode is a thorough §7 API Contracts section with **no §4 wireframes**, leaving frontend implementers to invent layout and component boundaries.

**Trigger — include §4 UI Wireframes (Delta) when ANY of:**

| Condition | Example |
|-----------|---------|
| `frontend` impact is **Medium** or **High** in Services Affected | Admin pages, dashboard changes, new modals |
| Spec adds a **new route** under `frontend/src/app/` | `/dashboard/admin/idp` |
| Spec **materially changes** an existing page (new filter bar, new panel, new primary action) | Fleet filters, delegation edit drawer, health banner |

**When `frontend` impact is None/Low and no routes/pages change:** §4 may be a single **N/A** paragraph — do not pad with unchanged screens.

**Rule: Every new route or materially changed page gets at least one ASCII wireframe in §4.**

| Artifact | Requirement |
|----------|-------------|
| **§4.1 Parent references** | Table linking to canonical wireframes for **unchanged** pages (do not duplicate full parent spec wireframes) |
| **§4.2 Screen inventory (delta)** | Table: Route \| Change type (New/Modified/Extended) \| Wireframe subsection |
| **§4.N Per-screen wireframes** | ASCII box diagram + route + key interactions; for **Modified**, include Before/After or call out delta vs parent ref |
| **Cross-links** | Persona Capability bullets that are UI-facing should reference §4 subsection (e.g. "Fleet filters — §4.3") |

**Do NOT:**

- Duplicate full wireframes from a parent spec or `docs/PRODUCT_USE_CASES_BY_PERSONA.md` for unchanged pages — **link** instead
- Put the only screen layout detail in §11 Demo Scenarios (journeys reference §4; they do not replace it)
- Ship Medium/High frontend impact without at least one delta wireframe per touched route

**Wireframe parity checklist (run before VALIDATE when §4 is in scope):**

```
For each row in §4.2 Screen inventory:
  □ §4.N has ASCII wireframe with route in heading
  □ Modified pages link to parent wireframe in §4.1
  □ Key buttons, filters, tables, and error/empty states visible in ASCII
  □ §11 demo steps for that screen cite §4.N (not re-draw full layout inline)
```

Reference implementations:
- Full catalog: `docs/spec/p5.2-it-admin-service-catalog-spec.md` §4
- Delta + before/after: `docs/spec/p5.1-ui-improvements-spec.md` §4
- Gap closure (parent links): extend parent §4 — see `docs/spec/p5.2-gap-closure-spec.md` when §4 is added

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

Ask targeted questions. Group them by category. These questions are designed to surface the information needed for all 16 sections of the downstream design doc:

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

### UI / Frontend (when frontend impact ≥ Medium or new routes)
- [ ] Which routes are **new** vs **materially changed**? (→ feeds §4 Screen inventory)
- [ ] Where are **parent wireframes** for unchanged pages? (`PRODUCT_USE_CASES_BY_PERSONA.md`, parent spec §4, prior design doc)
- [ ] What are the primary UI states per screen — loading, empty, error, success? (→ feeds §4 + design doc UI Screen Designs)
- [ ] Which API endpoints populate each table, filter, or modal? (→ feeds §4 key interactions + §7 API Contracts)

### Security
- [ ] What security boundaries does this feature cross?
- [ ] What tokens/credentials are involved and how are they stored?
- [ ] What happens on unauthorized access — fail-open or fail-closed?
```

**STOP and wait for answers before proceeding to Phase 2.**

---

## Phase 2: SPECIFY — Write the Spec Document

Write a structured specification covering **all 16 sections** below. This template is designed so that `/create-design-doc` can directly transform each section into its corresponding design doc section without guessing.

**Critical rule:** If the user's input lacks detail for a section, **ask for it** (Phase 1 questions) or **infer it** from context and codebase exploration rather than leaving `[placeholder]` text. A spec with placeholders is a spec that hasn't been written yet.

**Persona rule (non-negotiable):** After drafting the Persona Capability table, **immediately** draft user-story subsections for **every persona listed** (or document N/A personas in Non-Goals). Do not finish §1 with only IT Admin stories. Run the **Persona parity checklist** (see Persona Coverage Protocol) before Phase 3.

**Semantics rule:** If requirements use shorthand ("auto-provision", "self-service", "role-based", "admin sets once"), add a **Domain Semantics** subsection in §1 clarifying system behavior and what users **do not** have to do manually.

**Wireframe rule (optional-but-expected):** When frontend impact is Medium/High or any route/page changes, draft **§4 UI Wireframes (Delta)** before finishing §5 Technical Design. Run the **Wireframe parity checklist** (see UI Wireframes Protocol) before Phase 3. Link parent wireframes; do not duplicate unchanged screens.

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

Taken from the roadmap's **"Persona Capability Timeline"** — what becomes non-broken for each persona after this spec lands. **Each row MUST link to §1 user stories** (see Persona Coverage Protocol).

| Persona | Capability Unlocked | User Stories |
|---------|---------------------|--------------|
| **Employee** | [What works for this persona after this spec lands — copy from roadmap] | [§1 Employee](#user-stories--employee) |
| **IT Admin** | [What works for this persona] | [§1 IT Admin](#user-stories--it-admin) |
| **Security Team** | [What works for this persona] | [§1 Security Team](#user-stories--security-team) |
| **Engineer / Developer** | [What works for this persona] | [§1 Engineer / Developer](#user-stories--engineer--developer) |

*Omit personas not affected by this spec — do not leave empty rows. If only IT Admin is affected, state that explicitly in Non-Goals for other personas.*

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
4. [UI Wireframes (Delta)](#4-ui-wireframes-delta)
5. [Technical Design](#5-technical-design)
6. [Data Models](#6-data-models)
7. [API Contracts](#7-api-contracts)
8. [Security Considerations](#8-security-considerations)
9. [Project Structure](#9-project-structure)
10. [Testing Strategy](#10-testing-strategy)
11. [Demo Scenarios / User Journeys](#11-demo-scenarios--user-journeys)
12. [Rollout Plan](#12-rollout-plan)
13. [Boundaries](#13-boundaries)
14. [Dependencies & Risks](#14-dependencies--risks)
15. [Open Questions](#15-open-questions)
16. [References](#16-references)

---

## 1. Objective

[What we're building and why. 2-3 sentences max.]

### User Stories / Acceptance Criteria

**MANDATORY:** Group by persona. Stories must cover **every bullet** in the Persona Capability table for that persona. Minimum **≥2 stories per persona** (≥1 if single outcome).

Stories below map 1:1 to the Persona Capability table above.

#### User Stories — IT Admin

- As an **IT Admin**, I [concrete action] so that [measurable outcome]
- As an **IT Admin**, I [concrete action] so that [measurable outcome]

#### User Stories — Employee

- As an **Employee**, I [concrete action] so that [measurable outcome]
- As an **Employee**, I [concrete action] so that [measurable outcome]

#### User Stories — Security Team

- As a **Security Team** member, I [concrete action] so that [measurable outcome]
- As a **Security Team** member, I [concrete action] so that [measurable outcome]

#### User Stories — Engineer / Developer

- As an **Engineer**, I [concrete action] so that [measurable outcome]
- As an **Engineer**, I [concrete action] so that [measurable outcome]

*Delete persona subsections that are genuinely N/A for this spec (document why in Non-Goals).*

### [Optional] Domain Semantics — [Feature Name]

> Include when behavior is ambiguous (see Persona Coverage Protocol). Example: auto-provision, role visibility, narrow-only PATCH.

[Numbered behavior, explicit "user does NOT have to…", modes table]

### Success Criteria

**MANDATORY:** Group by the same persona headings as user stories.

**IT Admin**

- [ ] [Measurable criterion]

**Employee**

- [ ] [Measurable criterion]

**Security Team**

- [ ] [Measurable criterion]

**Engineer / Developer**

- [ ] [Measurable criterion]

**All personas**

- [ ] [Cross-cutting criterion — e.g. full test suite passes]

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

## 4. UI Wireframes (Delta)

> **Scope:** ASCII wireframes for **new or materially changed** screens only. For unchanged pages, link to parent wireframes in §4.1 — do not duplicate full layouts from parent specs or product docs.
>
> **N/A template** (when `frontend` impact is None/Low and no routes change): *"No frontend changes in this spec. §4 UI Wireframes not applicable."*

### 4.1 Parent / Canonical Wireframe References

| Screen / Flow | Source Document | Section | What It Defines |
|---------------|-----------------|---------|-----------------|
| [Unchanged page name] | `docs/PRODUCT_USE_CASES_BY_PERSONA.md` or `[parent-spec].md` | §[N] | [What the canonical wireframe already specifies] |
| [Another unchanged flow] | `docs/spec/p5.2-it-admin-service-catalog-spec.md` | §4.2 | [e.g. Service Catalog table layout — unchanged by this spec] |

### 4.2 Screen Inventory (Delta)

| Route | Change | Wireframe | Primary Persona |
|-------|--------|-----------|-----------------|
| `/dashboard/[path]` | New / Modified / Extended | §4.3 | IT Admin / Employee / … |
| `/dashboard/[path]` | Modified | §4.4 | … |

### 4.3 [Page Title] (`/dashboard/[path]`)

**Change:** New | Modified | Extended
**Parent ref:** [§4.1 row if Modified; omit if New]
**Validates:** [User story IDs or capability bullets]

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  [Page Title]                                              [Primary Action]  │
├──────────────────────────────────────────────────────────────────────────────┤
│  [Filter bar / tabs / breadcrumbs as applicable]                               │
├──────────────────────────────────────────────────────────────────────────────┤
│  [Main content: table, cards, form, or split panel]                          │
│                                                                              │
│  [Key columns, status badges, row actions]                                   │
│                                                                              │
│  [Empty state CTA or error banner if applicable]                             │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Key interactions:**
- [Primary action] → [API or navigation target]
- [Filter / search] → query params or `GET` endpoint
- [Row click / expand] → [detail panel or route]
- [Error / empty state] → [when shown, what user sees]

**Modified pages — optional Before / After:**

```
BEFORE (current — [file path]):
[ASCII of current layout — abbreviated]

AFTER (this spec):
[ASCII of target layout — highlight delta]
```

### 4.4 [Next Page Title] (`/dashboard/[path]`)

[Same structure as §4.3 for each row in §4.2 Screen inventory.]

---

## 5. Technical Design

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

## 6. Data Models

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

## 7. API Contracts

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

## 8. Security Considerations

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

## 9. Project Structure

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

## 10. Testing Strategy

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

## 11. Demo Scenarios / User Journeys

[Walk through concrete user journeys that validate this feature end-to-end. These are the "test cases for the design" — if the design can't support these scenarios, it has gaps.]

**Wireframe rule:** Reference §4 for screen layout (`see §4.3`). Do **not** duplicate full ASCII wireframes here — journeys describe **steps and outcomes**, not replace §4.

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
[Same structure. **MANDATORY: one scenario per persona** listed in Persona Capability table — IT Admin, Employee, Security Team, Engineer as applicable.]

### Scenario 3: [Persona] — [Journey Title]
[Continue until every persona in the capability table has a scenario.]

### Scenario N: [Error/Edge Case]
[At least one scenario covering a failure path — expired token, missing permission, provider down, ambiguous feature branch, etc.]

---

## 12. Rollout Plan

[How is this feature delivered? Phased or all-at-once? What is usable after each phase?]

### Phase 1: [Name] (Workstream [X])
**Tasks:** WS-[X]1 through WS-[X]N
**Duration:** ~[N] sessions
**Deliverable:** [What is usable after this phase]
**Demo impact:** [How this affects existing demos or user-facing behavior]

### Phase 2: [Name] (Workstream [Y])
[Same structure]

---

## 13. Boundaries

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

## 14. Dependencies & Risks

### External Dependencies
| Dependency | Risk | Mitigation |
|------------|------|------------|
| [what] | [risk] | [mitigation] |

### Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [risk] | [H/M/L] | [H/M/L] | [plan] |

---

## 15. Open Questions
[Anything unresolved that needs human input before implementation]

- [ ] [Question 1 — with enough context to answer it]
- [ ] [Question 2]

---

## 16. References
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
| Only IT Admin stories drafted | Expand §1 + §11 for every persona in Persona Capability table; add persona-grouped success criteria |
| Ambiguous product phrase | Add Domain Semantics box (what user does NOT do manually, modes table) |
| No error responses | Infer error cases (400, 401, 403, 404, 502) from auth/validation requirements |
| New/changed routes without §4 wireframes | Add §4.2 inventory + per-route ASCII; link parent wireframes in §4.1 |
| Frontend Medium/High impact, §4 is N/A | Either justify N/A in Non-Goals or add delta wireframes per UI Wireframes Protocol |

---

## Phase 3: VALIDATE — Human Review

Present the spec for review. Include a completeness summary showing which sections have content and which need input:

```markdown
## Spec Review Checkpoint

**Feature:** [name]
**Sections completed:** [N] of 16
**Open questions:** [count]

### Persona Coverage (MANDATORY)
| Persona | Capability row | §1 User Stories | §1 Success Criteria | §11 Scenario |
|---------|----------------|-----------------|---------------------|--------------|
| IT Admin | [x] | [x] | [x] | [x] |
| Employee | [x] | [x] | [x] | [x] |
| Security Team | [x] / N/A | [x] / N/A | [x] / N/A | [x] / N/A |
| Engineer / Developer | [x] / N/A | [x] / N/A | [x] / N/A | [x] / N/A |

### UI Wireframe Coverage (when §4 in scope)
| Route | In §4.2 inventory | ASCII in §4.N | Parent ref in §4.1 |
|-------|-------------------|---------------|---------------------|
| `/dashboard/...` | [x] | [x] | [x] / N/A (new route) |

### Completeness Summary
- [x] Objective & Success Criteria (persona-grouped)
- [x] Domain Semantics box (if ambiguous features present)
- [x] Goals & Non-Goals
- [x] Background (Current State + Motivation)
- [x] UI Wireframes (Delta) — or explicit N/A with justification
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
**Sections completed:** [N] of 16
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
| "IT Admin is the primary user — other personas can wait" | Persona Capability table promises outcomes for Employee/Security/Engineer; without stories, those outcomes are unverifiable. Write all persona sections in the first draft. |
| "Everyone knows what auto-provision means" | Ambiguous phrases cause wrong implementations. Add Domain Semantics with explicit negatives (what users do NOT do manually). |
| "The API contract defines the UI" | Endpoints do not specify layout, filters, or empty states. Add §4 delta wireframes for every new/changed route. |
| "Wireframes belong in the design doc only" | `/spec` §4 captures **delta** screens early; `/create-design-doc` expands to component + API mapping. Skipping §4 delays UI review until after breakdown. |

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
- **Frontend Medium/High impact but §4 missing or N/A without justification** — wireframe parity failure
- **§4.2 lists routes but subsections lack ASCII wireframes** — incomplete delta coverage
- **Full parent wireframes duplicated in §4** instead of linking §4.1 — maintainability debt
- **Only wireframes in §11 Demo Scenarios** — layout must live in §4; journeys reference it
- **Persona Capability table lists Employee/Security/Engineer but §1 user stories are IT Admin only** — persona parity failure
- **Flat user story list** without `#### User Stories — [Persona]` headings when multiple personas are affected
- **Success criteria not grouped by persona** when multiple personas are in scope
- **Ambiguous feature (auto-provision, narrow, role-based) without Domain Semantics box**
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
- [ ] Persona Capability Unlocked table includes **User Stories** column with §1 anchor links
- [ ] Persona Capability table has a row for each affected persona (no orphan capability bullets)
- [ ] "What This Spec Unblocks" table lists downstream priorities / workstreams

**Persona coverage (MANDATORY when >1 persona affected):**
- [ ] §1 has `#### User Stories — [Persona]` for every persona in capability table
- [ ] Each persona has ≥2 user stories (≥1 if single narrow outcome) covering all capability bullets
- [ ] §1 Success Criteria grouped by same persona headings
- [ ] §11 has ≥1 demo scenario per persona in capability table
- [ ] Domain Semantics subsection present if spec uses ambiguous product language

**UI wireframes (when frontend impact ≥ Medium or routes change):**
- [ ] §4.1 parent wireframe reference table present (or §4 marked N/A with justification)
- [ ] §4.2 screen inventory lists every new/changed route
- [ ] Each inventory row has matching §4.N subsection with ASCII wireframe
- [ ] Modified pages link to parent ref; demo scenarios cite §4 (not duplicate layout)

**Content (existing checks):**
- [ ] Spec is 200+ lines (if less, depth is likely missing)
- [ ] All 16 sections present (check Table of Contents)
- [ ] Objective is specific and testable (not vague)
- [ ] Success criteria are measurable and persona-grouped when applicable
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
| 4. UI Wireframes (Delta) | UI Screen Designs | **Expand:** per-page component breakdown, API mapping table, loading/empty/error states (pattern: `docs/design/deeptrail-dashboard-core-pages.md`) |
| 5. Technical Design | Technical Design | Add Mermaid diagrams, expand code detail, add Provider Parity per feature |
| 6. Data Models | Data Models | Verify column tables are complete, add config YAML |
| 7. API Contracts | API Contracts (Canonical) | Direct transfer with CANONICAL marker |
| 8. Security Considerations | Security Considerations | Expand into subsections |
| 9. Project Structure | Implementation Workstreams | Convert file tables into task tables + file tables per workstream |
| 10. Testing Strategy | Testing Strategy | Add Technical Requirements if missing |
| 11. Demo Scenarios | Demo Scenarios / User Journeys | Expand success criteria; **reference** UI Screen Designs (do not duplicate wireframes) |
| 12. Rollout Plan | Rollout Plan | Add demo impact per phase |
| 13. Boundaries | *(absorbed into design doc conventions)* | Referenced in Boundaries or Testing |
| 14. Dependencies & Risks | *(merged into relevant sections)* | Risks → Dependencies & Risks |
| 15. Open Questions | Open Questions | Direct transfer |
| 16. References | References | Add links to plan source |

**Key insight:** The more complete the spec, the less `/create-design-doc` has to generate. Sections marked "Direct transfer" pass through unchanged. Sections marked "Expand" require the design doc command to generate depth — if the spec is skeletal here, the design doc will also be skeletal.

**Spec depth determines `/create-design-doc` effort:**

| Spec Quality | `/create-design-doc` Effort | What It Does |
|---|---|---|
| **Thorough** (500+ lines, code snippets, Mermaid diagrams, file tables, §4 wireframes) | Low — focus on 5 delta items only | Restructures Technical Design into per-feature subsections; **expands §4 into UI Screen Designs** (components, API mapping, states); converts file tables into WS-ID task tables; adds Mermaid dependency graph; verifies data model column tables |
| **Moderate** (200-500 lines, some code, some gaps) | Medium — fill gaps + 5 delta items | Generates missing diagrams, wireframes, code interfaces, error responses, then applies the 5 delta items |
| **Skeletal** (under 200 lines, placeholders) | High — full generation | Treats like a plan file — generates depth for all 16 sections |

For a thorough spec, consider whether `/create-design-doc` adds enough value to justify running it, or whether you should skip directly to `/breakdown-design` (which generates task tables and dependency analysis as part of its own workflow).

---

## Reference

This command feeds into:
- `/create-design-doc` — **Next step (mandatory).** Transforms this spec into a 16-section design doc (500–800+ lines)
- `/breakdown-design` — Reads the design doc to create workstreams (internally runs `/explore-codebase`)
- `CLAUDE.md` — Architecture patterns and conventions

See also:
- `docs/spec/p5.2-it-admin-service-catalog-spec.md` — Gold-standard **spec** §4 (full admin UI wireframes)
- `docs/spec/p5.1-ui-improvements-spec.md` — Gold-standard **spec** §4 (before/after delta wireframes)
- `docs/spec/p5.2-gap-closure-spec.md` — Gold-standard **spec** (persona-grouped stories, Domain Semantics box; add §4 delta when frontend in scope)
- `docs/design/idp-enhanced-sso-features.md` — Gold-standard design doc (what `/create-design-doc` should produce from a good spec)
- `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md` — Gold-standard design doc (persona journey depth)
- `docs/DEVELOPER_WORKFLOW.md` — Full pipeline documentation
