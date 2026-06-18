# Triage: Discover and Prioritize Work

Scan multiple sources (GitHub issues, failing CI, stale progress, STATUS.md) to discover and prioritize what to work on next. Outputs a ranked work list for Ralph loop consumption or manual review.

## Invocation

```
/triage [workstream-name] [--source github|local|all] [--include-stale]
```

**Parameters:**
- `workstream-name` — Focus on a specific workstream (optional; default: scan all)
- `--source` — Where to look: `github` (issues + PRs), `local` (STATUS.md + progress JSON), `all` (default)
- `--include-stale` — Include tasks from previous AFK runs that stalled

---

## Instructions

### Step 1: Scan Sources

#### 1a. Local Sources (always checked)

```bash
# Check STATUS.md for incomplete tasks
if [ -n "$WORKSTREAM" ]; then
  grep -E "⏳|🔄|❌" "docs/workstreams/${WORKSTREAM}/STATUS.md" 2>/dev/null
fi

# Check ralph_progress.json for stalled tasks
if [ -f ".afk/ralph_progress.json" ]; then
  python3 -c "
import json
with open('.afk/ralph_progress.json') as f:
    d = json.load(f)
if d.get('metadata', {}).get('circuit_breaker') == 'OPEN':
    print('⚠️ Circuit breaker is OPEN — previous run stalled')
for task in d.get('tasks', []):
    if task.get('status') != 'complete':
        print(f\"  Incomplete: {task.get('id')} — {task.get('description', 'no description')}\")
"
fi

# Check for failing tests
python -m pytest tests/ --co -q 2>/dev/null | tail -5
```

#### 1b. GitHub Sources (if `--source github` or `--source all`)

```bash
# Open issues
gh issue list --state open --limit 20 --json number,title,labels,updatedAt

# Failing CI on current branch
gh run list --branch "$(git branch --show-current)" --limit 5 --json status,conclusion,name

# PRs needing attention
gh pr list --state open --json number,title,reviewDecision,statusCheckRollup
```

#### 1c. Stale AFK Tasks (if `--include-stale`)

```bash
# Check .afk/learnings.md for known failure patterns
[ -f ".afk/learnings.md" ] && cat .afk/learnings.md

# Check .afk/cost-log.txt for previous run costs
[ -f ".afk/cost-log.txt" ] && tail -5 .afk/cost-log.txt
```

### Step 2: Classify and Prioritize

Assign priority based on these rules:

| Priority | Criteria | Examples |
|----------|----------|---------|
| **P0 — Blocking** | Failing CI on main/dev, broken health checks | CI red, service down |
| **P1 — High** | Blocked tasks with identified root cause, security vulnerabilities | Stalled task with known fix |
| **P2 — Normal** | Open issues with engagement, next batch tasks | GitHub issues with 3+ reactions |
| **P3 — Backlog** | Nice-to-have, low-priority cleanup | Refactoring suggestions |

**De-duplication rules:**
- If a GitHub issue maps to a workstream task, show only the task (richer context)
- If a task appears in both STATUS.md and progress JSON, prefer STATUS.md
- Skip tasks already marked as complete

### Step 3: Generate Prioritized Output

Create `reports/triage-[YYYY-MM-DD-HHMMSS].md`:

```markdown
## Triage Report — [timestamp]

### P0 — Blocking
| # | Source | Item | Action |
|---|--------|------|--------|
| 1 | CI | test_agent_auth.py failing | Fix mock for delegation endpoint |

### P1 — High
| # | Source | Item | Action |
|---|--------|------|--------|
| 2 | STATUS.md | WS-C3 incomplete | Resume /autofix-pr implementation |

### P2 — Normal
| # | Source | Item | Action |
|---|--------|------|--------|
| 3 | GitHub #42 | Add retry logic to gateway calls | Implement with exponential backoff |

### P3 — Backlog
| # | Source | Item | Action |
|---|--------|------|--------|
| 4 | GitHub #55 | Update README examples | Low priority |

### Stats
- Total items found: [N]
- P0: [count] | P1: [count] | P2: [count] | P3: [count]
- Stale tasks recovered: [count]
```

### Step 4: Output Summary

Print to stdout:

```
Triage complete:
  P0 (blocking): [N] items
  P1 (high):     [N] items
  P2 (normal):   [N] items
  P3 (backlog):  [N] items

  Report: reports/triage-[timestamp].md
  Top item: [P0/P1 item description]

  Next: Review the report, then run the appropriate /run-batch or /execute-task.
```

---

## Safety Rules

1. **Triage does NOT auto-execute work.** It discovers and prioritizes only.
2. **The developer reviews triage output** before starting any work.
3. **For AFK mode:** Ralph reads the triage output as its prompt, but the developer reviewed and approved the triage first.
4. **Never create issues or PRs** from triage — that's a separate action.

## When to Use

- Starting a work session (what should I work on?)
- Before an AFK Ralph loop (what should Ralph work on?)
- After returning from AFK (what happened while I was gone?)
- When context-switching between workstreams

**When NOT to use:**
- When you already know exactly what to work on
- When executing a specific `/run-batch` command

## Related Skills

- `/afk-summary` — What happened during the AFK run
- `/run-batch` — Execute a specific batch (after triage identifies which batch)
- `/afk` — Switch to AFK mode before starting Ralph
