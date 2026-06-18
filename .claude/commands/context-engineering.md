# Context Engineering: Manage Context Budget and Compaction

Reference guide for managing Claude Code's context window effectively: compaction thresholds, recovery hooks, MCP connectors, and best practices for long-running sessions.

## Invocation

```
/context-engineering
```

No arguments — prints guidance and a reference card.

---

## Instructions

When this skill is invoked, output the following reference material:

### 1. Context Budget

```
┌──────────────────────────────────────────────────────┐
│  Claude Code Context Window                          │
│  ══════════════════════════════════════════════════   │
│                                                      │
│  Total window:           ~200k tokens                │
│  CLAUDE.md + system:     ~25-35k tokens              │
│  Available for work:     ~165-175k tokens            │
│                                                      │
│  Auto-compact threshold: configurable                │
│  Recommended setting:    CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000  │
│                                                      │
│  ⚠️  After compaction, only the summary survives.    │
│     Critical rules MUST be in:                       │
│     - CLAUDE.md (always loaded)                      │
│     - SessionStart compact hook (re-injected)        │
│     - NOT in conversation history (lost)             │
└──────────────────────────────────────────────────────┘
```

### 2. What Survives Compaction

| Source | Survives? | Notes |
|--------|-----------|-------|
| CLAUDE.md content | Yes | Always reloaded |
| SessionStart compact hook output | Yes | Re-injected on compaction |
| Conversation instructions ("remember to X") | **No** | Lost — use CLAUDE.md or hooks |
| Tool results from earlier turns | **No** | Summarized only |
| File contents you Read earlier | **No** | Must re-read if needed |
| Task/plan state | **Partially** | Summary captures high-level state |

### 3. Compact Recovery Hook

The `SessionStart(compact)` hook at `.claude/hooks/compact-recovery.sh` injects critical rules after compaction:

```
Critical rules re-injected:
├── Token types (User Token vs Agent JWT vs Internal)
├── MCP Gateway protocol (initialize before tools/call)
├── Async fixture pattern (@pytest_asyncio.fixture)
├── Merge point protocol (validation before merge actions)
└── Self-verification checklist
```

**To test the hook:**
```bash
bash .claude/hooks/compact-recovery.sh
```

**To update injected rules:** Edit `.claude/compact-recovery.md`

### 4. MCP Connectors Available

| Connector | Purpose | Use Case |
|-----------|---------|----------|
| GitHub MCP | PR status, issues, comments | `/triage`, `/babysit-pr` |
| Notion MCP | Page read/write | Documentation sync |
| Figma MCP | Design context | UI implementation |

**Adding a new MCP connector:**
```json
// In .claude/settings.local.json or MCP config
{
  "mcpServers": {
    "connector-name": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-name"]
    }
  }
}
```

### 5. Best Practices

**DO:**
- Put persistent constraints in CLAUDE.md (survives everything)
- Put critical recovery rules in `.claude/compact-recovery.md` (survives compaction)
- Use `--output-format json` in AFK mode to track token usage
- Break large tasks into batches that fit within context
- Use `/afk-summary` after long sessions to capture what happened

**DON'T:**
- Set constraints conversationally ("remember to always X") — lost on compaction
- Assume you still have file contents from 50+ turns ago — re-read
- Run 20+ tasks in a single context window — split across Ralph iterations
- Ignore compaction warnings — they mean context is about to be summarized

### 6. Debugging Compaction Issues

If behavior changes mid-session (rules forgotten, patterns ignored):

1. **Check if compaction occurred:** Look for the compaction summary message
2. **Verify hook ran:** Check if compact-recovery output appears after the summary
3. **Re-read critical files:** CLAUDE.md, task ticket, spec — don't rely on memory
4. **Check `.claude/compact-recovery.md`:** Does it contain the rule that was forgotten?

---

## When to Use

- Starting a long AFK session (review context budget first)
- After noticing Claude "forgot" a rule mid-session
- When configuring MCP connectors for a new workflow
- When debugging why a hook or rule isn't being applied

## Related Skills

- `/afk` — Toggle AFK mode (adjusts verbosity/permissions)
- `/afk-summary` — Generate post-session comprehension report
