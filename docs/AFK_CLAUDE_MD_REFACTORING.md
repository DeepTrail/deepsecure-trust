# CLAUDE.md Refactoring Analysis

> **Purpose:** Determine the target size and structure for CLAUDE.md after AFK refactoring (WS-E, Phase 3).
> **Decision:** 100-150 lines — TOC + critical rules + pointer table to reference docs.
> **Date:** 2026-06-09
> **Prerequisite:** `SessionStart` hook must be verified before any split.

---

## Current State

| Metric | Value |
|--------|-------|
| Lines | 1,117 |
| Words | 6,679 |
| Tokens (approx) | ~8,700 |
| Structure | Monolithic encyclopedia — everything inline |
| Loaded | Every session, every agent, every Ralph iteration |

The current CLAUDE.md contains: project overview, development commands, architecture overview, testing strategy, token types and auth flows, backend conventions, file path rules, task breakdown workflow, ticket structure, workstream prerequisites, status verification, merge point protocol, test suite health rules, documentation consistency rules, common pitfalls, self-verification process, and a lessons learned changelog.

All of this loads into every session's context window whether the agent needs it or not.

---

## Three Industry Approaches to CLAUDE.md Size

| Approach | Target Size | Who Uses It | Philosophy | Token Cost |
|----------|-------------|-------------|-----------|------------|
| **OpenAI AGENTS.md** | ~100 lines | OpenAI Engineering (1M LOC, zero human-written, 3.5 PRs/engineer/day) | TOC + pointers to `docs/`. Progressive disclosure — agents load what they need, when they need it. | ~1,300 tokens |
| **Boris / Matt Pocock** | ~100-150 lines | Boris Cherny (Head of Claude Code), Matt Pocock | Slim root + `CODE_STANDARDS.md` consumed only by reviewer agent on PRs. "Save tokens during implementation, spend them during review." | ~1,500-2,000 tokens |
| **steipete (contrarian)** | Started at 1 line, grew to ~800 iteratively | Peter Steinberger (PSPDFKit) | Rules built by the agent from failures, not authored upfront. Shared `AGENTS.MD` symlinked across repos. "If your CLAUDE.md grows faster than your codebase, you're over-engineering the harness." | ~10,000+ tokens |

### OpenAI's Pattern in Detail

From OpenAI's "Harness Engineering" post:
- `AGENTS.md` is the "table of contents" (~100 lines)
- `docs/` directory is the "system of record"
- Cross-linked documentation mechanically enforced through linters and CI
- Progressive disclosure: agents start with a small, stable entry point and are taught where to look next
- Result: ~1,500 PRs merged, ~1M lines of code, zero manually-written, 6+ hour autonomous runs

### Boris / Matt Pocock's Optimization

Boris Cherny: "Every project needs a CLAUDE.md checked into git. When Claude gets something wrong, fix it, then ask Claude to update CLAUDE.md so it never happens again. Every caught mistake becomes future prevention."

Matt Pocock: "Want to put something in CLAUDE.md? Stick it in `CODE_STANDARDS.md` instead. Then pass it to a reviewer agent that runs on every PR. Save tokens during implementation, spend them during review."

The key insight: **code standards are a review concern, not an implementation concern.** Moving them out of CLAUDE.md means the implementing agent doesn't burn tokens on rules that only matter during code review.

### steipete's Contrarian View

Peter Steinberger's approach is the opposite — he started with one line and let the agent iteratively build the rules file from failures over months. His test: "If your CLAUDE.md grows faster than your codebase, you're over-engineering the harness."

His shared `AGENTS.MD` file (~800 lines) is symlinked from `~/Projects/agent-scripts/AGENTS.MD` into every project, eliminating per-project maintenance. Rules are generic enough to apply across repos.

**Why this doesn't fit DeepSecure:** DeepSecure has highly project-specific rules (token types that cause 401 errors, MCP Gateway protocol flow, backend file path conventions, merge point protocol) that can't be shared across repos. The monolithic approach works for steipete because his rules are generic; DeepSecure's rules are specialized.

---

## The Caveat That Matters

> **Claude Code auto-loads `CLAUDE.md` at session start but does NOT auto-load referenced files.**

This is the single most important constraint for the refactoring. If you split CLAUDE.md and move critical rules (token types, backend conventions, merge point protocol) to `docs/TOKEN_TYPES.md`, every fresh Claude session — including every Ralph iteration — starts **without** those rules.

### What This Means Concretely

**Before refactoring (current):**
```
Session starts → CLAUDE.md (1,117 lines) auto-loaded → all rules available
```

