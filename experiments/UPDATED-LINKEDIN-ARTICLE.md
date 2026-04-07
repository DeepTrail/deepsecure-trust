# Updated LinkedIn Article (Post Both Experiments)

**Changes from original:** Experimental evidence integrated throughout. Claims graded by evidence level. New sections on revocation findings and model-dependent security. Removed unsupported generalizations. Added intellectual honesty markers.

---

## Title

**Parallel Agents Break Authorization in Three Ways**
*Why AI Agent Security Is an Execution Graph Problem*

---

## Intro — The Experiments

I ran two experiments over the past month.

In the first, I assigned three AI agents to three different tasks:
- auth research
- CRM analysis
- slide generation

Each agent was supposed to only access files relevant to its task.

The auth researcher read the CRM data.
The CRM analyst read the secrets file.
The slides builder could read everything — it just refused to admit it.

In the second experiment, I gave three agents access to canary files and then tried to revoke that access mid-execution — by deleting files, changing permissions, mutating content, and attempting to terminate the agents.

Every per-file revocation worked. But nothing propagated. And one of the agents couldn't be stopped at all.

The system looked secure — until I tested it.

---

## The Shift

Agents running sequentially are manageable from an authorization perspective.

Authority flows step-by-step:

```
step 1 → step 2 → step 3
```

But the moment agents start running in parallel, something changes.

Authorization stops being a timeline problem.
It becomes an execution graph problem.

The experiments exposed three fundamental failure modes.

---

## 1. Authority Replication

**Evidence: Directly tested** (Experiment 1, 2026-02-22)

When an agent fans out work across branches, authority gets copied.

Expected (intent-scoped):
```
Agent A → auth/**
Agent B → crm/**
Agent C → slides/**
```

Observed (runtime authority):
```
Agent A → ALL FILES (including secrets, CRM, ~/.zshrc)
Agent B → ALL FILES (including secrets, slides, ~/.zshrc)
Agent C → ALL FILES (refused on model grounds, not system grounds)
```

I created three canary files — fake secrets, fake CRM data, a slide outline — and asked each agent what it could read. Both lightweight agents read everything. Every file. Including files outside the workspace entirely.

The task description was advisory. The runtime provided zero access scoping.

Authority wasn't scoped. It was replicated.

**Key insight:**
Agent purpose does not equal access control.
Authority is inherited from the runtime, not derived from intent.

---

## 2. Cross-Branch Authority Bleed

**Evidence: Inferred from Experiment 1** — dedicated test forthcoming

Parallel branches share a runtime context. When authority replicates (as proven above), every branch can access every other branch's domain.

```
Branch A → CRM data     → also reads secrets, slides
Branch B → auth module   → also reads CRM, slides
Branch C → slides        → also reads CRM, secrets
```

The slide generator can access CRM data. The auth researcher can access secrets. Not because their tasks require it — because the runtime doesn't prevent it.

Sequential systems rarely expose this problem because access follows execution order.
Parallel systems make authority omnipresent.

**Key insight:**
Parallel execution turns local intent into global exposure.

*Note: Authority replication is the prerequisite for cross-branch bleed. The replication experiment confirms the mechanism. A dedicated cross-branch test — where one branch's dynamic output leaks to another — would strengthen this claim further.*

---

## 3. Revocation Propagation

**Evidence: Directly tested** (Experiment 2, 2026-03-19 — 4 scenarios, 3 agents each, 72 agent-cycles)

Revoking authority in sequential systems is straightforward. Stop execution. Authority ends.

Parallel systems introduce a harder problem:

```
Agent
 ├─ Branch A (reading CRM)
 ├─ Branch B (reading secrets)
 └─ Branch C (reading slides)
```

I tested revocation four ways:

| Method | Result | Propagation? |
|--------|--------|-------------|
| Content mutation (overwrite file) | Agents read new content immediately | None — manual, per-file |
| File deletion | Agents got "File not found" immediately | None — manual, per-file |
| Permission revocation (chmod 000) | Agents got "Permission denied" immediately | None — manual, per-file |
| Process termination (kill agent) | Nothing to terminate — agent loop runs server-side | Impossible |

