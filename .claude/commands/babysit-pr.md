# Babysit PR: Monitor PR Through CI → Review → Merge Lifecycle

Monitor a pull request through its full lifecycle: CI checks, reviewer feedback, merge readiness. Send notifications at each stage transition. Designed for AFK mode — you walk away, this keeps watching.

## Invocation

```
/babysit-pr <pr-number> [--auto-merge] [--interval 300]
```

**Parameters:**
- `pr-number` — The PR number to monitor (required)
- `--auto-merge` — Automatically merge when all conditions met (default: notify only)
- `--interval` — Check interval in seconds (default: 300 = 5 minutes)

---

## Instructions

### Step 1: Initial PR Assessment

Fetch current PR state:

```bash
# Get PR details
gh pr view <pr-number> --json title,state,reviewDecision,statusCheckRollup,mergeable,headRefName,baseRefName,isDraft

# Get CI check status
gh pr checks <pr-number>

# Get review status
gh pr view <pr-number> --json reviews --jq '.reviews[] | {author: .author.login, state: .state}'
```

Report initial state:

    ## Babysitting PR #[number]: [title]

    | Field | Status |
    |-------|--------|
    | Branch | [head] → [base] |
    | CI | [passing / failing / pending] |
    | Reviews | [N approved, M changes requested, K pending] |
    | Mergeable | [yes / no / conflicting] |
    | Draft | [yes / no] |

### Step 2: Monitor Loop

Enter monitoring loop. At each interval:

#### 2a. Check CI Status

```bash
gh pr checks <pr-number> --json name,state,conclusion
```

**State transitions to notify on:**
- `pending → in_progress` — "CI started running"
- `in_progress → success` — "CI passed"
- `in_progress → failure` — "CI FAILED: [failing check names]"
- `failure → success` (after fix push) — "CI recovered after fix"

#### 2b. Check Review Status

```bash
gh pr view <pr-number> --json reviews,reviewDecision
```

**Transitions to notify:**
- New review submitted → "Review from [author]: [APPROVED / CHANGES_REQUESTED / COMMENTED]"
- All required reviewers approved → "All reviews approved"
- Changes requested → "Changes requested by [author]: [first comment]"

#### 2c. Check Merge Readiness

A PR is merge-ready when ALL conditions are true:
- [ ] All CI checks passing
- [ ] At least one approval (or review not required)
- [ ] No merge conflicts
- [ ] Not a draft PR
- [ ] No changes requested (or changes addressed)

#### 2d. Send Notifications

For each state transition, notify via:

```bash
bash scripts/notify.sh "[PR #N]" "[status change description]" "[info|warning|error]"
```

| Event | Severity |
|-------|----------|
| CI passed | info |
| CI failed | error |
| Review approved | info |
| Changes requested | warning |
| Merge ready | info |
| Merge conflict | error |

### Step 3: Merge or Report

**If `--auto-merge` and all conditions met:**

```bash
gh pr merge <pr-number> --squash --delete-branch
bash scripts/notify.sh "PR #[N]" "Merged successfully" "info"
```

**If NOT `--auto-merge`:**

    ## PR #[number] is Merge-Ready

    All conditions met:
    - [x] CI passing
    - [x] Reviews approved
    - [x] No conflicts
    - [x] Not draft

    Waiting for manual merge. Run: gh pr merge [number] --squash

### Step 4: Generate Timeline

At the end (merge or manual stop), create `reports/pr-babysit-[PR_NUMBER].md`:

```markdown
## PR #[number] Babysit Report

### Timeline
| Time | Event |
|------|-------|
| [HH:MM] | Started monitoring |
| [HH:MM] | CI check started |
| [HH:MM] | CI passed |
| [HH:MM] | Review approved by [author] |
| [HH:MM] | Merged / Stopped |

### Summary
- Total monitoring time: [duration]
- CI runs: [count]
- Reviews received: [count]
- Final status: [merged / waiting / blocked]
```

---

## When to Use

- After creating a PR via `/go` or `/commit-push-pr`
- When you want to be notified about PR progress while AFK
- When waiting for CI on a critical PR

**When NOT to use:**
- Draft PRs still being worked on
- PRs you plan to force-push to (will trigger redundant CI notifications)

## Related Skills

- `/autofix-pr` — Fix CI failures and review comments automatically
- `/go` — Creates the PR; chain with `/babysit-pr` for full lifecycle
