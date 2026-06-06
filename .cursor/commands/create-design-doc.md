# Create Design Doc: Transform Spec or Plan into Formal Design Document

Transform a spec file (`docs/spec/*.md`) or plan file (`plans/*.plan.md`) into a formal design document in `docs/design/`.

## Workflow Position

```
Primary path (from /spec):
/spec (produces docs/spec/*.md) → /create-design-doc → /breakdown-design → ...
                                        ↑
                                   (YOU ARE HERE)

Alternative entry (from Plan Mode):
Plan Mode (produces .plan.md) → /create-design-doc → /breakdown-design → ...
```

**Note:** `/explore-codebase` is NOT a separate step — it is embedded inside `/breakdown-design` as a mandatory pre-breakdown phase.

## When to Use

- **Primary:** You have a spec from `/spec` at `docs/spec/[feature]-spec.md` that needs to become a formal design doc
- **Alternative:** You have a `.cursor/plans/*.plan.md` or `plans/*.plan.md` file from Plan Mode
- You need to convert between formats (spec → design doc or plan → design doc)
- The spec/plan has been approved and needs to become the canonical design doc

**When NOT to use:**
- Starting from scratch with no existing spec or plan — use `/spec` first
- Spec/plan is still in exploratory phase — stay in Plan Mode or finish `/spec` first
- Design doc already exists in `docs/design/` — edit it directly

## Quality Bar

The output of this command must match the depth and structure of proven design docs in this project:
- `docs/design/deeptrail-dashboard-core-pages.md` — **UI Screen Designs** gold standard: per-page ASCII, component breakdown, API mapping, loading/empty/error states
- `docs/design/idp-enhanced-sso-features.md` — 797 lines, 3 features with full API contracts, Mermaid diagrams, code snippets, per-workstream file tables
- `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md` — 987 lines, 10-step persona journey, demo scenarios with success criteria

**The output should be 500–800+ lines, not a 200-line skeleton.** If the plan lacks detail, the command should generate the missing depth (UI screen specs from spec §4, diagrams, code interfaces, data model tables) rather than leaving placeholders.

---

## Instructions

### Step 1: Read the Source Document

```
Read the source document at the path provided by the user.

Input priority (check in this order):
  1. docs/spec/[feature]-spec.md       (primary — from /spec command)
  2. plans/[feature]_[hash].plan.md    (alternative — workspace plans)
  3. .cursor/plans/[feature]_[hash].plan.md  (alternative — Cursor plans)
```

**If input is a spec file (`docs/spec/*.md`):**

The spec already contains structured requirements across 16 sections. Determine the spec's depth:

- **Thorough spec (500+ lines, code snippets, Mermaid diagrams, file tables, §4 wireframes):** Most sections are "direct transfer." Focus generation effort on the **5 delta items** only:
  1. **Expand UI Screen Designs** from spec §4 — per-page ASCII (carry forward), **component breakdown** table, **API mapping** table, and **loading / empty / error** states (pattern: `docs/design/deeptrail-dashboard-core-pages.md`)
  2. **Restructure Technical Design** into per-feature subsections (Problem / Architecture diagram / Design Details with code / Provider Parity) — the spec may have a flat component list
  3. **Convert Project Structure into Implementation Workstreams** with formal WS-ID task tables (Task ID, Description, Dependencies, Complexity, Acceptance Criteria) + file tables per workstream
  4. **Add Dependency Graph** — Mermaid `flowchart TD` showing inter-task and inter-workstream dependencies
  5. **Verify/complete Data Models** — ensure full column tables for all models the feature reads from or writes to (not just the models being modified)

- **Skeletal spec (under 300 lines, missing sections):** Treat as a plan file — run full generation for all 16 sections.

