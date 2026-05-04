# Commit Push PR: Ship Changes After Review

Commit current changes, push to remote, and create a pull request. This is the final shipping step — only run after `/run-checks` and `/review` have passed.

## Workflow Position

```
... → /run-checks → /review → /commit-push-pr
                                    ↑
                               (YOU ARE HERE — final step)
```

## When to Use

- After `/review` approves the change (or approves with nits)
- When all quality checks pass (`/run-checks`)
- When you have a coherent set of changes ready to merge
- After fixing review feedback and re-running checks

**When NOT to use:**
- Before running `/run-checks` — checks must pass first
- Before `/review` — code must be reviewed first
- When there are uncommitted debugging artifacts (print statements, test skips)
- When changes span unrelated features — split into separate PRs first
- When working in a worktree that hasn't been synced — run `/sync-worktree-status` first

---

## Instructions

### Phase 1: PRE-FLIGHT — Verify Readiness

Before touching git, verify everything is in order:

```bash
# Check current state
git status
git diff --stat
git diff --staged --stat
```

**Use the Shell tool** to run these commands.

**Pre-flight checklist:**

| Check | Command | Expected |
|-------|---------|----------|
| No secrets in diff | `git diff \| grep -iE '(password\|secret\|token\|api_key)='` | Empty |
| No .env files staged | `git diff --staged --name-only \| grep '\.env'` | Empty |
| No debug artifacts | `git diff \| grep -E '(print\(|breakpoint\(\|pdb\|import pdb)'` | Empty |
| No large binaries | `git diff --staged --stat \| tail -1` | Reasonable size |
| Quality checks passed | `/run-checks` was run | All passed |
| Review completed | `/review` was run | Approved or approved-with-nits |

**If any pre-flight check fails, STOP and fix before proceeding.**

### Phase 2: STAGE — Select Changes

```bash
# Review what's changed
git diff --stat

# Stage specific files (preferred — explicit is better)
git add path/to/file1.py path/to/file2.py tests/test_file.py

# Or stage all tracked changes (only if you've reviewed everything)
git add -A
```

**Use the Shell tool** to stage files. **Never stage blindly** — review the diff first.

**Files to NEVER stage:**
- `.env`, `.env.local`, `.env.production`
- `credentials.json`, `*.pem`, `*.key`
- `__pycache__/`, `.pytest_cache/`
- IDE-specific files (`.idea/`, `.vscode/settings.json` with secrets)

### Phase 3: COMMIT — Write a Good Message

**Use the Shell tool** with a HEREDOC for the commit message:

```bash
git commit -m "$(cat <<'EOF'
feat: add token validation to gateway middleware

- Implement JWT signature verification in request pipeline
- Add rate limiting for failed auth attempts (5/min per agent)
- Include regression test for timezone-aware expiry edge case

Implements: WS-B3
EOF
)"
```

**Commit message format:**

```
<type>: <concise summary in imperative mood>

- <bullet point explaining what changed>
- <another change>
- <test or verification added>

[Optional: Implements: WS-XX, Closes #NN, Fixes #NN]
```

| Type | When |
|------|------|
| `feat:` | New feature or capability |
| `fix:` | Bug fix |
| `refactor:` | Code restructuring (no behavior change) |
| `test:` | Adding or updating tests only |
| `docs:` | Documentation only |
| `chore:` | Build, CI, dependency updates |
| `security:` | Security fix or hardening |

**Commit message rules:**
- Imperative mood: "add validation" not "added validation"
- First line under 72 characters
- Body explains *why*, not *what* (the diff shows what)
- Reference task IDs when implementing workstream tasks

### Phase 4: PUSH — Send to Remote

```bash
# Push current branch (set upstream if first push)
git push -u origin HEAD
```

**Safety checks before push:**
- Never force-push to `main`, `dev`, or `master`
- If push is rejected, pull and rebase first: `git pull --rebase origin [branch]`
- For worktree branches: push the feature branch, not dev

### Phase 5: PR — Create Pull Request

**Use the Shell tool** with `gh pr create`:

```bash
gh pr create --title "feat: add token validation to gateway" --body "$(cat <<'EOF'
## Summary
- Implement JWT signature verification in gateway request pipeline
- Add rate limiting for failed auth attempts
- Regression test for timezone-aware expiry edge case

## Task Reference
- Implements: WS-B3
- Design doc: `docs/design/gateway-auth.md`

## Test Plan
- [ ] `pytest deeptrail-gateway/tests/middleware/ -v` passes
- [ ] `pytest deeptrail-gateway/tests/security/ -v` passes
- [ ] Manual: curl with expired token returns 401
- [ ] Manual: curl with valid token returns 200

## Changes
- `deeptrail-gateway/app/middleware/auth.py` — JWT validation logic
- `deeptrail-gateway/app/security/rate_limiter.py` — Rate limiting
- `deeptrail-gateway/tests/middleware/test_auth.py` — Test coverage

EOF
)"
```

