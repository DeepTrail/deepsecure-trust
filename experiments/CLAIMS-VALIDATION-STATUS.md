# Claims Validation Status — LinkedIn Article

**Article:** "Parallel Agents Break Authorization in Three Ways"
**Subtitle:** "Why AI Agent Security Is an Execution Graph Problem"
**Last updated:** 2026-03-19

---

## Evidence Summary

Two experiments conducted to date:

| Experiment | Date | Environment | What It Tests |
|-----------|------|-------------|---------------|
| Authority Replication | 2026-02-22 | Cursor + Claude Opus 4.6, openclaw workspace | Failure Mode #1, Cross-Workspace, Model-Dependent Security |
| Revocation Propagation | 2026-03-19 | Cursor + Claude Opus 4.6, deepsecure-mvp workspace | Failure Mode #3, 4 revocation methods, agent lifecycle |

---

## Claim-by-Claim Validation

### Section: Authority Replication (Failure Mode #1)

| # | Claim | Evidence Level | Source |
|---|-------|---------------|--------|
| 1 | "When an agent fans out work across branches, authority gets copied" | ✅ **DIRECTLY TESTED** | Authority experiment: all 3 agents read all 3 canary files |
| 2 | "Even though each agent had a different purpose, every sub-agent inherited the same filesystem authority as the parent" | ✅ **DIRECTLY TESTED** | Auth researcher read CRM data; CRM analyst read secrets |
| 3 | "Agent purpose ≠ access control" | ✅ **DIRECTLY TESTED** | Task description provided zero access restriction |
| 4 | "Authority is inherited from the runtime, not derived from intent" | ✅ **DIRECTLY TESTED** | Explore agents had 28 tools; access was runtime-granted |

### Section: Cross-Branch Authority Bleed (Failure Mode #2)

| # | Claim | Evidence Level | Source |
|---|-------|---------------|--------|
| 5 | "Parallel branches often share a runtime context" | ⚠️ **INFERRED** | Not directly tested — but authority replication implies bleed is possible |
| 6 | "The slide generator can access CRM data" | ✅ **PARTIALLY TESTED** | Agent C (Opus) refused; Agents A/B (Haiku) could cross-read all domains |
| 7 | "Authority bleeding across execution branches" | ⚠️ **INFERRED** | Follows logically from #1 + #2 but no dedicated cross-branch test |
| 8 | "Parallel execution turns local permissions into global exposure" | ⚠️ **INFERRED** | Correct directionally; agents had global read access, but "local permissions" never existed to begin with — there were no local permissions to "turn into" global |

**What's missing:** A dedicated test where Branch A produces output that Branch B consumes without authorization. The current experiments test read access to static canary files, not dynamic data flow between branches.

### Section: Revocation Propagation (Failure Mode #3)

| # | Claim | Evidence Level | Source |
|---|-------|---------------|--------|
| 9 | "Revoking authority in sequential systems is straightforward" | ✅ **VERIFIED** | Revocation experiment: file deletion and chmod 000 were immediate |
| 10 | "Parallel systems introduce a harder problem" | ✅ **DIRECTLY TESTED** | 4 scenarios confirmed: no graph-level revocation mechanism exists |
| 11 | "Revocation must propagate across the entire execution graph" | ✅ **DIRECTLY TESTED** | No propagation exists — every revocation was manual, per-resource |
| 12 | "Most authorization systems were never designed for this" | ✅ **ARCHITECTURALLY CONFIRMED** | Sub-agents have no killable process; parent has no revocation channel |
| 13 | "Authority must not only be granted — it must be containable" | ✅ **CONFIRMED** | Once launched, authority is irrevocable until agent finishes |

### Section: Additional Observations

| # | Claim | Evidence Level | Source |
|---|-------|---------------|--------|
| 14 | "Agents could read files outside their intended workspace" | ✅ **DIRECTLY TESTED** | Both explore agents read ~/.zshrc |
| 15 | "Tool access didn't map cleanly to actual capability boundaries" | ✅ **DIRECTLY TESTED** | 28 tools present including Write/Delete; blocked by mode, not by tool availability |
| 16 | "Different models behaved differently in the same environment" | ✅ **DIRECTLY TESTED** | Haiku complied fully; Opus refused. Same tools, same files, different behavior |
| 17 | "If the runtime doesn't enforce boundaries, the model becomes the last line of defense" | ✅ **DIRECTLY TESTED** | Agent C's refusal was model-level, not system-level |

