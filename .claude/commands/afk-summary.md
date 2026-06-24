# AFK Summary: Post-Session Comprehension Report

Generate a human-readable comprehension report after an AFK run. Covers what changed, why, what was surprising, and what's next. Prevents "comprehension debt" — returning from AFK to find 20 commits with no context.

## Invocation

```
/afk-summary [workstream-name] [--verbose] [--summary-only]
```

**Parameters:**
- `workstream-name` — Which workstream to summarize (optional; default: current branch's workstream)
- `--verbose` — Include full diffs and test output
- `--summary-only` — One-page executive summary

---

## Instructions

### Step 1: Gather Data

Collect information from multiple sources:

```bash
WORKSTREAM="${1:-$(basename $(git branch --show-current) | sed 's/feature\///')}"

# Git history since last tag or last 24 hours
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~20")
echo "=== Commits since $LAST_TAG ==="
git log "$LAST_TAG"..HEAD --oneline --stat

# Ralph progress
if [ -f ".afk/ralph_progress.json" ]; then
    echo "=== Ralph Progress ==="
    python3 -c "
import json
with open('.afk/ralph_progress.json') as f:
    d = json.load(f)
meta = d.get('metadata', {})
print(f\"Iterations: {meta.get('iterations_completed', '?')}\")
print(f\"Cost: \${meta.get('total_cost_usd', '?')}\")
print(f\"Circuit breaker: {meta.get('circuit_breaker', '?')}\")
for task in d.get('tasks', []):
    print(f\"  {task.get('id')}: {task.get('status', 'unknown')}\")
"
fi

# Cost log
if [ -f ".afk/cost-log.txt" ]; then
    echo "=== Cost Log ==="
    cat .afk/cost-log.txt
fi

# STATUS.md
if [ -f "docs/workstreams/${WORKSTREAM}/STATUS.md" ]; then
    echo "=== STATUS.md ==="
    grep -E "✅|❌|⏳" "docs/workstreams/${WORKSTREAM}/STATUS.md"
fi

# Completion reports
echo "=== Completion Reports ==="
ls docs/workstreams/${WORKSTREAM}/reports/ 2>/dev/null
```

### Step 2: Analyze Changes

For each commit since the last tag/checkpoint:

1. **What changed:** Files modified, lines added/removed
2. **Why:** Extract from commit message and completion reports
3. **Impact:** Which tasks/acceptance criteria were addressed

```bash
# Per-commit analysis
git log "$LAST_TAG"..HEAD --format="%H|%s" | while IFS='|' read hash msg; do
    echo "--- $msg ---"
    git diff-tree --no-commit-id --name-status -r "$hash"
done
```

### Step 3: Generate Report

Create `reports/afk-summary-[YYYY-MM-DD].md`:

```markdown
## AFK Summary — [date]

### Executive Summary
[2-3 sentences: what was accomplished, any issues, overall status]

### Stats
| Metric | Value |
|--------|-------|
| Commits | [N] |
| Tasks completed | [M of T] |
| Files changed | [count] |
| Lines added | [+count] |
| Lines removed | [-count] |
| Total cost | $[X.XX] |
| Ralph iterations | [N] |
| Circuit breaker | [CLOSED / OPEN] |

### What Changed

#### [Task ID]: [Task Name]
- **Files:** [list]
- **Changes:** [1-2 sentence summary]
- **Tests:** [added/modified count]
- **Status:** Complete / Partial

[Repeat for each task]

### What Was Surprising
[Issues encountered, unexpected behaviors, workarounds applied]

1. [Surprising finding 1 — and how it was handled]
2. [Surprising finding 2]

### Lessons Learned
[Add to .afk/learnings.md if not already there]

- [Lesson 1]
- [Lesson 2]

### Quality Metrics
| Metric | Before | After |
|--------|--------|-------|
| Test count | [N] | [M] |
| Lint issues | [N] | [M] |
| Security findings | [N] | [M] |

### Next Steps
1. [Highest priority remaining work]
2. [Second priority]
3. [Third priority]

### Recommended Next Command
```
[/run-batch X Y] or [/triage] or [specific fix needed]
```
```

### Step 4: Output Summary

Print to stdout:

    ## AFK Summary Complete

    - Tasks completed: [M of T]
    - Commits: [N]
    - Cost: $[X.XX]
    - Issues: [count]
    - Report: reports/afk-summary-[date].md

    Top finding: [most important thing the developer should know]

---

## When to Use

- After returning from an AFK Ralph loop
- At the end of a workday to summarize progress
- Before a standup to generate a status update
- After `/run-batch` completes to capture what happened

**When NOT to use:**
- Mid-session (wait until a natural checkpoint)
- For single-task completions (the completion report is sufficient)

## Related Skills

- `/afk` — Toggle AFK mode
- `/triage` — Discover what to work on next
- `/run-batch` — Execute the next batch of work