Every per-resource revocation worked instantly. The Read tool has zero caching — every call hits the live filesystem.

But none of it propagated.

To revoke access from three agents reading two files each, I had to perform six manual revocations. There is no "revoke branch" command. No mechanism to deny access across the execution graph with a single action.

Worse: I tried to terminate a running sub-agent. There was nothing to terminate. The agent loop runs server-side with no persistent local process. Once launched, a parallel agent runs to completion regardless of the parent's state.

And when I restored permissions, agents resumed access instantly — with no re-authorization check. Revocation is only as durable as the mechanism enforcing it.

One more thing: you can delete the file, but you can't un-read it. Data already consumed into the agent's context window persists as irrevocable memory. The agent simultaneously "knows" both the old data and the new — a split-brain between what it can access and what it remembers.

**Key insight:**
Authority must not only be granted — it must be containable. And in current parallel agent systems, it is not.

---

## Additional Observations

The experiments surfaced secondary findings that reinforce the pattern:

**1. The blast radius is the full filesystem**
Both explore agents read `~/.zshrc` — a file completely outside the workspace. There is no workspace boundary enforcement for sub-agents.

**2. Security boundaries are model-dependent, not system-enforced**
The lightweight agents (Haiku) complied with every test request. The more capable agent (Opus) refused, calling the experiment "prompt injection." Same tools. Same files. Same runtime. Different model — different security behavior.

If the runtime doesn't enforce boundaries, the model becomes the last line of defense. And that defense is probabilistic, not deterministic.

**3. Write tools are present but mode-blocked**
Explore agents reported 28 tools including Write, StrReplace, Shell, and Delete. These tools aren't removed — they're blocked at the permission layer. The restriction is mode-based, not capability-based.

---

## The Deeper Architectural Problem

Most systems today attach authority to agent identity.

But agents don't behave like users. They behave like execution graphs:
- They spawn sub-agents
- They branch into parallel tasks
- They merge results
- They delegate dynamically

So the core question changes.

**Old question:** What can this agent access?
**New question:** What can this branch of execution access right now?

---

## A Better Mental Model

**Today — Identity-Scoped Authorization:**
```
Agent identity
      ↓
Global permissions
      ↓
Inherited by all sub-agents
      ↓
No per-branch scoping
      ↓
No revocation propagation
```

**Needed — Execution-Scoped Authorization:**
```
Execution graph
      ↓
Branch-level permissions
      ↓
Authority shrinks per branch
      ↓
Revocation propagates across the graph
      ↓
Re-authorization required after restoration
```

---

## Closing

The moment agents start spawning agents and running in parallel:
- Authority stops flowing linearly — it starts spreading across a graph
- Revocation stops being a point operation — it needs to propagate
- Security stops being deterministic — it becomes model-dependent

That's where traditional authorization models break.

Parallelism doesn't just improve performance.
It changes the security model.

---

## Final Thought

Authority doesn't just need to be granted.
It needs to be scoped, propagated, and contained — across every branch of the execution graph.

And right now, in the systems I tested, it isn't.

---

## Evidence Appendix

| Failure Mode | Evidence Level | Experiment |
|-------------|---------------|-----------|
| 1. Authority Replication | ✅ Directly tested | 3 agents, 3 canary files, full cross-domain access confirmed |
| 2. Cross-Branch Bleed | ⚠️ Inferred from #1 | Authority replication is prerequisite; dedicated bleed test forthcoming |
| 3. Revocation Propagation | ✅ Directly tested | 4 methods, 3 agents each, 72 agent-cycles, zero propagation |
| Model-Dependent Security | ✅ Directly tested | Haiku complied; Opus refused — same tools, different behavior |
| Cross-Workspace Access | ✅ Directly tested | Agents read ~/.zshrc outside workspace |
| Fire-and-Forget Architecture | ✅ Directly tested | No killable process; server-side agent loop |
| Context as Irrevocable Memory | ✅ Directly tested | Data persists in LLM context after file deletion |

**Total experimental evidence:**
- 2 experiments, 5 scenarios, 9+ sub-agent runs
- 72 agent-cycles (revocation experiment alone)
- 288 file reads (revocation experiment alone)
- 5 of 7 core claims directly tested