**After naive refactoring (BROKEN):**
```
Session starts → CLAUDE.md (100 lines) auto-loaded → only TOC available
                 docs/TOKEN_TYPES.md NOT loaded → agent uses wrong token type → 401 error
                 docs/BACKEND_CONVENTIONS.md NOT loaded → agent creates files in wrong paths
```

**After correct refactoring (with SessionStart hook):**
```
Session starts → CLAUDE.md (100 lines) auto-loaded → TOC + critical rules available
              → SessionStart hook fires → reads .claude/compact-recovery.md
              → Critical rules injected into context
              → Agent has everything it needs
```

### What MUST Stay in CLAUDE.md (Never Move Out)

These rules cause immediate, hard-to-debug failures if missing. They must remain in the root CLAUDE.md file:

| Rule | Why It Can't Be Referenced | Failure Mode If Missing |
|------|---------------------------|------------------------|
| Login API returns `.token` not `.access_token` | Agent will get `null` token, cascade failures | Silent authentication failure |
| MCP Gateway requires `initialize` before `tools/call` | Agent will get "Session not found" error | Validation commands fail |
| Use `@pytest_asyncio.fixture` not `@pytest.fixture` for async | Agent writes broken tests | `AttributeError: 'async_generator'` |
| `< /dev/null` on every `claude --print` | Agent hangs silently in background | AFK iteration never starts |
| Never use `--dangerously-skip-permissions` | Agent bypasses all safety | Security violation |
| Agent JWT vs User Token vs Internal Token | Agent uses wrong auth type | 401 errors on vault/delegation endpoints |

### What Can Be Moved to Reference Docs

These are important but not catastrophic if an agent has to read them on-demand:

| Content | Move To | Token Savings |
|---------|---------|--------------|
| Development commands (`make install-dev`, `pytest`, etc.) | `docs/DEVELOPMENT_COMMANDS.md` | ~500 tokens |
| Full architecture overview (module structure, service ports) | `docs/ARCHITECTURE.md` | ~800 tokens |
| Testing strategy (test org, markers, fixtures) | `docs/TESTING_STRATEGY.md` | ~600 tokens |
| Token types full table (all three types, when to use each) | `docs/TOKEN_TYPES.md` | ~400 tokens |
| Lessons learned changelog (all 16 entries) | `docs/LESSONS_LEARNED.md` | ~1,200 tokens |
| Task breakdown workflow (templates, workstream patterns) | `docs/TASK_WORKFLOW.md` | ~1,500 tokens |
| Backend file path conventions | `docs/BACKEND_CONVENTIONS.md` | ~400 tokens |
| Self-verification 4-stage process | `docs/SELF_VERIFICATION.md` | ~800 tokens |
| Code quality rules (DRY, error handling, security) | `CODE_STANDARDS.md` (reviewer agent only) | ~600 tokens |
| **Total savings** | | **~6,800 tokens** |

### The Loading Mechanism

Two complementary mechanisms ensure reference docs are available when needed:

**1. SessionStart Hook (`compact-recovery.sh`)**

Fires on every session start and after every compaction event. Injects critical context:

```bash
#!/bin/bash
# .claude/hooks/compact-recovery.sh
# Reinject critical rules that MUST be in context

cat .claude/compact-recovery.md
# Contains: token types summary, MCP protocol, async fixtures,
# backend conventions summary, current workstream status
```

**2. Ralph Prompt Template**

Every Ralph iteration's prompt explicitly instructs the agent to read reference docs:

```markdown
# In ralph-prompt.md:
Before starting work, read these reference files:
- docs/TOKEN_TYPES.md (authentication patterns)
- docs/BACKEND_CONVENTIONS.md (file path rules)
- docs/TESTING_STRATEGY.md (test patterns)
```

**Both mechanisms must be verified before splitting CLAUDE.md.** This is why Phase 3 (CLAUDE.md Refactoring) has a hard prerequisite on Phase 1 (SessionStart hook verified).

---

## Target Structure After Refactoring

```
CLAUDE.md                              (~100-150 lines, TOC + critical rules)
CODE_STANDARDS.md                      (reviewer agent only — not loaded during implementation)
.claude/compact-recovery.md            (re-injected after compaction via SessionStart hook)
.afk/learnings.md                      (AFK loop failure log)
docs/
  DEVELOPMENT_COMMANDS.md              (extracted: setup, test, lint, build commands)
  ARCHITECTURE.md                      (extracted: module structure, patterns, ports)
  TESTING_STRATEGY.md                  (extracted: test org, markers, fixtures, pitfalls)
  TOKEN_TYPES.md                       (extracted: token types, auth flows, agent JWT creation)
  LESSONS_LEARNED.md                   (extracted: pitfalls changelog, anti-patterns)
  TASK_WORKFLOW.md                     (extracted: breakdown, ticket structure, workstream prereqs)
  BACKEND_CONVENTIONS.md               (extracted: file paths, naming, service directories)
  SELF_VERIFICATION.md                 (extracted: 4-stage review, micro/macro/meta checks)
  AFK_WORKFLOWS.md                     (existing — research document)
  AFK_DEVELOPER_WORKFLOW.md            (existing — end-to-end developer guide)
  AFK_CONTEXT_BUDGET.md                (existing — context budget analysis)
```

