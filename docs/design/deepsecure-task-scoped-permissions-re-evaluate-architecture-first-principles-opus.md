# Re-Evaluation: Task-Scoped Permissions Architecture

> **Design Document** | Version 1.0 | April 2026
>
> A first-principles re-evaluation of the task-scoped permission model proposed across DeepSecure's architecture documents. Covers the existing design, its tradeoffs and shortcomings, how task-scoped permissions should work per agent party type, a taxonomy of scoping dimensions beyond task-scoped, and a composable permission scoping architecture.

---

## Table of Contents

1. [Existing Design and Architecture (As Proposed)](#1-existing-design-and-architecture-as-proposed)
2. [Tradeoffs and Shortcomings of the Current Proposed Design](#2-tradeoffs-and-shortcomings-of-the-current-proposed-design)
3. [How Task-Scoped Permissions Should Work Across Agent Categories](#3-how-task-scoped-permissions-should-work-across-agent-categories)
4. [Beyond Task-Scoped: A Taxonomy of Permission Scoping](#4-beyond-task-scoped-a-taxonomy-of-permission-scoping)
5. [Proposed Generic Architecture: Composable Permission Scoping](#5-proposed-generic-architecture-composable-permission-scoping)
6. [What a "Truly Task-Scoped" Permission System Looks Like](#6-what-a-truly-task-scoped-permission-system-looks-like)
7. [Summary](#7-summary)

---

## 1. Existing Design and Architecture (As Proposed)

The current design spans multiple documents and proposes a **6-layer token hierarchy** where **Task Tokens (Layer 4)** are the mechanism for per-task scoping. Here's what's been designed:

### Permission Model Stack

| Layer | Component | Status |
|-------|-----------|--------|
| Permission Hierarchy (DAG) | URN-based tree with inheritance rules (grant propagation, deny precedence, specific-overrides-general) | Designed, not implemented |
| Execution Graph Extractor | Parse agent's planned tool calls via static analysis, plan declaration, runtime observation, or LLM inference | Designed, not implemented |
| Permission Solver (ILP) | MiniScope-based Integer Linear Programming to compute minimal permission set | Designed, not implemented |
| Task Management Service | Create tasks, issue scoped permissions with TTL, auto-revoke on completion | Designed, not implemented |
| Dynamic Scoping Engine | Intersect agent base policy with requested permissions, apply constraints | Designed, not implemented |
| Constraint Engine | Temporal, volume, data, contextual constraint evaluation at gateway | Designed, not implemented |
| Session Permission Modes | Always allow, allow this session, allow once, don't allow | Designed, not implemented |
| Four-Party Enforcement | Different enforcement paths per party type (1st, 2nd-M, 2nd-I, 3rd) | Designed, not implemented |

**The MVP implements 0% of per-task permissions.** It uses session-level delegation permissions embedded in the Agent JWT, enforced at the gateway via a static Permission Mapper. This is explicitly documented as an intentional simplification:

| | Model |
|---|---|
| **Full Architecture** | Per-task scoped permissions → Task Token → auto-revoke |
| **MVP Simplification** | Per-delegation permissions → Agent Session JWT → manual expiry |

### Source Documents

This re-evaluation is based on thorough reading of:

- `deepsecure-comprehensive-architecture-consolidated.md` — Part III: Per-Task Scoped Permissions (Sections 9–11)
- `deepsecure-least-privilege-design-for-ai-agents.md` — Permission tree, per-task dynamic scoping, four-party model
- `deepsecure-least-privilege-design-synthesis-updates.md` — MiniScope framework, ILP solver, execution graph, session permission model
- `deepsecure-virtual-mcp-server-mvp.md` — MVP scope and simplifications
- `MVP_ARCHITECTURE_DEEP_DIVE.md` — Permission Mapper, session manager, credential injection
- `MVP_COVERAGE_MATRIX.md` — Coverage gaps (0% per-task permissions)
- `PERMISSION_FLOW_ARCHITECTURE.md` — Four-layer permission flow
- `deepsecure-virtual-mcp-server-use-cases.md` — Enterprise use cases

---

## 2. Tradeoffs and Shortcomings of the Current Proposed Design

### Where It Works Best

Structured, predictable **1st-party agents** with known execution plans. When an organization builds its own agent, knows the code, and can declare upfront "this task needs `notion:pages:read` and `openai:chat:completions` for 30 minutes," the full stack makes sense:

- **Static analysis** of agent code yields a reliable execution graph
- **ILP solver** computes a genuinely minimal permission set
- **Task Token** is issued, used, and revoked cleanly
- **Audit** shows exactly which permissions were used vs. granted (identifying over-provisioning)

This maps well to:
- Batch-processing agents
- Scheduled data pipeline agents
- Tightly-scoped automation bots

### Where It Falls Short

#### Shortcoming 1: The "Upfront Declaration" Problem

The design assumes agents can declare their intent before execution:

```yaml
task:
  required_permissions:
    - "urn:deepsecure:service:openai:chat_completions"
    - "urn:deepsecure:data:sales:read"
```

LLM-based agents are fundamentally **non-deterministic**. A user says "research this prospect and prepare a summary," and the agent decides *at runtime* whether it needs Notion, Slack, HubSpot, or all three. The agent cannot pre-declare an execution graph because the execution graph **emerges from LLM reasoning**.

This makes the MiniScope approach (static analysis → execution graph → ILP solver → minimal permissions) theoretically elegant but practically fragile for the most common use case: conversational, tool-calling LLM agents.

#### Shortcoming 2: The Task Boundary Problem

The design assumes clear task boundaries: **create → execute → complete**. But real agentic workflows have:

- **Nested tasks**: Agent spawns sub-agents, each needing their own scoped permissions
- **Long-running tasks**: An SDR agent runs all day, not for 30 minutes
- **Iterative tasks**: Agent tries something, gets feedback, adjusts approach, needs different tools
- **Multi-step workflows without clear completion**: "Monitor Slack and update HubSpot when relevant messages appear"

The current Task Token model doesn't address continuous workflows well. It's modeled after request-response, not event-driven or streaming patterns.

#### Shortcoming 3: The Latency vs. Security Tradeoff

The ILP solver introduces computation time (the design itself acknowledges `computation_time_ms: 45` as an example). For interactive agents where users expect sub-second responses, adding a permission computation step before every task creates visible latency. The design includes fallback algorithms (greedy set cover, precomputed sets) but doesn't resolve the fundamental tension: **the more precisely you compute minimal permissions, the slower the grant**.

#### Shortcoming 4: Execution Graph Extraction is Impractical for Most Agent Types

| Extraction Method | Applicable To | Practical? |
|---|---|---|
| Static analysis | 1st party agents with known code | Only works for deterministic agents |
| Plan declaration | All (if honest) | LLM agents can't reliably pre-plan |
| Runtime observation | All (after the fact) | Useful for audit, useless for pre-flight |
| LLM plan extraction | All | "Medium accuracy" per the design doc — not trustworthy for security decisions |

For 2nd-party vendor-managed agents, you can't see the code at all. For 3rd-party agents, you can't trust their declarations. The execution graph approach fundamentally **only works for 1st-party agents**, yet the design tries to apply it universally.

#### Shortcoming 5: Conflation of "Task" Across Agent Categories

The four-party model is well-designed, but the task model doesn't adapt per party type:

| Party Type | What "Task" Means | Implication |
|---|---|---|
| **1st-party** | A well-defined unit of work with known tools | Task Token can be precisely scoped |
| **2nd-party vendor-managed** | Opaque — you only see API calls at the gateway | Task Token is a guess at best |
| **2nd-party vendor-integrated** | Observable via sandbox monitoring but not predictable | Task Token constrains but can't be pre-computed |
| **3rd-party SaaS agents** | Whatever they claim it is — trust nothing | Task Token is meaningless if the agent lies |

Using the same Task Token mechanism for all four is an abstraction that **leaks badly at the edges**.

#### Shortcoming 6: No Progressive Permission Escalation

The current design is binary: you either get the Task Token with all scoped permissions upfront, or you don't. There's no mechanism for:

- Starting with minimal permissions and requesting more as needed
- "Step-up" authorization (like step-up MFA for sensitive operations)
- Conditional approval flows (auto-approve low-risk, human-approve high-risk, within the same task)

---

## 3. How Task-Scoped Permissions Should Work Across Agent Categories

The fundamental insight is that the **scoping mechanism must match the enforcement point**, and different agent categories have different enforcement points.

### 3.1 First-Party (Self-Built) Agents

**Enforcement points**: Code-level instrumentation, SDK integration, gateway

**Ideal scoping model**: Progressive Capability Acquisition

Instead of pre-declaring all permissions upfront, 1st-party agents should acquire capabilities progressively:

```
Agent starts with: base permissions (always available)
Agent encounters tool call → requests capability from control plane
Control plane evaluates:
  - Is this within the agent's base policy?
  - Is this within the delegator's grants?
  - Does this pass constraint checks?
  → Issues a short-lived capability (allow-once or allow-for-N-seconds)
Agent uses capability → capability consumed/expired
```

This is essentially the "allow once" session mode from MiniScope, but made the **default rather than the exception**. The SDK wraps this so the developer experience is clean:

```python
async with client.task_context("research prospect") as ctx:
    # SDK automatically acquires/releases capabilities per tool call
    pages = await ctx.call("notion.search_pages", {"query": "prospect"})
    contact = await ctx.call("hubspot.get_contact", {"id": "123"})
    # On exit: all acquired capabilities released, audit report generated
```

**Why this works for 1st-party**: You control the SDK, so you can instrument every tool call. The permission check is at the call site, not pre-flight.

### 3.2 Second-Party Vendor-Managed Agents

**Enforcement points**: Gateway only (you can't instrument their code)

**Ideal scoping model**: Budget-Bounded Capability Tokens

Since you can't see inside the agent, scope permissions as **budgets rather than plans**:

```
Delegation: "This agent can make up to 100 HubSpot reads, 10 Slack searches,
            and 0 write operations, within an 8-hour window, costing at most $5"
```

The gateway enforces budgets per capability token:

- Track call counts per tool category
- Track data volume accessed
- Track cost (for LLM calls)
- Auto-expire the token on budget exhaustion or time expiry

This doesn't require knowing *what* the agent will do — it bounds the **damage envelope**.

**Why this works for vendor-managed**: You're not trying to predict behavior (impossible), you're bounding impact. The gateway already sits in the request path and can count/limit.

### 3.3 Second-Party Vendor-Integrated Agents

**Enforcement points**: Sandbox (network policy, syscall), gateway

**Ideal scoping model**: Sandbox + Progressive Capabilities with Behavioral Monitoring

Since these agents run in your infrastructure but use vendor code (a "black box"):

1. **Sandbox** restricts the runtime environment (network egress through gateway only)
2. **Gateway** enforces permissions per tool call (like 1st-party progressive model)
3. **Behavioral monitor** builds a runtime execution graph from observed calls
4. If observed behavior deviates from expected patterns, **tighten permissions dynamically**

This is the "runtime observation" execution graph method, but used for **anomaly detection** rather than pre-flight authorization:

```
Expected: Agent reads Notion, then writes a summary
Observed: Agent reads Notion, then calls HubSpot (unexpected)
Action: Flag for review, optionally pause agent pending approval
```

**Why this works for vendor-integrated**: You have full runtime visibility. You can't do static analysis (black box), but you can observe and react.

### 3.4 Third-Party SaaS Agents

**Enforcement points**: Edge gateway only (DMZ, zero-trust)

**Ideal scoping model**: Cryptographically-Bound Capability Tokens with Maximum Constraints

Third-party agents get the most restrictive model:

- **No standing permissions** — every request requires a fresh capability token
- **Macaroon-based tokens** with caveats (time, IP, scope, rate) that can only be further attenuated, never expanded
- **Per-call or per-session tokens** — never long-lived
- **Response filtering always enabled** (PII masking, data volume limits)
- **Anomaly detection at maximum sensitivity**

```yaml
Capability Token (Macaroon):
  agent: "external-agent-xyz"
  operations: ["public_api.read"]  # Minimum possible
  caveats:
    - expires_in: 300s
    - max_calls: 50
    - ip_binding: "203.0.113.0/24"
    - rate: "10/minute"
    - response_max_size: "1MB"
  non_transferable: true
```

**Why this works for 3rd-party**: You assume malicious intent. Cryptographic binding prevents token theft. Aggressive constraints bound the damage. You're not trying to understand their task — you're minimizing exposure.

### 3.5 Comparison Across Party Types

| Dimension | 1st Party | 2nd Party (Managed) | 2nd Party (Integrated) | 3rd Party |
|---|---|---|---|---|
| **Enforcement point** | SDK + Gateway | Gateway only | Sandbox + Gateway | Edge Gateway |
| **Scoping model** | Progressive capability | Budget-bounded token | Sandbox + progressive | Crypto-bound per-call |
| **Pre-flight required?** | No (just-in-time) | Yes (token issuance) | No (sandbox enforces) | Yes (strict token) |
| **Execution graph** | Build at runtime | N/A (opaque) | Observe at runtime | N/A (zero-trust) |
| **Step-up possible?** | Yes (auto or human) | No (fixed budget) | Yes (with review) | No (fixed token) |
| **Anomaly detection** | Optional | Gateway counting | Behavioral monitoring | Maximum sensitivity |
| **Trust in declarations** | High | Medium | Medium (verified) | None |
| **Permission granularity** | Per-tool-call | Per-budget-category | Per-tool-call | Per-call |

---

## 4. Beyond Task-Scoped: A Taxonomy of Permission Scoping

"Task-scoped" is just one dimension. A truly comprehensive permission scoping architecture should support multiple **orthogonal scoping dimensions** that can be composed:

| Scoping Dimension | What It Bounds | Best For |
|---|---|---|
| **Session-scoped** | MCP session lifetime; permissions valid while session is active | Interactive agents, conversational workflows |
| **Task-scoped** | Single unit of work with clear start/end | Batch agents, scheduled jobs, defined workflows |
| **Tool-call-scoped** | Single invocation of a single tool (allow-once) | High-risk operations, sensitive data access |
| **Workflow-scoped** | Multi-task orchestration with parent scope; child tasks inherit attenuated subset | Multi-agent systems, orchestrator patterns |
| **Time-scoped** | Calendar-based windows (business hours, specific dates) | Compliance requirements, operational boundaries |
| **Resource-scoped** | Specific resource instances (this page, this contact, this channel) | Data-level access control, row-level security |
| **Purpose-scoped** | Declared intent binding (auditable, enforceable for 1st-party) | Compliance, accountability, audit |
| **Budget-scoped** | Call count, data volume, token usage, cost ceiling | Cost control, blast radius bounding |
| **Delegation-scoped** | Inherited and attenuated from delegator's permissions | Multi-party trust chains |
| **Risk-scoped** | Auto-approve low-risk, human-approve high-risk, deny critical without explicit grant | Progressive trust, step-up authorization |

### Key Architectural Insight: Composability

These dimensions should be **composable, not exclusive**. A real permission grant might be:

> "This agent can read HubSpot contacts (**tool-call-scoped** to specific contact IDs → **resource-scoped**), during business hours (**time-scoped**), up to 100 calls per day (**budget-scoped**), as part of the Q1 outreach campaign (**purpose-scoped**), with the delegation expiring in 7 days (**delegation-scoped**), and any write operations require human approval (**risk-scoped**)."

The effective permission at any moment is the **intersection of all active scopes**:

```
Effective = Session ∩ Task ∩ Time ∩ Budget ∩ Resource ∩ Delegation ∩ Risk ∩ Purpose
```

---

## 5. Proposed Generic Architecture: Composable Permission Scoping

Rather than a single "Task Token" layer, the architecture should have a **Scope Composition Engine** that constructs the effective permission set from multiple scoping dimensions:

```
COMPOSABLE PERMISSION SCOPING ARCHITECTURE
═══════════════════════════════════════════════════════════════════

  ┌──────────────────────────────────────────────────────────────┐
  │                    SCOPE COMPOSITION ENGINE                    │
  │                                                                │
  │  Inputs (evaluated in order, intersected):                     │
  │                                                                │
  │  1. Agent Base Policy      → What the agent CAN do (ceiling)   │
  │  2. Delegation Grant       → What the user ALLOWS (subset)     │
  │  3. Party-Type Constraints → What the trust model PERMITS      │
  │  4. Active Scope Stack:                                        │
  │     ┌───────────────────────────────────────────────────────┐  │
  │     │ Workflow Scope (if multi-task)                         │  │
  │     │   └── Task Scope (if task-based)                      │  │
  │     │         └── Session Scope (MCP session)               │  │
  │     │               └── Call Scope (per tool invocation)    │  │
  │     └───────────────────────────────────────────────────────┘  │
  │  5. Cross-cutting Constraints:                                 │
  │     • Time constraints (when)                                  │
  │     • Budget constraints (how much)                            │
  │     • Resource constraints (which specific resources)          │
  │     • Risk policy (auto-approve vs human-approve)              │
  │     • Purpose binding (auditable intent)                       │
  │                                                                │
  │  Output: Effective Permission Set for THIS request             │
  │                                                                │
  └──────────────────────────────────────────────────────────────┘
```

### Per Party Type: Scope Stack and Enforcement

| Party Type | Primary Scope | Enforcement Point | Pre-flight Required? |
|---|---|---|---|
| 1st Party | Progressive (session → call) | SDK + Gateway | No (just-in-time) |
| 2nd Party Vendor-Managed | Budget-bounded capability token | Gateway only | Yes (token issuance) |
| 2nd Party Vendor-Integrated | Sandbox + progressive | Sandbox + Gateway | No (sandbox enforces) |
| 3rd Party | Capability token per-call | Edge Gateway | Yes (strict token) |

### How the Engine Evaluates a Request

For every incoming tool call, the Scope Composition Engine evaluates:

```
1. Is the agent authenticated?          → Agent Base Policy lookup
2. Is the delegation active?            → Delegation Grant check
3. What party type is this agent?       → Party-Type Constraints applied
4. Walk the scope stack (outer → inner):
   a. Workflow scope active?            → Check workflow-level permissions
   b. Task scope active?               → Check task-level permissions
   c. Session scope active?            → Check session-level permissions
   d. Call scope required?             → Evaluate per-call capability
5. Check cross-cutting constraints:
   a. Within allowed time window?       → Time constraint
   b. Within budget?                    → Budget constraint (calls, cost, volume)
   c. Accessing allowed resources?      → Resource constraint (specific IDs)
   d. Risk level acceptable?            → Risk policy (auto/human/deny)
   e. Purpose declared and valid?       → Purpose binding check

Result: ALLOW (all checks pass) or DENY (any check fails, with reason)
```

---

## 6. What a "Truly Task-Scoped" Permission System Looks Like

A truly task-scoped system needs to handle the **non-deterministic nature of LLM agents**. The answer is not "predict what the agent needs" (the current design's approach), but rather **"bound what the agent can do, and let it navigate within those bounds"**:

```
TRULY TASK-SCOPED PERMISSIONS
═══════════════════════════════════════════════════════════════════

1. DECLARE BOUNDS (not exact permissions)
   "This task may need: Notion read, Slack read, possibly HubSpot read.
    Budget: 50 API calls, 10 minutes, $1 max cost."

2. ISSUE BOUNDED TOKEN
   Token permits: {notion:read, slack:read, hubspot:read}
   Caveats: max_calls=50, ttl=600s, max_cost=$1

3. PROGRESSIVE CONSUMPTION
   Agent calls notion.search → 1 call consumed, budget 49 remaining
   Agent calls slack.search → 2 calls consumed, budget 48 remaining
   Agent decides HubSpot not needed → hubspot:read permission unused
   (Audit shows: granted 3 tools, used 2 → flag for tighter future scoping)

4. STEP-UP FOR SENSITIVE
   Agent wants to write to HubSpot → not in task bounds
   → Request escalation: "Agent requests hubspot:write for task XYZ"
   → Auto-approve if low-risk, human-approve if high-risk
   → Expand bounds temporarily (logged as exception)

5. COMPLETION + LEARNING
   Task completes (agent signals, or timeout)
   → All permissions revoked
   → Audit report: granted vs. used analysis
   → Feed into future permission recommendations
      ("For similar tasks, you only need notion:read + slack:read")
```

### Why This Model is Better

This approach works across all party types because it doesn't require predicting the execution graph. It requires **bounding the damage envelope** and **tracking consumption** within those bounds.

The ILP solver becomes useful not for pre-flight computation but for **post-hoc analysis** ("what was the minimal set this agent actually needed?") to improve future bounds.

| Property | Current Design | Truly Task-Scoped |
|---|---|---|
| **Permission declaration** | Exact set upfront | Bounded envelope |
| **Consumption tracking** | None (binary grant) | Progressive (calls counted) |
| **Step-up authorization** | Not supported | Built-in (risk-tiered) |
| **Post-hoc optimization** | Not supported | Granted-vs-used analysis feeds learning |
| **Continuous workflows** | Poorly supported | Supports via rolling budgets |
| **Non-deterministic agents** | Requires plan prediction | Only requires bound estimation |

---

## 7. Summary

| Aspect | Current Design | Recommended Evolution |
|---|---|---|
| **Permission model** | Pre-declared execution graph → ILP solver → minimal set | Bounded envelope → progressive consumption → post-hoc optimization |
| **Task boundaries** | Rigid create/execute/complete lifecycle | Flexible: session, task, workflow, or continuous modes |
| **Party-type adaptation** | Same Task Token for all | Different scoping strategies per party type |
| **Scoping dimensions** | Task-scoped only | Composable: session + task + call + time + budget + resource + purpose + risk |
| **Non-deterministic agents** | Assumes plan can be extracted | Bounds the envelope, doesn't predict the plan |
| **Latency impact** | Pre-flight ILP computation | Just-in-time capability checks (cached policy) |
| **Learning/improvement** | None | Post-hoc granted-vs-used analysis feeds future bounds |

### The Core Thesis

The existing design is **strong theoretically** but optimized for a world of deterministic, plan-declaring agents. The real world of LLM-based agents needs a more adaptive approach:

> **Bound the envelope, enforce at the boundary, observe and learn.**

The shift is from:
- *"Tell me exactly what you'll do"* → *"Tell me what you're trying to achieve"*
- *"Here are your permissions, use them or lose them"* → *"Here are your bounds, navigate within them"*
- *"Predict, grant, revoke"* → *"Bound, consume, learn"*

This evolution preserves the formal security properties of the existing design (minimal authorization, monotonic attenuation, temporal boundedness, non-circumvention, complete auditability) while making the system **practically viable for the non-deterministic, multi-party agent world**.

---

*Document Version: 1.0 | April 2026 | Re-evaluation of task-scoped permissions architecture from first principles*
