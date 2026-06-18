# Context Loading Strategy

How project instructions and reference documentation are loaded across CLI agents (Claude Code, Gemini CLI, OpenAI Codex), Cursor IDE, and AFK autonomous agents.

## Problem

A single monolithic instruction file (CLAUDE.md at 1,117 lines) wastes context budget — every session loads all 1,117 lines regardless of what the agent is actually doing. But splitting it into smaller files creates a different problem: the agent may not proactively read the extracted files, leading to mistakes that the monolithic version would have prevented.

The solution is a tiered loading architecture that guarantees critical rules are always present while making reference documentation available through context-appropriate mechanisms.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Tier 1: CLAUDE.md (204 lines) — AUTO-LOADED, ALL CONTEXTS    │
│                                                                 │
│   Contains only rules with a proven failure history:            │
│   • Token types table (5 incidents)                             │
│   • MCP Gateway protocol sequence (caused Session Not Found)    │
│   • Async test fixture rule (caused AttributeError)             │
│   • API contract verification pattern                           │
│   • Merge point protocol (sequential gate)                      │
│   • Workstream prerequisites (7-file check)                     │
│   • Test suite health (all tests must pass)                     │
│   • Pre-completion checklist                                    │
│   • Backend file path conventions                               │
│                                                                 │
│   Also contains Quick Reference table pointing to Tier 2 docs.  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
┌──────────────────────────┐  ┌──────────────────────────────────┐
│                          │  │                                  │
│  Tier 2: Reference Docs  │  │  Tier 3: Compact Recovery Hook  │
│  (4 files, 476 lines)   │  │  (27 lines, CLI/AFK only)       │
│                          │  │                                  │
│  • DEVELOPMENT_COMMANDS  │  │  Injected after context          │
│  • ARCHITECTURE          │  │  compaction. Covers the 6 most   │
│  • TESTING_GUIDE         │  │  dangerous gotchas as a cheat    │
│  • CODE_STANDARDS        │  │  sheet so the agent doesn't      │
│                          │  │  lose critical rules when prior   │
│  Pure reference — never  │  │  context is summarized.          │
│  caused agent failures.  │  │                                  │
│  Safe to load on demand. │  │  File: .claude/compact-recovery  │
│                          │  │  Hook: .claude/hooks/            │
│                          │  │        compact-recovery.sh       │
└──────────────────────────┘  └──────────────────────────────────┘
```

## How Each Tier Loads by Context

### Tier 1: CLAUDE.md (Auto-Loaded)

| Context | Loading Mechanism | Guaranteed |
|---------|-------------------|------------|
| **Claude Code CLI** | Runtime reads `CLAUDE.md` from project root at session start | Yes |
| **Gemini CLI** | Reads `GEMINI.md` (symlink or copy of `CLAUDE.md`) at session start | Yes |
| **OpenAI Codex CLI** | Reads `AGENTS.md` or `CODEX.md` (symlink or copy) at session start | Yes |
| **Cursor IDE** | Reads `.cursorrules` or `CLAUDE.md` at session start | Yes |
| **AFK (ralph.sh)** | Auto-loaded by `claude --print` runtime + Tier 2 injected via `--system-prompt` | Yes |

**For non-Claude CLIs:** Create symlinks or copies of `CLAUDE.md` with the filename each CLI expects:
```bash
# Gemini CLI
ln -s CLAUDE.md GEMINI.md

# OpenAI Codex
ln -s CLAUDE.md AGENTS.md

