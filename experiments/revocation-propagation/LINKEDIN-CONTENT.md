# LinkedIn Content: Parallel Agent Authorization

**Status:** Ready to publish
**Last updated:** 2026-03-19
**Evidence base:** 2 experiments, 7 scenarios, 360+ file reads

---

# Part 1: LinkedIn Post (Hook)

Use this as the standalone post that drives readers to the article.

---

I ran an experiment this week.

Three AI agents. Three different tasks. Three separate domains.

The auth researcher read the CRM data.
The CRM analyst read the secrets file.

Nothing escalated. But authority replicated.

Then I tried something harder.

I launched agents in a loop and revoked their access mid-execution.

File deletion worked — agents got errors immediately.
Permission changes worked — agents saw "denied" on next read.

But nothing propagated.

To revoke access from three agents, I had to revoke six times — once per file, per agent.

And when I tried to terminate a running sub-agent?

There was nothing to terminate.

The agent doesn't exist as a process you can kill. It runs server-side.

The parent has no off switch.

Full breakdown of three failure modes — authority replication, cross-domain access, and revocation propagation — in the article below.

When your agents spawn agents, does authority shrink per branch?

Or does everything inherit everything?

#AgenticAI #AIAgents #AgentSecurity #Authorization #ParallelExecution #DeepTrail

---

# Part 2: LinkedIn Article

Copy everything below this line into LinkedIn's article editor.

---

## Parallel Agents Break Authorization in Three Ways

**Why AI Agent Security Is an Execution Graph Problem**

---

### The Experiments

I ran two experiments to test how authorization behaves when AI agents run in parallel.

**Experiment 1: Authority Replication**

I assigned three AI agents to three different tasks:
- Agent A → research the auth module
- Agent B → analyze CRM data
- Agent C → build a slide outline

Each agent was supposed to only access files relevant to its task. I created canary files — fake secrets, fake CRM data, a slide outline — and asked each agent what it could actually read.

Results:
- The auth researcher read the CRM data
- The CRM analyst read the secrets file
- Both agents read ~/.zshrc outside the workspace

Task scope provided zero access control. Every agent inherited the same authority.

**Experiment 2: Revocation Propagation**

I launched three agents reading canary files in a loop — one read cycle every 30 seconds, six cycles total. At T+45 seconds, I revoked access using four different methods:

| Method | What Happened |
|--------|---------------|
| Content mutation | Agents saw new content on next read — zero caching |
| File deletion | Agents got "File not found" immediately |
| Permission change (chmod 000) | Agents got "Permission denied" immediately |
| Process termination | Nothing to terminate — no killable process exists |

Every per-file revocation worked. None of them propagated.

---

### The Shift

Agents running sequentially are manageable from an authorization perspective. Authority flows step-by-step:

```
step 1 → step 2 → step 3
```

But the moment agents start running in parallel, something changes.

Authorization stops being a timeline problem.
It becomes an execution graph problem.

```
Agent
 ├─ Branch A
 ├─ Branch B
 │    └─ Sub-agent
 └─ Branch C
```

The experiments exposed three failure modes.

---

### 1. Authority Replication

When an agent fans out work across branches, authority gets copied.

**Expected (intent-scoped):**
```
Agent A → auth/**
Agent B → crm/**
Agent C → slides/**
```

**Observed (runtime authority):**
```
Agent A → ALL FILES
Agent B → ALL FILES
Agent C → ALL FILES
```

Even though each agent had a different purpose, every sub-agent inherited the same filesystem authority as the parent.

Authority wasn't scoped. It was replicated.

**Key insight:**
- Agent purpose ≠ access control
- Authority is inherited from the runtime, not derived from intent

---

### 2. Cross-Domain Access

This is a direct consequence of authority replication.

Because every branch starts with global permissions, each branch can access any domain:
- The slide generator can read CRM data
- The auth researcher can read secrets
- The CRM analyst can read the presentation

Even though their tasks don't require it.

Sequential systems rarely expose this because access follows step order. Parallel systems make authority omnipresent — every branch has access to everything, simultaneously.

**Key insight:**
- Parallel execution multiplies the blast radius of global permissions

---

### 3. Revocation Doesn't Propagate

This is where the experiments produced the strongest findings.

**Per-file revocation works:**

| Method | Latency | Destructive? | Reversible? |
|--------|---------|--------------|-------------|
| Content mutation | 0 seconds | No | Yes |
| File deletion | 0 seconds | Yes | No |
| chmod 000 | 0 seconds | No | Yes |

Every agent got errors immediately on their next read. The Read tool has zero caching.

**But nothing propagates.**

To revoke access from three agents reading two files each, I had to perform six manual revocations. There's no "revoke branch" command. No graph-level mechanism.

**The architecture makes it worse:**

I tried to terminate a running sub-agent. There was nothing to terminate.

Sub-agents don't exist as persistent local processes. They run as server-side loops with ephemeral tool calls. The parent has no cancel button, no revocation channel, no way to stop a child agent after launch.

Once you launch a parallel agent, its authority is irrevocable until it finishes.

**And revocation has no persistence:**

When I restored file permissions (chmod 644), agents silently resumed reading — no re-authorization required. Revocation only holds as long as the mechanism enforcing it. Remove the block, and access returns automatically.

**Key insight:**
- Authority must not only be granted — it must be containable
- Current systems have no containment mechanism

---

### The Irrevocable Memory Layer

One finding surprised me.

When files were mutated from v1 to v2, agents saw v2 on their next read — tool access reflects live filesystem state. But the LLM's conversation context still contained v1 from earlier reads.

You can delete the file. You can't un-read it.

This creates a split-brain:

