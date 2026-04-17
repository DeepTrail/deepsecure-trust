# DeepSecure Intent-Based Permissions: First-Principles Architecture

> **Design Document** | Version 1.0 | April 2026
>
> A first-principles architecture for intent-based least-privilege permissions for AI agents, designed to sit above task-scoped permissions, compose across agent party types, and integrate with the existing DeepSecure control plane and gateway architecture.

---

## Executive Summary

Intent-based permissions should sit above task-scoped permissions, not replace them.

That is the central design decision of this document.

Task-scoped permissions are still necessary because side effects happen at the level of concrete execution units: a tool call, a query, a write, a send, a workflow step, a subtask. But task-scoped permissions alone are not enough for real agent systems because they only answer the question: **what is the agent allowed to do right now?**

Intent-based permissions answer the higher-order question: **what is the agent trying to achieve, what outcomes are allowed, what outcomes are prohibited, and what kinds of tasks should ever be derivable from that goal?**

This architecture treats:

- **Intent** as the semantic and governance boundary
- **Task** as the operational execution boundary
- **Step grants** as the concrete side-effect boundary

The resulting model is:

```text
User / Sponsor Intent
    ->
Intent Interpretation and Classification
    ->
Intent Authority Envelope
    ->
Task and Subtask Grants
    ->
Step / Tool / Action Grants
    ->
Runtime Verification, Drift Detection, and Revocation
```

This design preserves the strengths of task-scoped permissions while fixing their main shortcomings:

- task scopes can be too broad if the task is broad
- task boundaries are often fuzzy for long-running agents
- many agents cannot reliably predeclare their execution graph
- different agent party types expose different enforcement points

The architecture therefore separates:

- **semantic authorization**: is this within the approved purpose?
- **operational authorization**: is this concrete action currently allowed?
- **runtime trust management**: is the observed behavior still aligned?

The document defines:

1. A first-principles model for intent, tasks, actions, and authority
2. A layered architecture for intent-scoped least privilege
3. Canonical objects such as `IntentSpec`, `AuthorityEnvelope`, `TaskGrant`, and `StepGrant`
4. Party-type-specific enforcement strategies for 1st party, 2nd party vendor-managed, 2nd party vendor-integrated, and 3rd party SaaS agents
5. The algorithm families to explore for intent extraction, permission compilation, drift detection, dataflow control, and adaptive revocation
6. A concrete evolution path from the current DeepSecure MVP toward a production-grade architecture

---

## Source Context

This design builds on the current DeepSecure architecture set, especially:

- `docs/design/internal/markdowns/deepsecure-comprehensive-architecture-consolidated.md`
- `docs/design/internal/markdowns/deepsecure-least-privilege-design-for-ai-agents.md`
- `docs/design/internal/markdowns/deepsecure-least-privilege-design-synthesis-updates.md`
- `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md`
- `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-use-cases.md`
- `docs/architecture/PERMISSION_FLOW_ARCHITECTURE.md`
- `docs/architecture/MVP_ARCHITECTURE_DEEP_DIVE.md`
- `docs/workstreams/virtual-mcp-server-mvp/MVP_COVERAGE_MATRIX.md`
- `docs/design/deepsecure-task-scoped-permissions-re-evaluate-architecture-first-principles-opus.md`

This document does not discard that work. It reorganizes it under a stronger first-principles model.

---

## Table of Contents

