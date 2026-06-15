# AFK Context Budget Analysis

> **Purpose:** Determine the optimal `CLAUDE_CODE_AUTO_COMPACT_WINDOW` value for DeepSecure AFK sessions.
> **Decision:** `400,000` tokens (Boris Cherny's recommendation)
> **Date:** 2026-06-09

---

## Context Loaded Per AFK Session

Every Claude Code session in the DeepSecure repo loads a fixed base context before any work begins. During AFK (Ralph loop) iterations, workstream context is also loaded via `ralph-prompt.md`.

### Base Context (Every Session)

| Component | Words | Tokens (approx) | Notes |
|-----------|-------|-----------------|-------|
| `CLAUDE.md` | 6,679 | ~8,700 | 1,117 lines — monolithic, pre-refactoring |
| 23 skills (`.claude/commands/*.md`) | 66,830 | ~86,900 | All loaded into context at session start |
| 3 agent definitions (`.claude/agents/*.md`) | 2,528 | ~3,300 | `code-reviewer`, `security-auditor`, `test-engineer` |
| `settings.local.json` | 123 | ~160 | Permission allowlist/deny rules |
| **Base Total** | **76,160** | **~99,000** | |

### Largest Skills by Token Size

| Skill | Tokens | Notes |
|-------|--------|-------|
| `/run-plan` | ~7,970 | Largest — orchestrates full planning pipeline |
| `/breakdown-design` | ~6,390 | |
| `/spec` | ~6,360 | |
| `/create-task-spec` | ~6,210 | |
| `/create-design-doc` | ~5,630 | |
| `/run-batch` | ~5,430 | |
| `/create-batch-execution-plan` | ~5,430 | |
| `/create-workstream` | ~4,880 | |
| `/create-task-ticket` | ~4,700 | |
| Bottom 14 skills | ~1,300–3,800 each | |

### Workstream Context (AFK Sessions Only)

During Ralph loop iterations, the agent reads workstream planning files to understand what to implement.

| Component | Words (largest) | Tokens (approx) | Notes |
|-----------|----------------|-----------------|-------|
| `BATCH_EXECUTION_PLAN.md` | 53,465 | ~69,500 | Largest single workstream file |
| `BREAKDOWN.md` | 26,758 | ~34,800 | Task decomposition |
| `STATUS.md` | 16,376 | ~21,300 | Progress tracking |
| **Workstream Total** | **96,599** | **~125,600** | Worst case — all three read in full |

### Total Context Budget

| Scenario | Tokens | Remaining at 400k |
|----------|--------|-------------------|
| Interactive session (no workstream) | ~99,000 | ~301,000 for work |
| AFK iteration (base + workstream) | ~224,600 | ~175,400 for work |
| AFK iteration + reading source files + test output | ~325,000–375,000 | ~25,000–75,000 before compaction |

---

## Why 400,000 Tokens

### Industry Recommendations

| Value | Who | Rationale | Fit for DeepSecure |
|-------|-----|-----------|-------------------|
| **400,000** | Boris Cherny (Head of Claude Code) | "Context rot kicks in around 300k-400k tokens." Recommended for 1M context models. | **Best fit.** ~175k headroom for actual work after base+workstream context loads. |
| 300,000 | Matt Pocock (conservative) | "Keep under ~100k" — prefers restart over compaction entirely. | Too aggressive. Would compact early during any workstream task, losing work-in-progress context. |
| 200,000 | Claude Code default | Safe default for small projects with minimal CLAUDE.md. | **Too small.** DeepSecure's base context alone is ~99k — compaction would fire almost immediately on any workstream task. |

### The Sediment Problem

From the AFK research (`docs/AFK_WORKFLOWS.md`, line 397):

> Long-running single sessions accumulate stale context, outdated file contents, and compaction artifacts. After ~100k tokens, compacted context becomes increasingly unreliable: the agent may reference deleted files, use outdated API signatures, or repeat already-completed work.

**Why this matters less for DeepSecure AFK:** The Ralph loop pattern enforces fresh context per iteration. Each `ralph.sh` iteration starts a new `claude --print` invocation — no accumulated sediment across iterations. The 400k threshold only matters *within* a single iteration.

### Within a Single Ralph Iteration

Typical single-iteration flow and token consumption:

```
Start: 0 tokens
  + Base context (CLAUDE.md, skills, agents):     ~99,000 tokens
  + Workstream files (BREAKDOWN, BATCH_PLAN):    ~125,000 tokens
  = After loading:                                ~224,000 tokens

  + Read 5-10 source files for task:              ~30,000–60,000 tokens
  + Agent thinking + tool calls:                  ~30,000–50,000 tokens
  + Test output (pytest -v):                      ~10,000–20,000 tokens
  + Git operations, lint output:                   ~5,000–10,000 tokens
  = After work:                                   ~300,000–365,000 tokens

  Compaction fires at:                             400,000 tokens
  → SessionStart(compact) hook reinjects critical context
  → Agent continues with clean context
```

Most single-task iterations complete well under 400k. Complex tasks (large test suites, multiple files) may trigger one compaction — the `SessionStart(compact)` hook handles recovery.

---

## Post-Refactoring Improvement (Phase 3)

After WS-E (CLAUDE.md Refactoring), the context budget improves significantly:

| Component | Before (current) | After (Phase 3) | Savings |
|-----------|-----------------|-----------------|---------|
| `CLAUDE.md` | ~8,700 tokens | ~2,000 tokens (TOC only) | ~6,700 |
| Skills loaded | All 23 (~86,900) | On-demand via skill matching | ~60,000–70,000 |
| Reference docs | Inline in CLAUDE.md | Loaded via `SessionStart` hook only when needed | included above |
| **Base context** | **~99,000** | **~25,000–35,000** | **~64,000–74,000** |

Post-refactoring, a typical AFK iteration loads ~90,000–160,000 tokens (down from ~224,600), leaving ~240,000–310,000 tokens for actual work. The 400k threshold becomes even more comfortable.

---

## Configuration

```bash
# Set in shell profile (~/.zshrc)
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000

# Or per-session for testing
CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000 claude --print ...
```

### Companion Settings

| Setting | Value | Why |
|---------|-------|-----|
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | `400000` | Compact before context rot, after enough work headroom |
| `--max-turns 80` | Per Ralph iteration | Prevent single iteration from running indefinitely |
| `--max-budget-usd 5` | Per Ralph iteration | Cost ceiling prevents runaway token consumption |
| `SessionStart(compact)` hook | `.claude/hooks/compact-recovery.sh` | Reinject critical context after compaction fires |

---

## References

- Boris Cherny — `CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` recommendation ([howborisusesclaudecode.com](https://howborisusesclaudecode.com/))
- Matt Pocock — "Keep LLM context under ~100k tokens" (conservative, prefers restart)
- Dark Software Factory paper — The Sediment Problem (context degradation after ~100k)
- `docs/AFK_WORKFLOWS.md` lines 397-399 — Smart Zone analysis
- `docs/spec/afk-workflow-enablement-spec.md` — AFK spec (open question resolved: 400k)
