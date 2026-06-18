# Autofix PR: Autonomously Fix CI Failures and Review Comments

Fetch CI failure logs and review comments for a PR, diagnose issues, apply fixes, and re-push. Designed for AFK mode — CI fails, this fixes it without human intervention.

## Invocation

```
/autofix-pr <pr-number> [--auto-commit] [--max-attempts 3]
```

**Parameters:**
- `pr-number` — The PR to fix (required)
- `--auto-commit` — Commit and push fixes automatically (default: show diff and ask)
- `--max-attempts` — Maximum fix-push-wait cycles before giving up (default: 3)

---

## Instructions

### Step 1: Fetch PR State

```bash
# Get PR details and branch
PR_BRANCH=$(gh pr view <pr-number> --json headRefName --jq '.headRefName')
gh pr checks <pr-number> --json name,state,conclusion

# Checkout the PR branch
git fetch origin "$PR_BRANCH"
git checkout "$PR_BRANCH"
```

### Step 2: Diagnose CI Failures

```bash
# Get failing check details
FAILING=$(gh pr checks <pr-number> --json name,conclusion --jq '.[] | select(.conclusion == "FAILURE") | .name')

# For each failing check, get the log
for CHECK in $FAILING; do
    echo "=== $CHECK ==="
    gh run view --log-failed 2>/dev/null | tail -50
done
```

**Common failure patterns and fixes:**

| Failure Pattern | Diagnosis | Auto-Fix |
|----------------|-----------|----------|
| `ruff check` failure | Lint error | `ruff check --fix .` |
| `mypy` type error | Missing type annotation | Add annotation |
| `pytest` failure | Test assertion wrong | Read test, check if test or code is wrong |
| Import error | Missing dependency or wrong path | Fix import path |
| Merge conflict | Branch diverged | `git merge origin/[base]`, resolve |

### Step 3: Fetch Review Comments

```bash
# Get pending review comments
gh api repos/:owner/:repo/pulls/<pr-number>/comments --jq '.[] | {path: .path, line: .line, body: .body, author: .user.login}'

# Get review threads
gh pr view <pr-number> --json reviewThreads --jq '.reviewThreads[] | select(.isResolved == false)'
```

**For each unresolved comment:**

1. Read the comment and the referenced code
2. Determine if the comment requests a code change
3. If it contains a suggestion block: apply the suggestion directly
4. If it's a question: add a reply explaining the rationale
5. If it's a requested change: implement the fix

### Step 4: Apply Fixes

For each diagnosed issue:

1. Make the code change
2. Run the relevant check locally to verify:
   ```bash
   ruff check [file]       # for lint fixes
   pytest [test_file] -v   # for test fixes
   mypy [file]             # for type fixes
   ```
3. If the local check passes, stage the change

### Step 5: Commit and Push

**If `--auto-commit`:**

```bash
git add -A
git commit -m "fix: address CI failures and review comments

- [list of fixes applied]

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

git push origin "$PR_BRANCH"
```

**If NOT `--auto-commit`:**

Show the diff and ask:

    ## Proposed Fixes for PR #[number]

    ### Changes
    | File | Fix | Addresses |
    |------|-----|-----------|
    | [file] | [what changed] | CI: [check name] / Review: [author] |

    ### Diff
    [git diff output]

    Apply these fixes? (yes / review / cancel)

### Step 6: Monitor (if auto-commit)

After pushing:

```bash
# Wait for CI to start
sleep 30

# Chain to /babysit-pr for monitoring
echo "Fixes pushed. Monitoring CI..."
```

Report:

    ## Autofix Applied to PR #[number]

    | Fix | Applied | Verified Locally |
    |-----|---------|-----------------|
    | [fix 1] | ✅ | ✅ passes |
    | [fix 2] | ✅ | ✅ passes |

    Pushed to: [branch]
    Waiting for CI: gh pr checks [number]

**If max attempts reached without CI passing:**

    ## Autofix Exhausted — PR #[number]

    Applied [N] fix attempts but CI still failing.
    Remaining failures require human investigation:

    | Check | Failure | Attempts |
    |-------|---------|----------|
    | [check] | [error summary] | [N] |

    Escalating — manual review needed.

---

## Safety Rules

1. **Never force-push** — always regular push
2. **Never modify files outside the PR's scope** — only fix what the CI or reviews flagged
3. **Always verify fixes locally** before pushing
4. **Stop after max attempts** — don't loop forever
5. **Log all changes** — every fix must be explainable

## When to Use

- CI is failing on a PR you created
- Reviewer left actionable comments you want to address quickly
- During AFK mode, chained after `/babysit-pr` detects a CI failure

**When NOT to use:**
- The CI failure is in infrastructure (not your code)
- The review comment requires a design discussion
- The PR is someone else's (unless explicitly asked to help)

## Related Skills

- `/babysit-pr` — Monitors PR; can chain to this on CI failure
- `/go` — Creates the PR; if CI fails, chain to this
- `/security-scan` — If security check fails, run this for details
