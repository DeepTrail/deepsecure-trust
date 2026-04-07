# Intent-Based Permissions: First-Principles Architecture

> **Design Document** | Version 1.0 | April 2026
>
> A first-principles exploration of intent-based permission scoping for AI agents across all party types, contrasted with task-scoped permissions, with key algorithms, composable scoping dimensions, and a layered enforcement architecture.

---

## Executive Summary

This document presents a comprehensive architecture for **intent-based permissions** — a paradigm shift from the task-scoped permission model described in the existing DeepSecure design documents. Where task-scoped permissions ask an agent *"What operations will you perform?"*, intent-based permissions ask *"What are you trying to achieve?"*

This distinction is fundamental. LLM-based agents are non-deterministic: they cannot reliably pre-declare an execution graph because the execution path emerges from reasoning at runtime. Intent-based permissions embrace this non-determinism by **bounding the goal space rather than the execution path**, enabling least-privilege enforcement that works with the agentic paradigm rather than against it.

The architecture:
1. Defines a precise ontological distinction between **intent** and **task**
2. Introduces a **6-layer Intent Permission Stack** (Declaration → Classification → Envelope → Enforcement → Verification → Learning)
3. Specifies key algorithms for each layer (causal inference, sequential anomaly detection, information-theoretic minimization, LLM-as-judge alignment)
4. Adapts the intent model per **agent party type** (1st party, 2nd party vendor-managed, 2nd party vendor-integrated, 3rd party)
5. Proposes **composable scoping dimensions** beyond task-scoped (session, workflow, tool-call, time, resource, purpose, budget, delegation, risk)
6. Provides a concrete comparison showing when intent-based outperforms task-based and vice versa

### Source Documents (Prerequisites)

This document builds on and references:
- `deepsecure-comprehensive-architecture-consolidated.md` — Part III: Per-Task Scoped Permissions
- `deepsecure-least-privilege-design-for-ai-agents.md` — Four-party model, permission tree, per-task dynamic scoping
- `deepsecure-least-privilege-design-synthesis-updates.md` — MiniScope framework, ILP solver, execution graph
- `deepsecure-virtual-mcp-server-mvp.md` — MVP token flow and simplifications
- `PERMISSION_FLOW_ARCHITECTURE.md` — Four-layer permission flow (Notion capabilities → tool access)
- `MVP_ARCHITECTURE_DEEP_DIVE.md` — Permission Mapper, session manager, credential injection
- `MVP_COVERAGE_MATRIX.md` — Coverage gaps including 0% per-task permissions
- `deepsecure-virtual-mcp-server-use-cases.md` — Vendor integration, enterprise onboarding, MCP rollout

---

## Table of Contents