# Cursor IDE (if not reading CLAUDE.md directly)
ln -s CLAUDE.md .cursorrules
```

The content is tool-agnostic — it contains project rules, not Claude-specific instructions. Any LLM agent benefits from the same guardrails.

### Tier 2: Reference Docs (Context-Dependent Loading)

These files contain reference material that has never caused agent failures when absent. They are useful but not critical.

| File | Lines | Content |
|------|-------|---------|
| `docs/DEVELOPMENT_COMMANDS.md` | 156 | Environment setup, testing, build, debugging, service ports |
| `docs/ARCHITECTURE.md` | 75 | Module structure, backend services, key patterns |
| `docs/TESTING_GUIDE.md` | 101 | Test organization, markers, suite health rules |
| `CODE_STANDARDS.md` | 147 | Engineering preferences, code review, verification model |

**How each context accesses Tier 2:**

| Context | Loading Mechanism | Reliability |
|---------|-------------------|-------------|
| **Claude Code CLI** | Agent reads file via `Read` tool when Quick Reference table indicates relevance | ~80% — depends on agent judgment |
| **Gemini CLI** | Agent reads file when needed | ~80% |
| **Codex CLI** | Agent reads file when needed | ~80% |
| **Cursor IDE** | Agent reads file when needed | ~80% |
| **AFK (ralph.sh / afk-once.sh)** | **Injected into `--system-prompt`** — all 4 docs are prepended to the workstream prompt before the agent starts | **100%** |

#### AFK Injection Logic

Both `scripts/ralph.sh` and `scripts/afk-once.sh` contain this injection block:

```bash
# Inject extracted reference docs into system prompt for full AFK coverage.
# CLAUDE.md is auto-loaded but these docs are not — without injection, the AFK
# agent would need to proactively Read them, which is unreliable.
REF_DOCS=""
for doc in docs/DEVELOPMENT_COMMANDS.md docs/ARCHITECTURE.md docs/TESTING_GUIDE.md CODE_STANDARDS.md; do
    [ -f "$doc" ] && REF_DOCS="${REF_DOCS}
$(cat "$doc")
"
done

if [ -n "$REF_DOCS" ]; then
    PROMPT_CONTENT="${PROMPT_CONTENT}