**PR body must include:**
1. **Summary** — What changed and why (bullet points)
2. **Task Reference** — Which workstream task(s) this implements
3. **Test Plan** — How to verify the change works
4. **Changes** — Key files modified

### Phase 6: POST-SHIP — Update Tracking

After PR is created:

```bash
# Get PR URL
gh pr view --web
```

If this implements a workstream task, the completion report from `/complete-task` should already reference the task. If not:

```bash
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
```

**Use StrReplace** to update relevant status files if needed:
- `$MAIN_REPO/docs/workstreams/[feature]/STATUS.md` — Add PR link
- `$MAIN_REPO/docs/workstreams/[feature]/WORKSTREAM.md` — Add PR link to task row

---

## Output Format

```markdown
## Changes Committed and PR Created

### Commit
- **Hash:** [short hash]
- **Message:** [first line of commit message]
- **Branch:** [branch name]

### Files Changed
- `path/to/file.py` (+[additions]/-[deletions])
- `tests/test_file.py` (+[additions]/-[deletions])

### Pull Request
- **PR:** [#number] [title](URL)
- **Base:** [target branch] ← [source branch]

### Pre-Flight Results
| Check | Status |
|-------|--------|
| No secrets in diff | ✅ |
| Quality checks passed | ✅ |
| Review completed | ✅ |

---

PR is ready for team review.
```

---

## Worktree-Specific Workflow

When shipping from a worktree:

```bash
# From worktree
cd /Users/imaxxs/repositories/[feature]-control

# Commit and push the worktree's feature branch
git add -A
git commit -m "feat: implement token service for control plane"
git push -u origin feature/[feature]-control

# Create PR targeting dev (not main)
gh pr create --base dev --title "feat: ..." --body "..."
```

**After PR is merged**, update main repo:
```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev
git pull
/sync-worktree-status [feature-name]
```

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "I'll clean up the commit message later" | You won't. Write it properly now — future you (and reviewers) will thank you. |
| "Let me just force-push to fix the history" | Force-push rewrites shared history. Use `--force-with-lease` on feature branches only, never on dev/main. |
| "I'll skip the PR and push directly to dev" | PRs exist for review and audit trail. Even solo developers benefit from the checkpoint. |
| "The review was informal, that counts" | Informal review is better than nothing, but `/review` catches things conversation doesn't. Run it. |
| "I need to ship fast, skip checks" | Shipping broken code is slower than shipping correct code. The 5-minute check saves the 2-hour rollback. |
| "This is just a docs change, no PR needed" | Docs changes still benefit from review. Typos in API docs cause support tickets. |
| "I'll squash the commits later" | Squash before the PR, not after. Messy history in PRs makes review harder. |
| "Let me include this unrelated fix too" | One PR = one logical change. Mixed PRs are harder to review, harder to revert, and hide bugs. |

## Red Flags

- Committing without running `/run-checks` first
- Force-pushing to `main`, `dev`, or `master`
- Using `--no-verify` to skip pre-commit hooks
- Staging `.env` files or credentials
- Commit messages that say "fix", "update", or "changes" with no context
- PRs with 500+ lines changed (split them — see `/review` change sizing)
- Pushing directly to protected branches without a PR
- Including `print()` statements or `breakpoint()` calls in commits
- Creating PRs without a test plan section
- Committing generated files (`__pycache__/`, `*.pyc`, `.coverage`)

## Verification

Before declaring the PR shipped:

- [ ] Pre-flight checks passed (no secrets, no debug artifacts)
- [ ] Commit message follows conventional format with task reference
- [ ] Branch pushed to remote successfully
- [ ] PR created with Summary, Task Reference, Test Plan, and Changes sections
- [ ] PR targets the correct base branch (dev for feature work, main for releases)
- [ ] Status files updated with PR link (if workstream task)
- [ ] PR URL shared with user

---

## Reference

This command integrates with:
- `/run-checks` → Must pass before committing
- `/review` → Must approve before shipping
- `/sync-worktree-status` → Run after PR merge from worktree
- `/verify-batch-completion` → Run after batch of PRs merge
- Hooks (`beforeShellExecution`) → Blocks force-push to protected branches

See also:
- `CLAUDE.md` → "Git Safety Protocol" in system prompt
- `.cursor/hooks/before-shell.sh` → Blocks dangerous git commands