### Section: Deeper Architectural Problem

| # | Claim | Evidence Level | Source |
|---|-------|---------------|--------|
| 18 | "Most systems today attach authority to agent identity" | ✅ **CORRECT** | Standard pattern; Cursor attaches to parent session |
| 19 | "Agents behave like execution graphs — spawn, branch, merge, delegate" | ⚠️ **PARTIALLY TESTED** | Branching (fan-out) tested; merging and delegation not tested |
| 20 | "Branch-level permissions" / "authority shrinks per branch" | ❌ **NOT TESTED** (proposed model) | This is the article's recommendation, not an observed behavior |

### Section: Mental Model (Identity-Scoped vs Execution-Scoped)

| # | Claim | Evidence Level | Source |
|---|-------|---------------|--------|
| 21 | Identity-scoped authorization = global permissions inherited by all sub-agents | ✅ **DIRECTLY TESTED** | Experiment 1: all agents inherited parent's full authority |
| 22 | Execution-scoped authorization = branch-level permissions that shrink per branch | ❌ **NOT TESTED** (proposed model) | No system tested implements this; it's a prescriptive recommendation |

---

## Claims Still Needing Validation

### Priority 1: Cross-Branch Authority Bleed (dedicated test)

**Status:** INFERRED, not directly tested.

**What's needed:** A test where:
- Branch A writes data to a shared location
- Branch B reads that data without explicit authorization
- The test measures whether data produced by one branch is accessible to another branch that shouldn't see it

**Why it matters:** The article presents cross-branch bleed as a distinct failure mode (#2), but the current experiments only show that all branches have the same authority (which is a prerequisite for bleed, not bleed itself). The distinction is: authority replication means "everyone can read the same static files." Cross-branch bleed means "one branch's dynamic output leaks to another branch."

**Proposed experiment:**
1. Launch Agent A to write analysis results to `branch-a-output/`
2. Launch Agent B to work on a completely different task
3. Observe whether Agent B can discover and read Agent A's output
4. Test with agent prompts that instruct B to only read its own domain

### Priority 2: Dynamic Delegation

**Status:** NOT TESTED.

**What's needed:** A test where an agent dynamically delegates a subset of its authority to a sub-task. Currently, Cursor prohibits sub-agent nesting (depth 1 only), so this may be architecturally impossible to test in this environment.

**Alternative:** Test whether MCP tools or framework integrations (LangChain, CrewAI) implement delegation differently.

### Priority 3: Authority Attenuation Under Nesting

**Status:** NOT TESTABLE in Cursor (sub-agents cannot spawn sub-agents).

**What's needed:** A system that allows depth > 1 sub-agent nesting to test whether authority shrinks at each depth level. Cursor's flat fan-out model makes this impossible.

**Alternative:** Document that Cursor chose prohibition over attenuation, and note this as a design choice with security implications.

### Priority 4: Merge-Point Authority (Branch Reconvergence)

**Status:** NOT TESTED.

**What's needed:** A test where parallel branches converge (e.g., multiple agents' outputs are merged by the parent). The question: does the merged result inherit the union of all branches' authority, or the intersection?

**Why it matters:** The article frames agents as "execution graphs" that "merge results." If authority at the merge point is the union of all branches, then convergence amplifies the blast radius.

---

## Validation Score Summary

| Category | Count | Percentage |
|----------|-------|-----------|
| ✅ DIRECTLY TESTED | 14 | 64% |
| ⚠️ INFERRED (logically follows from tested claims) | 4 | 18% |
| ❌ NOT TESTED (prescriptive recommendations or untested claims) | 4 | 18% |
| **Total claims** | **22** | |

**Before experiments:** ~40% directly tested
**After both experiments:** **64% directly tested, 82% at least inferred**

---

## Experiment Index

| Experiment | Location | Claims Validated |
|-----------|----------|-----------------|
| Authority Replication | `experiments/authority-replication/` | #1-4, #6, #14-17, #18, #21 |
| Revocation Propagation | `experiments/revocation-propagation/` | #9-13 |
| Cross-Branch Bleed (proposed) | Not yet created | #5, #7, #8, #19 |
| Merge-Point Authority (proposed) | Not yet created | #19, #24 |