### Slim CLAUDE.md Template (~100-150 lines)

From the AFK research doc (adapted for DeepSecure):

```markdown
# CLAUDE.md

## Project
DeepSecure: Identity-as-Code for AI agents. Python CLI/SDK + backend services.

## Quick Reference
- Install: `make install-dev`
- Test: `pytest` | `make test-cov`
- Lint: `ruff check .` | `mypy deepsecure/`
- Format: `black .` | `isort .`
- All checks: `make check-all`

## Critical Rules
1. Always run `make check-all` before declaring done
2. Use correct token types (see docs/TOKEN_TYPES.md)
   - Login returns `.token` NOT `.access_token`
   - Vault endpoints need Agent JWT, not User Token
   - Vault refresh needs Internal Token + X-User-ID header
3. Verify file paths exist before documenting them
4. Never commit secrets or private keys
5. MCP Gateway requires `initialize` before `tools/call`
6. Use `@pytest_asyncio.fixture` for async fixtures, not `@pytest.fixture`
7. `< /dev/null` on every `claude --print` invocation (AFK)

## Architecture (read docs/ARCHITECTURE.md for details)
- `deepsecure/_core/`: Internal implementation
- `deepsecure/`: Public API layer
- `deeptrail-control/`: Control plane (port 8000)
- `deeptrail-gateway/`: Data plane (port 8002)

## Detailed References
| Topic | File |
|-------|------|
| Development commands | docs/DEVELOPMENT_COMMANDS.md |
| Architecture & patterns | docs/ARCHITECTURE.md |
| Testing strategy | docs/TESTING_STRATEGY.md |
| Token types & auth | docs/TOKEN_TYPES.md |
| Lessons learned | docs/LESSONS_LEARNED.md |
| Task workflow | docs/TASK_WORKFLOW.md |
| Backend conventions | docs/BACKEND_CONVENTIONS.md |
| Self-verification | docs/SELF_VERIFICATION.md |
| Code standards (review only) | CODE_STANDARDS.md |
| AFK workflows | docs/AFK_WORKFLOWS.md |
```

---

## Token Impact

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| CLAUDE.md tokens | ~8,700 | ~2,000 | ~6,700 (77%) |
| Per-session base context | ~99,000 | ~92,300 | ~6,700 |
| Per-session with on-demand loading | ~99,000 | ~95,000 (if all refs loaded) | ~4,000 |
| Per-session without ref loading | ~99,000 | ~92,300 | ~6,700 |

The primary gain is not the raw token savings (~6,700) but the **progressive disclosure** — agents only load reference docs when working in a domain that needs them. A Ralph iteration implementing auth endpoints loads `TOKEN_TYPES.md`; one implementing UI changes doesn't.

---

## Verification Checklist (Before Splitting)

These must ALL pass before CLAUDE.md is split:

- [ ] `SessionStart` hook fires correctly on new sessions
- [ ] `SessionStart(compact)` hook fires correctly after compaction
- [ ] `compact-recovery.sh` successfully injects `.claude/compact-recovery.md` content
- [ ] Fresh `claude --print` session loads all critical rules via hook
- [ ] Ralph iteration with slim CLAUDE.md + hook produces same quality output as current monolithic CLAUDE.md
- [ ] All reference doc files exist and are complete
- [ ] `ralph-prompt.md` template includes explicit read instructions for reference docs

**Do NOT split CLAUDE.md until all boxes are checked.** The split without a verified loading mechanism is a regression.

---

## References

- OpenAI — "Harness Engineering" ([openai.com](https://openai.com/index/harness-engineering/)) — AGENTS.md as TOC pattern
- Boris Cherny — CLAUDE.md as compounding engineering ([howborisusesclaudecode.com](https://howborisusesclaudecode.com/))
- Matt Pocock — CODE_STANDARDS.md pattern (save tokens during implementation, spend during review)
- Peter Steinberger — Iterative rules, shared AGENTS.MD ([steipete.me](https://steipete.me/posts/just-talk-to-it))
- `docs/AFK_WORKFLOWS.md` lines 677-703 — CLAUDE.md as TOC analysis
- `docs/AFK_WORKFLOWS.md` lines 2500-2566 — Phase 5 refactoring plan and slim template
- `docs/spec/afk-workflow-enablement-spec.md` — WS-E workstream (Phase 3)