1. [Core Thesis](#1-core-thesis)
2. [Why Intent Must Sit Above Task](#2-why-intent-must-sit-above-task)
3. [Definitions and Mental Model](#3-definitions-and-mental-model)
4. [First-Principles Security Invariants](#4-first-principles-security-invariants)
5. [Authority Stack Across the Agent System](#5-authority-stack-across-the-agent-system)
6. [Reference Architecture](#6-reference-architecture)
7. [Canonical Data Models](#7-canonical-data-models)
8. [Intent Lifecycle](#8-intent-lifecycle)
9. [Intent-Based vs Task-Scoped Permissions](#9-intent-based-vs-task-scoped-permissions)
10. [Party-Type Applicability](#10-party-type-applicability)
11. [Algorithms to Explore](#11-algorithms-to-explore)
12. [Thinking Through the Agent Stack](#12-thinking-through-the-agent-stack)
13. [Security Properties](#13-security-properties)
14. [Operational Tradeoffs](#14-operational-tradeoffs)
15. [Implementation Strategy for DeepSecure](#15-implementation-strategy-for-deepsecure)
16. [Open Questions](#16-open-questions)
17. [Summary](#17-summary)

---

## 1. Core Thesis

The core thesis is simple:

- **Intent-scoped authority defines the permissible goal space**
- **Task-scoped authority defines the permissible execution space**
- **Step-scoped authority defines the permissible immediate side effects**

This means intent-based permissions are not a replacement for task-scoped permissions. They are the layer that governs how task-scoped permissions can be derived, constrained, escalated, or revoked.

Put differently:

- Intent answers `why`
- Task answers `what now`
- Step grant answers `what exactly may happen next`

Any system that tries to do least privilege for agents using only intent will be too vague to enforce.

Any system that tries to do least privilege using only tasks will be too brittle, too local, and too easy to over-grant.

The architecture must combine both.

---

## 2. Why Intent Must Sit Above Task

### 2.1 Humans delegate goals, not permission strings

Most users do not think:

> grant `notion:pages:search`, `hubspot:contacts:read`, and `openai:chat:completions`

They think:

> research this customer and prepare a meeting brief

That means the natural delegation primitive is purpose- or intent-shaped, not task-shaped.

### 2.2 Tasks are execution artifacts, not governance artifacts

A task is usually produced by a planner, orchestrator, workflow engine, or tool-calling loop. It is already downstream of interpretation. If the interpretation is wrong, the task can still be perfectly task-scoped and still be wrong in a meaningful security sense.

Example:

- Intent: prepare an internal QBR summary
- Task: search unrelated HR docs for compensation data

That task could be mechanically well-scoped and still violate the approved purpose.

### 2.3 Intent absorbs replanning better than task models

Agents replan.

They:

- discover new data
- branch based on tool outputs
- invoke sub-agents
- retry with alternate tools
- shift from research to synthesis to mutation

A pure task model either:

- forces premature up-front declaration, or
- over-bundles permissions into a broad task token

An intent envelope can remain stable while tasks and subtasks evolve within it.

### 2.4 Intent provides better accountability

Audit logs become much more meaningful when they can answer:

- who authorized this agent?
- for what purpose?
- which tasks and actions were derived from that purpose?
- where did the behavior drift?

That is a much stronger story than task-only logging.

### 2.5 Intent is the correct place for prohibited outcomes

Many of the most important policies are not simply "allow these tools."

They are:

- do not exfiltrate customer data externally
- do not mutate CRM records without explicit approval
- do not access unrelated data domains
- do not produce outputs to unapproved destinations

Those are goal- and outcome-level constraints. They belong at the intent layer.

---

## 3. Definitions and Mental Model

### 3.1 Intent

An **intent** is a semantically meaningful objective with:

- a sponsor or accountable principal
- a goal statement
- allowed outcomes
- prohibited outcomes
- contextual constraints
- trust assumptions

Intent is not just free text. It is a structured object that may originate from:

- a human user instruction
- a workflow template
- a system-generated operational goal
- an agent-declared plan subject to validation

### 3.2 Task

A **task** is an execution unit derived from an intent.

It has:

- a narrower scope than the intent
- a bounded lifetime
- concrete capabilities and constraints
- an execution state

Tasks are operational objects. They should be attenuated children of intent authority.

### 3.3 Step

A **step** is the smallest permission-bearing unit that causes an external or durable side effect.

Examples:

- one tool call
- one SQL query
- one HTTP request
- one email send
- one file write
- one CRM update

### 3.4 Authority envelope

An **authority envelope** is the boundary of what is reasonable and permissible for a given intent.

It is not a flat permission list.

It should constrain:

- capabilities
- resources
- data classes
- allowed destinations
- time
- cost
- usage
- delegation depth
- risk escalation rules

### 3.5 Least privilege for agents

For agents, least privilege means:

- minimum authority
- minimum duration
- minimum data exposure
- minimum side-effect scope
- continuous verification
- revocation on drift or completion

---

## 4. First-Principles Security Invariants

Any intent-based permission architecture should preserve the following invariants.

### 4.1 Bounded authority

Every concrete permission must be derivable from a bounded higher-level source:

```text
Org Policy Ceiling
    >= User / Role Ceiling
    >= Provider / Service Scope Ceiling
    >= Delegation Ceiling
    >= Intent Envelope
    >= Task Grant
    >= Step Grant
```

Authority can narrow, never widen.

### 4.2 Non-circumvention

There must be no path for an agent to exercise protected authority without passing through an enforcement point under enterprise control.

### 4.3 Semantic-to-operational continuity

Every concrete action must be traceable back to:

- the intent that justified it
- the task that packaged it
- the concrete grant that allowed it

### 4.4 Revocability

All intent-, task-, and step-derived authority must be revocable:

- on timeout
- on completion
- on sponsor offboarding
- on policy change
- on anomaly or drift
- on manual kill switch

### 4.5 Output containment

It is not enough to control inputs. The system must constrain outputs and destinations, especially for external and semi-trusted agents.

### 4.6 Risk-adaptive enforcement

Higher-risk steps should require more evidence, stronger constraints, or explicit approval.

### 4.7 Full provenance

The audit system must be able to reconstruct:

- approved intent
- compiled envelope
- derived tasks
- observed behavior
- deviations
- outputs

---

## 5. Authority Stack Across the Agent System

The following is the recommended DeepSecure authority stack.

```text
Layer 0: Policy Foundation
    - Org policy
    - Role policy
    - Data classification policy
    - Party-type policy

Layer 1: Identity and Trust
    - User identity
    - Agent identity
    - Runtime attestation
    - Vendor assertion
    - External trust classification

Layer 2: Base Authority
    - Connected provider scopes
    - Role maximums
    - Delegated rights

Layer 3: Intent Authority
    - IntentSpec
    - Intent classification
    - Allowed / prohibited outcomes
    - Authority envelope

Layer 4: Task Authority
    - Task grants
    - Subtask grants
    - Per-stage narrowing

Layer 5: Step Authority
    - One-shot or short-lived step grants
    - Tool call authorization
    - Mutation approval

Layer 6: Runtime Assurance
    - Drift detection
    - Budget enforcement
    - Dataflow / provenance checks
    - Revocation
```

This stack cleanly separates meaning from execution.

---

## 6. Reference Architecture

### 6.1 High-level architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│                         CONTROL PLANE                             │
├────────────────────────────────────────────────────────────────────┤
│  Intent Registry        Capability Catalog       Policy Store     │
│  Intent Classifier      Authority Compiler       Risk Engine      │
│  Task Manager           Grant Store              Audit Correlator │
└────────────────────────────────────────────────────────────────────┘
                  │
                  │ signed grants + introspection + policy fetch
                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ENFORCEMENT ADAPTERS                           │
├────────────────────────────────────────────────────────────────────┤
│  SDK Wrapper   Orchestrator   MCP Gateway   Edge Proxy   Sandbox  │
│  Query Proxy   Output Guard   File Guard    Network Guard         │
└────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                   AGENTS AND EXTERNAL SYSTEMS                     │
├────────────────────────────────────────────────────────────────────┤
│  1st party agents                                                 │
│  2nd party vendor-integrated agents                               │
│  2nd party vendor-managed agents                                  │
│  3rd party SaaS agents                                            │
│  APIs, databases, file systems, queues, email, MCP servers        │
└────────────────────────────────────────────────────────────────────┘
```

### 6.2 Core components

#### Intent Registry

Stores:

- intent templates
- intent taxonomy
- classification labels
- allowed outcome schemas
- prohibited outcome schemas

#### Capability Catalog

A canonical registry of:

- tools
- APIs
- methods
- resources
- side effects
- data classes
- provider scope mappings

This is the canonical vocabulary layer that DeepSecure currently needs more of.

#### Authority Compiler

Compiles:

- base rights
- delegation ceilings
- party-type rules
- runtime trust evidence
- intent constraints

Into:

- `AuthorityEnvelope`
- `TaskGrant`
- `StepGrant`

#### Task Manager

Manages:

- task decomposition
- subtask creation
- task state
- progression rules
- grant issuance and revocation

#### Risk Engine

Scores:

- actions
- data access
- destinations
- mutations
- observed drift

And decides:

- allow
- allow with tighter bounds
- require approval
- deny
- suspend

#### Audit Correlator

Correlates:

- user
- agent
- intent
- task
- step
- resource
- output

This is critical for proving semantic continuity.

---

## 7. Canonical Data Models

The most important architectural improvement is to define the core objects explicitly.

### 7.1 `IntentSpec`

```yaml
intent_spec:
  intent_id: "intent-qbr-001"
  sponsor:
    user_id: "sarah@acme.com"
    org_id: "acme-corp"
    approved_by: "sarah@acme.com"

  principal:
    agent_id: "agent-sdr-001"
    party_type: "first_party"

  goal:
    title: "Prepare QBR brief"
    description: "Research Q3 performance and draft an internal review brief"

  outcome_policy:
    allowed_outcomes:
      - "internal_document_draft"
      - "internal_analytics_summary"
    prohibited_outcomes:
      - "external_email_send"
      - "crm_record_mutation"
      - "external_document_share"

  data_policy:
    allowed_domains:
      - "sales"
      - "meeting_notes"
    denied_domains:
      - "hr"
      - "legal"
    max_classification: "confidential"
    pii_access: "aggregate_only"

  destination_policy:
    allowed_destinations:
      - "storage://internal-reports/*"
      - "notion://workspace/internal/*"
    denied_destinations:
      - "email://external/*"
      - "slack://shared-channels/*"

  budgets:
    max_duration_minutes: 30
    max_tool_calls: 50
    max_cost_usd: 5
    max_rows_returned: 10000

  risk_policy:
    step_up_for:
      - "destructive_write"
      - "high_sensitivity_data"
      - "external_send"

  evidence:
    source: "user_prompt"
    confidence: 0.92
    classifier_version: "intent-classifier-v1"
```

### 7.2 `AuthorityEnvelope`

```yaml
authority_envelope:
  envelope_id: "env-abc123"
  intent_id: "intent-qbr-001"
  derived_from:
    - "org_policy:sales_rep"
    - "delegation:del-sarah-sdr-001"
    - "connected_service:notion"
    - "connected_service:hubspot"

  capability_bounds:
    allowed_capabilities:
      - "notion.page.search"
      - "notion.page.read"
      - "hubspot.deal.read"
      - "openai.chat.generate"
      - "storage.internal.write"
    denied_capabilities:
      - "hubspot.contact.update"
      - "slack.message.send"
      - "notion.page.share_external"

  resource_bounds:
    selectors:
      - service: "notion"
        path_pattern: "/workspace/qbr/**"
      - service: "hubspot"
        object_type: "deal"
        filter: "quarter = Q3"

  data_bounds:
    max_classification: "confidential"
    allowed_columns:
      - "amount"
      - "region"
      - "segment"
    denied_columns:
      - "ssn"
      - "compensation"

  output_bounds:
    allowed_output_types:
      - "internal_markdown"
      - "internal_notion_page"
    denied_output_types:
      - "external_email"
      - "public_share_link"

  temporal_bounds:
    valid_from: "2026-04-05T10:00:00Z"
    valid_until: "2026-04-05T10:30:00Z"

  adaptive_controls:
    require_approval_on_drift: true
    auto_suspend_on_high_risk: true
```

### 7.3 `TaskGrant`

```yaml
task_grant:
  task_id: "task-read-q3-data"
  parent_intent_id: "intent-qbr-001"
  purpose: "Gather Q3 sales data"
  derived_from_envelope: "env-abc123"

  permissions:
    - capability: "hubspot.deal.read"
      constraints:
        filter: "quarter = Q3"
        row_limit: 5000
    - capability: "notion.page.search"
      constraints:
        query_prefix: "QBR"

  lifecycle:
    status: "active"
    ttl_seconds: 300
    revoke_on_complete: true
```

### 7.4 `StepGrant`

```yaml
step_grant:
  step_id: "step-openai-summary-001"
  parent_task_id: "task-write-summary"
  capability: "openai.chat.generate"
  mode: "allow_once"
  constraints:
    model: "gpt-4"
    max_input_tokens: 8000
    max_output_tokens: 1500
  approval:
    required: false
```

### 7.5 `ObservedAction`

```yaml
observed_action:
  action_id: "act-001"
  agent_id: "agent-sdr-001"
  intent_id: "intent-qbr-001"
  task_id: "task-read-q3-data"
  step_id: "step-hubspot-query-001"
  capability: "hubspot.deal.read"
  resource: "hubspot://deals"
  effect_type: "read"
  data_classification: "confidential"
  destination: "internal_memory"
  timestamp: "2026-04-05T10:05:03Z"
```

---

## 8. Intent Lifecycle

The lifecycle below shows how intent-based permissions should work end to end.

### 8.1 Phase 0: identity and base authority

Before any intent is accepted, the system resolves:

- user identity
- agent identity
- party type
- provider scopes
- delegation ceilings
- runtime attestation

This forms the maximum possible authority boundary.

### 8.2 Phase 1: intent capture

Sources include:

- human prompt
- workflow template
- agent-declared objective
- operational event trigger

The system converts this into `IntentSpec`.

### 8.3 Phase 2: intent interpretation

The system:

- classifies the intent
- identifies likely capability families
- identifies prohibited action classes
- assigns risk level
- checks against policy

### 8.4 Phase 3: envelope compilation

The Authority Compiler builds the `AuthorityEnvelope` by intersecting:

- org ceiling
- user/role ceiling
- provider scope ceiling
- delegation ceiling
- party-type restrictions
- intent bounds

### 8.5 Phase 4: task derivation

The planner or orchestrator derives tasks. Each task receives a narrower `TaskGrant`.

This may happen:

- upfront for deterministic workflows
- progressively for dynamic workflows
- from observation for opaque agents

### 8.6 Phase 5: step authorization

At tool-call or side-effect time, the enforcement point validates:

- the relevant `StepGrant`, or
- the right to derive a fresh `StepGrant` from the `TaskGrant`

### 8.7 Phase 6: runtime verification

The system continuously checks:

- plan conformance
- budget adherence
- data scope adherence
- destination compliance
- intent drift

### 8.8 Phase 7: completion, suspension, or revocation

The intent and all derived grants are:

- completed and archived
- suspended pending review
- revoked due to drift or expiry

### 8.9 Lifecycle diagram

```text
Intent Capture
    ->
Classification / Risk Scoring
    ->
Authority Envelope Compilation
    ->
Task Derivation
    ->
Step Authorization
    ->
Runtime Verification
    ->
Complete / Suspend / Revoke
```

---

## 9. Intent-Based vs Task-Scoped Permissions

### 9.1 Fundamental difference

| Property | Intent-Based | Task-Scoped |
| --- | --- | --- |
| Primary question | What goal is authorized? | What execution unit is authorized? |
| Level | Semantic | Operational |
| Main artifact | `AuthorityEnvelope` | `TaskGrant` |
| Best for | Governing the whole workflow | Enforcing concrete execution |
| Failure mode | Semantic ambiguity or misclassification | Over-broad or brittle task boundary |
| Strength | Better alignment with human delegation | Better immediate enforceability |
| Weakness | Harder to prove directly | Misses goal-level policy violations |

### 9.2 Key insight

Task-scoped permissions are necessary but insufficient.

Intent-based permissions are powerful but too abstract on their own.

Therefore:

- **Intent should govern**
- **Task should operationalize**
- **Step should enforce**

### 9.3 Examples

#### Example A: internal research

Intent:

- research competitor positioning and draft internal summary

Allowed tasks:

- search Notion
- read CRM notes
- call LLM for synthesis
- write internal draft

Prohibited tasks:

- send outbound emails
- update CRM records
- share doc externally

Task-scoped alone would only protect each task locally. Intent-scoped protects the workflow boundary.

#### Example B: customer outreach workflow

Intent:

- draft outreach suggestions only

Allowed:

- read CRM
- search internal notes
- generate draft text

Not allowed:

- send messages
- update contact status

This is exactly where intent and outcome boundaries matter more than tool lists.

---

## 10. Party-Type Applicability

Intent-based permissions can work across all agent party types, but with different enforcement strength.

### 10.1 1st party self-built agents

This is the strongest fit.

Why:

- you control the code
- you control the SDK
- you can instrument planner, tool wrapper, and runtime
- you can do plan extraction and step gating

Recommended model:

- full `IntentSpec`
- `AuthorityEnvelope`
- progressive `TaskGrant`
- `allow_once` or short-lived `StepGrant`
- runtime drift detection

### 10.2 2nd party vendor-integrated agents

This is a moderate-to-strong fit.

Why:

- you control the runtime
- you may not fully control the code
- you can enforce egress through gateway
- you can monitor behavior from the sandbox and network layers

Recommended model:

- `IntentSpec`
- envelope compilation
- runtime observation
- adaptive narrowing
- strict sandbox and destination controls

### 10.3 2nd party vendor-managed agents

This is only a partial fit.

Why:

- you do not control the runtime
- you do not fully trust plan declarations
- most enforcement is at the API or gateway boundary

Recommended model:

- treat intent as a workflow-class or contract envelope
- issue short-lived external capability grants
- enforce budgets, destinations, and response filtering
- do not assume internal intent fidelity

### 10.4 3rd party SaaS agents

This is the weakest fit.

Why:

- the agent is external and largely untrusted
- declarations are weak evidence
- you only control the edge

Recommended model:

- use registered intent templates, not arbitrary free-text intent
- map intent to fixed capabilities and budgets
- enforce with edge capability tokens
- aggressively restrict outputs and data scope

### 10.5 Applicability matrix

| Party type | Intent useful? | Strong intent enforcement possible? | Main enforcement points |
| --- | --- | --- | --- |
| 1st party | Yes | Yes | SDK, planner, gateway, data layer |
| 2nd party vendor-integrated | Yes | Mostly | Sandbox, gateway, network guard |
| 2nd party vendor-managed | Yes | Partial | Gateway, contract, response filter |
| 3rd party SaaS | Limited | Weak | Edge gateway, quotas, output guard |

### 10.6 Conclusion on universality

Intent is universally useful as a governance and audit primitive.

Intent is not universally enforceable as a strong runtime truth.

That distinction must be built into the architecture.

---

## 11. Algorithms to Explore

The right architecture depends on the right algorithm families.

### 11.1 Intent normalization and classification

Goal:

- turn free-form goals into structured intent objects

Approaches:

- semantic parsing
- ontology mapping
- sequence-to-schema constrained extraction
- NLI / entailment-based label assignment
- embedding retrieval against approved intent templates

Use cases:

- classify into known workflow types
- extract prohibited actions
- identify required data domains

### 11.2 Capability graph search

Goal:

- map intent to plausible capabilities and prohibited capabilities

Approaches:

- knowledge graph traversal
- DAG search over capability-resource-effect graph
- ontology alignment between tool catalog and intent taxonomy
- constraint propagation

Use cases:

- derive the initial authority envelope
- identify what tasks are even derivable

### 11.3 Minimal permission compilation

Goal:

- given an intent and candidate plan, compute the smallest practical authority set

Approaches:

- weighted set cover
- ILP / MILP
- branch-and-bound
- SAT / SMT for richer logic
- heuristic progressive narrowing

Use cases:

- derive `TaskGrant` sets
- minimize broad envelope regions

### 11.4 Progressive planning and grant derivation

Goal:

- support dynamic workflows without over-granting upfront

Approaches:

- hierarchical task network decomposition
- partial-order planning
- receding-horizon planning
- online policy derivation

Use cases:

- issue tasks in stages
- escalate only when needed

### 11.5 Runtime conformance checking

Goal:

- verify that observed action sequences stay aligned with approved intent

Approaches:

- finite-state workflow automata
- temporal logic monitoring
- prefix-conformance checking on execution graphs
- graph edit distance from approved behavior families

Use cases:

- pause or revoke when unexpected steps appear

### 11.6 Drift and anomaly detection

Goal:

- detect behavior that is technically permitted but semantically suspicious

Approaches:

- sequence anomaly detection
- change-point detection
- Bayesian drift detection
- risk-scored policy violations
- representation-learning over tool call traces

Use cases:

- excessive browsing of unrelated data
- suspicious breadth expansion
- unusual output destinations

### 11.7 Dataflow and provenance control

Goal:

- ensure data retrieved under one intent is only used in approved ways

Approaches:

- taint tracking
- provenance graph construction
- information flow control
- policy-aware destination checks

Use cases:

- block export of sensitive data to unapproved destinations
- enforce that internal-only data stays internal

### 11.8 Output policy verification

Goal:

- control where results go and what they contain

Approaches:

- output classification
- destination allowlists
- structured output validation
- DLP-style policy checks

Use cases:

- prevent external email send
- prevent public share links
- enforce redaction

### 11.9 Risk-adaptive control

Goal:

- escalate friction only when risk rises

Approaches:

- rule-based risk scoring
- Bayesian trust updates
- contextual bandits for approval policy tuning
- human-in-the-loop triggers

Use cases:

- allow low-risk reads automatically
- require explicit approval for mutations

### 11.10 Which algorithms matter first

For DeepSecure, the likely order is:

1. intent normalization and classification
2. capability graph / catalog construction
3. progressive task derivation
4. runtime conformance and drift detection
5. provenance and output control
6. heavier optimization such as ILP / SMT

The architecture should not depend on perfect optimization at day one.

---

## 12. Thinking Through the Agent Stack

The strongest part of an intent-based design is that it forces first-principles reasoning across the entire stack rather than only at the gateway.

### 12.1 User and product layer

Questions:

- What is the user actually delegating?
- Is the delegation free-form or template-based?
- What prohibited outcomes should be captured explicitly?
- What should the approval UX look like?

Principle:

- intent capture quality is a security primitive, not just UX

### 12.2 Planner and orchestrator layer

Questions:

- Is there an explicit planner?
- Are tasks derived centrally or inside the agent?
- Can subtasks be observed and bounded?
- Can higher-risk steps be surfaced for approval?

Principle:

- the planner is the bridge between semantic authority and operational authority

### 12.3 SDK and tool layer

Questions:

- Can each tool declare capabilities, side effects, and data classes?
- Are tool wrappers enforcing pre-call checks?
- Can arguments be transformed into policy constraints?

Principle:

- the tool layer must be policy-addressable, not just callable

### 12.4 Gateway and network layer

Questions:

- Is all sensitive egress forced through DeepSecure?
- Can the gateway enforce resource, budget, and destination rules?
- Can external tokens stay hidden from agents?

Principle:

- non-circumvention is mandatory

### 12.5 Data layer

Questions:

- Can row and column constraints be enforced?
- Can data classification be attached to outputs?
- Can the system prevent joining unrelated sensitive domains?

Principle:

- least privilege must include data minimization, not just tool minimization

### 12.6 Model and prompt layer

Questions:

- Can prompt injection alter task derivation?
- Can the model coerce the system into step-up requests repeatedly?
- Can output policies be checked before delivery?

Principle:

- model behavior is part of the threat surface

### 12.7 Memory layer

Questions:

- Can the agent store sensitive intermediate results in memory?
- Does memory persist across intents?
- Are memories tagged with origin intent and classification?

Principle:

- cross-intent memory leakage breaks semantic least privilege

### 12.8 Output and action layer

Questions:

- what mutations are allowed?
- where may outputs be stored?
- what destinations are blocked?
- what actions require approval?

Principle:

- output control is as important as input control

### 12.9 Audit and analytics layer

Questions:

- can you reconstruct the full chain?
- can you explain why an action was allowed?
- can you detect drift and over-granting?

Principle:

- explainability is part of authorization quality

---

## 13. Security Properties

The architecture should aim to satisfy the following properties.

### 13.1 Intent boundedness

No task, subtask, or step grant may exceed its parent intent envelope.

### 13.2 Monotonic attenuation

All derived grants must be subsets of upstream authority.

### 13.3 Temporal boundedness

All grants must have finite life and clear revocation conditions.

### 13.4 Non-circumvention

All protected side effects must pass through a controlled enforcement point.

### 13.5 Provenance completeness

Every action must be attributable to:

- sponsor
- agent
- intent
- task
- step

### 13.6 Drift detectability

The system should be able to detect semantically suspicious sequences even if the individual calls look valid.

### 13.7 Output containment

Sensitive data must not be allowed to flow to prohibited destinations.

### 13.8 Party-type-aware trust attenuation

Weaker-trust agent categories must have stronger mediation and weaker assumptions.

---

## 14. Operational Tradeoffs

No design is free.

### 14.1 Benefits

- aligns with how humans delegate
- supports dynamic replanning
- improves audit meaning
- supports outcome-level policy
- composes with task and step grants
- works across party types with graceful degradation

### 14.2 Costs

- more policy complexity
- more metadata to define and maintain
- classifier and compiler quality matter
- runtime monitoring cost
- provenance and dataflow systems add implementation weight

### 14.3 Failure modes

- bad intent classification
- overly broad envelopes
- approval fatigue
- false positives in drift detection
- weak output controls
- missing capability catalog metadata

### 14.4 Mitigations

- start with approved intent templates
- keep humans in the loop for high-risk actions
- prefer progressive narrowing over broad upfront grants
- enforce destination controls early
- build a strong capability catalog before advanced ML logic

---

## 15. Implementation Strategy for DeepSecure

The design should evolve the current platform rather than replace it.

### 15.1 What exists today

Today DeepSecure already has:

- agent identity and session JWTs
- delegation model
- gateway enforcement
- permission mapper
- credential injection
- audit trail
- party-type thinking in the broader architecture

What is still missing in practice:

- real task token system
- rich scope-to-capability modeling
- capability catalog
- progressive grant derivation
- runtime drift detection
- output and dataflow controls

### 15.2 Recommended evolution path

#### Phase 1: canonical capability catalog

Build a shared model for:

- capability
- resource
- effect type
- data class
- provider scope mapping
- tool mapping

This should unify the current "permission mapper" and proposed "scope mapper" directionally, even if they remain deployed in separate services.

#### Phase 2: intent templates and `IntentSpec`

Add:

- approved intent templates
- structured intent schema
- simple classifier / extractor
- audit linkage from intent to session

Do not start with arbitrary unrestricted free-form intent in production.

#### Phase 3: authority envelope compiler

Add a control-plane compiler that intersects:

- role policy
- connected service scopes
- delegation ceiling
- party-type restrictions
- intent template bounds

Output:

- `AuthorityEnvelope`

#### Phase 4: progressive task grants

Layer true task-scoped permissions beneath the envelope:

- `TaskGrant`
- short TTL
- auto-revoke
- budget counters

This is where the existing task-token architecture fits cleanly.

#### Phase 5: step grants and approvals

Introduce:

- `allow_once`
- mutation approvals
- destination approvals
- high-risk data approvals

#### Phase 6: runtime drift detection

Add:

- execution trace collection
- conformance checks
- risk scoring
- automatic suspension or step-up approval

#### Phase 7: provenance and output controls

Add:

- output guard
- dataflow tracking
- destination policies
- cross-intent memory policies

### 15.3 Party-type rollout priority

Recommended order:

1. 1st party
2. 2nd party vendor-integrated
3. 3rd party edge capabilities
4. 2nd party vendor-managed

Why:

- 1st party is the easiest to instrument and validate
- vendor-integrated benefits from shared infrastructure controls
- 3rd party can use constrained templates and edge capability models
- vendor-managed requires the most trust translation and the least internal visibility

### 15.4 DeepSecure control plane changes

New recommended services:

- `IntentRegistryService`
- `CapabilityCatalogService`
- `AuthorityCompilerService`
- `IntentClassificationService`
- `TaskDerivationService`
- `RiskEvaluationService`
- `ProvenanceService`

### 15.5 DeepSecure gateway changes

New recommended middleware and guards:

- `IntentContextMiddleware`
- `TaskGrantMiddleware`
- `StepGrantValidator`
- `DestinationPolicyGuard`
- `OutputPolicyGuard`
- `RuntimeDriftSignalEmitter`

### 15.6 SDK changes

Recommended client features:

- `create_intent(...)`
- `derive_task(...)`
- `request_step_grant(...)`
- `intent_context(...)`
- `task_context(...)`
- automatic trace emission

### 15.7 Minimal production starting point

If the goal is practical delivery, the first production-worthy version should be:

- intent templates
- capability catalog
- envelope compiler
- progressive task grants
- one-shot mutation approvals
- gateway-enforced destination policies

That yields most of the strategic benefit without waiting for perfect execution-graph inference.

---

## 16. Open Questions

Several hard questions remain and should be treated as design topics rather than implementation details.

### 16.1 How free-form should intent be?

Options:

- template-only
- template plus free-form fields
- unrestricted natural language with classifier

Recommendation:

- start template-first

### 16.2 Should intent classification be authoritative?

Recommendation:

- no, classification is evidence for compilation, not the sole source of truth

### 16.3 Should grants be stateless JWTs?

Recommendation:

- use signed tokens plus server-side introspection/state for revocation, budgets, and provenance

### 16.4 How much should be done pre-flight versus just-in-time?

Recommendation:

- pre-flight for envelope compilation
- just-in-time for task and step grants

### 16.5 How should cross-intent memory be handled?

Recommendation:

- memory objects should carry origin-intent tags and data classifications

### 16.6 Can intent drift ever be tolerated?

Recommendation:

- minor drift within same approved envelope: allow and log
- major drift toward prohibited outcome: suspend or require approval

---

## 17. Summary

Intent-based permissions should govern the **purpose boundary** of agent behavior.

Task-scoped permissions should govern the **execution boundary** of agent behavior.

Step-scoped permissions should govern the **side-effect boundary** of agent behavior.

That is the cleanest first-principles model for agent least privilege.

A complete DeepSecure architecture should therefore:

- keep the existing task-scoped direction
- place it beneath an intent-scoped authority layer
- derive concrete grants progressively
- enforce at multiple points across the stack
- adapt trust assumptions by party type
- treat provenance, output control, and drift detection as first-class security controls

The most important conceptual shift is this:

**least privilege for agents is not only about minimizing the tools they can call; it is about minimizing the semantic authority they can exercise, the data they can traverse, the side effects they can produce, and the destinations to which they can carry results.**

Intent is where that higher-order boundary lives.

Task is where it becomes enforceable.

Step is where it becomes real.