1. [The Foundational Distinction: Intent vs. Task](#1-the-foundational-distinction-intent-vs-task)
2. [Why Task-Scoped Permissions Fall Short](#2-why-task-scoped-permissions-fall-short)
3. [The Intent Hierarchy: Reasoning Through the Agent Stack](#3-the-intent-hierarchy-reasoning-through-the-agent-stack)
4. [Intent-Based Permission Architecture](#4-intent-based-permission-architecture)
5. [The Six-Layer Intent Permission Stack](#5-the-six-layer-intent-permission-stack)
6. [Key Algorithms for Intent-Based Least-Privilege](#6-key-algorithms-for-intent-based-least-privilege)
7. [Intent-Based Permissions Across Agent Party Types](#7-intent-based-permissions-across-agent-party-types)
8. [Beyond Task-Scoped: A Taxonomy of Permission Scoping Dimensions](#8-beyond-task-scoped-a-taxonomy-of-permission-scoping-dimensions)
9. [Composable Permission Scoping Architecture](#9-composable-permission-scoping-architecture)
10. [Intent-Based vs. Task-Based: Decision Matrix](#10-intent-based-vs-task-based-decision-matrix)
11. [What "Truly Task-Scoped" Should Look Like](#11-what-truly-task-scoped-should-look-like)
12. [Current Design Tradeoffs and Shortcomings](#12-current-design-tradeoffs-and-shortcomings)
13. [Research Directions and Algorithm Roadmap](#13-research-directions-and-algorithm-roadmap)
14. [Implementation Considerations](#14-implementation-considerations)

---

## 1. The Foundational Distinction: Intent vs. Task

Before designing any architecture, we must be precise about what "intent" means and how it fundamentally differs from "task" at the conceptual level.

**A task is mechanistic**: "Call `notion.search_pages` with query 'Q3 sales', then call `openai.chat.completions` to summarize results." A task describes *what to do* — a sequence of operations.

**An intent is teleological**: "Help me prepare for my quarterly business review." An intent describes *what to achieve* — a goal with success criteria.

### 1.1 Ontological Comparison

| Property | Task-Scoped | Intent-Scoped |
|---|---|---|
| **Nature** | Mechanistic (how) | Teleological (why) |
| **Permission derivation** | Bottom-up: enumerate tool calls → derive needed permissions | Top-down: understand goal → infer reasonable permission envelope |
| **When permissions are known** | Before execution (pre-declaration) | Emerges during execution (progressive) |
| **What you verify** | "Did the agent only use declared tools?" | "Were the agent's actions consistent with the stated purpose?" |
| **Failure mode** | Under-specification (agent can't complete task) or over-specification (agent gets more than needed) | Misalignment (agent pursues a different goal than stated) |
| **Who bears the burden** | The agent (must predict its own needs) | The system (must understand and bound the goal) |
| **Temporal model** | Fixed window: start → execute → complete | Evolving: intent may refine, decompose, or shift as the agent learns |
| **Relationship to non-determinism** | Fights it (tries to predict the execution path) | Embraces it (bounds the goal space, not the execution path) |
| **Expressiveness** | Low (list of permissions) | High (natural language + structured metadata) |
| **User-friendliness** | Requires technical knowledge of tools/permissions | Matches how humans naturally think about delegation |

### 1.2 The Core Insight

**Task-scoped permissions try to constrain the path; intent-scoped permissions constrain the destination.**

Constraining the destination is both:
- **More permissive**: any path to the goal is acceptable (the agent has flexibility)
- **More restrictive**: paths that don't lead toward the goal are flagged, even if they use "permitted" tools (the system detects misalignment)

A task token that grants `notion:read` + `hubspot:read` permits reading *anything* in Notion or HubSpot, even if it's unrelated to the task. An intent-scoped permission for "QBR preparation" would flag excessive reading of unrelated Notion pages because it's behaviorally inconsistent with preparation, even though `notion:read` is technically within the envelope.

---

## 2. Why Task-Scoped Permissions Fall Short

The existing design (documented in `deepsecure-comprehensive-architecture-consolidated.md`, Part III and `deepsecure-least-privilege-design-for-ai-agents.md`, Section 4) proposes task-scoped permissions built on:

1. **Execution Graph Extraction** — Parse the agent's planned tool calls
2. **ILP Solver (MiniScope)** — Compute minimal permission set via Integer Linear Programming
3. **Task Token** — Issue a time-bounded token with scoped permissions
4. **Auto-revocation** — Revoke all permissions on task completion

This design has five structural shortcomings when applied to real-world agent deployments:

### 2.1 The Upfront Declaration Problem

The design assumes agents can declare their intent before execution:

```yaml
task:
  required_permissions:
    - "urn:deepsecure:service:openai:chat_completions"
    - "urn:deepsecure:data:sales:read"
```

LLM-based agents are fundamentally non-deterministic. A user says "research this prospect and prepare a summary," and the agent decides at runtime whether it needs Notion, Slack, HubSpot, or all three. The agent cannot pre-declare an execution graph because the execution graph emerges from LLM reasoning.

This makes the MiniScope approach (static analysis → execution graph → ILP solver → minimal permissions) theoretically elegant but practically fragile for the most common use case: conversational, tool-calling LLM agents.

### 2.2 The Task Boundary Problem

The design assumes clear task boundaries: create → execute → complete. But real agentic workflows have:

- **Nested tasks**: Agent spawns sub-agents, each needing their own scoped permissions
- **Long-running tasks**: An SDR agent runs all day, not for 30 minutes
- **Iterative tasks**: Agent tries something, gets feedback, adjusts approach, needs different tools
- **Continuous workflows**: "Monitor Slack and update HubSpot when relevant messages appear"

The Task Token model doesn't address continuous workflows well. It's modeled after request-response, not event-driven or streaming patterns.

### 2.3 The Latency vs. Security Tradeoff

The ILP solver introduces computation time (the design itself acknowledges `computation_time_ms: 45` as a typical value). For interactive agents where users expect sub-second responses, adding a permission computation step before every task creates visible latency. The design includes fallback algorithms (greedy set cover, precomputed sets) but doesn't resolve the fundamental tension: the more precisely you compute minimal permissions, the slower the grant.

### 2.4 Execution Graph Extraction is Impractical for Most Agent Types

| Extraction Method | Applicable To | Practical? |
|---|---|---|
| Static analysis | 1st party agents with known code | Only works for deterministic agents |
| Plan declaration | All (if honest) | LLM agents can't reliably pre-plan |
| Runtime observation | All (after the fact) | Useful for audit, useless for pre-flight |
| LLM plan extraction | All | "Medium accuracy" per the design doc — not trustworthy for security decisions |

For 2nd-party vendor-managed agents, you can't see the code at all. For 3rd-party agents, you can't trust their declarations. The execution graph approach fundamentally only works for 1st-party agents with deterministic behavior, yet the design attempts to apply it universally.

### 2.5 No Progressive Permission Escalation

The current design is binary: you either get the Task Token with all scoped permissions upfront, or you don't. There's no mechanism for:

- Starting with minimal permissions and requesting more as needed
- "Step-up" authorization (like step-up MFA for sensitive operations)
- Conditional approval flows (auto-approve low-risk, human-approve high-risk, within the same execution context)

---

## 3. The Intent Hierarchy: Reasoning Through the Agent Stack

Intent exists at multiple levels of the agent stack. A robust intent-based permission system must reason about all of them.

```
INTENT HIERARCHY (from human to machine)
═══════════════════════════════════════════════════════════════════

Level 0: USER INTENT (ground truth, but ambiguous)
─────────────────────────────────────────────────
"Prepare me for my QBR meeting with the VP next Thursday"
│
│  The human knows what they want but expresses it imprecisely.
│  This is the NORMATIVE authority — what SHOULD happen.
│
▼
Level 1: INTERPRETED INTENT (agent's understanding)
─────────────────────────────────────────────────────
Agent interprets: "I need to:
  - Find Q3 sales numbers (Notion/HubSpot)
  - Check calendar for meeting details (Calendar)
  - Draft talking points (OpenAI)
  - Maybe update a Notion page with the prep doc"
│
│  The agent's interpretation may be correct, partially correct,
│  or subtly wrong. This is where ALIGNMENT risk lives.
│
▼
Level 2: DECOMPOSED SUB-INTENTS (planning)
──────────────────────────────────────────
Sub-intent A: "Gather sales data"     → needs: HubSpot read, Notion read
Sub-intent B: "Understand meeting"    → needs: Calendar read
Sub-intent C: "Generate content"      → needs: OpenAI chat
Sub-intent D: "Store results"         → needs: Notion write
│
│  Each sub-intent has a tighter permission envelope than the
│  parent intent. Decomposition ATTENUATES.
│
▼
Level 3: TOOL-CALL INTENT (execution)
─────────────────────────────────────
Call: notion.search_pages(query="Q3 sales")
  └── Intent: "Find the Q3 sales report page"
Call: hubspot.get_contacts(filter="closed_won, Q3")
  └── Intent: "Get list of deals closed in Q3"
Call: openai.chat(messages=[...sales data...])
  └── Intent: "Summarize this data into talking points"
│
│  Each tool call has an implicit intent. If the CALL INTENT
│  doesn't align with the SUB-INTENT, something is wrong.
│
▼
Level 4: SYSTEM-OBSERVED INTENT (behavioral inference)
──────────────────────────────────────────────────────
The system observes the PATTERN of calls and infers:
  "This looks like a data-gathering-and-summarization workflow"
  vs.
  "This looks like a data-exfiltration pattern"

│  This is where ANOMALY DETECTION operates.
│  The system doesn't need the agent to declare intent —
│  it infers intent from behavior and checks alignment.
```

### 3.1 Key Principle: Bidirectional Flow

Permission decisions flow **DOWN** this hierarchy (each level attenuates permissions), while verification flows **UP** (observed behavior is checked against declared intent at each level).

```
Permission Grant:    User Intent → Interpreted → Sub-Intents → Tool Calls
                     (broadest)                                (narrowest)
                     
Verification:        Tool Calls → Sub-Intents → Interpreted → User Intent
                     (concrete)                                (abstract)
                     "Were these calls consistent with the stated goal?"
```

---

## 4. Intent-Based Permission Architecture

### 4.1 The Permission Grant Model Comparison

**Task-scoped** (current design):
```
Agent → "I need permissions [A, B, C] for task T"
System → Validates A, B, C against policy → Issues Task Token
Agent → Uses A, B, C (or subset) → Task complete → Token revoked
```

**Intent-scoped** (proposed):
```
Agent → "My intent is I (natural language + structured metadata)"
System → Classifies I → Derives permission envelope E(I) → Issues Intent Token
Agent → Requests capability from E(I) per tool call → System grants/denies in real-time
        If request falls outside E(I) → Step-up: expand envelope or deny
Agent → Signals intent fulfilled → Token revoked
System → Post-hoc: verifies actions aligned with I → Feeds learning loop
```

The critical architectural difference: the permission envelope is derived from the intent, not from the agent's self-declared needs. The agent doesn't say "I need HubSpot read access." The system says "given your stated intent of QBR preparation, HubSpot read access is within the reasonable envelope."

### 4.2 The Permission Envelope Concept

A **permission envelope** is not a permission set. It is a bounded region in permission space that represents "what is reasonable for this intent."

```
PERMISSION SPACE (all possible permissions)
═══════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  AGENT BASE POLICY (ceiling)                                │  │
│  │                                                              │  │
│  │  ┌──────────────────────────────────────────────────────┐   │  │
│  │  │  DELEGATION GRANT (user's consent)                    │   │  │
│  │  │                                                        │   │  │
│  │  │  ┌──────────────────────────────────────────────┐     │   │  │
│  │  │  │  INTENT ENVELOPE E(I)                         │     │   │  │
│  │  │  │  (what's reasonable for this goal)             │     │   │  │
│  │  │  │                                                │     │   │  │
│  │  │  │  ┌──────────────────────────────────────┐     │     │   │  │
│  │  │  │  │  ACTUALLY USED (observed at runtime)  │     │     │   │  │
│  │  │  │  │                                        │     │     │   │  │
│  │  │  │  │  notion:read ✓                         │     │     │   │  │
│  │  │  │  │  hubspot:read ✓                        │     │     │   │  │
│  │  │  │  │  openai:chat ✓                         │     │     │   │  │
│  │  │  │  └──────────────────────────────────────┘     │     │   │  │
│  │  │  │                                                │     │   │  │
│  │  │  │  calendar:read (in envelope, not used)         │     │   │  │
│  │  │  │  notion:write (in envelope, not used)          │     │   │  │
│  │  │  └──────────────────────────────────────────────┘     │   │  │
│  │  │                                                        │   │  │
│  │  │  hubspot:write (in delegation, NOT in envelope)        │   │  │
│  │  └──────────────────────────────────────────────────────┘   │  │
│  │                                                              │  │
│  │  admin:* (in base policy, NOT in delegation)                 │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  financial:* (outside all boundaries)                             │
└──────────────────────────────────────────────────────────────────┘

Effective permissions = BasePolicy ∩ Delegation ∩ Envelope(Intent)
```

The envelope adds a layer of restriction BETWEEN the delegation and the actual usage. Task-scoped permissions jump directly from delegation to usage. Intent-scoped permissions add the "is this reasonable for the goal?" filter.

---

## 5. The Six-Layer Intent Permission Stack

### Layer 0: Policy Foundation (Constraints)

**Purpose**: Define the absolute bounds within which intent operates.

**Components**: Agent base policy, delegation grants, party-type constraints, organizational policies, regulatory requirements.

**Property**: Intent can narrow permissions, never expand beyond policy.

```yaml
policy_foundation:
  agent_base_policy:
    description: "Maximum permissions this agent type can ever have"
    source: "Organization admin configuration"
    
  delegation_grant:
    description: "What the delegating user has consented to"
    source: "User-created delegation with explicit permission selection"
    
  party_type_constraints:
    description: "Trust-model-based restrictions"
    source: "Party classification (1st, 2nd-M, 2nd-I, 3rd)"
    
  organizational_policies:
    description: "Organization-wide rules (business hours, data classification)"
    source: "IT admin configuration"
    
  regulatory_requirements:
    description: "Compliance constraints (GDPR, SOC2, HIPAA)"
    source: "Compliance configuration"

  invariant: |
    For any intent I and any permission p:
      p ∈ Envelope(I) ⟹ p ∈ BasePolicy ∩ Delegation ∩ PartyConstraints
    
    Intent can NEVER grant permissions outside the policy foundation.
```

### Layer 1: Intent Declaration (Input)

**Purpose**: Capture intent from the appropriate source per party type.

**Sources**: Agent SDK (1st party), user delegation (2nd-M, 3rd party), behavioral observation (2nd-I), system inference (all).

**Output**: Raw intent with metadata and confidence.

```yaml
intent_declaration:
  
  intent_schema:
    intent_id: "string (unique)"
    natural_language: "string (human-readable goal description)"
    structured:
      goal_type: "enum (data_analysis, content_creation, workflow_automation, communication, administrative)"
      data_domains: "list (sales, calendar, docs, crm, financial, hr, ...)"
      output_type: "enum (document, message, data_update, notification, none)"
      sensitivity: "enum (public, internal, confidential, restricted)"
      expected_duration: "string (minutes, hours, days, ongoing)"
    declared_by: "enum (agent, user, system)"
    confidence: "float (0.0 - 1.0)"
    context:
      user_id: "string (delegating user)"
      session_id: "string (current session)"
      prior_intents: "list (recent intent history for this agent)"

  sources_by_party_type:
    first_party:
      primary: "Agent declares via SDK (programmatic)"
      secondary: "System infers from tool call patterns"
      trust_level: "HIGH — your code, your declarations"
      
    second_party_vendor_managed:
      primary: "User declares at delegation time"
      secondary: "Vendor may pass intent metadata per request"
      trust_level: "MEDIUM — trust user declaration, verify vendor claims"
      
    second_party_vendor_integrated:
      primary: "System observes from sandbox behavior"
      secondary: "Agent may declare via instrumented SDK"
      trust_level: "MEDIUM — verify declarations against observations"
      
    third_party:
      primary: "User declares at delegation time"
      secondary: "NONE — agent's declared intent is ignored"
      trust_level: "NONE — zero-trust, only delegator's intent matters"
```

### Layer 2: Intent Classification (Understanding)

**Purpose**: Classify and decompose declared/observed intent.

**Output**: Intent category, embedding, sub-intents, risk level.

```yaml
intent_classification:
  
  components:
    
    intent_taxonomy_classifier:
      description: "Maps intent to a hierarchical taxonomy of known intent categories"
      algorithm: "Fine-tuned classifier or embedding-based nearest-neighbor"
      output: "Taxonomy node + confidence score"
      
    intent_embedding:
      description: "Dense vector representation of intent for similarity computation"
      algorithm: "Sentence transformer fine-tuned on intent-permission pairs"
      output: "768-dimensional embedding vector"
      dimensions: 768
      
    intent_decomposer:
      description: "Breaks parent intent into constituent sub-intents"
      algorithm: "LLM-based decomposition with taxonomy-guided prompting"
      output: "List of sub-intents, each with its own classification"
      
    intent_risk_scorer:
      description: "Assesses the risk/sensitivity level of the intent"
      algorithm: "Rule-based (data domain sensitivity) + learned (historical incident correlation)"
      output: "Risk score (0.0 - 1.0) and risk category"

  intent_taxonomy:
    description: |
      Hierarchical taxonomy of intent categories. Each node carries:
      - A default permission template (the envelope for that category)
      - A risk profile
      - An embedding centroid (average vector of classified intents)
      - A behavioral signature (typical tool call patterns)
    
    structure:
      organization:
        data_analysis:
          reporting:
            periodic_review: "QBR prep, monthly report, weekly standup prep"
            ad_hoc_query: "One-off question, data exploration"
            compliance_report: "Audit report, SOC2 evidence, regulatory filing"
          research:
            prospect_research: "Lead qualification, account mapping"
            competitive_analysis: "Competitor tracking, market positioning"
            market_research: "Industry trends, market sizing"
          forecasting:
            pipeline_analysis: "Revenue projection, deal forecasting"
        content_creation:
          communication:
            email_drafting: "Outreach emails, follow-up, nurture sequences"
            message_posting: "Slack updates, announcements, team notifications"
            meeting_scheduling: "Calendar management, meeting coordination"
          document_generation:
            report_writing: "Summary, brief, memo, analysis document"
            presentation_building: "Slides, pitch deck, QBR deck"
        workflow_automation:
          crm_management: "Contact updates, deal progression, lead scoring"
          data_sync: "Cross-system synchronization, data migration"
          notification_routing: "Alert management, escalation"
        administrative:
          access_management: "Permission changes, delegation updates"
          configuration: "Settings updates, preference changes"
```

### Layer 3: Intent-to-Permission Envelope (Permission Derivation)

**Purpose**: Compute the minimal permission envelope for a classified intent.

**Key Property**: The envelope is derived from the intent, not from the agent's self-declared needs.

```yaml
intent_to_envelope:
  
  description: |
    Derives the PERMISSION ENVELOPE — the set of permissions that are
    REASONABLE for this intent, not the exact set the agent will need.
    
    The envelope is the intersection of:
    1. Agent's base policy (ceiling)
    2. Delegation grant (user's consent)
    3. Party-type constraints (trust model)
    4. Intent-derived reasonableness (what makes sense for this goal)
    
    Envelope(I) = BasePolicy ∩ Delegation ∩ PartyConstraints ∩ IntentReasonable(I)
  
  algorithms:
    
    template_matching:
      description: "Known intent category → pre-defined permission set"
      when_to_use: "High-confidence classification into well-known category"
      accuracy: "High for common intents, poor for novel intents"
      latency: "< 1ms (lookup)"
      example: |
        Category: "data_analysis.reporting.periodic_review"
        Template: {notion:read, hubspot:read, openai:chat, calendar:read, notion:write}
    
    learned_mapping:
      description: "Historical intent → permission traces, statistical inference"
      when_to_use: "Sufficient historical data for this intent category"
      accuracy: "Improves with data volume"
      latency: "< 10ms (model inference)"
      example: |
        Training data: 500 traces of "periodic_review" intents
        Learned: P(notion:read | periodic_review) = 0.97
                 P(hubspot:read | periodic_review) = 0.82
                 P(slack:read | periodic_review) = 0.34
                 P(hubspot:write | periodic_review) = 0.05
        Envelope (threshold 0.2): {notion:read, hubspot:read, openai:chat, slack:read}
    
    causal_inference:
      description: "Causal graph from intent to data domains to tools to permissions"
      when_to_use: "When you need to explain WHY a permission is in the envelope"
      accuracy: "High for well-modeled domains"
      latency: "< 50ms (graph traversal)"
      example: |
        Intent: "QBR preparation"
          ├── CAUSES need for: "sales data"
          │   └── REQUIRES: {hubspot:contacts:read, hubspot:deals:read}
          ├── CAUSES need for: "meeting context"
          │   └── REQUIRES: {calendar:events:read}
          ├── CAUSES need for: "internal documents"
          │   └── REQUIRES: {notion:pages:read, notion:pages:search}
          ├── CAUSES need for: "content generation"
          │   └── REQUIRES: {openai:chat:completions}
          └── MAY CAUSE need for: "output storage"
              └── REQUIRES: {notion:pages:write} [conditional, lower confidence]
        
        NOT causally related:
          ✗ hubspot:contacts:delete (destructive, no causal path from QBR prep)
          ✗ slack:messages:send (communication, not preparation)
          ✗ financial:transfers:create (unrelated domain entirely)
    
    semantic_similarity:
      description: "Similar intents → similar permissions"
      when_to_use: "Novel intent that doesn't match known categories well"
      accuracy: "Medium (depends on quality of similarity)"
      latency: "< 20ms (nearest-neighbor search)"
      example: |
        New intent: "Prepare board meeting materials"
        Closest known: "periodic_review" (similarity: 0.91)
        Use periodic_review's envelope as starting point, adjust for "board" context
        (higher sensitivity → remove low-confidence permissions, add approval requirement)
    
    information_theoretic:
      description: "Maximize relevance while minimizing envelope size"
      when_to_use: "Optimization pass after initial envelope computation"
      accuracy: "Optimal (by definition)"
      latency: "< 100ms (optimization)"
      formulation: |
        Objective:
          maximize  I(Intent; Permissions)     // permissions are RELEVANT to intent
          minimize  H(Permissions)             // permissions are MINIMAL
          subject to P(success | Permissions) ≥ threshold  // enough to complete
        
        Approximation:
          Score(P) = λ₁ · Relevance(P, Intent) - λ₂ · Size(P) + λ₃ · Sufficiency(P, Intent)
        
        Where:
          Relevance = average P(permission_j | intent) for j in P
          Size = |P| / |P_total| (normalized count of permissions)
          Sufficiency = P(intent achievable | permissions = P) estimated from historical traces
```

### Layer 4: Intent Enforcement (Runtime)

**Purpose**: Enforce the permission envelope during execution, with drift detection and step-up authorization.

```yaml
intent_enforcement:
  
  description: |
    For each tool call during execution, the enforcement layer:
    1. Checks if the tool is within the intent envelope → Allow
    2. Checks if the tool is outside the envelope but within delegation → Step-up decision
    3. Checks if the tool is outside delegation entirely → Deny
    4. Monitors for behavioral drift from the stated intent
  
  per_call_validation:
    in_envelope:
      action: "Allow immediately"
      logging: "Standard audit log"
      
    outside_envelope_within_delegation:
      action: "Step-up decision based on risk"
      decision_tree:
        low_risk:
          action: "Auto-expand envelope, log as exception"
          example: "Agent needs slack:read for QBR prep (not in default envelope but low-risk)"
        medium_risk:
          action: "Pause execution, request justification from agent"
          example: "Agent needs hubspot:write for QBR prep (unusual but not dangerous)"
        high_risk:
          action: "Deny, alert delegating user"
          example: "Agent needs hubspot:delete for QBR prep (destructive, clearly outside intent)"
          
    outside_delegation:
      action: "Deny unconditionally"
      logging: "Security event audit log"
  
  drift_detection:
    description: |
      Track the sequence of tool calls and check:
      "Is the PATTERN of calls consistent with the stated intent?"
      
      Two complementary algorithms:
      
      1. Behavioral Embedding Comparison (batch)
         - Compute behavioral centroid for intent category from historical traces
         - Embed current execution trajectory
         - Compare distance to centroid
         - If distance exceeds threshold → drift detected
      
      2. Sequential Anomaly Detection (online, per-call)
         - At each tool call, compute log-likelihood ratio:
           P(call_t | stated_intent) / P(call_t | background_model)
         - Accumulate via CUSUM statistic
         - If cumulative sum exceeds threshold → drift detected
    
    on_drift_detected:
      - classify: "What does the current trajectory LOOK LIKE?"
      - if_benign_different_intent: "Ask agent to re-declare intent, recompute envelope"
      - if_known_attack_pattern: "Deny immediately, alert security team"
      - if_novel_pattern: "Pause execution, request human review"
```

### Layer 5: Intent Verification (Post-Hoc)

**Purpose**: After execution, verify that the agent's actions were consistent with the stated intent. Feed results back into the learning layer.

```yaml
intent_verification:
  
  action_intent_alignment:
    description: |
      Score how well the observed actions served the stated intent.
      Two approaches with different cost/accuracy tradeoffs.
    
    llm_as_judge:
      description: "Use an LLM to evaluate action-intent alignment"
      when_to_use: "Sampled verification (not every execution), high-risk intents"
      cost: "High (LLM inference per verification)"
      accuracy: "High (nuanced understanding of intent)"
      prompt_template: |
        Intent: "{intent_natural_language}"
        
        Actions taken:
        {for each action: "{tool_name}({arguments}) → {result_summary}"}
        
        Rate the alignment of each action with the stated intent on a scale
        of 1-5. Flag any actions that seem unrelated or potentially concerning.
        Assess whether the overall sequence of actions was a reasonable path
        toward achieving the stated intent.
    
    embedding_based_alignment:
      description: "Compute cosine similarity between intent and action embeddings"
      when_to_use: "Every execution (low cost), initial screening"
      cost: "Low (embedding computation)"
      accuracy: "Medium (may miss subtle misalignment)"
      algorithm: |
        1. Embed the intent: e_intent = embed(intent_natural_language)
        2. Embed each action: e_action_i = embed("{tool}.{method}({args})")
        3. Per-action alignment: score_i = cosine_similarity(e_intent, e_action_i)
        4. Overall alignment: mean(score_i)
        5. Flag: any action_i where score_i < threshold
  
  permission_utilization_analysis:
    description: |
      Compare granted envelope vs. actually used permissions.
      Unused permissions → tighten future envelopes.
      Envelope expansions triggered → review if intent classification was correct.
    
    metrics:
      envelope_utilization: "|used| / |envelope|"
      expansion_rate: "count(step-up grants) / count(total calls)"
      denial_rate: "count(denials) / count(total calls)"
    
    feedback:
      high_utilization: "Envelope is well-sized → reinforce this mapping"
      low_utilization: "Envelope is too broad → tighten for this intent category"
      high_expansion_rate: "Envelope is too tight or intent was misclassified → investigate"
      high_denial_rate: "Agent is attempting actions outside its authority → security review"
  
  outcome_verification:
    description: |
      Did the agent achieve the stated intent?
      This is the ultimate measure of whether the permission system worked correctly.
    
    signals:
      agent_declared_success: "Agent signals intent fulfilled (self-report)"
      output_produced: "Expected output was created (e.g., Notion page exists)"
      user_satisfaction: "User indicates task was completed satisfactorily"
      
    feedback:
      success_with_tight_envelope: "Ideal — reinforce this intent→permission mapping"
      success_with_expansions: "Acceptable — consider adding expanded permissions to default envelope"
      failure_with_denials: "Envelope may have been too tight — review denied permissions"
      failure_without_denials: "Agent failure unrelated to permissions — no permission model change needed"
```

### Layer 6: Intent Learning (Feedback Loop)

**Purpose**: Continuously improve the intent→permission mapping system.

```yaml
intent_learning:
  
  intent_trace_database:
    description: |
      The central data store for all learning. Every execution produces a trace:
    schema:
      intent_id: "string"
      intent_text: "string"
      intent_category: "taxonomy node"
      intent_embedding: "vector"
      agent_id: "string"
      party_type: "enum"
      permissions_granted: "set (the envelope)"
      permissions_used: "set (actually exercised)"
      actions_taken: "list (ordered tool calls with arguments and results)"
      step_up_requests: "list (envelope expansion events)"
      denials: "list (denied tool call attempts)"
      alignment_score: "float (from verification layer)"
      outcome: "enum (success, partial, failure)"
      duration: "seconds"
      timestamp: "datetime"
  
  envelope_refinement:
    description: |
      Over time, narrow envelopes toward observed minimal sets.
      Use Bayesian updating: posterior permission probabilities given
      accumulated traces for each intent category.
    
    algorithm: |
      For each intent category C and each permission p:
        P(p needed | C) = (count of traces where p was used for C) + α
                          / (count of all traces for C) + α + β
      
      Where α, β are prior parameters (start uniform, converge with data)
      
      Update envelope:
        Envelope(C) = {p : P(p needed | C) > threshold}
      
      Threshold adapts:
        - More data → tighter threshold (more confident in estimates)
        - Higher risk category → lower threshold (include more permissions to avoid denials)
  
  intent_taxonomy_evolution:
    description: |
      Discover new intent categories from clustering traces.
      Split overly-broad categories, merge near-identical ones.
    
    algorithm: |
      1. Periodically cluster intent embeddings using HDBSCAN
      2. For each cluster:
         - If it maps cleanly to existing taxonomy node → no change
         - If it spans multiple nodes → investigate (possible merge)
         - If it doesn't map to any node → candidate new category
      3. For new categories:
         - Bootstrap permission template from cluster's permission traces
         - Add to taxonomy with "provisional" status
         - Promote to "stable" after N successful traces
  
  anomaly_baseline_updates:
    description: |
      Update "normal" behavioral profiles per intent category.
      As the system learns, its definition of "normal" becomes more precise,
      and drift detection becomes more sensitive.
    
    algorithm: |
      1. Compute behavioral centroid per intent category from recent traces
      2. Compute standard deviation of trajectory distances from centroid
      3. Set drift threshold = centroid + k * std_dev (k adjustable)
      4. Retrain periodically (weekly or after N new traces)
```

---

## 6. Key Algorithms for Intent-Based Least-Privilege

### 6.1 Intent Classification and Embedding

**Problem**: Given a natural language intent (or observed behavior), classify it and represent it in a way that enables permission reasoning.

**Algorithm: Hierarchical Intent Taxonomy with Embedding**

```python
class IntentClassifier:
    """
    Classifies natural language intent into the intent taxonomy
    and produces an embedding for similarity-based reasoning.
    """
    
    def __init__(
        self,
        taxonomy: IntentTaxonomy,
        embed_model: SentenceTransformer,
        reranker: ContextualReranker
    ):
        self.taxonomy = taxonomy
        self.embed_model = embed_model
        self.reranker = reranker
    
    def classify(
        self, 
        intent_text: str, 
        context: AgentContext
    ) -> ClassifiedIntent:
        # 1. Embed the intent
        embedding = self.embed_model.encode(intent_text)
        
        # 2. Find closest taxonomy nodes by embedding similarity
        candidates = self.taxonomy.nearest_nodes(embedding, k=5)
        
        # 3. Re-rank with context
        #    (agent type, user role, historical patterns, active services)
        ranked = self.reranker.score(candidates, context)
        
        # 4. Decompose into sub-intents
        sub_intents = self.decomposer.decompose(
            intent_text, ranked[0].node
        )
        
        # 5. Compute risk score
        risk = self.risk_scorer.score(
            intent_text, ranked[0].node, context
        )
        
        return ClassifiedIntent(
            category=ranked[0].node,
            confidence=ranked[0].score,
            embedding=embedding,
            sub_intents=sub_intents,
            risk_score=risk,
            permission_envelope=ranked[0].node.permission_template
        )
```

### 6.2 Learned Envelope from Historical Traces

**Problem**: Given intent I, predict the set of permissions P that will be needed.

This is a **set prediction problem**: predict which elements of a discrete set will be required.

**Approach A: Collaborative Filtering for Permissions**

Treat permission prediction like a recommendation problem. "Agents with similar intents typically needed these permissions."

```
Permission Matrix:
                    notion:read  notion:write  hubspot:read  hubspot:write  openai:chat  slack:read
QBR_prep_1             1            0              1              0              1            0
QBR_prep_2             1            1              1              0              1            0
QBR_prep_3             1            0              1              0              1            1
prospect_research_1    0            0              1              1              1            0
prospect_research_2    1            0              1              1              1            0

For new "QBR prep" intent:
  → Confident: {notion:read, hubspot:read, openai:chat} (100% of similar)
  → Possible: {notion:write, slack:read} (33% of similar)
  → Include in envelope if probability > threshold (e.g., 0.2)
```

**Approach B: Bayesian Permission Inference**

```
P(permission_j | intent_category) = 
    (count(intent_category uses permission_j) + α) / 
    (count(intent_category total) + α + β)

Envelope = {p_j : P(p_j | category) > threshold}

Threshold is a hyperparameter trading off security vs. usability:
  threshold = 0.8  → very tight (may cause step-up requests)
  threshold = 0.2  → looser (fewer interruptions, larger blast radius)
  threshold = adaptive → start at 0.5, tighten as more data accumulates
```

**Approach C: Causal Graph Reasoning**

Build a causal DAG relating intents to data domains to tools to permissions:

```
CAUSAL GRAPH:
═══════════════════════════════════════════════════════════════════

Intent: "QBR preparation"
    │
    ├── CAUSES need for: "sales data"
    │   └── REQUIRES: {hubspot:contacts:read, hubspot:deals:read}
    │
    ├── CAUSES need for: "meeting context"
    │   └── REQUIRES: {calendar:events:read}
    │
    ├── CAUSES need for: "internal documents"
    │   └── REQUIRES: {notion:pages:read, notion:pages:search}
    │
    ├── CAUSES need for: "content generation"
    │   └── REQUIRES: {openai:chat:completions}
    │
    └── MAY CAUSE need for: "output storage"
        └── REQUIRES: {notion:pages:write} [conditional]

Intent: "QBR preparation" does NOT cause:
    ✗ hubspot:contacts:delete (destructive, not related)
    ✗ slack:messages:send (communication, not preparation)
    ✗ financial:transfers:create (unrelated domain)
```

The causal graph enables **counterfactual reasoning**: "Would removing `hubspot:contacts:delete` from the envelope prevent the agent from achieving the intent? No → it's not in the envelope."

This is the most principled approach because it reasons about *why* a permission is needed, not just *whether* it was used historically.

### 6.3 Runtime Intent Drift Detection

**Problem**: During execution, detect when the agent's behavior diverges from the stated intent.

**Algorithm: Sequential Anomaly Detection (CUSUM)**

```python
class IntentDriftDetector:
    """
    Uses Cumulative Sum (CUSUM) control chart to detect
    when an agent's behavior drifts from the stated intent.
    """
    
    def __init__(
        self,
        intent_model: IntentBehaviorModel,
        background_model: BackgroundBehaviorModel,
        threshold: float = 5.0
    ):
        self.intent_model = intent_model
        self.background_model = background_model
        self.threshold = threshold
        self.cumulative_sum = 0.0
    
    def observe_call(
        self,
        tool_call: ToolCall,
        intent: ClassifiedIntent
    ) -> DriftResult:
        """
        Called for each tool invocation during execution.
        
        Computes log-likelihood ratio and accumulates.
        Alarms when cumulative evidence of drift exceeds threshold.
        """
        # Log-likelihood ratio: how much more likely is this call
        # under the background model vs. the intent model?
        p_intent = self.intent_model.probability(tool_call, intent)
        p_background = self.background_model.probability(tool_call)
        
        # Guard against division by zero
        if p_intent < 1e-10:
            log_ratio = 10.0  # strong evidence of drift
        else:
            log_ratio = math.log(p_background / p_intent)
        
        # CUSUM: accumulate evidence, reset to 0 if negative
        self.cumulative_sum = max(0.0, self.cumulative_sum + log_ratio)
        
        if self.cumulative_sum > self.threshold:
            return DriftResult(
                drifted=True,
                score=self.cumulative_sum,
                trigger_call=tool_call,
                recommendation=self._classify_drift(tool_call, intent)
            )
        
        return DriftResult(drifted=False, score=self.cumulative_sum)
    
    def _classify_drift(
        self,
        trigger_call: ToolCall,
        intent: ClassifiedIntent
    ) -> str:
        """Classify what the drift looks like."""
        # Embed current trajectory
        trajectory_embedding = self.embed_trajectory(self.call_history)
        
        # Check against known patterns
        if self.attack_detector.matches(trajectory_embedding):
            return "DENY_AND_ALERT"
        
        # Check if it looks like a different benign intent
        alt_intent = self.intent_classifier.classify_from_behavior(
            self.call_history
        )
        if alt_intent.confidence > 0.8:
            return f"RECLASSIFY_TO_{alt_intent.category}"
        
        return "PAUSE_FOR_REVIEW"
```

**Algorithm: Behavioral Embedding Comparison (Batch)**

```python
class BehavioralDriftDetector:
    """
    Compares the agent's execution trajectory against the
    expected behavioral centroid for the stated intent category.
    """
    
    def __init__(self, trace_database: IntentTraceDatabase):
        self.centroids = {}
        self._compute_centroids(trace_database)
    
    def _compute_centroids(self, db: IntentTraceDatabase):
        """Compute behavioral centroid per intent category."""
        for category in db.get_categories():
            traces = db.get_traces(category=category, limit=1000)
            trajectories = [
                self._embed_trajectory(t.actions_taken) 
                for t in traces
            ]
            self.centroids[category] = {
                "mean": np.mean(trajectories, axis=0),
                "std": np.std(trajectories, axis=0),
                "threshold": np.mean(trajectories, axis=0) 
                             + 2 * np.std(trajectories, axis=0)
            }
    
    def check_alignment(
        self,
        actions_so_far: List[ToolCall],
        intent_category: str
    ) -> AlignmentResult:
        """Check if current trajectory aligns with intent category."""
        trajectory = self._embed_trajectory(actions_so_far)
        centroid = self.centroids[intent_category]
        
        distance = np.linalg.norm(trajectory - centroid["mean"])
        threshold = np.linalg.norm(centroid["threshold"] - centroid["mean"])
        
        return AlignmentResult(
            aligned=distance < threshold,
            distance=distance,
            threshold=threshold,
            percentile=self._compute_percentile(distance, intent_category)
        )
```

### 6.4 Post-Hoc Intent-Action Alignment Verification

**Problem**: After execution, verify that the agent's actions were consistent with the stated intent.

**Algorithm: LLM-as-Judge (Sampled, High-Accuracy)**

```python
class IntentAlignmentJudge:
    """
    Uses an LLM to evaluate whether observed actions
    were consistent with the stated intent.
    """
    
    JUDGE_PROMPT = """
    You are a security auditor evaluating whether an AI agent's actions
    were consistent with its stated intent.
    
    STATED INTENT: {intent}
    
    ACTIONS TAKEN (in order):
    {actions}
    
    For each action, rate alignment with the intent on a scale of 1-5:
      5 = Directly and obviously serves the intent
      4 = Reasonably related to the intent
      3 = Tangentially related, could be justified
      2 = Weakly related, unusual for this intent
      1 = Unrelated or concerning
    
    Also provide:
    - Overall alignment score (1-5)
    - Any actions that seem concerning and why
    - Whether the sequence as a whole represents a reasonable path
      toward the stated intent
    
    Respond in JSON format.
    """
    
    async def evaluate(
        self,
        intent: str,
        actions: List[ToolCallRecord]
    ) -> AlignmentReport:
        actions_text = "\n".join([
            f"{i+1}. {a.tool_name}({a.arguments}) → {a.result_summary}"
            for i, a in enumerate(actions)
        ])
        
        prompt = self.JUDGE_PROMPT.format(
            intent=intent,
            actions=actions_text
        )
        
        response = await self.llm.complete(prompt)
        return AlignmentReport.from_json(response)
```

**Algorithm: Embedding-Based Alignment (Faster Alternative)**

```python
class EmbeddingAlignmentScorer:
    """
    Fast alignment scoring using embedding similarity.
    Lower accuracy than LLM-as-judge but runs on every execution.
    """
    
    def score(
        self,
        intent_text: str,
        actions: List[ToolCallRecord]
    ) -> AlignmentScore:
        e_intent = self.embed_model.encode(intent_text)
        
        action_scores = []
        for action in actions:
            action_text = f"{action.tool_name}: {action.description}"
            e_action = self.embed_model.encode(action_text)
            similarity = cosine_similarity(e_intent, e_action)
            action_scores.append(ActionAlignment(
                action=action,
                score=similarity,
                flagged=similarity < self.flag_threshold
            ))
        
        return AlignmentScore(
            overall=np.mean([a.score for a in action_scores]),
            per_action=action_scores,
            flagged_actions=[a for a in action_scores if a.flagged]
        )
```

### 6.5 Information-Theoretic Permission Minimization

**Problem**: How do you formally define "minimal" in the context of intent-based permissions?

**Algorithm: Mutual Information Maximization**

The optimal permission envelope maximizes the mutual information between the intent and the granted permissions while minimizing the total permission set:

```
Objective:
  maximize  I(Intent; Permissions)     // permissions are RELEVANT to intent
  minimize  H(Permissions)             // permissions are MINIMAL
  subject to P(success | Permissions) ≥ threshold  // enough to complete

Where:
  I(Intent; Permissions) = how much knowing the intent tells you about
                           which permissions are needed
  H(Permissions) = entropy of the permission set (bigger set = higher entropy = riskier)
  P(success) = probability agent can achieve intent with these permissions

This is a constrained optimization problem. In practice, approximate with:
  Score(P) = λ₁ · Relevance(P, Intent) - λ₂ · Size(P) + λ₃ · Sufficiency(P, Intent)

Where:
  Relevance = average P(permission_j | intent) for j in P
  Size = |P| / |P_total| (normalized count of permissions)
  Sufficiency = P(intent achievable | permissions = P) estimated from historical traces
  
  λ₁, λ₂, λ₃ are tunable weights:
    Security-biased:   λ₁=0.3, λ₂=0.5, λ₃=0.2  (minimize size aggressively)
    Usability-biased:  λ₁=0.2, λ₂=0.2, λ₃=0.6  (prioritize sufficiency)
    Balanced:          λ₁=0.33, λ₂=0.33, λ₃=0.33
```

---

## 7. Intent-Based Permissions Across Agent Party Types

The critical question: can intent-based permissions work for all four party types? The answer is yes, but the **source of intent** and **enforcement mechanism** differ fundamentally per party type.

```
INTENT SOURCES AND ENFORCEMENT BY PARTY TYPE
═══════════════════════════════════════════════════════════════════

                    INTENT SOURCE              ENFORCEMENT           TRUST IN
PARTY TYPE          (where does intent         (where are perms      DECLARED
                     come from?)               enforced?)            INTENT?
─────────────────────────────────────────────────────────────────────────────
1st Party           Agent declares via SDK     SDK + Gateway          HIGH
                    + system validates         Progressive capability (your code)

2nd Party           User declares at           Gateway only           MEDIUM
Vendor-Managed      delegation time            Budget-bounded token   (contractual)
                    ("for Q1 outreach")        

2nd Party           System observes from       Sandbox + Gateway      MEDIUM
Vendor-Integrated   sandbox behavior           Behavioral monitoring  (observable)

3rd Party           User declares at           Edge Gateway           NONE
                    delegation time            Capability token       (zero-trust)
                    (agent's intent ignored)   
```

### 7.1 First-Party: Full Intent Pipeline

You control the code, so you get the richest intent model.

```python
# 1st Party: Agent explicitly declares intent via SDK
async with deepsecure.intent_context(
    intent="Prepare QBR materials for VP meeting",
    metadata={
        "goal_type": "content_generation",
        "data_domains": ["sales", "calendar", "docs"],
        "sensitivity": "internal",
        "output": "notion_page"
    }
) as ctx:
    # SDK sends intent to control plane
    # Control plane classifies → computes envelope → returns intent token
    # Every tool call within this block is validated against the envelope
    
    pages = await ctx.call("notion.search_pages", {"query": "Q3 sales"})
    # ✓ Within envelope (notion:read is reasonable for QBR prep)
    
    deals = await ctx.call("hubspot.get_deals", {"filter": "Q3"})
    # ✓ Within envelope (hubspot:read is reasonable for QBR prep)
    
    await ctx.call("hubspot.delete_contact", {"id": "123"})
    # ✗ OUTSIDE envelope: destructive CRM operation is NOT reasonable
    #   for content generation intent → DENIED
    
    # Post-hoc: alignment verification runs, scores feed back to model
```

**What's different from task-scoped**: The agent doesn't declare "I need `notion:read` and `hubspot:read`." It declares "I'm preparing QBR materials." The system determines what's reasonable for that intent. If the agent later needs something unexpected (say, Slack search), the system can evaluate: "Is Slack search reasonable for QBR prep?" rather than "Did the agent declare Slack search upfront?"

### 7.2 Second-Party Vendor-Managed: Intent at Delegation Time

You can't instrument the vendor's agent, so intent must come from the **delegating user**.

```json
{
  "agent_id": "vendor-sales-agent-001",
  "intent": "Q1 sales outreach campaign",
  "intent_metadata": {
    "goal_type": "crm_management",
    "data_domains": ["contacts", "deals"],
    "sensitivity": "business_confidential",
    "expected_duration": "30_days"
  },
  "constraints": {
    "max_contacts_per_day": 100,
    "allowed_hours": "09:00-18:00 EST"
  }
}
```

The system computes the permission envelope from Sarah's stated intent:
- "Q1 outreach" → `{hubspot:contacts:read, hubspot:contacts:create, hubspot:deals:read, slack:messages:read}`
- The envelope is baked into the delegation token
- The vendor agent's actual behavior is monitored at the gateway for drift from this intent profile

**What's different from task-scoped**: Instead of Sarah listing specific permissions, she describes the purpose. The system determines what permissions are reasonable for "sales outreach" and Sarah can review/adjust the computed envelope. This is more natural for non-technical users and produces better-scoped delegations because the system has statistical knowledge about what "outreach" actually requires.

### 7.3 Second-Party Vendor-Integrated: Intent Inferred from Behavior

You can't see the code but you can observe everything in the sandbox.

```
1. Agent starts in sandbox with delegation-scoped permissions
2. System observes first N tool calls
3. Intent classifier infers: "This looks like data_analysis.research.prospect"
4. System computes envelope for inferred intent
5. If agent's subsequent calls stay within envelope → continue
6. If agent drifts → flag, tighten, or pause
```

For vendor-integrated agents, **declared intent is less trustworthy** (vendor could declare anything). **Observed intent** from behavioral patterns is the ground truth. This is effectively behavioral fingerprinting: the system builds a model of "what does this type of work look like" and continuously validates that the agent's behavior matches.

### 7.4 Third-Party: Intent is Irrelevant (Delegator's Intent Only)

For third-party agents, you practice zero-trust. The agent's declared intent is ignored. Only the delegator's intent matters.

```
The delegator (your user or system) declares:
  "This external agent may read public API endpoints for the purpose
   of data export, limited to their authorized customer segment."

Permission envelope derived from DELEGATOR's intent, not agent's claim.
Agent's behavior monitored for deviation from expected patterns.
Agent never knows what the "expected" pattern is (information asymmetry
is a security feature).
```

### 7.5 Comparison Table

| Dimension | 1st Party | 2nd Party (Managed) | 2nd Party (Integrated) | 3rd Party |
|---|---|---|---|---|
| **Intent source** | Agent SDK | User delegation | Behavioral observation | User delegation |
| **Trust in declared intent** | High | Medium | Medium (verified) | None |
| **Envelope computation** | Full pipeline (all algorithms) | Template + budget bounds | Learned from observation | Strict template only |
| **Runtime enforcement** | Progressive capability per call | Budget-bounded token | Sandbox + behavioral monitoring | Capability token per-call |
| **Drift detection** | CUSUM + embedding | Gateway call counting | Sandbox behavioral anomaly | Edge rate limiting |
| **Step-up allowed?** | Yes (auto or human) | No (token is fixed) | Yes (but requires re-sandboxing) | No (capability is fixed) |
| **Post-hoc verification** | Full (LLM judge + embedding) | Gateway logs + alignment | Full (sandbox audit) | Gateway logs only |
| **Learning feedback** | Rich (full trace) | Moderate (gateway-visible only) | Rich (full sandbox trace) | Minimal (edge logs) |

---

## 8. Beyond Task-Scoped: A Taxonomy of Permission Scoping Dimensions

"Task-scoped" is just one dimension. A truly comprehensive permission scoping architecture should support multiple orthogonal scoping dimensions that can be composed.

| Scoping Dimension | What It Bounds | Best For | Enforcement Point |
|---|---|---|---|
| **Session-scoped** | MCP session lifetime; permissions valid while session is active | Interactive agents, conversational workflows | Gateway session manager |
| **Task-scoped** | Single unit of work with clear start/end | Batch agents, scheduled jobs, defined workflows | Task token validation |
| **Intent-scoped** | Goal-oriented envelope derived from stated purpose | LLM-based agents, non-deterministic workflows | Intent enforcement layer |
| **Tool-call-scoped** | Single invocation of a single tool (allow-once) | High-risk operations, sensitive data access | Per-call capability check |
| **Workflow-scoped** | Multi-task orchestration with parent scope; child tasks inherit attenuated subset | Multi-agent systems, orchestrator patterns | Workflow token with delegation |
| **Time-scoped** | Calendar-based windows (business hours, specific dates) | Compliance requirements, operational boundaries | Temporal constraint evaluator |
| **Resource-scoped** | Specific resource instances (this page, this contact, this channel) | Data-level access control, row-level security | Resource filter at gateway |
| **Purpose-scoped** | Declared intent binding (auditable, enforceable for 1st-party) | Compliance, accountability, audit | Intent verification layer |
| **Budget-scoped** | Call count, data volume, token usage, cost ceiling | Cost control, blast radius bounding | Usage tracking middleware |
| **Delegation-scoped** | Inherited and attenuated from delegator's permissions | Multi-party trust chains | Delegation chain validator |
| **Risk-scoped** | Auto-approve low-risk, human-approve high-risk, deny critical without explicit grant | Progressive trust, step-up authorization | Risk evaluator + approval workflow |

### 8.1 Key Insight: Composability

These dimensions should be **composable, not exclusive**. A real permission grant might be:

> "This agent can read HubSpot contacts (**tool-call-scoped** to specific contact IDs → **resource-scoped**), during business hours (**time-scoped**), up to 100 calls per day (**budget-scoped**), as part of the Q1 outreach campaign (**purpose-scoped**), with the delegation expiring in 7 days (**delegation-scoped**), and any write operations require human approval (**risk-scoped**)."

The effective permission at any moment is the intersection of all active scopes:

```
Effective = Session ∩ Intent ∩ Time ∩ Budget ∩ Resource ∩ Delegation ∩ Risk
```

---

## 9. Composable Permission Scoping Architecture

Rather than a single "Task Token" layer, the architecture should have a **Scope Composition Engine** that constructs the effective permission set from multiple scoping dimensions.

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
  │     │   └── Intent Scope (goal-derived envelope)            │  │
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

### 9.1 Per Party Type Scope Stack

| Party Type | Primary Scope | Enforcement Point | Pre-flight Required? |
|---|---|---|---|
| 1st Party | Progressive (intent → session → call) | SDK + Gateway | No (just-in-time) |
| 2nd Party Vendor-Managed | Budget-bounded capability token | Gateway only | Yes (token issuance) |
| 2nd Party Vendor-Integrated | Sandbox + progressive | Sandbox + Gateway | No (sandbox enforces) |
| 3rd Party | Capability token per-call | Edge Gateway | Yes (strict token) |

---

## 10. Intent-Based vs. Task-Based: Decision Matrix

| Scenario | Task-Based Answer | Intent-Based Answer |
|---|---|---|
| Agent needs a tool not pre-declared | **Deny** (not in task token) | **Evaluate**: is this tool reasonable for the stated intent? If yes, grant. If ambiguous, step-up. If no, deny. |
| Agent makes 100 calls to the same tool | **Allow** (if in task token) | **Question**: is 100 calls consistent with the intent pattern? If "QBR prep" typically needs 5-10, flag at 20. |
| Agent accesses data in an unexpected domain | **Deny** (not declared) | **Analyze causally**: does this data domain have a causal relationship to the stated intent? |
| Two agents declare the same intent | Get identical task tokens (if same request) | Get similar but personalized envelopes based on historical patterns, user context, and trust level. |
| Agent completes faster than expected | Token remains valid until TTL | System notes the behavioral anomaly but doesn't necessarily intervene. |
| Agent's execution path is novel | Not addressed (task doesn't model paths) | Behavioral drift detector evaluates if the novel path is still intent-aligned. |
| Non-technical user creates delegation | Must select permissions from a list | Describes purpose in natural language, system computes appropriate permissions. |
| Agent needs different tools than usual | Must re-declare task or fail | Step-up authorization: expand envelope if justified, within delegation bounds. |

### 10.1 When Task-Based is Better

Task-scoped permissions remain superior for:

| Scenario | Why Task-Based Wins |
|---|---|
| **Deterministic batch agents** | Execution path is known; exact permissions can be pre-computed |
| **Compliance-critical workflows** | Auditors want to see explicit pre-approval of each permission |
| **Simple, single-tool operations** | Intent classification overhead is unjustified for "call this one API" |
| **Scheduled automation** | Runs the same way every time; no non-determinism to handle |

### 10.2 When Intent-Based is Better

Intent-scoped permissions are superior for:

| Scenario | Why Intent-Based Wins |
|---|---|
| **LLM-based conversational agents** | Can't predict tool calls; intent captures the goal |
| **Non-technical users creating delegations** | Natural language intent > permission checklist |
| **Multi-step reasoning workflows** | Agent discovers what tools it needs during execution |
| **Cross-service workflows** | Intent naturally spans services; tasks are per-service |
| **Long-running agents** | Intent persists across sessions; tasks expire |
| **Behavioral anomaly detection** | Intent provides a baseline for "normal"; tasks don't model behavior |

---

## 11. What "Truly Task-Scoped" Should Look Like

Even within the intent-based paradigm, there is a role for task-like scoping. The key improvement is shifting from "predict what the agent needs" to "bound what the agent can do, and let it navigate within those bounds."

```
TRULY TASK-SCOPED PERMISSIONS (revised model)
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

This approach works across all party types because it doesn't require predicting the execution graph. It requires bounding the damage envelope and tracking consumption within those bounds. The ILP solver becomes useful not for pre-flight computation but for **post-hoc analysis** ("what was the minimal set this agent actually needed?") to improve future bounds.

---

## 12. Current Design Tradeoffs and Shortcomings

### 12.1 Summary of Current Proposed Design

The current architecture (across the referenced documents) proposes task-scoped permissions built on a 6-layer token hierarchy where Task Tokens (Layer 4) are the mechanism for per-task scoping:

| Layer | Component | Status |
|-------|-----------|--------|
| Permission Hierarchy (DAG) | URN-based tree with inheritance rules | Designed, not implemented |
| Execution Graph Extractor | Parse agent's planned tool calls | Designed, not implemented |
| Permission Solver (ILP) | MiniScope-based ILP for minimal set | Designed, not implemented |
| Task Management Service | Create tasks, issue scoped permissions, auto-revoke | Designed, not implemented |
| Dynamic Scoping Engine | Intersect base policy with requested permissions | Designed, not implemented |
| Constraint Engine | Temporal, volume, data, contextual constraints | Designed, not implemented |
| Session Permission Modes | Always/session/once/deny | Designed, not implemented |
| Four-Party Enforcement | Different paths per party type | Designed, not implemented |

**The MVP implements 0% of per-task permissions.** It uses session-level delegation permissions embedded in the Agent JWT, enforced at the gateway via a static Permission Mapper.

### 12.2 Where Current Design Works Best

Structured, predictable 1st-party agents with known execution plans. When an organization builds its own agent, knows the code, and can declare upfront "this task needs `notion:pages:read` and `openai:chat:completions` for 30 minutes," the full MiniScope stack (static analysis → execution graph → ILP solver → Task Token) delivers genuine least-privilege.

This maps well to:
- Batch-processing agents
- Scheduled data pipeline agents
- Tightly-scoped automation bots
- Deterministic workflow agents

### 12.3 Where Current Design Falls Short

1. **The "Upfront Declaration" Problem**: LLM agents can't predict their own tool calls
2. **The Task Boundary Problem**: Real workflows are nested, iterative, long-running, or continuous
3. **The Latency vs. Security Tradeoff**: ILP computation adds latency to interactive workflows
4. **Execution Graph Extraction is Impractical**: Only works for 1st-party deterministic agents
5. **Conflation of "Task" Across Party Types**: Same Task Token mechanism applied to fundamentally different trust models
6. **No Progressive Permission Escalation**: Binary grant/deny with no step-up path

### 12.4 Proposed Evolution

| Aspect | Current Design | Recommended Evolution |
|---|---|---|
| Permission model | Pre-declared execution graph → ILP solver → minimal set | Intent declaration → envelope computation → progressive consumption → post-hoc optimization |
| Task boundaries | Rigid create/execute/complete lifecycle | Flexible: session, intent, task, workflow, or continuous modes |
| Party-type adaptation | Same Task Token for all | Different scoping strategies per party type |
| Scoping dimensions | Task-scoped only | Composable: session + intent + call + time + budget + resource + purpose + risk |
| Non-deterministic agents | Assumes plan can be extracted | Bounds the envelope, doesn't predict the plan |
| Latency impact | Pre-flight ILP computation | Just-in-time capability checks (cached policy) |
| Learning/improvement | None | Post-hoc granted-vs-used analysis feeds future envelope computation |

---

## 13. Research Directions and Algorithm Roadmap

### 13.1 Algorithm Families to Explore

| Algorithm Family | Application to Intent-Based Permissions | Key Approaches |
|---|---|---|
| **Hierarchical Multi-Label Classification** | Intent taxonomy classification with multiple applicable labels | Hierarchical softmax, recursive neural networks |
| **Set Function Learning** | Predicting permission SETS from intent features (not individual permissions) | Deep Sets, Set Transformer architectures |
| **Causal Inference** | Determining which permissions are causally required vs. merely correlated | Do-calculus, structural causal models, counterfactual reasoning |
| **Sequential Hypothesis Testing** | Real-time drift detection during execution | CUSUM, SPRT (Sequential Probability Ratio Test), change-point detection |
| **Inverse Reinforcement Learning** | Learning intent from observed behavior (for 2nd-party integrated agents) | MaxEnt IRL, Bayesian IRL |
| **Information-Theoretic Optimization** | Computing minimal permission envelopes | Rate-distortion theory, information bottleneck method |
| **Contrastive Learning** | Building intent embeddings that separate permission-relevant features | SimCLR applied to intent-permission pairs |
| **Conformal Prediction** | Providing calibrated uncertainty for envelope size ("this envelope covers the true needs with 95% probability") | Split conformal, adaptive conformal inference |
| **Graph Neural Networks** | Reasoning over causal permission graphs and intent decomposition trees | GCN/GAT over permission DAGs |
| **Online Learning / Bandits** | Adapting the security-usability tradeoff (envelope tightness) over time | Contextual bandits for threshold tuning |

### 13.2 Implementation Priority

| Priority | Component | Rationale |
|---|---|---|
| **P0** | Intent taxonomy + template-based envelopes | Immediate value with minimal ML complexity |
| **P0** | Per-call validation against envelope | Core enforcement mechanism |
| **P1** | Bayesian permission inference from traces | Enables data-driven envelope refinement |
| **P1** | CUSUM drift detection | Real-time behavioral anomaly detection |
| **P1** | Post-hoc embedding-based alignment scoring | Low-cost verification for every execution |
| **P2** | Causal graph for permission reasoning | Principled envelope computation with explanations |
| **P2** | LLM-as-judge alignment verification | High-accuracy sampled verification |
| **P2** | Intent taxonomy evolution (HDBSCAN clustering) | System learns new intent categories |
| **P3** | Information-theoretic envelope optimization | Provably minimal envelopes |
| **P3** | Conformal prediction for envelope sizing | Calibrated uncertainty guarantees |
| **P3** | Inverse RL for vendor-integrated intent inference | Infer vendor agent goals from behavior |

---

## 14. Implementation Considerations

### 14.1 Relationship to Existing MVP Architecture

The intent-based permission system builds ON TOP of the existing MVP architecture, not replacing it:

| Existing Component | Role in Intent System |
|---|---|
| **Permission Mapper** (Gateway) | Still used for tool→permission translation at runtime |
| **Delegation Service** (Control Plane) | Extended with intent metadata at delegation time |
| **Agent Session JWT** | Extended with intent_id and envelope_id claims |
| **MCP Session Manager** | Extended with intent context per session |
| **Audit Logger** | Extended with intent alignment scores |
| **Fail-Closed Security** | Unchanged — intent system fails closed if classification fails |

### 14.2 Cold-Start Strategy

Before the learning layer has accumulated sufficient traces:

1. **Phase 1**: Use curated intent taxonomy with hand-crafted permission templates (expert knowledge)
2. **Phase 2**: Supplement with Bayesian inference as traces accumulate (> 50 traces per category)
3. **Phase 3**: Enable causal graph reasoning and information-theoretic optimization (> 500 traces)
4. **Phase 4**: Enable intent taxonomy evolution and conformal prediction (> 5000 traces)

### 14.3 Formal Security Properties

The intent-based system preserves all formal security properties from the existing design and adds one:

| Property | Definition | How Intent System Preserves/Adds |
|---|---|---|
| **Minimal Authorization** | No permission granted beyond what's sufficient | Envelope is bounded by delegation ∩ policy; post-hoc analysis tightens over time |
| **Monotonic Attenuation** | Delegated permissions can only decrease | Intent envelope ⊆ Delegation ⊆ Base Policy (strictly narrowing) |
| **Temporal Boundedness** | All permissions have finite validity | Intent tokens have TTL; auto-revoke on intent completion |
| **Non-Circumvention** | No path bypasses enforcement | All traffic through gateway; SDK enforces intent context |
| **Complete Auditability** | Every grant/use/revocation is logged | Intent traces provide richer audit than permission-only logs |
| **Intent Alignment** *(NEW)* | Actions are consistent with stated purpose | Drift detection + post-hoc verification + learning loop |

### 14.4 Performance Characteristics

| Operation | Expected Latency | When It Runs |
|---|---|---|
| Intent classification | < 20ms | Once per intent declaration |
| Envelope computation (template) | < 1ms | Once per intent declaration |
| Envelope computation (learned) | < 10ms | Once per intent declaration |
| Per-call envelope check | < 1ms | Every tool call |
| CUSUM drift detection | < 1ms | Every tool call |
| Behavioral embedding comparison | < 5ms | Periodically (every 10 calls) |
| Post-hoc embedding alignment | < 50ms | After intent completion |
| Post-hoc LLM-as-judge | 2-5s | Sampled (10% of executions) |

---

## Summary

The fundamental shift from task-based to intent-based permissions is this:

**Task-based** asks: *"What operations will you perform?"* — This is the wrong question for non-deterministic agents because they don't know the answer.

**Intent-based** asks: *"What are you trying to achieve?"* — This is the right question because:

1. **Humans naturally think in terms of goals**, not tool calls — delegation becomes more natural
2. **The system can learn** what permissions are reasonable for a goal — improving over time
3. **Verification becomes about alignment** (did actions serve the goal?) not compliance (did actions match the declaration?) — catching more subtle misuse
4. **It degrades gracefully**: if the agent needs an unexpected tool, the system can reason about whether it's goal-relevant rather than just denying it — fewer false denials
5. **It works across all party types**: different intent sources and enforcement mechanisms, same conceptual framework

The existing task-based design is strong theoretically but optimized for a world of deterministic, plan-declaring agents. The real world of LLM-based agents needs a more adaptive approach: **bound the envelope, enforce at the boundary, observe and learn.**

---

## Next Steps

**Pending review and approval:**

1. **Evaluate against existing MiniScope/ILP design** — determine which components complement vs. replace
2. **Prototype intent taxonomy** — curate initial categories with permission templates for DeepSecure's supported services (Notion, Slack, HubSpot)
3. **Design intent schema for SDK** — `deepsecure.intent_context()` API surface
4. **Design intent metadata for delegation** — extend delegation endpoint with intent fields
5. **Prototype CUSUM drift detector** — using simulated agent traces
6. **Collect initial intent-permission traces** — from demo scenarios and E2E tests
7. **Evaluate embedding models** — for intent classification and alignment scoring

---

*Document Version: 1.0 | April 2026 | First-principles architecture for intent-based permissions*
