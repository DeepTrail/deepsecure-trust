# Re-Evaluation: Task-Scoped Permissions Architecture

> **Design Document** | Version 1.0 | April 2026
>
> A first-principles re-evaluation of DeepSecure's task-scoped permission architecture, synthesizing the current design intent, the MVP reality, the trust-model implications across agent party types, and a more generic authority-grant architecture for least-privilege execution.

---

## Executive Summary

This re-evaluation is based on a full read of the relevant task-scoping, least-privilege, party-model, MVP architecture, coverage, and permission-flow documents.

The synthesis leads to one clear conclusion:

The architecture currently has two different realities:

1. The **target design** is aiming for real task-scoped least privilege.
2. The **implemented/MVP architecture** is still session-scoped delegation with tool filtering.

The target state is explicit in the consolidated architecture:

### `deepsecure-comprehensive-architecture-consolidated.md`

```text
1. TASK CREATION
   Agent -> Control Plane: "I need to summarize Q3 sales"
2. PERMISSION SCOPING
   1. Get agent's base permissions from policy
   5. Create time-bounded scoped permissions
3. TASK TOKEN ISSUANCE
   Control Plane -> Agent: Task Token JWT
4. GATEWAY ENFORCEMENT
   Request matches scoped permission
   Constraints satisfied
5. AUTOMATIC REVOCATION
   All scoped permissions revoked
```

But the MVP coverage docs are equally clear that this does not exist today:

### `MVP_COVERAGE_MATRIX.md`

```text
## Part V: Per-Task Scoped Permissions Coverage
The full architecture implements per-task permission scoping for true least privilege.
This is entirely missing from the MVP.

Task Token Model   Scoped to single task   0%
Task Lifecycle     Create -> Execute -> Revoke   0%
Permission Request Agent requests per task       0%
Dynamic Scoping    Minimum required permissions  0%
Auto-Revocation    On task completion            0%
```

So the current situation is not "task-scoped permissions exist and need refinement." The current situation is:

- the design vocabulary for task scoping is fairly mature
- the implementation is still a session-level delegation model
- the next architecture should stop treating task-scoping as just another token layer and instead treat it as a general authority-compilation and runtime-enforcement problem

---

## Source Documents

This re-evaluation draws on the architecture set below:

- `docs/design/internal/markdowns/deepsecure-comprehensive-architecture-consolidated.md`
- `docs/design/internal/markdowns/deepsecure-least-privilege-design-for-ai-agents.md`
- `docs/design/internal/markdowns/deepsecure-least-privilege-design-synthesis-updates.md`
- `docs/workstreams/virtual-mcp-server-mvp/MVP_ARCHITECTURE_ANALYSIS.md`
- `docs/architecture/MVP_ARCHITECTURE_DEEP_DIVE.md`
- `docs/workstreams/virtual-mcp-server-mvp/MVP_COVERAGE_MATRIX.md`
- `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-use-cases.md`
- `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md`
- `docs/architecture/PERMISSION_FLOW_ARCHITECTURE.md`

---

## Table of Contents

