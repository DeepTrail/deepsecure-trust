# Go: AFK-Friendly Ship Pipeline

Composite command: verify the app, lint, run adversarial review, then commit-push-PR. Append `/go` to any task to convert it from "implement interactively" to "implement and ship unattended."

## Workflow Position

```
/execute-task → [code changes] → /go
                                   ↑
                              (YOU ARE HERE)
                                   │
                                   ├── Step 1: /verify-app
                                   ├── Step 2: Lint + type check
                                   ├── Step 3: Adversarial review (afk-verifier agent)
                                   ├── Step 4: /security-scan
                                   └── Step 5: /commit-push-pr → PR URL
```

## Invocation

```
/go [--skip-verify] [--skip-review] [--skip-security] [--title "PR title"] [--reviewer username]
```

**Parameters:**
- `--skip-verify` — Skip `/verify-app` (services not available)
- `--skip-review` — Skip adversarial review step
- `--skip-security` — Skip `/security-scan`
- `--title` — Custom PR title (default: auto-generated from commits)
- `--reviewer` — Request specific reviewer on the PR

---

## Instructions

### Step 1: Verify Application

Run `/verify-app --skip-docker` (or full if services are available):

```bash
echo "Step 1/5: Verifying application..."
```

Invoke the `/verify-app` skill. If it reports failures:

    ## /go STOPPED at Step 1: Verification Failed

    [verification failure details]

    Fix the failures, then run `/go` again.

**Exit on failure.** Do not proceed to lint if tests are failing.

### Step 2: Lint & Type Check

```bash
echo "Step 2/5: Lint & type check..."

# Lint
ruff check deepsecure/ 2>&1
LINT_EXIT=$?

# Type check
mypy deepsecure/ --ignore-missing-imports 2>&1
MYPY_EXIT=$?
```

If lint fails:

```bash
# Auto-fix what can be fixed
ruff check deepsecure/ --fix
LINT_EXIT=$?
```

If still failing after auto-fix:

    ## /go STOPPED at Step 2: Lint/Type Failures

    [remaining errors]

    Fix manually, then run `/go` again.

### Step 3: Adversarial Review

Spawn the `afk-verifier` agent to review the diff:

```bash
echo "Step 3/5: Adversarial review..."

# Generate diff for review
DIFF=$(git diff --cached HEAD 2>/dev/null || git diff HEAD)
```

The afk-verifier agent reviews:
- Does every change match the task description?
- Are there unclear or suspicious modifications?
- Are there missing tests for new behavior?
- Are there security concerns?

**Agent verdict categories:**

| Verdict | Action |
|---------|--------|
| **APPROVE** | Proceed to Step 4 |
| **WARN** (non-blocking) | Log warnings, proceed |
| **BLOCK** (critical issue) | Stop, show review feedback |

If BLOCK:

    ## /go STOPPED at Step 3: Review Blocked

    The adversarial reviewer flagged critical issues:

    [review findings]

    Address the findings, then run `/go` again.

### Step 4: Security Scan

Run `/security-scan`:

```bash
echo "Step 4/5: Security scan..."
```

Invoke the `/security-scan` skill. If HIGH severity findings:

    ## /go STOPPED at Step 4: Security Issues

    [security findings]

    Fix HIGH severity issues, then run `/go` again.

### Step 5: Commit, Push, PR

```bash
echo "Step 5/5: Shipping..."
```

Invoke `/commit-push-pr`:

1. **Stage changes:**
   ```bash
   git add -A  # or specific files
   ```

2. **Generate commit message** from the changes:
   ```bash
   git commit -m "[auto-generated message based on diff analysis]

   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
   ```

3. **Push:**
   ```bash
   git push origin "$(git branch --show-current)"
   ```

4. **Create PR:**
   ```bash
   gh pr create --title "[title]" --body "[auto-generated body]"
   ```

### Final Output

    ## /go Complete

    | Step | Status |
    |------|--------|
    | 1. Verify | ✅ All tests pass |
    | 2. Lint | ✅ Clean |
    | 3. Review | ✅ Approved (N warnings) |
    | 4. Security | ✅ No HIGH findings |
    | 5. Ship | ✅ PR created |

    **PR:** [URL]

    Chain with: /babysit-pr [pr-number]

---

## Pipeline Behavior

The pipeline is **fail-fast**: if any step fails, all subsequent steps are skipped.

```
Step 1 FAIL → STOP (don't lint broken code)
Step 2 FAIL → STOP (don't review code with lint errors)
Step 3 BLOCK → STOP (don't ship code with critical review issues)
Step 4 FAIL → STOP (don't ship code with security vulnerabilities)
Step 5 FAIL → STOP (report git/gh error)
```

## When to Use

- After implementing a feature — `/go` handles everything from verify to PR
- In AFK mode — append `/go` to any task prompt for unattended ship
- When you want a single command to run the full quality pipeline

**When NOT to use:**
- Exploratory work (not ready to ship)
- When you need to manually craft the PR description
- When changes span multiple PRs (ship each separately)

## Related Skills

- `/verify-app` — Step 1 (standalone verification)
- `/security-scan` — Step 4 (standalone security scan)
- `/babysit-pr` — Post-ship monitoring (chain after `/go`)
- `/autofix-pr` — If CI fails after ship, fix automatically
- `/commit-push-pr` — Step 5 standalone (existing skill)