---
# Reference Documentation (auto-injected for AFK context)
${REF_DOCS}"
fi
```

This runs before `claude --print --system-prompt "$PROMPT_CONTENT"`, so the AFK agent receives:
1. The workstream-specific Ralph prompt (from `ralph-prompt.md`)
2. All 4 reference docs appended after a `---` separator
3. Plus CLAUDE.md auto-loaded by the runtime

Total AFK context at session start: ~680 lines of project rules (204 CLAUDE.md + 476 injected).

### Tier 3: Compact Recovery Hook (Post-Compaction Safety Net)

When a conversation exceeds context limits, the runtime compresses prior messages into a summary. Critical rules from CLAUDE.md may be lost in this summarization. The compact recovery hook re-injects a 27-line cheat sheet covering the 6 most dangerous categories.

**File:** `.claude/compact-recovery.md`

**Contents:**
```
Token Types       → .token not .access_token, Agent JWT for vault, Internal Token for refresh
MCP Protocol      → initialize FIRST, then tools/list, then tools/call
Async Fixtures    → @pytest_asyncio.fixture, NOT @pytest.fixture
Merge Protocol    → Validation → Container Deploy → Container Tests → Success Criteria → Merge Actions
Self-Verification → ReadLints after edits, run tests before completion
File Paths        → [service]/app/ prefix, tests/ at root for cross-service
```

**Hook:** `.claude/hooks/compact-recovery.sh` — triggered on `SessionStart` after compaction, outputs the cheat sheet content to stdout so the agent sees it in its next context window.

| Context | Available | Why |
|---------|-----------|-----|
| **Claude Code CLI** | Yes | Claude Code hooks API supports SessionStart events |
| **Gemini CLI** | No | No equivalent hook mechanism |
| **Codex CLI** | No | No equivalent hook mechanism |
| **Cursor IDE** | No | Cursor does not support Claude Code hooks |
| **AFK** | Yes | Runs via Claude Code runtime, hooks apply |

For CLIs without hook support, the critical rules are still present in Tier 1 (CLAUDE.md) and will survive compaction if the runtime's summarization preserves the instruction file — which it typically does, since instruction files are treated as system-level context.

## Coverage Matrix

| Context | Tier 1 (critical rules) | Tier 2 (reference docs) | Tier 3 (post-compaction) | Overall |
|---------|------------------------|------------------------|-------------------------|---------|
| **Claude Code CLI** | Auto-loaded (100%) | Read on demand (~80%) | Hook injected (100%) | ~95% |
| **Gemini CLI** | Auto-loaded via GEMINI.md (100%) | Read on demand (~80%) | Not available | ~90% |
| **Codex CLI** | Auto-loaded via AGENTS.md (100%) | Read on demand (~80%) | Not available | ~90% |
| **Cursor IDE** | Auto-loaded (100%) | Read on demand (~80%) | Not available | ~90% |
| **AFK (Ralph)** | Auto-loaded (100%) | Injected (100%) | Hook injected (100%) | ~100% |

## Why This Split

The decision of what stays inline vs. what gets extracted is based on empirical failure data, not intuition.

### Inline (Tier 1) — Has caused real agent failures

| Rule | Incidents | What Went Wrong |
|------|-----------|-----------------|
| Token type confusion | 5 | Agent used `.access_token` instead of `.token`, wrong token type for vault ops |
| MCP initialize-first | 3 | Agent called `tools/call` without `initialize`, got "Session not found" |
| Async fixture decorator | 2 | Agent used `@pytest.fixture` for async, got AttributeError |
| Merge point ordering | 1 | Agent ran git tag before container tests — unvalidated merge point |
| Test suite health | 1 | 151 pre-existing failures dismissed as "not my workstream" |
| Codebase exploration | 1 | Tasks created for "missing" components that already existed |

### Extracted (Tier 2) — Never caused agent failures

| Document | Why It's Safe to Extract |
|----------|-------------------------|
| `DEVELOPMENT_COMMANDS.md` | Agent can discover commands via `make help`, `--help` flags |
| `ARCHITECTURE.md` | Agent can discover structure via `find`, `ls`, `grep` |
| `TESTING_GUIDE.md` | Standard pytest patterns; the one dangerous rule (async fixtures) is inline |
| `CODE_STANDARDS.md` | Only needed during formal code reviews, not every task |

## Adding New Rules

When adding a new rule to the project:

1. **Has this caused a real failure?** If yes → add to CLAUDE.md (Tier 1) and add a row to the Lessons Learned table
2. **Is this reference material the agent can discover?** If yes → add to the appropriate Tier 2 doc
3. **Is this a critical gotcha that must survive compaction?** If yes → also add a one-liner to `.claude/compact-recovery.md`

## File Inventory

| File | Location | Lines | Tier | Auto-loaded |
|------|----------|-------|------|-------------|
| `CLAUDE.md` | Project root | 204 | 1 | All contexts |
| `docs/DEVELOPMENT_COMMANDS.md` | `docs/` | 156 | 2 | AFK only |
| `docs/ARCHITECTURE.md` | `docs/` | 75 | 2 | AFK only |
| `docs/TESTING_GUIDE.md` | `docs/` | 101 | 2 | AFK only |
| `CODE_STANDARDS.md` | Project root | 147 | 2 | AFK only |
| `docs/TOKEN_TYPES.md` | `docs/` | 172 | 2* | AFK only |
| `.claude/compact-recovery.md` | `.claude/` | 27 | 3 | Post-compaction |

*`TOKEN_TYPES.md` contains the full Agent JWT creation flow (6-step Ed25519 challenge-response). The critical summary (token table, MCP sequence, async fixture rule) is inline in CLAUDE.md. The full flow is in `TOKEN_TYPES.md` for when the agent needs to write validation commands.

## Adapting for Non-Claude CLIs

To use this strategy with Gemini CLI, OpenAI Codex, or other CLI coding agents:

### 1. Create the instruction file symlink

```bash
# Pick the filename your CLI expects
ln -s CLAUDE.md GEMINI.md      # Gemini CLI
ln -s CLAUDE.md AGENTS.md      # Codex CLI
ln -s CLAUDE.md .cursorrules   # Cursor (if needed)
```

### 2. AFK injection works regardless of CLI

The `ralph.sh` and `afk-once.sh` scripts use `claude --print`, but the injection pattern is portable. For a Gemini-based AFK loop:

```bash
# Same injection logic, different CLI command
PROMPT_CONTENT=$(cat "$PROMPT_FILE")
for doc in docs/DEVELOPMENT_COMMANDS.md docs/ARCHITECTURE.md docs/TESTING_GUIDE.md CODE_STANDARDS.md; do
    [ -f "$doc" ] && PROMPT_CONTENT="${PROMPT_CONTENT}\n$(cat "$doc")"
done

gemini --prompt "$PROMPT_CONTENT" ...
```

### 3. Compact recovery is Claude-specific

The hook mechanism (`.claude/hooks/`) is Claude Code-specific. For other CLIs, ensure the critical rules in CLAUDE.md Tier 1 are comprehensive enough to survive without post-compaction injection. Currently they are — the compact recovery hook is a safety net, not a requirement.