1. [Existing Design And Architecture](#1-existing-design-and-architecture)
2. [Tradeoffs And Shortcomings](#2-tradeoffs-and-shortcomings)
3. [When The Current Design Works Best](#3-when-the-current-design-works-best)
4. [When It Falls Short](#4-when-it-falls-short)
5. [A More Generic Design For Task-Scoped Permissions](#5-a-more-generic-design-for-task-scoped-permissions)
6. [How It Should Work By Party Type](#6-how-it-should-work-by-party-type)
7. [What Truly Task-Scoped Permissions Mean](#7-what-truly-task-scoped-permissions-mean)
8. [Other Ways To Scope Permissions Beyond Task-Scoped](#8-other-ways-to-scope-permissions-beyond-task-scoped)
9. [Bottom Line](#9-bottom-line)

---

## 1. Existing Design And Architecture

The current proposed design, across the full architecture documents, has five major elements.

### 1.1 Layered authority model

The design envisions a layered chain that starts above the agent and ends at the backend resource:

- external provider scopes or service capabilities
- DeepSecure canonical permission model
- delegation token or user-granted authority
- agent session JWT
- proposed task token
- backend-specific OAuth token exchange or injected credentials

This is directionally strong because it recognizes that authority is derived, attenuated, and context-bound rather than flat.

### 1.2 Control-plane-centric PDP model

The proposed control plane is the intended policy decision point and includes:

- permission tree or DAG
- task management service
- dynamic scoping engine
- party type registry
- scoped permission store
- usage quota tracker
- constraint definition store

This gives the system a place to compute authority rather than merely store it.

### 1.3 Gateway-centric PEP model

The gateway is the intended policy enforcement point and is designed to handle:

- tool filtering
- scoped permission validation
- action control
- constraint evaluation
- JIT credential injection
- audit logging
- usage tracking

This is one of the strongest parts of the current overall architecture. DeepSecure is already thinking in terms of PDP and PEP separation.

### 1.4 Four-party trust model

The architecture correctly distinguishes between:

- **1st party self-built**
- **2nd party vendor-managed**
- **2nd party vendor-integrated**
- **3rd party SaaS / external**

That distinction matters because each category has a different combination of:

- code visibility
- runtime control
- trust assumptions
- secret exposure risk
- enforcement surface

### 1.5 MiniScope-style enhancement path

The least-privilege design synthesis proposes a path built around:

- execution graph extraction
- tool-to-permission registry
- ILP or greedy minimal-permission solving
- session modes like `allow_once` and `allow_this_session`
- permission DAGs reconstructed from provider scopes

This is conceptually sophisticated and gives the design a formal optimization path rather than an ad hoc permission list.

### 1.6 What is actually implemented today

The implemented architecture today is much simpler:

- user connects services
- user delegates a set of permissions to an agent
- agent gets a session JWT containing delegated permissions
- gateway maps tool calls to permissions and filters/enforces at runtime
- credentials stay server-side and are injected just in time
- audit is strong
- task-scoped permission issuance is absent
- scope-to-permission validation is still weak or missing in the current permission-flow architecture

That last gap matters a great deal.

### 1.7 Why the current permission-flow gap matters

The current permission-flow document explicitly calls out the problem:

### `PERMISSION_FLOW_ARCHITECTURE.md`

```text
Gap 1: No Validation of Delegation Against Connected Scopes

Connected scopes:     ["read_pages", "search_content"]
Delegated permissions:["notion:pages:search", "notion:pages:read",
                       "notion:pages:create"]  <- CREATE not in scopes!

Sarah could delegate notion:pages:create even though her Notion integration
only has "Read content" capability.

Gap 2: No Mapping Between Scope Strings and Permission Strings

There is no mapping from:
"read_pages" -> ["notion:pages:read", "notion:pages:search"]
```

So even before "true task scoping" is introduced, the authority chain below task level is not yet fully normalized.

That is an architectural signal:

- the current model still has vocabulary mismatches
- the canonical permission model is not yet fully composed across provider scope, delegation, and runtime enforcement
- task-scoped design must fix that foundation rather than stack on top of it naively

---

## 2. Tradeoffs And Shortcomings

The current proposal has strong concepts, but it also has structural tradeoffs and blind spots.

### 2.1 Summary table

| Current approach | Works best when | Falls short when |
| --- | --- | --- |
| Session-level delegated permissions | You need simple, explainable, coarse tool filtering | An agent has long sessions, multi-step plans, or mixed-risk subtasks |
| Gateway-centered enforcement | All important side effects go through MCP/API calls | The agent has local side effects, browser actions, file writes, or can exfiltrate derived data after retrieval |
| Explicit permission request model | The task can be clearly declared in advance | The agent discovers work dynamically or replans during execution |
| Execution graph + solver model | 1st-party and sandboxed 2nd-party integrated agents, where code or runtime is visible | 2nd-party vendor-managed and 3rd-party agents, where plans are hidden or untrusted |
| Party-type-specific branches | You need trust-sensitive policy differences | The core model fragments into four mostly separate systems instead of one generic authority model |
| JWT task token idea | Stateless fast checks | Revocation, quotas, usage counters, and mid-task narrowing need server state anyway |

### 2.2 Biggest architectural shortcomings

The biggest design shortcomings in the current proposal are:

#### 1. Task-scoped is treated mostly as "issue another token"

The current proposal still tends to frame task scoping as:

- declare task
- issue task token
- attach token to requests

That is necessary, but it is not sufficient.

Real task scoping needs:

- canonical authority compilation
- lineage across subtasks
- continuous narrowing
- dynamic revocation
- budget and usage tracking
- cross-channel enforcement

#### 2. There is no single canonical authority model

The current design still lacks a single authority chain that composes:

- provider scopes
- user or role ceilings
- delegation ceilings
- task ceilings
- runtime conditions

Without one canonical chain, each layer risks implementing a slightly different meaning of "allowed."

#### 3. The design over-relies on up-front declaration

For many agents, especially LLM-driven agents:

- plans are incomplete at the start
- tasks are discovered dynamically
- sub-agents may be spawned later
- the workflow shifts as evidence arrives

That means "declare exact required permissions before execution" works best for predictable automation, not for adaptive agents.

#### 4. It is much stronger on tool control than on dataflow control

The current architecture does well at:

- tool visibility
- tool call filtering
- direct API-side gating

It is weaker on:

- row-level scope
- field-level scope
- data sensitivity propagation
- output restrictions
- post-read exfiltration of derived results

#### 5. The task token is too transport-flavored

The proposed `X-Task-Token` style is too HTTP/MCP-specific.

A truly generic task authority model should work across:

- MCP tools
- browser automation
- SDK calls
- background jobs
- local file operations
- sandboxed vendor agents

So the architecture should define a generic grant model first, then adapt it to transports.

#### 6. The permission structure is not consistently DAG-first

Some docs describe a tree, others a DAG. The generic model should be DAG-first because:

- provider scopes often subsume multiple disjoint capabilities
- permissions can have multiple valid parents
- set-containment relationships are not always tree-shaped

#### 7. Task lineage is underspecified

The current proposal does not yet define:

- parent task
- subtask
- delegated subtask
- retry
- resume
- handoff
- partial completion

Without lineage, task-scoped least privilege is too shallow for real agent workflows.

---

## 3. When The Current Design Works Best

The current direction works best in environments where the execution surface is controlled and the workflow is legible.

### 3.1 Best-fit environments

The current design is strongest for:

- **1st-party self-built agents** running in your infrastructure
- **2nd-party vendor-integrated agents** running in your infrastructure with sandboxing and egress control
- **MCP/API-heavy workflows** where all meaningful side effects go through the gateway
- **enterprise onboarding and delegation** use cases where the biggest immediate wins are credential isolation, tool filtering, and audit attribution

### 3.2 Why it works well there

In those contexts:

- the execution path is more observable
- the runtime is more controllable
- the agent can be forced through known enforcement points
- the data plane is narrow enough that tool-level enforcement still buys meaningful protection

This is why the current architecture is directionally right even though it is incomplete.

---

## 4. When It Falls Short

The current proposal falls short when the trust boundary moves outside the system, when plans are dynamic, or when dataflow matters as much as tool choice.

### 4.1 Weak-fit environments

The current direction becomes much weaker for:

- **2nd-party vendor-managed agents**, because you cannot trust or inspect their internal plan
- **3rd-party SaaS agents**, because "task scoped" cannot depend on honest task declaration
- **long-running agents**, copilots, or background workers where "one task" is blurry
- **data-sensitive workflows**, where sensitivity depends on row, field, customer, or discovered context rather than just tool name
- **dynamic workflows**, where access must be narrowed continuously as the task unfolds, not only once at task start

### 4.2 Deeper reason it falls short

The deeper reason is that the architecture still assumes too much of the following:

- tasks are cleanly bounded
- required permissions can be known in advance
- all high-risk effects occur through the same gateway
- the most important security problem is tool access rather than dataflow and output control

Those assumptions hold for some automation systems, but not for the general agent case.

---

## 5. A More Generic Design For Task-Scoped Permissions

The key architectural change is this:

Stop treating task scoping as a special token layer, and instead make it a universal **authority compilation and enforcement model**.

### 5.1 Core objects

The generic model should be built on the following core objects.

#### Capability Catalog

A canonical action and resource model independent of:

- vendor-specific scopes
- tool names
- endpoint naming differences

This is the vocabulary layer.

#### Authority Sources

Every task grant should be derived from multiple ceilings:

- org policy
- role policy
- provider-granted scopes
- vendor contract
- user delegation
- runtime attestation

This is the source-of-authority layer.

#### Authority Compiler

A control-plane service that:

1. computes the effective maximum authority available to the actor
2. compiles a task-specific subset from that authority
3. emits grants that are enforceable by runtime adapters

#### Task Authority Grant

The central runtime object should be a **Task Authority Grant**, not merely a raw task token.

It should be:

- bound to `tenant`
- bound to `user` or other sponsor
- bound to `agent`
- bound to `party_type`
- bound to `runtime_attestation`
- bound to `task_id`
- bound to declared `purpose`

It should contain:

- allowed capabilities
- resource selectors
- data selectors
- budgets
- TTL
- output restrictions
- delegation rules

It should be:

- revocable
- usage-tracked
- introspectable server-side

#### Enforcement Adapters

The model should be enforced by adapters appropriate to the runtime:

- gateway
- sandbox
- edge proxy
- provider token exchange layer
- audit and trace pipeline

### 5.2 The generic authority chain

The generic chain should be:

```text
provider capability
    ->
canonical capability
    ->
user / role maximum
    ->
delegation ceiling
    ->
task authority grant
    ->
step / subtask grant
    ->
runtime decision
```

That chain generalizes across all four party types.

### 5.3 Why this is better than "Task Token Layer 4"

The current architecture places heavy emphasis on Layer 4 Task Tokens.

The better framing is:

- a signed token may carry a reference or proof for the task grant
- but the architectural primitive is the **grant**, not the token
- the grant is what holds dynamic state, budget, lineage, and revocation semantics

That is the more future-proof design.

---

## 6. How It Should Work By Party Type

The important idea is that the **grant format stays the same**, but the evidence and enforcement differ by party type.

### 6.1 Summary table

| Party type | Best generic model |
| --- | --- |
| 1st party self-built | Full task authority grants, execution-plan extraction, step/subtask narrowing, monotonic delegation |
| 2nd party vendor-integrated | Same grant model, but enforced with sandbox attestation, egress-only-via-gateway, and runtime observation instead of trusted static analysis |
| 2nd party vendor-managed | Do not pretend you have internal task scoping; issue workflow-scoped external capabilities with strict gateway mediation, short TTLs, response filtering, and audit reconciliation |
| 3rd party SaaS agents | Zero-trust edge capabilities only; tenant-bound, purpose-bound, often one-shot or short-session; never direct secret-backed internal tool access |

### 6.2 1st party self-built

This is the ideal case for true task scoping.

You can support:

- execution-plan extraction
- task and subtask lineage
- progressive narrowing
- monotonic delegation
- short-lived step grants
- rich local and gateway enforcement

This is where the current solver-heavy and execution-graph-heavy design is most realistic.

### 6.3 2nd party vendor-integrated

This is a strong but slightly weaker case than 1st party.

You cannot fully trust static analysis of the code, but you still control:

- the runtime
- the sandbox
- the network path
- the gateway
- the audit surface

So the same task grant model can still work, but it should rely more on:

- runtime observation
- sandbox attestation
- behavioral anomaly detection
- tighter egress control

### 6.4 2nd party vendor-managed

This is where the architecture must be honest.

You generally cannot do true internal task scoping because:

- you do not control the runtime
- you cannot inspect the planner
- you cannot trust internal subtask declarations

So instead of pretending otherwise, issue:

- workflow-scoped external capability grants
- short TTLs
- strict gateway mediation
- aggressive response filtering
- audit reconciliation against vendor logs

This is still valuable, but it is different from first-party task scoping.

### 6.5 3rd party SaaS agents

This is the weakest-trust scenario.

The architecture should assume:

- the agent may lie
- the agent may over-collect
- the agent may attempt exfiltration

So the right answer is:

- zero-trust edge capabilities
- strong tenant binding
- strong purpose binding
- short-lived or one-shot grants
- no direct secret-backed internal tool access

This is task-like only in the external workflow sense, not in the internal planning sense.

---

## 7. What Truly Task-Scoped Permissions Mean

A permission model is truly task-scoped only if all of the following are true.

### 7.1 Required properties

It is bound to:

- a specific task identity
- a sponsor or approving principal
- a concrete agent instance

It grants:

- only the minimum operations needed for that task
- not the full delegated or session maximum

It is constrained by:

- resource scope
- data slice
- output destination
- budget
- time window

It is non-transferable and bound to:

- proof of possession
- runtime attestation
- or other strong identity/runtime evidence

It supports:

- subtask derivation only by attenuation

It is enforced:

- continuously at runtime
- not just once at issuance

It can be revoked:

- on timeout
- on anomaly
- on offboarding
- on policy change
- on manual stop

It produces full lineage for:

- who approved it
- what it allowed
- what was actually used
- what outputs were created

### 7.2 Practical recommendation

One practical recommendation follows directly from those properties:

Do not make real task scoping a purely stateless JWT model.

Use:

- a short-lived signed grant representation
- plus server-side introspection and state

Because real task scoping needs:

- revocation
- usage counters
- step-up approval
- dynamic budgets

A pure stateless token is too weak for that job.

---

## 8. Other Ways To Scope Permissions Beyond Task-Scoped

Task scope is only one dimension. Strong systems compose several.

### 8.1 Scoping taxonomy

- **Identity-scoped**: based on who the user or agent is
- **Role-scoped**: based on org role or team
- **Session-scoped**: valid for one interactive session or conversation
- **Workflow-scoped**: valid for an entire business process or job run
- **Step-scoped**: valid only for one subtask or tool invocation
- **Resource-scoped**: limited to specific systems, objects, folders, channels, records, or tenants
- **Data-scoped**: limited to rows, fields, labels, or classifications
- **Action-scoped**: limited to exact tool or API methods
- **Purpose-scoped**: bound to declared business intent
- **Time-scoped**: TTL, business hours, expiry window
- **Budget-scoped**: max calls, rows, tokens, dollars, records changed
- **Environment-scoped**: only from approved runtime, sandbox, network, or device attestation
- **Output-scoped**: restrict where results may be sent, stored, or copied

### 8.2 Key insight

The best model is usually not:

> task scoped instead of these

It is:

> task + data + action + time + budget + runtime attestation

That is the real shape of least privilege for agents.

---

## 9. Bottom Line

The current direction is correct, but the architecture should shift from:

> task token as another layer

to:

> generic authority grant compiled from multiple ceilings and enforced by multiple adapters

### 9.1 Final conclusion by party type

For **1st-party self-built** and **2nd-party vendor-integrated** agents, true task scoping is realistic.

For **2nd-party vendor-managed** and **3rd-party SaaS** agents, you usually cannot get true internal task scoping. The right answer there is:

- externally enforced workflow or capability scoping
- shorter TTLs
- stronger mediation
- stricter output controls

### 9.2 Final architectural recommendation

The next-generation DeepSecure task-scoped architecture should be built around:

1. a canonical capability catalog
2. an authority compiler
3. a task authority grant model
4. per-party enforcement adapters
5. server-side grant introspection and revocation
6. step and subtask attenuation
7. stronger dataflow and output controls

### 9.3 Core thesis

The architecture should no longer think of task scoping as just a token.

It should think of task scoping as:

- a compiled authority boundary
- derived from multiple upstream ceilings
- bound to a concrete work unit
- attenuated over time
- enforced across multiple runtime surfaces
- and explainable through full lineage

That is the version of task-scoped least privilege that can actually scale across first-, second-, and third-party agent patterns.