See the [Section Mapping table in `/spec`](.cursor/commands/spec.md#section-mapping-spec--design-doc) for the exact transformation rules per section.

**If input is a plan file (`.plan.md`):**

Extract from the plan:
- **Title/Name** — from the plan's `name:` frontmatter or first heading
- **Overview** — the `overview:` frontmatter or first paragraph
- **Todos/Phases** — from the `todos:` frontmatter (structured tasks)
- **Technical decisions** — architecture choices, stack decisions, trade-offs
- **Implementation details** — directory structure, patterns, conventions
- **Current state** — what exists today (critical for `/breakdown-design`'s embedded codebase exploration)

Run full generation for all 16 sections — plan files are lightweight and require significant depth generation.

### Step 2: Determine Feature Name

Derive a kebab-case feature name for the output file:
- From spec title: "Spec: P3 — GCP Post-P2 UX Alignment" → `p3-gcp-ux-alignment`
- From plan title: "IdP Enhanced SSO Features Plan" → `idp-enhanced-sso-features`
- From plan overview: "Extend the Google and Keycloak IdP integrations..." → `idp-enhanced-sso-features`
- Or ask the user: "What should I name this design doc?"

### Step 3: Create the Design Document

**Output path:** `docs/design/[feature-name].md`

Transform the plan content into the formal design doc structure below. **This is a 16-section template** — all sections are required unless explicitly marked optional. **UI Screen Designs (§5)** is required when the spec has frontend Medium/High impact or §4 lists delta routes; otherwise mark N/A with justification. If the source document doesn't provide enough detail for a section, **generate the content** from context rather than leaving `[placeholder]` text.

```markdown
# [Feature Name] Design Document

> **Status**: Draft
> **Author**: [from source context or ask]
> **Created**: [today's date]
> **Last Updated**: [today's date]
> **Spec**: [docs/spec/[spec-file].md](../../docs/spec/[spec-file].md) *(if created from spec)*
> **Plan**: [plans/[original-plan-file].plan.md](../../plans/[original-plan-file].plan.md) *(if created from plan)*

---

## Table of Contents

1. [Overview](#overview)
2. [Goals](#goals)
3. [Non-Goals](#non-goals)
4. [Background](#background)
5. [UI Screen Designs](#ui-screen-designs)
6. [Technical Design](#technical-design)
7. [Data Models](#data-models)
8. [API Contracts (Canonical Source)](#api-contracts-canonical-source)
9. [Security Considerations](#security-considerations)
10. [Implementation Workstreams](#implementation-workstreams)
11. [Dependency Graph](#dependency-graph)
12. [Testing Strategy](#testing-strategy)
13. [Demo Scenarios / User Journeys](#demo-scenarios--user-journeys)
14. [Rollout Plan](#rollout-plan)
15. [Open Questions](#open-questions)
16. [References](#references)

---

## Overview

[1-3 paragraph summary of what this design does and why it matters. Include the end-state: what the system looks like after implementation.]

---

## Goals

- [ ] [Goal 1 — measurable outcome]
- [ ] [Goal 2 — measurable outcome]
- [ ] [Goal 3 — measurable outcome]

## Non-Goals

- **[Non-goal 1]** — [Why deferred and when to revisit]
- **[Non-goal 2]** — [Why deferred and when to revisit]

---

## Background

### Current State

[Describe what exists TODAY. This section is critical — it is the baseline that `/breakdown-design` uses (via its embedded `/explore-codebase` step) to classify tasks as Create vs. Modify vs. Verify.]

| Capability | Current Status | Notes |
|------------|----------------|-------|
| [capability 1] | Implemented / Partial / Missing | [details] |
| [capability 2] | Implemented / Partial / Missing | [details] |

[If the feature touches multiple providers/services, use a provider comparison table:]

| Capability | Provider A | Provider B |
|------------|-----------|-----------|
| [capability] | [status] | [status] |

### Motivation

1. **[Business reason 1.]** [Concrete scenario: "When X happens, users must Y, but today they have to Z..."]
2. **[Business reason 2.]** [Concrete scenario]
3. **[Business reason 3.]** [Concrete scenario]

---

## UI Screen Designs

> **Canonical UI section.** Expands spec §4 UI Wireframes (Delta) into implementation-ready screen specs. Pattern: `docs/design/deeptrail-dashboard-core-pages.md` and `docs/spec/frontend-architecture-spec.md` screen-design links.
>
> **N/A template** (backend-only spec): *"No frontend changes. UI Screen Designs not applicable."*

### Parent Wireframe References (unchanged screens)

| Screen / Flow | Source | Section | Notes |
|---------------|--------|---------|-------|
| [Unchanged page] | `docs/PRODUCT_USE_CASES_BY_PERSONA.md` or parent spec | §[N] | Linked — not redrawn here |

### Screen Inventory (this feature)

| Route | Change | Design § | Frontend file (expected) |
|-------|--------|----------|--------------------------|
| `/dashboard/[path]` | New / Modified | §5.1 | `frontend/src/app/(dashboard)/...` |

### Page: [Page Title]

**Route:** `/dashboard/[path]`
**Purpose:** [One sentence — what the user accomplishes on this screen]
**Persona:** [Primary persona]
**Spec wireframe:** [§4.N from source spec]

#### Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  [Page Title]                                              [Primary Action]  │
├──────────────────────────────────────────────────────────────────────────────┤
│  [Filters / tabs / breadcrumbs]                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  [Main content region]                                                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Component Breakdown

| Component | Props / Behavior | Source |
|-----------|------------------|--------|
| `[ComponentName]` | `[key props]` | `GET /api/v1/[endpoint]` |
| `[FilterBar]` | `filters[]`, `onChange` | Query params → list endpoint |
| `[DataTable]` | `columns[]`, `rowActions` | Response field mapping |

#### API Mapping

| UI Element | Method | Endpoint | Request / Query | Response fields used |
|------------|--------|----------|-----------------|------------------------|
| Table rows | GET | `/api/v1/[path]` | `?filter=&page=` | `[field]`, `[field]` |
| Primary action | POST | `/api/v1/[path]` | `{ ... }` | `[field]` |
| Detail panel | GET | `/api/v1/[path]/{id}` | — | `[field]` |

#### States

**Loading:** Skeleton matching table/card layout (pulsing blocks).

**Empty:** `[Illustration/message]` + CTA `[action]` → `[route or API]`.

**Error:** `ErrorCard` with `[message]` + Retry; gateway-down banner when `GET [health]` fails.

**Success / edge:** [e.g. pending invite badge, monotonic-narrow disabled controls, read-only revoked row]

### Page: [Next Page Title]

[Repeat Wireframe + Component Breakdown + API Mapping + States for each row in Screen inventory.]

---

## Technical Design

[For each major feature/component, include a subsection with: Problem, Architecture (Mermaid diagram), and Design Details (with code snippets).]

### Feature 1: [Name]

#### Problem

[What specific technical problem does this feature solve?]

#### Architecture

[Create a Mermaid sequence diagram or flowchart for this feature. Do NOT just copy from the plan — create the appropriate diagram even if the plan doesn't have one.]

` ` `mermaid
sequenceDiagram
    participant Client
    participant ControlPlane as Control Plane
    participant ExternalService as External Service

    Client->>ControlPlane: [action]
    ControlPlane->>ExternalService: [call]
    ExternalService-->>ControlPlane: [response]
    ControlPlane-->>Client: [result]
` ` `

#### Design Details

[Include code-level detail: class interfaces, function signatures, configuration. Not just descriptions — actual code showing the proposed implementation approach.]

**1. [Component Name]**

New/modified class or function in `[file-path]`:

` ` `python
class [ClassName]:
    """[Docstring explaining purpose]"""

    async def [method_name](self, [params]: [types]) -> [return_type]:
        """[What this method does]"""
        ...
` ` `

**2. [Component Name]**

[Configuration or settings changes:]

` ` `python
[field_name]: [type] = Field(
    default=[default],
    alias="[ENV_VAR_NAME]",
)
` ` `

**3. [Integration Point]**

[How this feature integrates with existing code — which file, which function, what changes:]

` ` `python
# In [file-path], after [existing-code-landmark]:
[code snippet showing integration]
` ` `

#### Provider Parity

[For features touching multiple providers (Keycloak, Google, etc.): explain how the feature works with each provider and whether any provider-specific code is needed.]

### Feature 2: [Name]

[Same structure: Problem, Architecture (Mermaid), Design Details (code), Provider Parity]

### Key Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|--------------------|--------|-----------|
| [decision 1] | A, B, C | [chosen] | [why] |

### Services Affected

| Service | Impact | Changes |
|---------|--------|---------|
| deeptrail-control | [None/Low/Medium/High] | [summary] |
| deeptrail-gateway | [None/Low/Medium/High] | [summary] |
| deepsecure (SDK) | [None/Low/Medium/High] | [summary] |
| frontend | [None/Low/Medium/High] | [summary] |

---

## Data Models

[For each new or modified model, include a full column table — NOT just "[Extract from plan]".]

### New: [ModelName]

| Column | Type | Description |
|--------|------|-------------|
| `id` | `String(64)` PK | UUID-based identifier |
| `[field]` | `[SQLAlchemy type]` | [Description, including constraints] |
| `[field]` | `[type]` | [Description] |
| `created_at` | `DateTime(timezone=True)` | When record was created |

[If the model uses encryption, note the pattern:]

Encryption uses [pattern] (symmetric key from `settings.SECRET_KEY`).

### New: [ConfigModel] (MVP: config file, not DB)

[For config-file-based models, show the YAML/JSON structure:]

` ` `yaml
# [config-file-name].yaml
[key]:
  - [field]: "[value]"
    [field]: "[value]"
    [nested_field]:
      - "[value1]"
      - "[value2]"
` ` `

### Modified: [ExistingModelName]

[Note: "No schema changes" or describe the specific modifications.]

---

## API Contracts (Canonical Source)

> **CRITICAL**: This section is the CANONICAL source for all API endpoints.
> Task tickets, tests, and implementations MUST match these exactly.

### Service: [Service Name]

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| [METHOD] | `/api/v1/[path]` | [purpose] | [auth type] |

[For each endpoint, include full request/response detail:]

#### [METHOD] /api/v1/[path]

**Request:**
` ` `
Authorization: Bearer <[token-type]>
Content-Type: application/json
` ` `

` ` `json
{
  "[field]": "[value]",
  "[field]": "[value]"
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
| 401 | [when this error occurs] |
| 403 | [when this error occurs] |
| 502 | [when this error occurs] |

[If the feature exposes MCP tools rather than REST endpoints, list those:]

**New MCP Tools (via tools/list):**

| Namespace | Tool | Arguments |
|-----------|------|-----------|
| `[service].[tool_name]` | [Description] | `[arg]: [type]` |

---

## Security Considerations

[This is a security product — every design doc MUST have this section. Include subsections for each security concern relevant to this feature.]

### [Security Concern 1: e.g., Token Storage]

- [How tokens/secrets are stored (encrypted at rest? which algorithm?)]
- [What key is used for encryption]
- [Whether values are ever exposed in API responses or logs]
- [Revocation behavior]

### [Security Concern 2: e.g., API Access Control]

- [Which scope/permission is required]
- [What happens if the scope is not authorized (fail-open vs fail-closed)]
- [Rate limiting considerations]

### [Security Concern 3: e.g., Session Security]

- [Session lifecycle (creation, refresh, revocation)]
- [Token rotation behavior]
- [Grace windows or expiry handling]

---

## Implementation Workstreams

[Group related tasks into workstreams. Each workstream includes a task table AND a files-to-modify table.]

### Workstream A: [Name] ([Service])

| Task ID | Description | Dependencies | Complexity | Acceptance Criteria |
|---------|-------------|--------------|------------|---------------------|
| WS-A1 | [description] | None | S | [criteria] |
| WS-A2 | [description] | WS-A1 | M | [criteria] |
| WS-A3 | [description] | WS-A2, WS-A3 | M | [criteria] |

**Files to modify/create:**
| File | Action |
|------|--------|
| `[service]/app/[path]/[file].py` | [Create / Modify]: [what changes] |
| `[service]/app/[path]/[file].py` | [Create / Modify]: [what changes] |
| `[service]/tests/[path]/[test_file].py` | [Create / Update]: [what tests] |

### Workstream B: [Name] ([Service])

[Same structure: task table + files table]

### Workstream C: [Name] ([Service])

[Same structure]

### Estimated Complexity

| Feature/Workstream | Complexity | Rationale |
|--------------------|------------|-----------|
| WS-A: [Name] | [S/M/L] ([N] tasks) | [Brief justification] |
| WS-B: [Name] | [S/M/L] ([N] tasks) | [Brief justification] |

---

## Dependency Graph

[Create a Mermaid flowchart showing dependencies between workstreams and tasks. This is what `/create-batch-execution-plan` relies on.]

` ` `mermaid
flowchart TD
    subgraph WSA [Workstream A: Name]
        A1["WS-A1: Description"]
        A2["WS-A2: Description"]
        A3["WS-A3: Description"]
        A1 --> A2
        A2 --> A3
    end

    subgraph WSB [Workstream B: Name]
        B1["WS-B1: Description"]
        B2["WS-B2: Description"]
        B1 --> B2
    end
` ` `

[State whether workstreams are parallel or sequential:]

All [N] workstreams are **[fully independent / partially dependent]** and can execute in [parallel / sequence]. [Workstream X] and [Workstream Y] both modify `[file]` but in [separate / overlapping] code paths.

---

## Testing Strategy

### Unit Tests

| Test | Location | What It Validates |
|------|----------|-------------------|
| `test_[name].py` | `[service]/tests/[module]/` | [What the test proves] |
| `test_[name].py` (update) | `[service]/tests/[module]/` | [What changes in existing test] |

### Integration Tests

| Test | Location | Services Required |
|------|----------|-------------------|
| [Test name] | `[service]/tests/integration/` | [Which services must be running] |

### End-to-End Tests

| Test | Location | What It Validates |
|------|----------|-------------------|
| `test_[name].py` | `tests/e2e/` (root) | [Full flow description] |

### Technical Requirements

| Requirement | Correct Pattern | Common Mistake |
|-------------|-----------------|----------------|
| Async fixtures | `@pytest_asyncio.fixture` | `@pytest.fixture` (breaks async) |
| HTTP client | `httpx.AsyncClient` | `requests` (sync) |
| Mock external APIs | `respx` or `httpx` mock | Calling live APIs in tests |

---

## Demo Scenarios / User Journeys

[Walk through concrete user journeys that exercise this feature end-to-end. These validate whether the design solves the stated problem. **Screen layout lives in §5 UI Screen Designs** — journeys reference routes and outcomes (`see §5.1`), they do not replace per-page wireframes. The gold-standard `deepsecure-virtual-mcp-server-mvp.md` pairs persona steps with screen references; backend-only features may use CLI output instead of ASCII.]

### Scenario 1: [Persona] — [Journey Title]

**Persona:** [Name, role, context — e.g., "Sarah, Security Engineer at Acme Corp"]

**Pre-conditions:** [What must exist before this journey starts]

**Steps:**

| Step | Action | System Behavior | Validates |
|------|--------|-----------------|-----------|
| 1 | [What the user does] | [What the system responds with] | [Which feature/requirement] |
| 2 | [Next action] | [Response] | [Feature] |
| 3 | [Next action] | [Response] | [Feature] |

**Expected outcome:** [What the user sees/has when done]
**Success criteria:** [How to programmatically verify this scenario passed]

**Screen reference:** [§5.N UI Screen Designs — or CLI/curl output for backend-only steps]

` ` `
# Backend-only example (when no UI):
$ curl -s ... | jq '.[field]'
→ expected value
` ` `

### Scenario 2: [Persona] — [Journey Title]

[Same structure. Include at least one scenario per primary persona affected by this feature.]

### Scenario 3: [Edge Case / Error Path]

[At least one scenario should cover a failure or edge case — e.g., expired token, revoked permission, missing provider configuration.]

---

## Rollout Plan

### Phase 1: [Name] (Workstream [X])

**Tasks:** WS-[X]1 through WS-[X]N
**Duration:** [N] tasks, ~[N] sessions
**Deliverable:** [What is usable after this phase]
**Demo impact:** [How this affects demos or user-facing behavior]

### Phase 2: [Name] (Workstream [Y])

[Same structure]

### Phase 3: [Name] (Workstream [Z])

[Same structure]

---

## Open Questions

- [ ] [Question 1 — include enough context for someone to answer it]
- [ ] [Question 2]

---

## References

- [Plan source](../../plans/[file].plan.md) — Original plan
- [Related design 1](./[related-doc].md) — [How it relates]
- [Related design 2](./[related-doc].md) — [How it relates]
- [External reference](https://...) — [What it documents]
```

### Step 4: Handle Source Document Format

**If input is a spec file (`docs/spec/*.md`):**

Spec files use markdown with 16 numbered sections. Use the [Section Mapping table](.cursor/commands/spec.md) to map each spec section to its design doc counterpart. For a thorough spec:
- Sections marked "Direct transfer" → copy with minimal reformatting
- Sections marked "Expand" → add the delta (UI Screen Designs from §4, per-feature Technical Design subsections, task tables, dependency graph, fuller code interfaces)
- Spec §4 (UI Wireframes Delta) → Design §5 (UI Screen Designs) — **mandatory expand** when frontend in scope
- Section 9 (Project Structure) → becomes Section 10 (Implementation Workstreams) — add WS-IDs, dependencies, complexity, per-task acceptance criteria

**If input is a plan file (`.plan.md`):**

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
- `overview:` → Overview section
- `todos:` → Implementation Workstreams + Rollout Plan
- `todos[].status` → Phase status
- Body content below frontmatter → Distribute across relevant sections (code snippets → Technical Design, file lists → Workstream file tables, decisions → Key Decisions table)

### Step 5: Generate Missing Depth

**Critical rule:** If the source document lacks detail for a section, **create the content** — do not leave placeholders.

**For plan files** — most sections need generation:

| Missing from Plan | What to Generate |
|-------------------|------------------|
| No architecture diagram | Create Mermaid sequence/flowchart from described flow |
| No code snippets | Write class interfaces and function signatures from described behavior |
| No data model columns | Infer column types from described fields and existing models in codebase |
| No API request/response | Write JSON examples from described endpoints |
| No security section | Analyze the feature for token handling, encryption, access control, and session lifecycle |
| No current state | Explore existing codebase to document what exists today |
| No file tables | Map described changes to actual project file paths |
| No error responses | Infer error cases (401, 403, 404, 502) from auth/validation requirements |
| No user journeys | Create persona-based walkthroughs from the feature's goals and API contracts |
| No §4 wireframes but frontend in scope | Generate §5 from routes in Project Structure + API Contracts; add ASCII + component/API tables |
| Spec §4 ASCII only | Expand §5 with component breakdown, API mapping, loading/empty/error states per page |

**For thorough spec files (500+ lines)** — focus on the 5 delta items:

| What the Spec Has | What to Add in Design Doc |
|--------------------|---------------------------|
| Spec §4 delta ASCII wireframes | §5 UI Screen Designs: component breakdown, API mapping, states per page |
| Flat "Key Components" list under Technical Design | Per-feature subsections: Problem / Architecture (Mermaid) / Design Details (code) / Provider Parity |
| Project Structure file tables (file, action, purpose) | Implementation Workstream task tables with WS-IDs, dependencies, complexity, per-task acceptance criteria |
| No dependency graph | Mermaid `flowchart TD` showing task-level and workstream-level dependencies |
| Enum/model modification tables | Full column tables for ALL models the feature reads from (not just models being modified) |
| API contracts summary | Verify error response table is present (401, 403, 404 conditions) |

### Step 6: Enrich with DeepSecure Conventions

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

**Provider parity:** For every feature section in Technical Design, include a "Provider Parity" note explaining how the feature works with Keycloak vs Google (or other providers). If no provider-specific behavior, state "No provider-specific changes needed."

### Step 7: Validate Completeness

Before saving, verify the design doc has ALL 16 required sections:

```markdown
## Design Doc Completeness Check

- [ ] Table of Contents (with anchor links)
- [ ] Section 1: Overview (1-3 paragraph summary)
- [ ] Section 2: Goals (checklist format)
- [ ] Section 3: Non-Goals (with "when to revisit")
- [ ] Section 4: Background (Current State table + Motivation)
- [ ] Section 5: UI Screen Designs (per-page ASCII + components + API mapping + states — or explicit N/A)
- [ ] Section 6: Technical Design (per-feature: Problem + Architecture diagram + Code snippets + Provider Parity)
- [ ] Section 7: Data Models (full column tables, not placeholders)
- [ ] Section 8: API Contracts (CANONICAL — full request/response/error for each endpoint)
- [ ] Section 9: Security Considerations (at least 2 subsections)
- [ ] Section 10: Implementation Workstreams (task table + files table per workstream)
- [ ] Section 11: Dependency Graph (Mermaid flowchart)
- [ ] Section 12: Testing Strategy (unit + integration + E2E tables + technical requirements)
- [ ] Section 13: Demo Scenarios / User Journeys (at least 1 per primary persona + 1 error path; reference §5)
- [ ] Section 14: Rollout Plan (per-phase duration + deliverables + demo impact)
- [ ] Section 15: Open Questions
- [ ] Section 16: References (with link back to plan source)
```

**Minimum quality gates:**
- At least 1 Mermaid diagram (sequence or flowchart)
- **When frontend in scope:** every delta route in §5 has wireframe + component table + API mapping + states
- At least 1 code snippet per feature in Technical Design
- Full column tables for every new data model
- Request + Response + Error table for every new API endpoint
- Files-to-modify table for every workstream
- At least 1 user journey per primary persona + 1 error-path scenario
- Document is 500+ lines (if less, depth is likely missing)

Flag any sections that couldn't be filled:
```markdown
### ⚠️ Sections Needing Human Input
- [ ] API Contracts — Plan did not specify endpoints
- [ ] Data Models — Plan mentions database but no schema
```

### Step 8: Save and Report

Save the design doc:
```
docs/design/[feature-name].md
```

The original source file (spec or plan) remains untouched — the design doc is a new artifact.

---

## Output Format

```markdown
## Design Doc Created ✅

**Source:** `docs/spec/[feature]-spec.md` (or `plans/[original-plan].plan.md`)
**Output:** `docs/design/[feature-name].md`

### Conversion Summary
- **Sections filled:** [N] of 16
- **UI screens documented:** [N] (wireframe + components + API mapping + states)
- **Features documented:** [N] (with code-level detail)
- **Mermaid diagrams:** [N]
- **API endpoints specified:** [N] (with full request/response/error)
- **Data models specified:** [N] (with full column tables)
- **Workstreams:** [N] (with file tables)
- **Demo scenarios:** [N] (with success criteria)
- **Open questions:** [N]

### Sections Filled
- [x] Overview
- [x] Goals & Non-Goals
- [x] Background (Current State + Motivation)
- [x] UI Screen Designs ([N] pages — or N/A)
- [x] Technical Design ([N] features with diagrams + code)
- [x] Data Models ([N] models with column tables)
- [ ] API Contracts ⚠️ [needs human input]
- [x] Security Considerations
- [x] Implementation Workstreams ([N] workstreams with file tables)
- [x] Dependency Graph (Mermaid)
- [x] Testing Strategy (with technical requirements)
- [x] Demo Scenarios / User Journeys ([N] scenarios)
- [x] Rollout Plan
- [x] Open Questions
- [x] References

### Next Steps
1. Review and enrich: `docs/design/[feature-name].md`
2. Run `/breakdown-design docs/design/[feature-name].md` to create workstreams (internally runs `/explore-codebase`)

### Pipeline Position
/spec → /create-design-doc ✅ → /breakdown-design → ...
```

---

## Example: Converting the IdP Enhanced SSO Features Plan

**Input:** `plans/idp_enhanced_sso_features_da0ea094.md`

**Output:** `docs/design/idp-enhanced-sso-features.md` (797 lines)

**What the conversion produced:**
- 16 sections with Table of Contents
- Background section with provider comparison table (Keycloak vs Google capabilities)
- 3 features in Technical Design, each with: Problem, Mermaid sequence diagram, Design Details with Python code, Provider Parity
- Full Data Models section: `IdPSession` with 11-column table + `GroupPolicy` YAML config
- API Contracts (Canonical Source): full request/response/error for `POST /auth/sso/refresh` + 9 OAuth endpoints
- Security Considerations: 4 subsections (Token Storage, Directory API, Token Isolation, Session Security)
- 3 Implementation Workstreams: each with task table (WS-IDs, complexity, acceptance) + files-to-modify table
- Mermaid dependency graph showing all workstreams
- Testing Strategy: unit + integration + E2E tables + technical requirements table
- Demo Scenarios: 3 user journeys (SSO refresh, Google Groups policy, session expiry edge case)
- Rollout Plan: 3 phases with duration, deliverables, demo impact

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "The plan is short, so the design doc should be short" | A short plan means MORE generation needed, not less. Infer data models, create diagrams, write code interfaces. |
| "I'll add code snippets later during implementation" | Without code-level design, `/breakdown-design` can't scope tasks accurately. Include interfaces NOW. |
| "Security isn't relevant to this feature" | Every feature in a security product touches auth, tokens, or data access. Write the security section. |
| "Current State isn't needed for a new feature" | Even new features replace or extend something. Document what exists today so `/breakdown-design` can validate during codebase exploration. |
| "Mermaid diagrams are optional" | Without diagrams, reviewers and downstream commands can't understand the flow. Create them. |
| "File tables can be figured out during breakdown" | `/breakdown-design` relies on file tables to scope tasks. Missing tables = over-scoped breakdown. |
| "Spec §4 has wireframes — design doc doesn't need UI section" | §4 is delta ASCII only; §5 must add components, API mapping, and states for implementers. |
| "Wireframes in demo scenarios are enough" | Journeys are flows, not screen specs. §5 is mandatory when frontend is in scope. |

## Red Flags

- Design doc under 300 lines (almost certainly missing depth)
- No Mermaid diagrams (flows are ambiguous)
- API Contracts with only a summary table (no request/response/error detail)
- Data Models section says "[Extract from plan]" (placeholder was not replaced)
- No Security Considerations section (every feature needs one)
- No Current State / Background section (baseline unknown)
- No files-to-modify tables in workstreams (breakdown can't scope)
- No code snippets in Technical Design (implementation approach unclear)
- No Demo Scenarios / User Journeys (design can't be validated against real usage)
- No error-path scenario (only happy paths = incomplete design)
- **Frontend in scope but §5 UI Screen Designs missing or N/A without justification**
- **§5 pages lack component breakdown or API mapping tables** (ASCII alone is spec-level, not design-level)
- **Demo scenarios duplicate full wireframes** instead of referencing §5

## Verification

Before declaring the design doc complete:

- [ ] Document is 500+ lines
- [ ] All 16 sections present (check Table of Contents)
- [ ] At least 1 Mermaid diagram exists
- [ ] Every new data model has a full column table
- [ ] Every new API endpoint has request + response + error detail
- [ ] Every workstream has a files-to-modify table
- [ ] Security Considerations has at least 2 subsections
- [ ] Background / Current State documents what exists today
- [ ] Technical Design features include code snippets
- [ ] Provider Parity noted for features touching multiple providers
- [ ] At least 1 user journey per primary persona
- [ ] At least 1 error-path / edge-case scenario
- [ ] **UI (when in scope):** each delta route has §5 page with wireframe, component table, API mapping, states
- [ ] Demo scenarios reference §5 screen subsections (no duplicate full ASCII layouts)

---

## Reference

This command integrates with:
- `/spec` — **Prior step (primary).** Creates the spec at `docs/spec/[feature]-spec.md` that this command transforms
- Plan Mode — **Alternative entry.** Creates `.plan.md` files this command can also read
- `/breakdown-design` — **Next step.** Reads workstream file tables and dependency graph to create tasks (internally runs `/explore-codebase`)
- `.cursorrules` → Plan file location rules (must be in `plans/` directory)

**Input sources (in priority order):**
1. `docs/spec/[feature]-spec.md` — Primary input from `/spec`
2. `plans/[feature]_[hash].plan.md` — From Plan Mode or `CreatePlan` tool
3. `.cursor/plans/[feature]_[hash].plan.md` — From `CreatePlan` tool (should be moved to `plans/` per workspace rules)

See also:
- `docs/design/deeptrail-dashboard-core-pages.md` — Gold-standard **UI Screen Designs** (wireframe + components + API mapping + states)
- `docs/design/idp-enhanced-sso-features.md` — Gold-standard design doc (797 lines)
- `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md` — Gold-standard design doc (persona journey, 987 lines)
- `docs/spec/p5.2-it-admin-service-catalog-spec.md` §4 — Gold-standard spec §4 wireframes (input to design §5)
- `docs/spec/p5.1-ui-improvements-spec.md` §4 — Gold-standard delta/before-after wireframes
- `CLAUDE.md` → "Codebase Exploration Before Breakdown (CRITICAL)"
- `docs/DEVELOPER_WORKFLOW.md` → Phase 0: Define