| Layer | After Revocation | Revocable? |
|-------|------------------|------------|
| Filesystem | Access denied | Yes |
| Tool reads | Return errors | Yes |
| LLM context | Still has the data | No |

Content mutation revokes future tool-mediated access. It cannot revoke data already consumed into the agent's reasoning context.

---

### The Deeper Architectural Problem

Most systems today attach authority to agent identity.

But agents don't behave like users. They behave like execution graphs.

They:
- Spawn sub-agents
- Branch into parallel tasks
- Merge results
- Delegate dynamically

So the core question changes.

**Old question:** What can this agent access?

**New question:** What can this branch of execution access right now?

---

### A Better Mental Model

**Today — Identity-Scoped Authorization**
```
Agent identity
      ↓
Global permissions
      ↓
Inherited by all sub-agents
      ↓
No revocation channel
```

**Needed — Execution-Scoped Authorization**
```
Execution graph
      ↓
Branch-level permissions
      ↓
Authority shrinks per branch
      ↓
Revocation propagates
```

---

### What the Experiments Proved

| Claim | Evidence |
|-------|----------|
| Task description provides no access control | 3 agents, 3 tasks, identical access |
| Authority replicates across branches | All branches read all files |
| Per-file revocation works | 4 methods, 0-second latency, all effective |
| No graph-level revocation exists | Every revocation required manual per-file action |
| Sub-agents cannot be terminated | No killable process — architecture prevents it |
| Revocation has no persistence | Restore permissions → access silently resumes |
| LLM context is irrevocable | Data read before revocation persists in agent memory |

---

### Closing

The moment agents start spawning agents and running in parallel:
- Authority stops flowing linearly
- It starts spreading across a graph
- And traditional authorization models break

Parallelism doesn't just improve performance. It changes the security model.

**The takeaway:**

Authority doesn't just need to be granted. It needs to be scoped, propagated, and contained across the execution graph.

The systems we have today can grant authority. They cannot contain it.

---

*When your agents spawn agents, does authority shrink per branch? Or does every branch inherit everything?*

---

#AgenticAI #AIAgents #AgentSecurity #Authorization #ParallelExecution #ExecutionGraph #DeepTrail

---

# Part 3: Article Metadata

| Field | Value |
|-------|-------|
| Word count | ~950 words |
| Reading time | ~4 minutes |
| Evidence sources | 2 experiments, 7 scenarios total, 360+ file reads |
| Accuracy score | 9.1/10 |
| Quality score | 9.2/10 |

---

# Part 4: Publishing Checklist

Before publishing:

- [ ] Copy Part 1 (Post) into LinkedIn post composer
- [ ] Copy Part 2 (Article) into LinkedIn article editor
- [ ] Add a header image (execution graph diagram recommended)
- [ ] Schedule post to go live, then article 1 hour later (or simultaneous)
- [ ] Tag relevant connections who work on agent infrastructure
- [ ] Prepare 2-3 follow-up comments with additional context

---

# Part 5: Follow-Up Comments (Pre-Written)

Post these as comments on your own post to boost engagement:

**Comment 1 (Methodology):**
> The experiments ran in Cursor using Claude sub-agents (parent: Opus 4.6, children: Haiku). Full protocol, canary files, and results available if anyone wants to reproduce. The key was using versioned markers (VERSION=1, NONCE=...) so we could distinguish fresh reads from cached/stale content.

**Comment 2 (Implications):**
> The finding that surprised me most: sub-agents have no killable local process. They run as server-side loops. So "terminate the agent" isn't even an option — there's nothing to terminate. The parent launches children and then becomes irrelevant. Fire and forget, with no revocation channel.

**Comment 3 (Call to Action):**
> Curious how others are handling this. If you're building agent orchestration, what's your revocation model? Per-resource? Per-session? Something at the execution graph level? Would love to see how different frameworks approach this.

---

# Part 6: Changes from Previous Draft

| Section | Change |
|---------|--------|
| Intro | Now references both experiments with specific results |
| Section 2 | Renamed from "Cross-Branch Bleed" to "Cross-Domain Access"; clarified as consequence of #1 |
| Section 3 | Expanded with all 4 revocation scenarios + new findings (no killable process, no persistence) |
| New section | Added "The Irrevocable Memory Layer" — split-brain between tool access and LLM context |
| Evidence table | Added explicit mapping of claims to experimental evidence |
| Closing | Tightened to core message |

---

# Part 7: Experiment Reference

All experimental artifacts are in this directory:

```
experiments/revocation-propagation/
├── EXPERIMENT-PROTOCOL.md          # Full experimental design
├── RUNBOOK.md                       # Step-by-step execution
├── canary/                          # Versioned test files
│   ├── SECRETS.env
│   ├── CRM-DATA.csv
│   ├── SLIDE-OUTLINE.md
│   └── HEARTBEAT.txt
├── controller/                      # Revocation scripts
│   ├── revocation-timer.sh
│   ├── reset-canary.sh
│   └── kill-monitor.sh
├── agent-prompts/                   # Sub-agent prompts
│   ├── long-running-reader.md
│   └── parent-orchestrator.md
└── results/
    ├── scenario-A-results.md        # Parent termination
    ├── scenario-B-results.md        # File deletion
    ├── scenario-C-results.md        # Permission revocation
    ├── scenario-D-results.md        # Content mutation
    └── summary.md                   # Cross-scenario analysis
```

Previous experiment (Authority Replication) artifacts are in the openclaw repo:
```
tmp-authority-test/
├── EXPERIMENT-PROTOCOL.md
├── EXPERIMENT-RESULTS.md
├── FAKE-SECRETS.env
├── CRM-DATA.csv
└── SLIDES-OUTLINE.md
```
